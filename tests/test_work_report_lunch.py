"""午间加班声明、项目、时段、导出和考勤计回；仅隔离 SQLite。"""
from datetime import date
from uuid import uuid4
from io import BytesIO
import pytest
from pydantic import ValidationError
from openpyxl import load_workbook
from test_chat_participant_access import environment
from test_monthly_shift import setup
from test_attendance import at
from task_schemas import DailyReportItemInput,DailyReportSaveRequest
from task_models import DailyReport,DailyReportItem
from attendance_models import AttendanceClockSession
import attendance_service


def lunch(**extra):
    metadata={'report_types':['笔译项目'],'order_no':'TP-001','quantity':1,'quantity_unit':'页','lunch_overtime':True,'lunch_overtime_confirmed':True,'lunch_start':'12:00','lunch_end':'13:00',**extra}
    return DailyReportItemInput(source_type='manual',task_type='项目工作',task_name='午间测试项目',progress_content='校对文件',duration_minutes=60,display_metadata=metadata)


@pytest.mark.parametrize('metadata',[{'lunch_overtime_confirmed':False},{'lunch_start':'11:59'},{'lunch_end':'13:31'},{'lunch_start':'13:00'},{'lunch_start':'bad'},{'report_types':[]}])
def test_lunch_requires_declaration_types_and_real_window(metadata):
    with pytest.raises(ValidationError):lunch(**metadata)


def test_report_overlap_rejected():
    with pytest.raises(ValidationError):DailyReportSaveRequest(items=[lunch(),lunch()])


def test_finalized_lunch_credited_once_not_draft_and_export_marked(environment):
    import task_service,daily_report_mail_service
    from monthly_shift import SHIFTS
    db,(admin,person,other)=environment;setup(db,[admin,person,other])
    day=date(2026,10,28)
    clock=AttendanceClockSession(id=uuid4(),user_id=person.id,day=day,segment=0,check_in=at('2026-10-28T09:00'),check_out=at('2026-10-28T18:30'),shift_snapshot=SHIFTS[1],confirmations={'early_work_confirmed':True,'breakfast_after_eating':True});db.add(clock)
    report=DailyReport(id=uuid4(),user_id=person.id,report_date=day,status='draft');db.add(report);db.flush()
    value=lunch().model_dump();row=DailyReportItem(id=uuid4(),report_id=report.id,sort_order=0,**value);db.add(row);db.commit()
    assert attendance_service.attendance_report(db,person,day,'month')['totals']['overtime_minutes']==0
    report.status='finalized';db.commit()
    result=attendance_service.attendance_report(db,person,day,'month');record=result['records'][0]
    assert result['totals']['overtime_minutes']==60 and result['totals']['lunch_overtime_minutes']==60
    assert record['lunch_original_deducted_minutes']==90 and record['lunch_deducted_minutes']==30
    assert result['monthly_balances'][0]['overtime_minutes']==60
    assert attendance_service.attendance_report(db,person,day,'month')['totals']['overtime_minutes']==60
    assert attendance_service.attendance_report(db,other,day,'month')['records']==[]
    assert '中午加班' in daily_report_mail_service._report_rows(report)[0]['task_type']
    book=load_workbook(BytesIO(task_service.report_to_xlsx(report)));assert '中午加班' in book.active['B5'].value
    # 下午上班时间仍固定13:30，不因午间工作顺延。
    assert clock.shift_snapshot['periods'][1].startswith('13:30')
