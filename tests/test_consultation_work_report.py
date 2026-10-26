"""新咨询强制填写与七点归日；全部使用隔离 SQLite。"""
from datetime import datetime,date,timezone
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_chat_participant_access import environment
from test_work_report_access import report
import consultation_work_report as capture
from chat_time import BUSINESS_TIMEZONE
from work_report_dates import report_business_date,report_day_range

def consultation(db,user):
    from models import Consultation,Client
    client=Client(id=uuid4(),client_name='客户全称',client_short_name='客户简称',client_code='C-TEST')
    row=Consultation(id=uuid4(),client_id=client.id,consultation_code='ZX-TEST',consultation_method='其他',consultation_method_detail='在线表单',consultation_type='笔译',client_source='官网',project_intake={})
    db.add_all([client,row]);capture.mark_pending(row,user);db.commit();return row

def payload(**kwargs):
    return capture.ConsultationReportWrite(**({'order_no':'ZX-TEST','task_name':'客户全称 - 新咨询对接','progress_content':'在线表单 - 笔译 - 官网','quantity':'1.5','quantity_unit':'次','duration_minutes':20}|kwargs))

@pytest.mark.parametrize('value,expected',[
    ('2026-10-24T06:59:59+08:00','2026-10-23'),('2026-10-24T07:00:00+08:00','2026-10-24'),
    ('2027-01-01T00:30:00+08:00','2026-12-31'),('2026-10-23T23:00:00+00:00','2026-10-24')])
def test_seven_am_boundary(value,expected):
    assert report_business_date(datetime.fromisoformat(value)).isoformat()==expected
    start,end=report_day_range(date.fromisoformat(expected))
    assert start.hour==end.hour==7 and (end-start).total_seconds()==86400

@pytest.mark.parametrize('fields',[{'quantity':''},{'quantity':-1},{'quantity':'nan'},{'quantity_unit':' '},{'duration_minutes':0},{'progress_content':'data:image/png;base64,test'}])
def test_all_fields_required_and_images_rejected(fields):
    with pytest.raises(ValidationError):payload(**fields)

def test_pending_context_owner_and_protected_capture(environment):
    db,(owner,other,_)=environment
    row=consultation(db,owner)
    assert capture.pending(db,owner)[0]['id']==row.id
    assert not capture.pending(db,other)
    data=capture.capture_context(db,owner,row.id)
    assert data['client_name']=='客户全称' and data['task_name']=='客户全称 - 新咨询对接'
    assert data['progress_content']=='在线表单 - 笔译 - 官网'
    with pytest.raises(HTTPException):capture.capture_context(db,other,row.id)
    assert capture.preserve_capture(None,{capture.CAPTURE_KEY:{'status':'completed'}})=={}
    original=row.project_intake[capture.CAPTURE_KEY]
    assert capture.preserve_capture(row.project_intake,{capture.CAPTURE_KEY:{'owner_id':str(other.id)}})[capture.CAPTURE_KEY]==original

def test_append_finalized_preserves_items_revision_and_sync(environment,monkeypatch):
    db,(owner,viewer,_)=environment
    from test_work_report_access import configure_user
    import work_report_access as access
    import work_report_collaboration as collaboration
    configure_user(db,viewer)
    access.save_rule(db,viewer,access.AccessRuleWrite(name='查看',viewer_ids=[viewer.id],senders_all=True))
    row=consultation(db,owner)
    day=date(2026,10,23);existing=report(db,owner,day)
    original_id=existing.items[0].id;confirmed_at=existing.finalized_at
    monkeypatch.setattr(capture,'now',lambda:datetime(2026,10,24,6,59,tzinfo=BUSINESS_TIMEZONE))
    messages=[]
    import notification_ws
    monkeypatch.setattr(notification_ws,'broadcast_to_users',lambda users,event:messages.append((users,event)))
    result=capture.submit(db,owner,row.id,payload())
    assert result['report_id']==existing.id and result['report_date']==day
    assert existing.status=='finalized' and existing.finalized_at==confirmed_at
    assert len(existing.items)==2 and existing.items[0].id==original_id
    assert not collaboration.revision_status(db,existing.id)[1]
    assert existing.items[-1].display_metadata['added_at'].endswith('+08:00')
    assert str(viewer.id) in messages[0][0]
    assert capture.submit(db,owner,row.id,payload())['already_saved']
    assert len(existing.items)==2 and not capture.pending(db,owner)
    assert len(access.received_report(db,viewer,existing.id)['items'])==2

def test_draft_created_and_stale_save_preserves_append(environment,monkeypatch):
    db,(owner,_,_)=environment
    import task_service as service
    from task_schemas import DailyReportSaveRequest
    from task_models import DailyReport,DailyReportItem
    row=consultation(db,owner)
    monkeypatch.setattr(capture,'now',lambda:datetime(2026,10,24,8,tzinfo=BUSINESS_TIMEZONE))
    result=capture.submit(db,owner,row.id,payload())
    saved=db.get(DailyReport,result['report_id']);assert saved.status=='draft'
    monkeypatch.setattr(service,'derive_daily_report_items',lambda *args:[])
    original=DailyReportItem
    monkeypatch.setattr(service,'DailyReportItem',lambda **kw:original(id=uuid4(),**kw))
    service.save_daily_report(db,owner,date(2026,10,24),DailyReportSaveRequest(items=[]))
    assert len(saved.items)==1
    assert saved.items[0].display_metadata['source']=='consultation_handoff'
    assert len(service.preview_daily_report(db,owner,saved.report_date,refresh=True)['items'])==1
