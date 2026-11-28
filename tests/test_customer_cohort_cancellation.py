"""客户跨业务新老判断、分级取消及原始说明保留；全部使用隔离SQLite。"""
from datetime import date,datetime
from uuid import uuid4
import pytest
from tests.test_chat_participant_access import environment
from tests.test_interpretation_lifecycle import setup_service
from models import Client,TranslationProject
from interpretation_models import InterpretationProject,InterpretationProjectStatusHistory
from annotation_models import AnnotationProject
from recruitment_models import RecruitmentProject
from client_cohort import snapshots,ClientCohortOverride
from interpretation_partial_cancellation import CancellationDetails,InterpretationCancellationClassification,classify_existing
import interpretation_service as service
from interpretation_schemas import InterpretationProjectCreate
from resource_models import ResourcePerson

def test_cross_module_count_age_and_temporary_range_ignore_manual(environment,monkeypatch):
 db,users=environment
 import client_cohort
 monkeypatch.setattr(client_cohort,'business_now',lambda:datetime.fromisoformat('2026-11-28T10:00:00+08:00'))
 customer=Client(id=uuid4(),client_code='CC',client_name='跨业务客户');db.add(customer)
 db.add(TranslationProject(id=uuid4(),order_no='TP-261001-001',client_id=customer.id,project_name='笔译'))
 db.commit();assert snapshots(db,[customer.id])[str(customer.id)]['cohort']=='new'
 db.add(InterpretationProject(id=uuid4(),order_no='IP-261102-001',client_id=customer.id,project_name='口译'));db.commit()
 state=snapshots(db,[customer.id])[str(customer.id)];assert state['cohort']=='old' and state['order_count']==2
 db.add(ClientCohortOverride(client_id=customer.id,cohort='new',reason='手工调整',history=[],updated_by=users[0].id));db.commit()
 assert snapshots(db,[customer.id])[str(customer.id)]['cohort']=='new'
 state=snapshots(db,[customer.id],start=date(2026,10,1),end=date(2026,10,31))[str(customer.id)];assert state['cohort']=='new' and state['order_count']==1
 state=snapshots(db,[customer.id],start=date(2026,11,1),end=date(2026,11,30))[str(customer.id)];assert state['cohort']=='old'
 aged=Client(id=uuid4(),client_code='AGED',client_name='满三个月');db.add(aged);db.add(RecruitmentProject(id=uuid4(),order_no='HP-260828-001',client_id=aged.id,project_name='招聘'));db.commit()
 assert snapshots(db,[aged.id])[str(aged.id)]['cohort']=='old'


def test_nested_cancel_links_interpreter_and_preserves_original(environment,monkeypatch):
 db,users=environment;setup_service(db,monkeypatch)
 person=ResourcePerson(id=uuid4(),resource_code='RC-CANCEL',full_name='问题译员',status='standby');db.add(person);db.commit()
 project=service.create_interpretation_project(db,InterpretationProjectCreate(project_name='取消联动',interpreter_assignments=[{'translator_id':person.id}]),users[0].id)
 with pytest.raises(ValueError,match='弹窗'):service.update_interpretation_project_status(db,project.id,'cancelled',changed_by=users[0].id)
 db.rollback()
 path=['客户已取消','译员原因','译员主观原因','态度问题']
 details=CancellationDetails(reason_paths=[path,['客户不回复']],translator_issues=[{'translator_id':str(person.id),'reason_path':path}],note='保留截图说明原文')
 result=service.update_interpretation_project_status(db,project.id,'cancelled',change_note='原始说明全文',changed_by=users[0].id,cancellation_details=details)
 assert result.project_status=='cancelled'
 assert result.interpreter_assignments[0].cancellation_issues[0]['reason_path']==path
 record=db.query(InterpretationCancellationClassification).filter_by(project_id=project.id).one()
 assert record.original_note=='原始说明全文' and record.details['note']=='保留截图说明原文'
 event=db.get(InterpretationProjectStatusHistory,record.status_event_id);assert '问题译员' in event.change_note and '态度问题' in event.change_note


def test_partial_and_required_explanations(environment,monkeypatch):
 db,users=environment;setup_service(db,monkeypatch)
 project=service.create_interpretation_project(db,InterpretationProjectCreate(project_name='部分取消'),users[0].id)
 with pytest.raises(ValueError):CancellationDetails(reason_paths=[['其他原因（自行填写）']])
 for value in ['无法找到译员','无法提供合适译员']:
  with pytest.raises(ValueError):CancellationDetails(reason_paths=[[value]])
 details=CancellationDetails(reason_paths=[['行程/计划改变'],['支付定金后（部分）取消']],note='共同截图与说明')
 result=service.update_interpretation_project_status(db,project.id,'partially_cancelled',changed_by=users[0].id,cancellation_details=details)
 assert result.project_status=='partially_cancelled'
 assert db.query(InterpretationCancellationClassification).filter_by(project_id=project.id).one().details['reason_paths']==details.reason_paths


def test_historical_classification_is_idempotent_and_original_unchanged(environment):
 db,_=environment
 project=InterpretationProject(id=uuid4(),order_no='IP-261101-777',project_name='旧取消',project_status='cancelled');db.add(project)
 raw='客户预算低；原始说明及标点均保留。'
 event=InterpretationProjectStatusHistory(id=uuid4(),project_id=project.id,to_status='cancelled',effective_on=datetime(2026,11,1),changed_at=datetime(2026,11,1),change_note=raw);db.add(event);db.commit()
 assert classify_existing(db)['inserted']==1;db.commit();assert classify_existing(db)['inserted']==0
 db.expire_all();assert db.get(InterpretationProjectStatusHistory,event.id).change_note==raw
 record=db.query(InterpretationCancellationClassification).one();assert record.original_note==raw
 assert record.details['reason_paths']==[['客户已取消','客户预算低']]


def test_new_tables_migration_is_idempotent(environment):
 from tools.apply_client_cohort_cancellation_migration import apply_migration
 from sqlalchemy import inspect
 db,_=environment;before=set(inspect(db.connection()).get_table_names())
 apply_migration(db.connection());apply_migration(db.connection())
 assert set(inspect(db.connection()).get_table_names())==before


@pytest.mark.parametrize('text,path',[
 ('客户那边预算不足，按取消处理',['客户已取消','客户预算低']),
 ('客户一直不回复，按取消处理',['客户不回复']),
 ('客户那边暂时出不了国',['客户已取消','客户无法出国']),
 ('战争原因',['客户已取消','不可抗力']),
 ('客户说同事那边找了',['客户已找到','同事找到译员']),
 ('找不到适合的译员资源',['无法提供合适译员']),
])
def test_historical_classification_semantics(text,path):
 from interpretation_partial_cancellation import classify_original
 assert path in classify_original('cancelled',text)['reason_paths']


def test_manual_client_override_requires_reason_and_keeps_business_status(environment,monkeypatch):
 from routers import clients
 from fastapi import HTTPException
 db,users=environment;monkeypatch.setattr(clients,'user_has_permission',lambda *_:True)
 row=Client(id=uuid4(),client_code='MANUAL',client_name='手动客户',client_status='active');db.add(row);db.commit()
 with pytest.raises(HTTPException):clients.client_cohort_write(row.id,{'cohort':'old','reason':''},db,users[0])
 saved=clients.client_cohort_write(row.id,{'cohort':'old','reason':'业务确认','expected_updated_at':None},db,users[0])
 assert saved['cohort']=='old' and saved['history'][0]['reason']=='业务确认'
 with pytest.raises(HTTPException) as stale:clients.client_cohort_write(row.id,{'cohort':'new','reason':'旧窗口','expected_updated_at':None},db,users[0])
 assert stale.value.status_code==409
 db.rollback()
 restored=clients.client_cohort_write(row.id,{'cohort':None,'reason':'恢复自动','expected_updated_at':saved['updated_at']},db,users[0])
 assert restored['cohort']=='new' and len(restored['history'])==2
 assert db.get(Client,row.id).client_status=='active'
