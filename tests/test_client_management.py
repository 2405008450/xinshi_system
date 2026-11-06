from uuid import uuid4

from sqlalchemy import create_engine, inspect, event

from tests.test_chat_participant_access import environment
from models import Client, ClientCooperation, SubClient, TranslationProject
from interpretation_models import InterpretationProject
from annotation_models import AnnotationProject
from recruitment_models import RecruitmentProject
from client_cooperation_projects import client_project_groups
from schemas import ClientCreate, ClientUpdate, ClientResponse
from tools.apply_client_cooperation_migration import apply_migration


def test_cooperation_persist_clear_and_schema(environment):
    db, _ = environment
    payload = ClientCreate(client_code='CL-TEST', client_name='测试', client_short_name='测试', cooperation_info='合作协议\n下一阶段安排')
    row = Client(id=uuid4(), **payload.model_dump(exclude={'customer_type'}))
    db.add(row); db.commit(); db.expire_all()
    loaded = db.get(Client, row.id)
    assert ClientResponse.model_validate(loaded).cooperation_info == payload.cooperation_info
    assert loaded.remarks is None
    loaded.cooperation_info = '更新合作信息'
    db.commit(); db.expire_all()
    assert db.get(Client, row.id).cooperation_info == '更新合作信息'
    patch = ClientUpdate(client_name='更名').model_dump(exclude_unset=True)
    assert 'cooperation_info' not in patch
    loaded.cooperation_info = ''
    db.commit(); db.expire_all()
    assert db.get(Client, row.id).cooperation_info == ''


def test_projects_exact_customer_all_modules_and_empty_groups(environment):
    db, _ = environment
    client = Client(id=uuid4(), client_code='CL-A', client_name='同名', client_short_name='同名')
    other = Client(id=uuid4(), client_code='CL-B', client_name='同名', client_short_name='同名')
    sub = SubClient(id=uuid4(), parent_client_id=client.id, sub_client_code='CL-A.001', client_name='子客户', client_short_name='子')
    db.add_all([client, other, sub]); db.commit()
    assert client_project_groups(db, client.id) == {'groups': []}
    for model in (TranslationProject, InterpretationProject, AnnotationProject, RecruitmentProject):
        db.add_all([
            model(id=uuid4(), order_no='A-001', project_name='直接项目', client_id=client.id),
            model(id=uuid4(), order_no='A-002', project_name='子客户项目', sub_client_id=sub.id),
            model(id=uuid4(), order_no='B-001', project_name='其他客户', client_id=other.id),
        ])
    db.commit()
    groups = client_project_groups(db, client.id)['groups']
    assert [g['module'] for g in groups] == ['translation', 'interpretation', 'annotation', 'recruitment']
    assert all(len(g['items']) == 2 for g in groups)
    assert all({r['project_name'] for r in g['items']} == {'直接项目', '子客户项目'} for g in groups)


def test_migration_repeatable_only_new_table():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        Client.__table__.create(connection)
        apply_migration(connection)
        apply_migration(connection)
        assert set(inspect(connection).get_table_names()) == {'client', 'client_cooperation'}


def test_crud_cooperation_preserves_remarks_and_partial_updates(environment, monkeypatch):
    from crud import create_client, update_client, delete_client
    db, _ = environment
    import crud
    # 只补齐内存库 UUID，不替换后续查询仍需使用的 ORM 类型。
    def assign_ids(session, *_):
        for item in session.new:
            if isinstance(item, Client) and item.id is None:
                item.id = uuid4()
    event.listen(db, 'before_flush', assign_ids)
    row = create_client(db, ClientCreate(
        client_name='客户', client_short_name='客户', client_code='CL-CRUD',
        remarks='基本备注', cooperation_info='合作内容',
    ))
    updated = update_client(db, row.id, ClientUpdate(client_name='更名'))
    assert updated.cooperation_info == '合作内容'
    updated = update_client(db, row.id, ClientUpdate(cooperation_info='新内容'))
    assert updated.cooperation_info == '新内容' and updated.remarks == '基本备注'
    delete_client(db, row.id)
    assert db.query(ClientCooperation).filter_by(client_id=row.id).first() is None


def test_project_summary_requires_both_customer_and_project_read(environment, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers import auth, clients
    db, users = environment
    client = Client(id=uuid4(), client_code='CL-AUTH', client_name='客户', client_short_name='客户')
    db.add(client); db.commit()
    app = FastAPI()
    app.include_router(clients.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: users[0]
    granted = {'clients:read'}
    monkeypatch.setattr(auth, 'user_has_permission', lambda db, uid, code: code in granted)
    with TestClient(app) as http:
        path = f'/clients/{client.id}/projects'
        assert http.get(path).status_code == 403
        granted.add('projects:read')
        assert http.get(path).json() == {'groups': []}
        assert http.get(f'/clients/{uuid4()}/projects').status_code == 404
        granted.remove('clients:read')
        assert http.get(path).status_code == 403
