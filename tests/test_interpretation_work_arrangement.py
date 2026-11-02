"""口译今日安排权限、跨天保留、版本保护和新表重复创建，仅隔离 SQLite。"""
from datetime import datetime,timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect
from test_chat_participant_access import environment
from interpretation_models import InterpretationProject
from interpretation_work_arrangement import InterpretationWorkDay
import interpretation_work_arrangement as service
from chat_time import BUSINESS_TIMEZONE


@pytest.fixture
def setup(environment,monkeypatch):
    db,(owner,member,outsider)=environment
    member.username='zixia'
    project=InterpretationProject(id=uuid4(),order_no='IP-ARRANGE-001',project_name='口译安排测试',project_status='in_progress')
    db.add(project);db.commit()
    clock=[datetime(2026,11,2,10,tzinfo=BUSINESS_TIMEZONE)]
    monkeypatch.setattr(service,'now',lambda:clock[0])
    return db,member,outsider,project,clock


def write(revision=0,status='not_today'):
    return service.ArrangementWrite(revision=revision,arrangement_status=status,remaining_time='1_2h')


def test_context_save_cross_day_revision_and_personal_isolation(setup):
    db,user,other,project,clock=setup
    before=service.context(db,user,project.id)
    assert before['items'][0]['arrangement_status']=='in_progress'
    assert before['items'][0]['remaining_time'] is None
    saved=service.save(db,user,project.id,write())
    assert saved['arrangement_status']=='not_today' and saved['revision']==1
    assert project.project_status=='in_progress'
    clock[0]+=timedelta(days=1)
    assert service.context(db,user,project.id)['items'][0]['arrangement_status']=='not_today'
    with pytest.raises(HTTPException) as stale:
        service.save(db,user,project.id,write())
    assert stale.value.status_code==409
    db.rollback()
    resumed=service.save(db,user,project.id,write(1,'in_progress'))
    assert resumed['revision']==2
    assert db.query(InterpretationWorkDay).count()==2
    with pytest.raises(HTTPException) as denied:
        service.save(db,other,project.id,write())
    assert denied.value.status_code==404
    db.rollback()
    project.project_status='settled';db.commit()
    with pytest.raises(HTTPException):
        service.context(db,user,project.id)


def test_today_filter_matches_task_scope_and_defaults(setup):
    db,user,_,project,clock=setup
    def visible():
        return db.query(InterpretationProject).filter(service.today_filter(db,user)).count()
    assert visible()==1
    service.save(db,user,project.id,write())
    assert visible()==0
    clock[0]+=timedelta(days=1)
    assert visible()==0
    service.save(db,user,project.id,write(1,'in_progress'))
    assert visible()==1


def test_new_table_migration_repeatable_and_existing_data_unchanged(environment):
    from tools.apply_interpretation_work_arrangement_migration import apply_migration
    from models import AppUser
    db,_=environment
    count=db.query(AppUser).count()
    connection=db.connection()
    InterpretationWorkDay.__table__.drop(connection)
    apply_migration(connection);apply_migration(connection)
    info=inspect(connection)
    assert info.has_table('interpretation_work_day')
    assert any(set(row['column_names'])=={'user_id','project_id','work_date'} for row in info.get_unique_constraints('interpretation_work_day'))
    assert {row['referred_table'] for row in info.get_foreign_keys('interpretation_work_day')}=={'app_user','interpretation_project'}
    assert db.query(AppUser).count()==count
