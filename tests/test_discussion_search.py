from datetime import date, datetime, timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment
from chat_time import BUSINESS_TIMEZONE


@pytest.fixture
def history(environment):
    from chat_session_category_models import ChatSessionCategory, ChatSessionCategoryFolder
    from discussion_chat_models import DiscussionMember, DiscussionMessage, DiscussionMessageAction
    from models import ChatProjectAttachment
    db, (actor, colleague, outsider) = environment
    room, foreign = uuid4(), uuid4()
    for rid in (room, foreign):
        db.add(ChatSessionCategory(id=rid, name=str(rid), active=True, updated_by=actor.id))
        db.flush(); db.add(ChatSessionCategoryFolder(category_id=rid, parent_key='dcb1f917-6000-4000-8000-000000000002'))
    db.add_all([DiscussionMember(room_id=room, user_id=person.id, last_read_id=0) for person in (actor, colleague)])
    db.add(DiscussionMember(room_id=foreign, user_id=outsider.id, last_read_id=0))
    files = {}
    for label, rid, name, mime in [('doc',room,'客户方案%_v1.docx','application/msword'),
                                  ('image',room,'现场.jpg','image/jpeg'), ('video',room,'演示.mp4','video/mp4'),
                                  ('foreign',foreign,'SecretName.docx','application/msword')]:
        attachment = ChatProjectAttachment(id=uuid4(), uploaded_by=actor.id, original_name=name,
            storage_name=f'discussion_{rid.hex}_{uuid4().hex}', content_type=mime, file_size=10)
        db.add(attachment); files[label] = f'[附件](discussion-file://{attachment.id})'
    start = datetime(2026,11,26,tzinfo=BUSINESS_TIMEZONE)
    bodies = [files['doc'], files['image'], files['video'], f'![截图](screenshot://{uuid4()}#'+('a'*64)+')',
              '资料链接 https://example.org/reference', '#小程序://会议工具/示例',
              files['foreign'], '普通文字，不是文件或小程序', files['doc'], files['doc']]
    for index, content in enumerate(bodies,1):
        at = start + timedelta(hours=12)
        if index == 1: at = start
        if index == 9: at = start + timedelta(days=1) - timedelta(microseconds=1)
        if index == 10: at = start + timedelta(days=1)
        db.add(DiscussionMessage(id=index, room_id=room, sender_id=actor.id if index != 3 else colleague.id,
            sender_name='Alice' if index != 3 else 'Bob', client_message_id=uuid4(), content=content, created_at=at))
    db.flush()
    db.add(DiscussionMessageAction(message_id=1,user_id=actor.id,user_name='Alice',favorited_at=start))
    db.add(DiscussionMessageAction(message_id=2,user_id=colleague.id,user_name='Bob',favorited_at=start))
    db.commit()
    return db, actor, colleague, outsider, room, foreign


def ids(history, **params):
    import discussion_chat_service as service
    db, actor, _, _, room, _ = history
    return [int(row['id']) for row in service.messages(db,actor,room,**params)['items']]


def test_file_media_links_and_miniapps_are_real_content_types(history):
    assert ids(history,kind='file') == [1,9,10]
    assert ids(history,kind='media') == [2,3,4]
    assert ids(history,kind='link') == [5]
    assert ids(history,kind='miniapp') == [6]
    assert ids(history,keyword='SecretName') == []


def test_keyword_fields_literal_symbols_and_combined_person_date_favorite(history):
    _, actor, colleague, _, _, _ = history
    assert ids(history,keyword='Alice 方案%_') == [1,9,10]
    assert ids(history,kind='file',keyword='方案',sender_user_id=actor.id,
        start_date=date(2026,11,26),end_date=date(2026,11,26)) == [1,9]
    assert ids(history,kind='media',sender_user_id=colleague.id) == [3]
    assert ids(history,kind='file',favorites_only=True,keyword='Alice') == [1]
    assert ids(history,kind='media',favorites_only=True) == []
    assert ids(history,keyword='方案XZ') == []


def test_filtered_cursor_sender_options_and_room_access(history):
    import discussion_chat_service as service
    from discussion_search import sender_options
    db, actor, colleague, outsider, room, foreign = history
    page = service.messages(db,actor,room,kind='file',limit=2)
    assert [int(row['id']) for row in page['items']] == [9,10] and page['has_more']
    assert ids(history,kind='file',before=9,limit=2) == [1]
    assert {row['id'] for row in sender_options(db,actor,room)['senders']} == {str(actor.id),str(colleague.id)}
    with pytest.raises(HTTPException): service.messages(db,outsider,room,kind='all')
    with pytest.raises(HTTPException): sender_options(db,actor,foreign)
    with pytest.raises(HTTPException) as bad:
        service.messages(db,actor,room,start_date=date(2026,11,27),end_date=date(2026,11,26))
    assert bad.value.status_code == 422
