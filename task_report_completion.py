"""个人任务完成时原子追加报告，调用方负责提交事务。"""
from uuid import uuid4
from fastapi import HTTPException
from pydantic import ValidationError
from chat_time import now
from models import AppUser
from task_models import DailyReport,DailyReportItem
from task_schemas import DailyReportItemInput,DailyReportSaveRequest
from work_report_dates import report_business_date


def append_report_item(db,user,item,source,task_id):
    item=item.model_copy(deep=True)
    item.source_type,item.source_id='manual',task_id
    try:
        item=DailyReportItemInput.model_validate(item.model_dump())
        DailyReportSaveRequest(items=[item])
    except ValidationError:
        raise HTTPException(422,'请完整填写任务类型、项目、具体任务、工作量、单位和实际耗时；所有字段请使用文字或数字')
    from work_report_categories import validate_categories
    try:validate_categories(db,user,[item])
    except PermissionError as error:raise HTTPException(403,str(error))
    except ValueError as error:raise HTTPException(422,str(error))
    item.display_metadata={**(item.display_metadata or {}),'source':source,'_feedback_key':str(uuid4()),
                           'arrangement_id' if source=='project_arrangement' else 'personal_task_id':str(task_id)}
    db.query(AppUser.id).filter_by(id=user.id).with_for_update().first()
    day=report_business_date(now())
    report=db.query(DailyReport).filter_by(user_id=user.id,report_date=day).with_for_update().first()
    if report and report.status=='finalized':raise HTTPException(409,'当天工作报告已确认，请先撤回后再完成任务')
    stamp=now().replace(tzinfo=None)
    if not report:
        report=DailyReport(id=uuid4(),user_id=user.id,report_date=day,status='draft',generated_at=stamp,created_at=stamp,updated_at=stamp)
        db.add(report);db.flush()
    entry=DailyReportItem(id=uuid4(),report_id=report.id,sort_order=max((row.sort_order for row in report.items),default=-1)+1,created_at=stamp,**item.model_dump())
    report.items.append(entry);report.updated_at=stamp
    return entry
