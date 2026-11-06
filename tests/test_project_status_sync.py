from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
import project_status_sync as sync

def test_status_snapshot_read_permission_and_minimal_fields(context):
    http,db,clients,granted,actor=context
    root=project(db,clients[0]);http.app.include_router(sync.router)
    response=http.post('/project-status-sync/snapshot',json={'items':[{'projectType':'translation','id':str(root.id)}]})
    assert response.status_code==200,response.text
    assert response.json()=={'items':[{'projectType':'translation','id':str(root.id),'status':root.project_status or ''}]}
    assert http.post('/project-status-sync/snapshot',json={'items':[{'projectType':'other','id':str(root.id)}]}).status_code==422
    granted.discard('projects:read')
    assert http.post('/project-status-sync/snapshot',json={'items':[]}).status_code==403

def test_commit_only_coalesces_all_flushes_and_rollback_sends_nothing(context,monkeypatch):
    http,db,clients,_,actor=context
    root=project(db,clients[0]);sent=[]
    import notification_ws
    monkeypatch.setattr(notification_ws,'dispatch_project_status',lambda items:sent.extend(items))
    root.project_status='confirmed';db.flush();assert not sent
    root.project_status='sent_to_client';db.flush();db.commit()
    assert sent==[{'projectType':'translation','id':str(root.id),'status':'sent_to_client'}]
    sent.clear();root.project_status='cancelled';db.flush();db.rollback();db.commit();assert not sent
    root.project_name='仅改名称';db.commit();assert not sent

def test_child_status_and_savepoint_not_published_until_outer_commit(context,monkeypatch):
    from tests.test_customer_translation_rates import context as tree
    http,db,_,_,actor=context
    client,root,middle,leaf=tree(db,actor);sent=[]
    import notification_ws
    monkeypatch.setattr(notification_ws,'dispatch_project_status',lambda items:sent.extend(items))
    with db.begin_nested():leaf.status='sent_to_client';db.flush()
    assert not sent
    db.commit()
    assert {'projectType':'translation_suborder','id':str(leaf.id),'status':'sent_to_client'} in sent

def test_websocket_delivers_only_watched_entities_and_removes_closed_connections():
    import asyncio
    from uuid import uuid4
    from notification_ws import NotificationConnectionManager
    class Socket:
        def __init__(self):self.sent=[]
        async def send_json(self,value):self.sent.append(value)
    manager=NotificationConnectionManager();one,two=Socket(),Socket();actor=uuid4()
    manager.watch_project_status(actor,one,[{'projectType':'translation','id':'one'}])
    manager.watch_project_status(actor,two,[{'projectType':'annotation','id':'two'}])
    asyncio.run(manager.send_project_status([{'projectType':'translation','id':'one','status':'confirmed'}]))
    assert len(one.sent)==1 and not two.sent
    manager.disconnect(actor,one)
    assert (str(actor),one) not in manager.project_status_subscriptions
