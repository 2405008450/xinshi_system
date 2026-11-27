"""状态通知仅使用已保存的变更历史，不重发项目详情。"""
from uuid import UUID
from fastapi import HTTPException
from interpretation_models import InterpretationProjectStatusHistory


def content(db,project_id,event_id):
    try:event_id=UUID(str(event_id))
    except ValueError:raise HTTPException(422,'状态变更记录编号无效')
    event=db.query(InterpretationProjectStatusHistory).filter_by(id=event_id,project_id=project_id).first()
    if not event or event.from_status is None or event.from_status==event.to_status:
        raise HTTPException(422,'没有该项目的状态变更记录，请重新打开项目核对')
    from project_statistics import INTERPRETATION_STATUSES
    from automatic_project_notice import mark_automatic
    return mark_automatic('项目状态：'+INTERPRETATION_STATUSES.get(event.to_status,event.to_status)+'\n变更原因：'+(event.change_note or '未填写变更原因'))


def automatic_reason(project):
    names='、'.join(row.translator_name for row in project.interpreter_assignments if row.translator_name)
    chosen='、'.join(row.translator_name for row in project.interpreter_assignments if getattr(row,'client_selected',False) and row.translator_name)
    if project.project_status=='candidates_provided':return f'已登记译员：{names or "已登记人选"}（{project.assigned_interpreter_count}人）'
    if project.project_status=='client_selected':return '客户选定译员：'+(chosen or '已选定人选')
    if project.project_status=='client_changed':return '客户选定人选调整为：'+(chosen or '暂未选定，原选定已取消')
    return '更新译员安排'
