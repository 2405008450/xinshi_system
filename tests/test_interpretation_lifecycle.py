"""新增口译生命周期仅使用隔离SQLite，不发送外部通知。"""
from datetime import datetime
from uuid import uuid4
from types import SimpleNamespace
import pytest
from sqlalchemy import event,inspect
from tests.test_chat_participant_access import environment
from interpretation_models import InterpretationProject,InterpretationProjectTimeRange,InterpretationProjectStatusHistory
from interpretation_schemas import InterpretationProjectCreate,InterpretationProjectUpdate
from resource_models import ResourcePerson
import interpretation_service as service
import interpretation_lifecycle as lifecycle

def clock(text):return lifecycle.business_datetime(datetime.fromisoformat(text))
def setup_service(db,monkeypatch):
 def ids(session,*_):
  for row in session.new:
   if hasattr(row,'id') and row.id is None:row.id=uuid4()
 event.listen(db,'before_flush',ids)
 monkeypatch.setattr(service,'generate_interpretation_order_no',lambda *_:'IP-LIFE-'+str(uuid4())[:8])

def test_contract_paths_are_atomic_and_do_not_regress_running_projects(environment,monkeypatch):
 db,users=environment;setup_service(db,monkeypatch)
 people=[ResourcePerson(id=uuid4(),resource_code=f'RC-CONTRACT-{n}',full_name=f'译员{n}',status='standby') for n in range(2)]
 db.add_all(people);db.commit()
 project=service.create_interpretation_project(db,InterpretationProjectCreate(project_name='合同测试',interpreter_assignments=[{'translator_id':p.id} for p in people]),users[0].id)
 def save(paths,customer='',status=None):
  return service.update_interpretation_project(db,project.id,InterpretationProjectUpdate(project_status=status or project.project_status,contract_path=customer,interpreter_assignments=[{'translator_id':p.id,'contract_path':path} for p,path in zip(people,paths)]),users[0].id)
 project=save(['一.pdf','']);assert project.project_status=='candidates_provided'
 project=save(['一.pdf','二.pdf']);assert project.project_status=='interpreter_contract_signed'
 project=save(['一.pdf','二.pdf'],'客户.pdf');assert project.project_status=='both_contracts_signed'
 read=service.get_interpretation_project(db,project.id);assert [r.contract_path for r in read.interpreter_assignments]==['一.pdf','二.pdf']
 project=save(['一.pdf','二.pdf'],'客户.pdf','in_progress');assert project.project_status=='in_progress'
 project=save(['修改.pdf','二.pdf'],'客户修改.pdf');assert project.project_status=='in_progress'

def test_customer_contract_can_be_registered_first(environment,monkeypatch):
 db,users=environment;setup_service(db,monkeypatch)
 project=service.create_interpretation_project(db,InterpretationProjectCreate(project_name='先客户合同',contract_path='客户.pdf'),users[0].id)
 assert project.project_status=='client_contract_signed'

def test_new_table_migration_is_idempotent(environment):
 db,_=environment
 from tools.apply_interpretation_lifecycle_migration import apply_migration
 before=set(inspect(db.connection()).get_table_names());apply_migration(db.connection());apply_migration(db.connection())
 assert set(inspect(db.connection()).get_table_names())==before

def test_date_transitions_reminders_dedup_and_original_room_dispatch(environment,monkeypatch):
 db,users=environment
 from models import AppNotification
 import database,project_delivery,project_chat_crud
 monkeypatch.setattr(database,'engine',db.get_bind());monkeypatch.setattr(project_chat_crud,'_push_notifications',lambda *_:None)
 monkeypatch.setattr(lifecycle,'recipients',lambda *_:(users[0].id,[users[1].id]))
 dispatched=[];monkeypatch.setattr(project_delivery,'send',lambda *args,**kw:dispatched.append((args[3],kw['status_change_id'])))
 project=InterpretationProject(id=uuid4(),order_no='IP-DATE',project_name='自动日期',project_status='deal_pending_execution',created_by=users[0].id)
 project.time_ranges=[InterpretationProjectTimeRange(id=uuid4(),sequence_no=1,scheduled_start=datetime(2026,12,7,9),scheduled_end=datetime(2026,12,8,18))]
 db.add(project);db.add(lifecycle.InterpretationLifecycle(project_id=project.id,assignment_data={},date_automation_enabled=True,notice_keys=[],pending_status_ids=[],activated_at=clock('2026-12-01T09:00')));db.commit()
 def tick(at):
  monkeypatch.setattr(lifecycle,'business_now',lambda:clock(at));lifecycle.worker_once();db.expire_all()
 tick('2026-12-04T09:00');count=db.query(AppNotification).count();assert count==1
 tick('2026-12-04T09:30');assert db.query(AppNotification).count()==count
 tick('2026-12-04T14:00');assert db.query(AppNotification).count()==count+1
 tick('2026-12-07T09:00');assert db.get(InterpretationProject,project.id).project_status=='in_progress'
 tick('2026-12-08T18:00');assert db.get(InterpretationProject,project.id).project_status=='ended'
 assert len(dispatched)==2 and dispatched[0][0]==dispatched[1][0]==project.id
 events=db.query(InterpretationProjectStatusHistory).filter_by(project_id=project.id).all();assert [r.to_status for r in events]==['in_progress','ended']
 tick('2026-12-10T09:00');assert any('收集客户反馈' in row.content for row in db.query(AppNotification))

def test_terminal_and_unactivated_historical_projects_untouched(environment,monkeypatch):
 db,users=environment
 import database
 monkeypatch.setattr(database,'engine',db.get_bind());monkeypatch.setattr(lifecycle,'business_now',lambda:clock('2026-12-10T12:00'))
 for status,enabled in [('cancelled',True),('initial_follow_up',False)]:
  project=InterpretationProject(id=uuid4(),order_no='IP-SKIP-'+status,project_name='不自动覆盖',project_status=status)
  project.time_ranges=[InterpretationProjectTimeRange(id=uuid4(),sequence_no=1,scheduled_start=datetime(2026,12,1),scheduled_end=datetime(2026,12,2))]
  db.add(project);db.add(lifecycle.InterpretationLifecycle(project_id=project.id,date_automation_enabled=enabled,assignment_data={},notice_keys=[],pending_status_ids=[],activated_at=clock('2026-12-01')))
 db.commit();lifecycle.worker_once();db.expire_all()
 assert {p.project_status for p in db.query(InterpretationProject)}=={'cancelled','initial_follow_up'}

def test_failed_status_notice_retries_same_event_without_duplicate_transition(environment,monkeypatch):
 db,users=environment
 import database,project_delivery,project_chat_crud
 monkeypatch.setattr(database,'engine',db.get_bind())
 monkeypatch.setattr(project_chat_crud,'_push_notifications',lambda *_:None)
 monkeypatch.setattr(lifecycle,'recipients',lambda *_:(users[0].id,[]))
 monkeypatch.setattr(lifecycle,'business_now',lambda:clock('2026-12-07T10:00'))
 project=InterpretationProject(id=uuid4(),order_no='IP-RETRY',project_name='重试',project_status='deal_pending_execution',created_by=users[0].id)
 project.time_ranges=[InterpretationProjectTimeRange(id=uuid4(),sequence_no=1,scheduled_start=datetime(2026,12,7,9),scheduled_end=datetime(2026,12,8,18))]
 db.add(project);db.add(lifecycle.InterpretationLifecycle(project_id=project.id,date_automation_enabled=True,assignment_data={},notice_keys=[],pending_status_ids=[],activated_at=clock('2026-12-01')));db.commit()
 attempts=[]
 def send(*args,**kwargs):
  attempts.append((args[4],kwargs['status_change_id']))
  if len(attempts)==1:raise RuntimeError('模拟发送失败')
 monkeypatch.setattr(project_delivery,'send',send)
 lifecycle.worker_once();db.expire_all()
 assert db.get(InterpretationProject,project.id).project_status=='in_progress'
 assert len(db.get(lifecycle.InterpretationLifecycle,project.id).pending_status_ids)==1
 lifecycle.worker_once();db.expire_all()
 assert len(attempts)==2 and attempts[0]==attempts[1]
 assert db.get(lifecycle.InterpretationLifecycle,project.id).pending_status_ids==[]
 assert db.query(InterpretationProjectStatusHistory).filter_by(project_id=project.id).count()==1
