"""主题检索、原会话授权、事务和手工事项的隔离数据库回归。"""
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_resource_issues import environment
from chat_topic_models import ChatTopic, ChatMessageTopic, ChatTopicAudit
from chat_topic_schemas import TopicCreate, TopicUpdate, MessageTopicWrite
from resource_issue_schemas import IssueCreate, IssueUpdate
from schemas import AnnotationProjectChatMessageCreate
import chat_topic_service as topics

ROOT = UUID('00000000-0000-0000-0000-000000001002')
CHILD = UUID('00000000-0000-0000-0000-000000001015')


def tag(db, data, kind='annotation', topic_id=CHILD, revision=0, actor='proposer'):
    row = topics.require_message(db, data['users'][actor], data['messages'][kind].id, lock=True)
    topics.set_message_topic(db, data['users'][actor], row, topic_id, revision)
    return row


@pytest.mark.parametrize('kind', ['translation', 'annotation', 'direct'])
def test_classify_clear_version_and_permissions(environment, kind):
    db, data = environment
    row = tag(db, data, kind)
    meta = topics.message_metadata(row, data['users']['proposer'].id)
    assert meta['topic_id'] == str(CHILD) and meta['topic_revision'] == 1
    assert meta['topic_path'] == '资源开拓讨论 / 高校渠道'
    assert meta['can_classify']
    with pytest.raises(HTTPException) as forbidden:
        topics.set_message_topic(db, data['users']['collector'], row, None, 1)
    assert forbidden.value.status_code == 403
    with pytest.raises(HTTPException) as conflict:
        topics.set_message_topic(db, data['users']['proposer'], row, None, 0)
    assert conflict.value.status_code == 409
    topics.set_message_topic(db, data['users']['proposer'], row, None, 1)
    assert topics.message_metadata(row, data['users']['proposer'].id)['topic_revision'] == 2
    assert db.get(ChatMessageTopic, row.id).topic_id is None
    assert db.query(ChatTopicAudit).filter_by(entity_id=row.id).count() == 2


def test_cross_conversation_counts_obey_acl_and_include_children(environment):
    db, data = environment
    for kind in data['messages']:
        tag(db, data, kind)
    def search(actor, topic=ROOT, **changes):
        return topics.search(db, data['users'][actor], topic, changes.get('scope', 'all'),
                             changes.get('kind'), changes.get('id'), changes.get('keyword', ''), changes.get('before'), changes.get('limit', 30))
    assert search('collector')['total'] == 3
    assert search('manager')['total'] == 2
    assert search('admin')['total'] == 2  # 管理员仍看不到非本人私聊。
    assert search('outsider')['total'] == 0
    assert search('collector', scope='current', kind='direct', id=data['direct'].id)['total'] == 1
    assert search('manager', scope='current', kind='direct', id=data['direct'].id)['total'] == 0
    first = search('collector', limit=1)
    second = search('collector', limit=1, before=first['next_before'])
    assert first['total'] == second['total'] == 3 and first['items'][0]['id'] != second['items'][0]['id']
    assert search('collector', keyword='%')['total'] == 0
    data['messages']['annotation'].recalled_at = __import__('annotation_chat_service').chat_now()
    db.flush()
    assert search('collector')['total'] == 2
    with pytest.raises(HTTPException):
        topics.require_message(db, data['users']['admin'], data['messages']['direct'].id)


def test_menu_levels_duplicates_permissions_and_revision(environment):
    db, data = environment
    from routers.chat_topics import create, update
    with pytest.raises(HTTPException) as forbidden:
        create(TopicCreate(name='其他业务'), db, data['users']['collector'])
    assert forbidden.value.status_code == 403
    child = create(TopicCreate(name='校园招聘', parent_id=ROOT), db, data['users']['admin'])
    with pytest.raises(HTTPException) as depth:
        create(TopicCreate(name='三级', parent_id=UUID(child['id'])), db, data['users']['admin'])
    assert depth.value.status_code == 422
    payload = TopicUpdate(name='校园招聘', description='修改说明', sort_order=30, active=False, revision=1)
    changed = update(UUID(child['id']), payload, db, data['users']['admin'])
    assert changed['revision'] == 2 and not changed['selectable']
    with pytest.raises(HTTPException) as stale:
        update(UUID(child['id']), payload, db, data['users']['admin'])
    assert stale.value.status_code == 409
    with pytest.raises(HTTPException):
        topics.get_topic(db, UUID(child['id']), selecting=True)


def test_source_snapshot_and_manual_request_idempotency(environment):
    db, data = environment
    import resource_issue_service as issues
    tag(db, data)
    payload = IssueCreate(source_message_id=data['messages']['annotation'].id, category='idea', content='高校合作想法')
    collected = issues.create_issue(db, data['users']['collector'], payload)
    assert collected['topic_id'] == str(CHILD)
    tag(db, data, topic_id=None, revision=1)
    assert issues.serialize(db, data['users']['collector'], db.get(__import__('resource_issue_models').DevelopmentIssue, UUID(collected['id'])))['topic_id'] == str(CHILD)
    manual = IssueCreate(category='arrangement', content='手工联系高校', topic_id=CHILD, client_request_id=uuid4())
    created = issues.create_issue(db, data['users']['collector'], manual)
    assert created['source_type'] == 'manual' and created['source_message_id'] is None
    assert created['proposer_id'] == str(data['users']['collector'].id)
    assert created['topic_path'].endswith('高校渠道')
    assert issues.create_issue(db, data['users']['collector'], manual)['id'] == created['id']
    updated = issues.update_issue(db, data['users']['collector'], UUID(created['id']), IssueUpdate(content='修改手工事项', revision=created['revision'], topic_id=None))
    assert updated['topic_id'] is None and updated['topic_path'] == ''
    with pytest.raises(ValidationError):
        IssueCreate(category='idea', content='没有请求标识')


@pytest.mark.parametrize('kind', ['annotation', 'direct', 'translation'])
def test_send_topic_is_atomic_and_roundtrips(environment, kind):
    db, data = environment
    user = data['users']['proposer']
    request_id = uuid4()
    if kind == 'translation':
        from project_chat_crud import create_project_chat_message
        send = lambda tid, rid=request_id: create_project_chat_message(db, data['translation'].id, user, '发送前选择主题', topic_id=tid, client_message_id=rid, notify=False)
    else:
        service = __import__('annotation_chat_service' if kind == 'annotation' else 'direct_chat_service')
        send = lambda tid, rid=request_id: service.send_message(db, data[kind].id, user, AnnotationProjectChatMessageCreate(content='发送前选择主题', topic_id=tid, client_message_id=rid))
    message = send(CHILD)
    assert topics.message_metadata(message, user.id)['topic_id'] == str(CHILD)
    assert send(CHILD).id == message.id
    from models import ChatProjectMessage
    count = db.query(ChatProjectMessage).count()
    with pytest.raises(HTTPException):
        with db.begin_nested():
            send(uuid4(), uuid4())
    assert db.query(ChatProjectMessage).count() == count


def test_history_topic_filter_is_shared_by_totals_and_results(environment):
    db, data = environment
    tag(db, data)
    from chat_history_search import search_chat_history
    result = search_chat_history(db, project_type='annotation', project_id=data['annotation'].id, user_id=data['users']['proposer'].id, topic_id=ROOT)
    assert result['total'] == result['totals']['all'] == len(result['items']) == 1
    topics.set_message_topic(db, data['users']['proposer'], data['messages']['annotation'], None, 1)
    assert search_chat_history(db, project_type='annotation', project_id=data['annotation'].id, user_id=data['users']['proposer'].id, topic_id=ROOT)['total'] == 0


def test_disabled_parent_preserves_history_but_rejects_new_classification(environment):
    db, data = environment
    row = tag(db, data)
    db.get(ChatTopic, ROOT).active = False
    db.flush()
    assert topics.search(db, data['users']['proposer'], ROOT, 'all', None, None, '', None, 30)['total'] == 1
    with pytest.raises(HTTPException) as stopped:
        topics.set_message_topic(db, data['users']['proposer'], row, CHILD, 1)
    assert stopped.value.status_code == 409
    assert db.get(ChatMessageTopic, row.id).topic_id == CHILD


def test_old_schema_keeps_ordinary_chat_serializable(environment, monkeypatch):
    db, data = environment
    monkeypatch.setattr(topics, 'schema_ready', lambda _db: False)
    from routers.project_chat import _serialize_message
    result = _serialize_message(data['messages']['translation'], current_user_id=data['users']['proposer'].id)
    assert result.content == data['messages']['translation'].content
    assert result.topic_id is None and not result.can_classify


def test_duplicate_sibling_name_returns_conflict(environment):
    db, data = environment
    from routers.chat_topics import create
    with pytest.raises(HTTPException) as duplicate:
        create(TopicCreate(name='高校渠道', parent_id=ROOT), db, data['users']['admin'])
    assert duplicate.value.status_code == 409
