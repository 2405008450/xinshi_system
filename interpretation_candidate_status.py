"""译员安排保存与人选状态在同一项目事务中更新。"""
PIPELINE={'initial_follow_up','candidates_provided','client_selected','client_changed'}


def selected_ids(db,project):
    from interpretation_client_selection import attach
    attach(db,[project])
    return {row.translator_id for row in project.interpreter_assignments if getattr(row,'client_selected',False)}


def apply(db,project,previous_selected):
    if project.project_status not in PIPELINE:return
    chosen=selected_ids(db,project)
    if previous_selected and chosen!=previous_selected:
        project.project_status='client_changed'
    elif project.project_status=='client_changed' and chosen==previous_selected:
        return
    elif chosen:project.project_status='client_selected'
    elif project.interpreter_assignments:project.project_status='candidates_provided'
    else:project.project_status='initial_follow_up'
