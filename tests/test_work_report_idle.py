"""仅使用隔离内存数据库验证空闲时间声明与历史快照。"""
from datetime import date,datetime
from uuid import uuid4
from io import BytesIO
import pytest
from pydantic import ValidationError
from openpyxl import load_workbook
from test_chat_participant_access import environment
from task_schemas import ManualDailyReportSaveRequest


@pytest.mark.parametrize('minutes,confirmed',[(None,True),(-1,True),(1441,True),(1.5,True),('5',True),(True,True),(30,False),(30,1),(30,'true')])
def test_manual_report_requires_explicit_minutes_and_confirmation(minutes,confirmed):
    with pytest.raises(ValidationError):ManualDailyReportSaveRequest(idle_minutes=minutes,idle_declaration_confirmed=confirmed,items=[])


def test_idle_roundtrip_revision_export_and_mail(environment,monkeypatch):
    import task_service as service
    from task_models import DailyReport
    from work_report_idle import DECLARATION_TEXT
    from work_report_collaboration import ReportRevision
    from daily_report_mail_service import render_daily_report_mail
    db,(user,_,_)=environment
    monkeypatch.setattr(service,'derive_daily_report_items',lambda *_:[])
    stamp=datetime(2026,10,30,8)
    report=DailyReport(id=uuid4(),user_id=user.id,report_date=date(2026,10,30),status='draft',generated_at=stamp,created_at=stamp,updated_at=stamp)
    db.add(report);db.commit()
    original=ManualDailyReportSaveRequest(idle_minutes=0,idle_declaration_confirmed=True,items=[])
    report=service.save_daily_report(db,user,report.report_date,original,finalize=True)
    data=service.serialize_report(report)
    assert data['idle_minutes']==0 and data['idle_declaration_confirmed'] is True
    assert data['idle_declaration_text']==DECLARATION_TEXT
    assert data['idle_confirmed_at'].utcoffset().total_seconds()==8*3600
    assert service.preview_daily_report(db,user,report.report_date)['idle_minutes']==0
    report=service.save_daily_report(db,user,report.report_date,ManualDailyReportSaveRequest(idle_minutes=25,idle_declaration_confirmed=True,items=[]),finalize=True,amend=True)
    revision=db.query(ReportRevision).filter_by(report_id=report.id).one()
    assert revision.before_data['idle_minutes']==0 and revision.after_data['idle_minutes']==25
    sheet=load_workbook(BytesIO(service.report_to_xlsx(report))).active
    assert any('25分钟' in str(cell.value) for line in sheet for cell in line)
    assert any(cell.value==DECLARATION_TEXT for line in sheet for cell in line)
    html,text=render_daily_report_mail([],None,idle_data=service.serialize_report(report))
    assert '25分钟' in html and DECLARATION_TEXT in text and '不计入工作耗时合计' in text


def test_idle_migration_is_idempotent_and_does_not_backfill(environment):
    from sqlalchemy import inspect
    from task_models import DailyReportIdleDeclaration
    from tools.apply_work_report_idle_migration import apply_migration
    db,_=environment
    DailyReportIdleDeclaration.__table__.drop(db.connection())
    apply_migration(db.connection());apply_migration(db.connection())
    assert inspect(db.connection()).has_table('daily_report_idle_declaration')
    assert db.query(DailyReportIdleDeclaration).count()==0
