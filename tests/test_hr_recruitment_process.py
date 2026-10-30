"""招聘过程条件校验、源需求同步、并发及权限；只用隔离 SQLite。"""
from datetime import date,datetime
from uuid import uuid4
import pytest
from pydantic import ValidationError
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text,inspect
from test_chat_participant_access import environment
from test_monthly_shift import setup
import hr_recruitment_requirements as requirements
import hr_recruitment_process as process


@pytest.fixture
def arranged(environment):
    db,users=environment;setup(db,users)
    demand=requirements.create(db,users[0],requirements.RequirementCreate(client_id=uuid4(),request_date=date(2026,10,29),recruitment_city='广州',position='翻译',reason='新增岗位',headcount=2,details='医学翻译'))
    return db,users,demand


def fields(requirement_id,**values):return {'requirement_id':requirement_id,'applicant_name':'候选甲',**values}


@pytest.mark.parametrize('kind',['candidate_withdrew','company_declined'])
def test_withdrawal_requires_reason(kind):
    with pytest.raises(ValidationError):process.CandidateCreate(client_id=uuid4(),**fields(uuid4(),willingness=kind,willingness_reason=' '))
    value=process.CandidateCreate(client_id=uuid4(),**fields(uuid4(),willingness=kind,willingness_reason=' 明确原因 '))
    assert value.willingness_reason=='明确原因'


def test_interview_result_time_and_reserved_status_validation():
    base=fields(uuid4())
    with pytest.raises(ValidationError):process.CandidateCreate(client_id=uuid4(),**base,first_interview_done=True)
    with pytest.raises(ValidationError):process.CandidateCreate(client_id=uuid4(),**base,second_interview_done=True,second_interview_at='2026-10-30T10:00:00',second_result='结果')
    with pytest.raises(ValidationError):process.CandidateCreate(client_id=uuid4(),**base,willingness='yes')
    with pytest.raises(ValidationError):process.CandidateCreate(client_id=uuid4(),**base,actual_onboarded=True)
    with pytest.raises(ValidationError):process.CandidateCreate(client_id=uuid4(),**base,recruitment_city='伪造城市')
    value=process.CandidateCreate(client_id=uuid4(),**base,first_interview_done=False,first_result='隐藏旧结果')
    assert value.first_result==''


def test_create_interviews_willingness_date_and_idempotency(arranged):
    db,(admin,_,_),demand=arranged
    request=process.CandidateCreate(client_id=uuid4(),**fields(demand['id'],first_interview_done=True,first_interview_at='2026-10-29T09:00:00+08:00',first_result='一面通过',second_interview_done=True,second_interview_at='2026-10-30T09:00:00+08:00',second_result='二面通过',willingness='yes',onboarding_date='2026-11-05'))
    result=process.create(db,admin,request)
    assert result['recruitment_city']=='广州' and result['position']=='翻译'
    assert result['first_result']=='一面通过' and result['second_result']=='二面通过'
    assert result['onboarding_date']==date(2026,11,5) and result['actual_onboarded'] is None
    assert result['first_interview_at'].isoformat().endswith('+08:00')
    assert process.create(db,admin,request)['id']==result['id'] and db.query(process.HrRecruitmentCandidate).count()==1


def test_live_city_position_sync_search_and_deleted_requirement_history(arranged):
    db,(admin,_,_),demand=arranged
    result=process.create(db,admin,process.CandidateCreate(client_id=uuid4(),**fields(demand['id'])))
    values=requirements.RequirementUpdate(request_date=date(2026,10,29),recruitment_city='深圳',position='译审',reason='调整',headcount=2,details='经验要求',revision=1)
    requirements.update(db,admin,demand['id'],values)
    rows=process.listing(db,admin,keyword='深圳 译审 候选')['items']
    assert len(rows)==1 and rows[0]['position']=='译审' and rows[0]['recruitment_city']=='深圳'
    requirements.delete(db,admin,demand['id'],2)
    assert process.listing(db,admin)['items'][0]['requirement_deleted']
    with pytest.raises(HTTPException):process.create(db,admin,process.CandidateCreate(client_id=uuid4(),**fields(demand['id'])))
    updated=process.update(db,admin,result['id'],process.CandidateUpdate(**fields(demand['id'],willingness='candidate_withdrew',willingness_reason='个人安排'),revision=1))
    assert updated['willingness_reason']=='个人安排' and updated['requirement_deleted']


def test_stale_revision_delete_and_non_hr_are_rejected(arranged):
    db,(admin,person,_),demand=arranged
    result=process.create(db,admin,process.CandidateCreate(client_id=uuid4(),**fields(demand['id'])))
    request=process.CandidateUpdate(**fields(demand['id'],willingness='company_declined',willingness_reason='岗位暂停'),revision=1)
    process.update(db,admin,result['id'],request)
    with pytest.raises(HTTPException) as stale:process.update(db,admin,result['id'],request.model_copy(update={'applicant_name':'不同修改'}))
    assert stale.value.status_code==409
    with pytest.raises(HTTPException):process.delete(db,admin,result['id'],1)
    with pytest.raises(HTTPException):process.listing(db,person)
    process.delete(db,admin,result['id'],2)
    remaining=process.listing(db,admin)
    assert remaining['total']==1 and remaining['items'][0]['is_placeholder']


def test_http_validation_and_reserved_field(arranged):
    from routers.auth import get_current_user
    from database import get_db
    db,(admin,person,_),demand=arranged
    app=FastAPI();app.include_router(process.router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:admin
    with TestClient(app) as client:
        request={'client_id':str(uuid4()),**fields(str(demand['id']))}
        assert client.post('/hr-recruitment/process',json={**request,'actual_onboarded':True}).status_code==422
        assert client.post('/hr-recruitment/process',json={**request,'willingness':'yes'}).status_code==422
        assert client.post('/hr-recruitment/process',json=request).status_code==200
        app.dependency_overrides[get_current_user]=lambda:person
        assert client.get('/hr-recruitment/process').status_code==403


def test_process_migration_idempotent_no_existing_schema_changes(arranged):
    from tools.apply_hr_recruitment_process_migration import apply_migration
    db,_,_=arranged
    process.HrRecruitmentCandidate.__table__.drop(db.connection());db.commit()
    before=[row['name'] for row in inspect(db.connection()).get_columns('hr_recruitment_requirement')]
    apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert [row['name'] for row in inspect(db.connection()).get_columns('hr_recruitment_requirement')]==before
    assert inspect(db.connection()).has_table('hr_recruitment_candidate')


def test_requirements_automatically_appear_without_fake_candidates_and_search_pagination(arranged):
    db,(admin,_,_),demand=arranged
    before=db.query(process.HrRecruitmentCandidate).count()
    initial=process.listing(db,admin)
    assert initial['total']==1 and initial['items'][0]['is_placeholder']
    assert initial['items'][0]['requirement_id']==demand['id']
    assert initial['items'][0]['recruitment_city']=='广州'
    assert db.query(process.HrRecruitmentCandidate).count()==before
    other=requirements.create(db,admin,requirements.RequirementCreate(client_id=uuid4(),request_date=date(2026,10,30),recruitment_city='上海',position='全岗位',reason='人数不足',headcount=2,details='具体要求'))
    assert process.listing(db,admin,keyword='上海 全岗位')['total']==1
    assert process.listing(db,admin,keyword='不存在')['total']==0
    assert process.listing(db,admin,page=2,limit=1)['total']==2
    assert len(process.listing(db,admin,page=2,limit=1)['items'])==1
    first=process.create(db,admin,process.CandidateCreate(client_id=uuid4(),**fields(demand['id'])))
    items=process.listing(db,admin)['items']
    assert len(items)==2 and sum(bool(item.get('is_placeholder')) for item in items)==1
    assert any(item['id']==first['id'] for item in items)
    process.create(db,admin,process.CandidateCreate(client_id=uuid4(),**fields(demand['id'],applicant_name='第二位应聘人')))
    assert process.listing(db,admin)['total']==3
    requirements.delete(db,admin,other['id'],other['revision'])
    assert process.listing(db,admin)['total']==2
