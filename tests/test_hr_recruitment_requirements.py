"""招聘需求编号、搜索、权限和并发版本；隔离 SQLite。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException,FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text,inspect
from pydantic import ValidationError
from test_chat_participant_access import environment
from test_monthly_shift import setup
import hr_recruitment_requirements as service


def data(**values):return service.RequirementCreate(client_id=uuid4(),request_date=date(2026,10,29),position='英语翻译',reason='项目新增',headcount=2,details='熟悉医学翻译\n具备审校经验',**values)


def test_date_number_idempotent_soft_delete_does_not_reuse_number(environment):
    db,users=environment;setup(db,users);admin=users[0]
    request=data();first=service.create(db,admin,request)
    assert first['demand_no']=='RT-261029-001'
    assert service.create(db,admin,request)['id']==first['id']
    service.delete(db,admin,first['id'],first['revision'])
    second=service.create(db,admin,data())
    assert second['demand_no']=='RT-261029-002'
    tomorrow=data().model_copy(update={'request_date':date(2026,10,30)})
    assert service.create(db,admin,tomorrow)['demand_no']=='RT-261030-001'
    assert service.list_rows(db,admin)['total']==2
    assert db.query(service.RecruitmentRequirement).count()==3


def test_update_keeps_number_and_rejects_stale_revision(environment):
    db,users=environment;setup(db,users);admin=users[0]
    row=service.create(db,admin,data())
    request=service.RequirementUpdate(**{**data().model_dump(exclude={'client_id'}),'request_date':date(2026,10,30),'headcount':3},revision=1)
    result=service.update(db,admin,row['id'],request)
    assert result['demand_no']=='RT-261029-001' and result['request_date']==date(2026,10,30) and result['revision']==2
    assert service.update(db,admin,row['id'],request)['revision']==2
    with pytest.raises(HTTPException) as conflict:service.update(db,admin,row['id'],request.model_copy(update={'position':'项目经理'}))
    assert conflict.value.status_code==409
    with pytest.raises(HTTPException):service.delete(db,admin,row['id'],1)


def test_multiterm_search_across_fields_and_literal_special_characters(environment):
    db,users=environment;setup(db,users);admin=users[0]
    service.create(db,admin,data())
    service.create(db,admin,data().model_copy(update={'position':'工程师','details':'SQL 100% _C++'}))
    assert service.list_rows(db,admin,'医学 英语')['total']==1
    assert service.list_rows(db,admin,'英语 缺少词')['total']==0
    assert service.list_rows(db,admin,'100% _C++')['total']==1
    assert service.list_rows(db,admin,'261029 2')['total']==2
    assert service.list_rows(db,admin,page=2,limit=1)['total']==2
    assert len(service.list_rows(db,admin,page=2,limit=1)['items'])==1


def test_hr_only_endpoints_and_required_fields(environment):
    db,users=environment;setup(db,users);admin,person,_=users
    from database import get_db
    from routers.auth import get_current_user
    app=FastAPI();app.include_router(service.router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:person
    with TestClient(app) as client:
        request=data().model_dump(mode='json')
        assert client.get('/hr-recruitment/requirements').status_code==403
        assert client.post('/hr-recruitment/requirements',json=request).status_code==403
        app.dependency_overrides[get_current_user]=lambda:admin
        assert client.post('/hr-recruitment/requirements',json={**request,'headcount':0}).status_code==422
        assert client.post('/hr-recruitment/requirements',json={**request,'details':'  '}).status_code==422
        result=client.post('/hr-recruitment/requirements',json=request)
        assert result.status_code==200 and result.json()['created_at'].endswith('+08:00')
        row=result.json()
        assert client.get(f'/hr-recruitment/requirements/{row["id"]}').status_code==200
        assert client.delete(f'/hr-recruitment/requirements/{row["id"]}?revision=1').status_code==200
        assert client.get(f'/hr-recruitment/requirements/{row["id"]}').status_code==404


def test_migration_idempotent_without_altering_app_user():
    from tools.apply_hr_recruitment_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE app_user (id UUID PRIMARY KEY)'))
        apply_migration(connection);apply_migration(connection)
        assert inspect(connection).has_table('hr_recruitment_requirement')
        assert [row['name'] for row in inspect(connection).get_columns('app_user')]==['id']
    engine.dispose()


def test_recruitment_city_saved_searchable_and_omission_preserves_it(environment):
    db,users=environment;setup(db,users);admin=users[0]
    request=data().model_copy(update={'recruitment_city':'广州'})
    row=service.create(db,admin,request)
    assert row['recruitment_city']=='广州' and service.create(db,admin,request)['id']==row['id']
    assert service.list_rows(db,admin,'广州 医学')['total']==1
    assert service.list_rows(db,admin,'深圳 医学')['total']==0
    fields=request.model_dump(exclude={'client_id','recruitment_city'})
    result=service.update(db,admin,row['id'],service.RequirementUpdate(**fields,revision=1))
    assert result['recruitment_city']=='广州'
    result=service.update(db,admin,row['id'],service.RequirementUpdate(**fields,recruitment_city='深圳',revision=2))
    assert result['recruitment_city']=='深圳' and service.list_rows(db,admin,'深圳')['total']==1


def test_recruitment_city_migration_only_adds_linked_table(environment):
    from tools.apply_hr_recruitment_city_migration import apply_migration
    db,_=environment
    service.RecruitmentRequirementCity.__table__.drop(db.connection());db.commit()
    before=[row['name'] for row in inspect(db.connection()).get_columns('hr_recruitment_requirement')]
    apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert [row['name'] for row in inspect(db.connection()).get_columns('hr_recruitment_requirement')]==before
    assert inspect(db.connection()).has_table('hr_recruitment_requirement_city')
