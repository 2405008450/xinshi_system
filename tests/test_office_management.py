"""办公室字典、工位与真实人员数；仅隔离 SQLite，不连接业务库。"""
from uuid import uuid4
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text,inspect,event
from test_chat_participant_access import environment
from test_monthly_shift import setup
from models import AppUser
from schemas import AppUserCreate,AppUserUpdate
from tools.apply_office_management_migration import apply_migration
import office_management as office
import crud


@pytest.fixture
def offices(environment):
    db,users=environment;setup(db,users);apply_migration(db.connection());db.commit()
    return db,users


def test_default_cities_no_invented_seats_or_employee_assignments(offices):
    db,users=offices;value=office.catalog(db)
    assert {row['name'] for row in value['items']}=={'广州办公室','深圳南山办公室','上海办公室'}
    assert all(row['seats'] is None and row['actual_people']==0 for row in value['items'])
    assert value['unassigned_people']==3 and db.query(office.EmployeeOffice).count()==0


def test_person_city_omission_clear_rename_and_real_counts(offices):
    db,(admin,person,other)=offices;gz=office.default_id('广州')
    assert crud.update_user(db,person.id,AppUserUpdate(office_city_id=gz)).city=='广州'
    crud.update_user(db,other.id,AppUserUpdate(office_city_id=gz,is_active=False))
    value=next(row for row in office.catalog(db)['items'] if row['id']==gz)
    assert value['actual_people']==1 and value['registered_people']==2
    crud.update_user(db,person.id,AppUserUpdate(full_name='改名不改城市'))
    assert db.get(office.EmployeeOffice,person.id).office_city_id==gz
    office.save(db,office.OfficeUpdate(city='广州市',name='广州新办公室',seats=12,revision=1),gz)
    assert office.attach_users(db,[person])[0].city=='广州市'
    assert len(crud.get_users(db,office_city_id=gz,active_only=True))==1
    assert crud.count_users(db,office_city_id=gz,active_only=True)==1
    person.is_deleted=True;db.commit()
    assert next(row for row in office.catalog(db)['items'] if row['id']==gz)['actual_people']==0
    crud.update_user(db,other.id,AppUserUpdate(office_city_id=None))
    assert db.get(office.EmployeeOffice,other.id) is None
    assert crud.count_users(db,office_city_id=gz)==0


def test_new_city_unique_seats_zero_and_stale_revision(offices):
    db,_=offices
    result=office.save(db,office.OfficeWrite(city='杭州',name='杭州办公室',seats=0))
    row=db.get(office.OfficeSite,__import__('uuid').UUID(result['id']))
    assert row.seats==0
    with pytest.raises(HTTPException):office.save(db,office.OfficeWrite(city=' 杭州 ',name='重复',seats=3))
    office.save(db,office.OfficeUpdate(city='杭州',name='杭州办公室',seats=20,revision=1),row.id)
    with pytest.raises(HTTPException) as stale:office.save(db,office.OfficeUpdate(city='杭州',name='过期修改',seats=30,revision=1),row.id)
    assert stale.value.status_code==409 and db.get(office.OfficeSite,row.id).seats==20


def test_user_creation_city_atomic_validation_and_return(offices,monkeypatch):
    db,users=offices
    monkeypatch.setattr(crud,'hash_password',lambda value:'disabled')
    import organization_service
    monkeypatch.setattr(organization_service,'publish',lambda *args:None)
    def assign_id(_mapper,_connection,target):
        if target.id is None:target.id=uuid4()
    event.listen(AppUser,'before_insert',assign_id)
    try:
        value=crud.create_user(db,AppUserCreate(username='office-new-user',full_name='新城市人员',password='test-only',office_city_id=office.default_id('深圳')))
        assert value.city=='深圳' and value.office_name=='深圳南山办公室'
        with pytest.raises(HTTPException):crud.create_user(db,AppUserCreate(username='invalid-city-user',password='test-only',office_city_id=uuid4()))
        assert db.query(AppUser).filter_by(username='invalid-city-user').count()==0
        with pytest.raises(HTTPException):crud.update_user(db,value.id,AppUserUpdate(full_name='不应写入',office_city_id=uuid4()))
        assert db.get(AppUser,value.id).full_name=='新城市人员'
    finally:event.remove(AppUser,'before_insert',assign_id)


def test_users_page_city_count_filter_and_office_read_write_permissions(offices,monkeypatch):
    db,(admin,readonly,outsider)=offices;gz=office.default_id('广州')
    crud.update_user(db,readonly.id,AppUserUpdate(office_city_id=gz))
    from routers import users as users_router,auth
    from database import get_db
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda db,uid:['system:users:read','system:users:write'] if uid==admin.id else ['system:users:read'] if uid==readonly.id else [])
    monkeypatch.setattr(auth,'user_has_permission',lambda db,uid,code:uid==admin.id)
    app=FastAPI();app.include_router(office.router);app.include_router(users_router.router)
    app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[auth.get_current_user]=lambda:readonly
    with TestClient(app) as client:
        assert client.get('/office-management').status_code==200
        assert client.post('/office-management',json={'city':'杭州','name':'杭州办公室','seats':10}).status_code==403
        params={'office_city_id':str(gz),'active_only':True,'skip':0,'limit':10}
        result=client.get('/users/page',params=params)
        assert result.status_code==200 and result.json()['total']==1 and result.json()['items'][0]['city']=='广州'
        assert len(client.get('/users/',params=params).json())==1
        assert client.get('/users/count',params=params).json()['total']==1
        app.dependency_overrides[auth.get_current_user]=lambda:admin
        assert client.post('/office-management',json={'city':'杭州','name':'杭州办公室','seats':-1}).status_code==422
        assert client.post('/office-management',json={'city':'杭州','name':'杭州办公室','seats':10}).status_code==200
        app.dependency_overrides[auth.get_current_user]=lambda:outsider
        assert client.get('/office-management').status_code==403


def test_migration_only_new_tables_idempotent_seeded_defaults():
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE app_user (id UUID PRIMARY KEY)'))
        apply_migration(connection);apply_migration(connection)
        assert connection.execute(text('SELECT count(*) FROM organization_office_site')).scalar()==3
        assert [row['name'] for row in inspect(connection).get_columns('app_user')]==['id']
        assert inspect(connection).has_table('employee_office_city')
    engine.dispose()
