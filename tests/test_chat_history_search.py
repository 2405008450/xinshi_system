"""聊天记录检索：类型筛选、撤回排除、权限和游标。数据库用例沿用标注群聊的显式开关。"""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from chat_history_search import ChatHistoryError, extract_urls, search_chat_history


def test_extract_urls_trims_trailing_punctuation_and_rejects_bad_cursor():
    assert extract_urls('见 https://example.com/a. 和 www.xinshi.test/b, 以及 www.xinshi.test/c。') == [
        'https://example.com/a',
        'www.xinshi.test/b',
        'www.xinshi.test/c',
    ]
    assert extract_urls('没有链接') == []
    with pytest.raises(ChatHistoryError, match='分页游标无效'):
        search_chat_history(
            None,
            project_type='annotation',
            project_id=uuid4(),
            user_id=uuid4(),
            cursor='not-a-cursor',
        )


@pytest.fixture
def environment(monkeypatch):
    import os
    if os.getenv('RUN_ANNOTATION_CHAT_DB_TESTS') != '1':
        pytest.skip('仅在局域网调试机显式开启数据库测试')
    import main  # noqa: F401
    from database import engine
    from sqlalchemy.orm import Session
    from models import AppUser, Role, RolePermission, UserRole, TranslationProject
    from annotation_models import AnnotationProject
    import annotation_chat_service as service
    import project_chat_crud
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode='create_savepoint')
    monkeypatch.setattr(service, 'publish', lambda *a, **k: None)
    monkeypatch.setattr(service, 'notify_state', lambda *a, **k: None)
    monkeypatch.setattr(project_chat_crud, '_push_notifications', lambda *a, **k: None)
    role = Role(role_name='chat-search-' + uuid4().hex[:12])
    users = [AppUser(username='chat-search-' + uuid4().hex, password_hash='disabled', full_name=f'检索测试{i}', is_active=True) for i in range(4)]
    projects = [AnnotationProject(order_no='SRCH-' + uuid4().hex[:20], project_name='检索测试', project_types=[]) for _ in range(2)]
    translation = TranslationProject(order_no='TR-' + uuid4().hex[:12], project_name='笔译定位')
    db.add_all([role, translation, *users, *projects])
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_code='projects:read'))
    db.add_all(UserRole(user_id=user.id, role_id=role.id) for user in users[:3])
    db.flush()
    try:
        yield db, users, projects, translation
    finally:
        db.close()
        transaction.rollback()
        connection.close()


def _attachment(db, project, user, name, content_type):
    from models import ChatProjectAttachment
    row = ChatProjectAttachment(
        uploaded_by=user.id,
        annotation_project_id=project.id,
        original_name=name,
        storage_name=uuid4().hex,
        content_type=content_type,
        file_size=128,
    )
    db.add(row)
    db.flush()
    return row


def _send(db, project, user, content='测试消息', attachment_ids=None):
    from annotation_chat_service import send_message
    from schemas import AnnotationProjectChatMessageCreate
    return send_message(db, project.id, user, AnnotationProjectChatMessageCreate(
        content=content,
        attachment_ids=attachment_ids or [],
    ))


def _search(db, project, user, **kwargs):
    return search_chat_history(
        db,
        project_type='annotation',
        project_id=project.id,
        user_id=user.id,
        **kwargs,
    )


def test_history_filters_images_links_files_and_skips_recalled(environment):
    db, users, projects, _translation = environment
    from annotation_chat_service import recall_message
    from models import ChatProjectMessageFavorite
    image = _attachment(db, projects[0], users[0], '现场图.png', 'image/png')
    quoted = _attachment(db, projects[0], users[0], '报价单.pdf', 'application/pdf')
    secret = _attachment(db, projects[0], users[0], '秘密.pdf', 'application/pdf')
    other = _attachment(db, projects[1], users[0], '其他.pdf', 'application/pdf')
    _send(db, projects[0], users[0], '现场照片', [image.id])
    file_message = _send(db, projects[0], users[0], '请看报价', [quoted.id])
    recalled = _send(db, projects[0], users[0], '撤回前 https://secret.example/hide', [secret.id])
    _send(db, projects[0], users[1], '资料 https://example.com/spec 与 www.xinshi.test/a。')
    _send(db, projects[1], users[0], '其他项目 https://example.com/other', [other.id])
    recall_message(db, projects[0].id, recalled.id, users[0])
    db.add(ChatProjectMessageFavorite(message_id=file_message.id, user_id=users[1].id))
    db.commit()

    images = _search(db, projects[0], users[1], kind='image')
    files = _search(db, projects[0], users[1], kind='file')
    links = _search(db, projects[0], users[1], kind='link')
    named = _search(db, projects[0], users[1], kind='file', keyword='报价单')
    favorites = _search(db, projects[0], users[1], kind='all', favorites_only=True)
    by_sender = _search(db, projects[0], users[1], kind='all', sender_user_id=users[0].id)

    assert [item['attachment']['original_name'] for item in images['items']] == ['现场图.png']
    assert {item['attachment']['original_name'] for item in files['items']} == {'报价单.pdf'}
    assert '秘密.pdf' not in {item['attachment']['original_name'] for item in files['items']}
    assert {item['url'] for item in links['items']} == {'https://example.com/spec', 'www.xinshi.test/a'}
    assert 'https://secret.example/hide' not in {item['url'] for item in links['items']}
    assert [item['attachment']['original_name'] for item in named['items']] == ['报价单.pdf']
    assert [item['message_id'] for item in favorites['items']] == [file_message.id]
    assert by_sender['total'] >= 1
    assert all(item['sender_user_id'] == users[0].id for item in by_sender['items'])
    assert images['totals']['image'] == 1
    assert files['totals']['file'] == 1
    assert links['totals']['link'] == 2


def test_history_cursor_pages_without_overlap(environment):
    db, users, projects, _translation = environment
    for index in range(3):
        attachment = _attachment(db, projects[0], users[0], f'附件{index}.pdf', 'application/pdf')
        _send(db, projects[0], users[0], f'文件{index}', [attachment.id])
    seen = []
    cursor = None
    for _ in range(4):
        page = _search(db, projects[0], users[1], kind='file', limit=1, cursor=cursor)
        assert len(page['items']) == (1 if len(seen) < 3 else 0)
        if not page['items']:
            assert page['next_cursor'] is None
            break
        seen.append(page['items'][0]['attachment']['id'])
        cursor = page['next_cursor']
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 3


def test_history_rejects_user_without_project_permission(environment):
    db, users, projects, _translation = environment
    from fastapi import HTTPException
    from routers.annotation_chat import history
    with pytest.raises(HTTPException) as exc:
        history(projects[0].id, kind='all', limit=10, db=db, user=users[3])
    assert exc.value.status_code == 403


def test_translation_history_window_can_locate_and_load_older(environment):
    db, users, _projects, translation = environment
    from models import ChatProjectMessage
    from project_chat_crud import list_project_chat_messages_around, list_project_chat_messages_before
    base = datetime(2026, 1, 1, 9, 0, 0)
    rows = []
    for index in range(5):
        row = ChatProjectMessage(
            project_id=translation.id,
            sender_user_id=users[0].id,
            sender_name='笔译测试',
            content=f'笔译消息{index} https://example.com/{index}',
            message_type='user',
            created_at=base + timedelta(minutes=index),
        )
        db.add(row)
        rows.append(row)
    db.flush()
    window, _total, has_older, has_newer = list_project_chat_messages_around(
        db, translation.id, rows[2].id, limit=3, include_user_messages=True,
    )
    assert [item.id for item in window] == [rows[1].id, rows[2].id, rows[3].id]
    assert has_older and has_newer
    older, more = list_project_chat_messages_before(
        db, translation.id, window[0].created_at, window[0].id, limit=10, include_user_messages=True,
    )
    assert [item.id for item in older] == [rows[0].id]
    assert more is False
    found = search_chat_history(
        db, project_type='translation', project_id=translation.id, user_id=users[0].id,
        kind='link', keyword='example.com/4', include_user_messages=True,
    )
    assert [item['url'] for item in found['items']] == ['https://example.com/4']
