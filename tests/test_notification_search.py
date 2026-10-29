from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_chat_participant_access import environment  # noqa: F401


def setup_notifications(environment):
    db, (user, other, _) = environment
    from models import AppNotification
    from business_time import business_now
    rows = [
        (user,'resource_request_dispatch',False,'Alpha · 已收到','项目 RR-007'),
        (user,'resource_request_dispatch',True,'Alpha · 已处理','RR-007'),
        (user,'resource_request_dispatch',False,'Beta · 取消通知','项目 RR-008'),
        (user,'chat_summary',False,'Alpha 总结同步','项目 RR-007'),
        (user,'chat_summary',True,'literal%_\\value','普通内容'),
        (user,'workflow',False,'Alpha 工作流','RR-007'),
        (other,'resource_request_dispatch',False,'Alpha 他人通知','RR-007'),
    ]
    for receiver,kind,read,title,content in rows:
        db.add(AppNotification(id=uuid4(),recipient_user_id=receiver.id,notification_type=kind,is_read=read,title=title,content=content,created_at=business_now()))
    db.commit()
    from routers.notifications import router
    from routers.auth import get_current_user
    from database import get_db
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:user
    return db, user, TestClient(app)


def test_search_filters_counts_privacy_and_global_unread(environment):
    db,user,client=setup_notifications(environment)
    base={'channel':'business','notification_types':['resource_request_dispatch','chat_summary']}
    all_rows=client.get('/notifications/page',params=base).json()
    assert all_rows['total']==5
    assert all(row['recipient_user_id']==str(user.id) for row in all_rows['items'])
    found=client.get('/notifications/page',params={**base,'keyword':'RR-007 ALPHA'}).json()
    assert found['total']==3
    filtered=client.get('/notifications/page',params={**base,'keyword':'RR-007 ALPHA','notification_type':'resource_request_dispatch','read_status':'unread'}).json()
    assert filtered['total']==1 and '已收到' in filtered['items'][0]['title']
    read=client.get('/notifications/page',params={**base,'read_status':'read'}).json()
    assert read['total']==2 and all(item['is_read'] for item in read['items'])
    for keyword in ['%_', '\\value', 'LITERAL%_\\VALUE']:
        literal=client.get('/notifications/page',params={**base,'keyword':keyword}).json()
        assert literal['total']==1 and literal['items'][0]['title']=='literal%_\\value'
    assert client.get('/notifications/unread-count',params=base).json()=={'count':3}
    assert client.get('/notifications/page',params={**base,'keyword':'不存在'}).json()=={'items':[],'total':0}
    assert client.get('/notifications/page',params={**base,'keyword':''}).json()['total']==5
    for params in [{'skip':-1},{'limit':101},{'read_status':'invalid'}]:
        assert client.get('/notifications/page',params=params).status_code==422


def test_pagination_and_read_move_record_between_filters(environment):
    db,user,client=setup_notifications(environment)
    base={'notification_type':'resource_request_dispatch','channel':'business','limit':1}
    first=client.get('/notifications/page',params=base).json()
    second=client.get('/notifications/page',params={**base,'skip':1}).json()
    assert first['total']==second['total']==3
    assert first['items'][0]['id']!=second['items'][0]['id']
    unread=client.get('/notifications/page',params={**base,'read_status':'unread'}).json()
    assert unread['total']==2
    assert client.post(f'/notifications/{unread["items"][0]["id"]}/read').status_code==200
    assert client.get('/notifications/page',params={**base,'read_status':'unread'}).json()['total']==1
    assert client.get('/notifications/page',params={**base,'read_status':'read'}).json()['total']==2


def test_system_bell_excludes_conversation_feed_and_read_all_is_isolated(environment):
    db, user, client = setup_notifications(environment)
    from models import AppNotification
    from business_time import business_now
    db.add(AppNotification(id=uuid4(),recipient_user_id=user.id,notification_type='direct_chat_mention',is_read=False,title='聊天 @',content='聊天',created_at=business_now()))
    db.commit()
    legacy = AppNotification(id=uuid4(),recipient_user_id=user.id,notification_type='annotation_project_chat',related_project_type='annotation',is_read=False,title='标注群聊新消息',content='历史普通聊天通知',created_at=business_now())
    db.add(legacy)
    for kind in ['discussion_chat', 'interpretation_project_chat', 'recruitment_project_chat_mention', 'new_group_chat_invite', ' CHAT_NEW_MESSAGE ']:
        db.add(AppNotification(id=uuid4(),recipient_user_id=user.id,notification_type=kind,is_read=False,title='其他会话消息',content='隔离测试',created_at=legacy.created_at))
    db.commit()
    params = {'channel': 'system'}
    result = client.get('/notifications/page', params=params)
    assert result.status_code == 200
    assert result.json()['total'] == 1
    assert result.json()['items'][0]['notification_type'] == 'workflow'
    assert client.get('/notifications/unread-count', params=params).json() == {'count': 1}
    assert [row['notification_type'] for row in client.get('/notifications/', params=params).json()] == ['workflow']
    assert client.post('/notifications/read-all', params=params).json() == {'updated': 1}
    feed = {'channel': 'business', 'notification_types': ['resource_request_dispatch', 'chat_summary']}
    assert client.get('/notifications/unread-count', params=feed).json() == {'count': 3}
    assert client.get('/notifications/unread-count', params={'channel': 'system'}).json() == {'count': 0}
    assert db.query(AppNotification).filter(AppNotification.recipient_user_id == user.id, AppNotification.notification_type == 'direct_chat_mention').one().is_read is False

    db.refresh(legacy)
    assert legacy.is_read is False


def test_chat_channel_rule_covers_all_existing_and_future_chat_families(environment):
    db, (user, _, _) = environment
    from models import AppNotification
    from notification_channels import filter_notification_channel, CHAT_NOTIFICATION_TYPES
    from business_time import business_now
    kinds = list(CHAT_NOTIFICATION_TYPES) + ['interpretation_project_chat', 'recruitment_project_chat_mention', 'new_group_chat_invite', ' CHAT_NEW_MESSAGE ']
    for kind in kinds + ['workflow_chatty_update', 'chat_summary', 'resource_request_dispatch']:
        db.add(AppNotification(id=uuid4(),recipient_user_id=user.id,notification_type=kind,is_read=False,title='分类测试',content='隔离测试',created_at=business_now()))
    db.flush()
    query = db.query(AppNotification).filter(AppNotification.recipient_user_id == user.id)
    assert {row.notification_type for row in filter_notification_channel(query, AppNotification, 'chat').all()} == set(kinds)
    assert {row.notification_type for row in filter_notification_channel(query, AppNotification, 'system').all()} == {'workflow_chatty_update'}
    assert {row.notification_type for row in filter_notification_channel(query, AppNotification, 'business').all()} == {'workflow_chatty_update', 'chat_summary', 'resource_request_dispatch'}
