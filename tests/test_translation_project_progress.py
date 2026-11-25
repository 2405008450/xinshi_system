"""统一进度使用隔离 SQLite，绝不连接业务数据库。"""
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from models import TranslationProject
from tests.test_chat_participant_access import environment
from translation_project_progress import TranslationProjectProgress, ProgressWrite, save, report
from tools.apply_translation_project_progress_migration import apply_migration
from concurrency import StaleUpdateError


def seed(db,actor):
    row=TranslationProject(id=uuid4(),order_no='TP-261125-999',project_name='进度测试',project_status='confirmed',updated_at=datetime(2026,11,25,8),created_by=actor.id)
    db.add(row);db.commit();return row


def payload(row,**updates):
    return ProgressWrite(project_status=updates.pop('project_status',row.project_status),change_note=updates.pop('change_note','进度说明'),effective_on=datetime(2026,11,25,0,30,tzinfo=timezone.utc),expected_updated_at=updates.pop('expected_updated_at',row.updated_at),request_id=updates.pop('request_id',uuid4()),**updates)


def test_note_only_and_idempotent_retry_timezone_and_long_note(environment):
    db,users=environment;row=seed(db,users[0]);body=payload(row,change_note='详细进度'*500)
    first=save(db,row.id,body,users[0]);again=save(db,row.id,body,users[0])
    assert first==again and db.query(TranslationProjectProgress).count()==1
    assert first['project_status']=='confirmed'
    assert first['items'][0]['effective_on']=='2026-11-25T08:30:00+08:00'
    assert first['items'][0]['change_note']==body.change_note
    with pytest.raises(HTTPException):save(db,row.id,body.model_copy(update={'change_note':'不同内容'}),users[0])


def test_status_and_note_saved_together_through_existing_crud(environment):
    db,users=environment;row=seed(db,users[0])
    result=save(db,row.id,payload(row,project_status='cancelled'),users[0])
    assert result['project_status']=='cancelled'
    assert result['items'][0]['from_status']=='confirmed'
    assert result['items'][0]['to_status']=='cancelled'
    assert result['items'][0]['change_note']=='进度说明'


def test_stale_version_and_invalid_status_do_not_add_records(environment):
    db,users=environment;row=seed(db,users[0])
    with pytest.raises(StaleUpdateError):save(db,row.id,payload(row,expected_updated_at=datetime(2026,11,24)),users[0])
    assert db.query(TranslationProjectProgress).count()==0
    with pytest.raises(HTTPException):save(db,row.id,payload(row,project_status='not-supported'),users[0])
    assert db.query(TranslationProjectProgress).count()==0


def test_migration_can_run_twice(environment):
    db,_=environment
    TranslationProjectProgress.__table__.drop(db.connection(),checkfirst=True)
    apply_migration(db.connection());apply_migration(db.connection())
    assert db.query(TranslationProjectProgress).count()==0


def test_status_business_failure_rolls_back_pending_progress(environment, monkeypatch):
    import crud
    from translation_project_progress import write_progress
    db,users=environment;row=seed(db,users[0])
    def fail(*args,**kwargs):
        db.flush()
        raise ValueError('状态变更被业务校验拒绝')
    monkeypatch.setattr(crud,'update_translation_project',fail)
    with pytest.raises(ValueError):write_progress(row.id,payload(row,project_status='cancelled'),db,users[0])
    assert db.query(TranslationProjectProgress).count()==0
    assert db.get(TranslationProject,row.id).project_status=='confirmed'
