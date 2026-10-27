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
