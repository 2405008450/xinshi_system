"""译员安排保存与人选状态在同一项目事务中更新。"""
from difflib import SequenceMatcher
PIPELINE={'initial_follow_up','candidates_provided','candidates_added','candidates_adjusted','client_selected','client_changed','client_cancelled','client_added','client_reduced','client_mixed','client_contract_signed','interpreter_contract_signed','both_contracts_signed','client_interpreter_connected'}
ROSTER_STATUSES={'candidates_provided','candidates_added','candidates_adjusted'}


def roster(project):
    return [str(row.translator_id) for row in project.interpreter_assignments if row.translator_id]


def roster_change(previous,current):
    if set(previous)==set(current):return None
    if not previous:return '已登记译员'
    if not current:return '移除译员登记'
    replaced=added=removed=0
    for tag,a,b,c,d in SequenceMatcher(a=previous,b=current,autojunk=False).get_opcodes():
        if tag=='replace':
            paired=min(b-a,d-c);replaced+=paired;removed+=b-a-paired;added+=d-c-paired
        elif tag=='delete':removed+=b-a
        elif tag=='insert':added+=d-c
    if added and removed:return '译员增加+移除'
    if replaced and added:return '译员调整+增加'
    if removed:return '译员减少'
    if replaced:return '译员调整'
    return '增加译员'


def selected_ids(db,project):
    from interpretation_client_selection import attach
    attach(db,[project])
    return {row.translator_id for row in project.interpreter_assignments if getattr(row,'client_selected',False)}


def apply(db,project,previous_selected,previous_roster=()):
    if project.project_status not in PIPELINE:return
    current=roster(project);change=roster_change(previous_roster,current)
    chosen=selected_ids(db,project)
    if previous_selected and chosen!=previous_selected:
        project.project_status=('client_cancelled' if not chosen else 'client_added' if previous_selected<chosen else 'client_reduced' if chosen<previous_selected else 'client_mixed')
    elif chosen and chosen!=previous_selected and previous_roster:project.project_status='client_selected'
    elif change:
        project.project_status=('candidates_provided' if not previous_roster else
            'candidates_added' if set(previous_roster)<set(current) else 'candidates_adjusted')
    return change
