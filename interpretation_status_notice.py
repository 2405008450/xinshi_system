"""状态通知仅使用已保存的变更历史，不重发项目详情。"""
from uuid import UUID
import re
from fastapi import HTTPException
from interpretation_models import InterpretationProjectStatusHistory


def content(db,project_id,event_id):
    try:event_id=UUID(str(event_id))
    except ValueError:raise HTTPException(422,'状态变更记录编号无效')
    event=db.query(InterpretationProjectStatusHistory).filter_by(id=event_id,project_id=project_id).first()
    if not event or event.from_status is None:
        raise HTTPException(422,'没有该项目的状态变更记录，请重新打开项目核对')
    from project_statistics import INTERPRETATION_STATUSES
    from automatic_project_notice import mark_automatic
    label=INTERPRETATION_STATUSES.get(event.to_status,event.to_status)
    if event.to_status in {'candidates_provided','candidates_added','candidates_adjusted'}:
        count=re.findall(r'（(?:当前登记)?(\d+)人）',event.change_note or '')
        if count:label+=f'（{count[-1]}人）'
    return mark_automatic('项目状态：'+label+'\n变更原因：'+(event.change_note or '未填写变更原因'))


def automatic_reason(project,roster_change=None,previous_roster_names=None,previous_selected_names=None):
    names='、'.join(row.translator_name for row in project.interpreter_assignments if row.translator_name)
    chosen='、'.join(row.translator_name for row in project.interpreter_assignments if getattr(row,'client_selected',False) and row.translator_name)
    suffix=f'（当前登记{project.assigned_interpreter_count}人）' if project.project_status in {'candidates_provided','candidates_added','candidates_adjusted'} else ''
    current_selected_names=[row.translator_name for row in project.interpreter_assignments if getattr(row,'client_selected',False)]
    if previous_selected_names and sorted(previous_selected_names)!=sorted(current_selected_names):
        added=[name for name in current_selected_names if name not in previous_selected_names]
        removed=[name for name in previous_selected_names if name not in current_selected_names]
        if not current_selected_names:return '客户取消人选：'+'、'.join(previous_selected_names)
        if added and removed:return '客户增减人选：增加：'+'、'.join(added)+'；减少：'+'、'.join(removed)
        if added:return '客户增加人选：'+'、'.join(added)
        return '客户减少人数：'+'、'.join(removed)
    if previous_selected_names==[] and chosen:return '客户选定译员：'+chosen+suffix
    if roster_change in {'译员调整','译员调整+增加'} and previous_roster_names:
        return '客户调整译员：'+'、'.join(previous_roster_names)+' 调整为 '+(names or '无')+suffix
    if roster_change:return f'{roster_change}：{names or "无"}（{project.assigned_interpreter_count}人）'
    if project.project_status=='candidates_provided':return f'已登记译员：{names or "已登记人选"}（{project.assigned_interpreter_count}人）'
    if project.project_status=='client_selected':return '客户选定译员：'+(chosen or '已选定人选')
    if project.project_status=='client_changed':return '客户调整译员：'+('、'.join(previous_selected_names or []) or '原选定译员')+' 调整为 '+(chosen or '未选定')
    return '在项目编辑窗口调整状态'
