from fastapi import FastAPI,Depends
from fastapi.testclient import TestClient
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
from database import get_db
from routers import auth
import saved_data_sync as sync

def test_read_dependencies_and_opaque_versions_only_commit_changes(context,monkeypatch):
    _,db,clients,_,actor=context
    row=project(db,clients[0]);sent=[]
    import notification_ws
    monkeypatch.setattr(notification_ws,'dispatch_saved_data',lambda value:sent.append(value))
    app=FastAPI();app.add_middleware(sync.SavedReadMiddleware);app.include_router(sync.router)
    app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[auth.get_current_user]=lambda:actor
    @app.get('/example')
    def read():return {'items':[{'id':str(item.id),'name':item.project_name} for item in db.query(type(row)).all()]}
    with TestClient(app) as http:
        result=http.get('/example');assert 'translation_project' in result.headers['x-saved-resources']
        before=http.post('/saved-data-sync/versions',json={'resources':['translation_project']}).json()
        row.project_name='修改后的名称';db.flush();assert not sent
        db.commit();assert 'translation_project' in sent[-1]
        after=http.post('/saved-data-sync/versions',json={'resources':['translation_project']}).json()
        assert before!=after
        assert '修改后的名称' not in str(after) and 'n_tup' not in str(after)
        sent.clear();row.project_name='回滚的名称';db.flush();db.rollback();db.commit();assert not sent
        assert http.post('/saved-data-sync/versions',json={'resources':['bad; SQL']}).status_code==422
