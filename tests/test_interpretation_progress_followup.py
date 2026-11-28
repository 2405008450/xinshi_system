from datetime import datetime
from uuid import uuid4
from copy import deepcopy
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_interpretation_lifecycle import setup_service
from interpretation_schemas import InterpretationProjectCreate
from interpretation_models import InterpretationProjectStatusHistory
from interpretation_partial_cancellation import InterpretationCancellationClassification,review_classification,classify_original
from interpretation_progress import ProgressWrite,save,history
import interpretation_service as service

def test_three_tracks_retries_and_atomic_chat_failure(environment,monkeypatch):
 db,users=environment;setup_service(db,monkeypatch)
 item=service.create_interpretation_project(db,InterpretationProjectCreate(project_name='三轨道'),users[0].id)
 for track in ['project','customer','interpreter']:
  payload=ProgressWrite(track=track,change_note=track+'具体进度',effective_on=datetime.fromisoformat('2026-11-28T09:00:00+08:00'),request_key=uuid4(),send_to_chat=False)
  save(db,item.id,payload,users[0]);save(db,item.id,payload,users[0])
  assert len([row for row in history(db,item.id,track) if row['changeNote']==payload.change_note])==1
 import project_delivery
 monkeypatch.setattr(project_delivery,'send',lambda *_args,**_kwargs:(_ for _ in ()).throw(HTTPException(503,'发送失败')))
 monkeypatch.setattr('interpretation_progress.audience',lambda *_:[])
 payload=ProgressWrite(project_status='in_progress',change_note='更改状态',effective_on=datetime.fromisoformat('2026-11-28T10:00:00+08:00'),request_key=uuid4())
 with pytest.raises(HTTPException):save(db,item.id,payload,users[0])
 db.rollback();db.refresh(item);assert item.project_status=='initial_follow_up'

def test_review_keeps_original_and_rejects_stale_review(environment,monkeypatch):
 db,users=environment;setup_service(db,monkeypatch)
 item=service.create_interpretation_project(db,InterpretationProjectCreate(project_name='复核'),users[0].id)
 item.project_status='cancelled';raw='项目取消'
 record=InterpretationCancellationClassification(project_id=item.id,project_status='cancelled',original_note=raw,details={'reason_paths':[['其他原因（自行填写）']],'needs_review':True},source='auto');db.add(record);db.commit()
 before=deepcopy(record.details);payload={'classification_id':str(record.id),'expected_details':before,'details':{'reason_paths':[['客户未回复原因']]}}
 review_classification(db,item.id,payload,users[0].id);db.commit()
 assert record.original_note==raw and not record.details['needs_review'] and item.project_status=='cancelled'
 with pytest.raises(HTTPException) as exc:review_classification(db,item.id,payload,users[0].id)
 assert exc.value.status_code==409
 assert classify_original('cancelled','项目取消')['reason_paths']==[['客户未回复原因']]


def test_default_mentions_exclude_each_author(environment,monkeypatch):
 db,users=environment;setup_service(db,monkeypatch)
 item=service.create_interpretation_project(db,InterpretationProjectCreate(project_name='互相提醒'),users[0].id)
 monkeypatch.setattr('interpretation_lifecycle.recipients',lambda *_:(users[0].id,[users[1].id,users[2].id]))
 from interpretation_progress import audience
 for author in users:
  assert {row.id for row in audience(db,item,author)}=={row.id for row in users if row.id!=author.id}


def test_recruitment_cancellation_requires_real_note(environment,monkeypatch):
 db,users=environment;setup_service(db,monkeypatch)
 from recruitment_models import RecruitmentProject,RecruitmentProjectProgress
 from recruitment_service import update_recruitment_project_status
 item=RecruitmentProject(id=uuid4(),order_no='HP-261129-001',project_name='取消原因校验',project_status='sourcing');db.add(item);db.commit()
 with pytest.raises(ValueError,match='填写原因'):update_recruitment_project_status(db,item.id,'cancelled',users[0].id)
 db.rollback()
 update_recruitment_project_status(db,item.id,'cancelled',users[0].id,note='客户已改变招聘计划')
 saved=db.query(RecruitmentProjectProgress).filter_by(project_id=item.id).one()
 assert saved.note=='客户已改变招聘计划' and not saved.is_system
