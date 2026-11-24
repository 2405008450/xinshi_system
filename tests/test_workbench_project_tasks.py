"""统一任务列表的跨来源分页、筛选、去重与权限回归，仅隔离 SQLite。"""
from datetime import date
from uuid import uuid4

from annotation_models import AnnotationProject
from models import TranslationProject
from personal_daily_task import PersonalDailyTask
from project_arrangement import ProjectArrangement
from test_chat_participant_access import environment
from workbench_project_tasks import search
from workflow_models import ProjectWorkbenchResponsibility


def test_unified_sources_filter_paging_and_deduplication(environment):
    db, (owner, member, outsider) = environment
    day = date(2026, 11, 24)
    translation = TranslationProject(id=uuid4(), order_no='TP-001', project_name='笔译任务',
                                     project_manager_id=owner.id, project_status='confirmed')
    annotation = AnnotationProject(id=uuid4(), order_no='AP-001', project_name='标注任务',
                                   project_status='trial_in_progress', task_description='客户样本')
    hidden = TranslationProject(id=uuid4(), order_no='TP-SECRET', project_manager_id=outsider.id)
    db.add_all([translation, annotation, hidden])
    db.flush()
    db.add(ProjectWorkbenchResponsibility(id=uuid4(), annotation_project_id=annotation.id,
                                           role_code='project_manager', assignee_id=owner.id))
    for index in range(2):
        db.add(ProjectArrangement(id=uuid4(), project_id=translation.id, assignee_id=owner.id,
                                   assigned_by=member.id, work_date=day, content=f'安排任务{index}'))
    db.add(PersonalDailyTask(user_id=owner.id, work_date=day, status='pending', report_row={
        'task_name': '自填任务', 'progress_content': '保留自主任务',
        'display_metadata': {'selected_project_type': '标注项目', 'project_id': str(annotation.id), 'order_no': annotation.order_no},
    }))
    db.commit()
    result = search(db, owner, day, page_size=2)
    assert result['total'] == 3
    assert len(result['items']) == 2
    assert {row['value'] for row in result['project_types']} == {'translation', 'annotation'}
    second = search(db, owner, day, page=2, page_size=2)
    assert len(second['items']) == 1
    assert len({row['row_key'] for row in result['items'] + second['items']}) == 3
    assert search(db, outsider, day)['total'] == 1
    assert search(db, member, day)['total'] == 0
    assert search(db, owner, day, filters={'project_type': ['annotation']})['total'] == 1
    assert search(db, owner, day, statuses={'annotation': ['paused']})['total'] == 2
    assert search(db, owner, day, filters={'project_type': ['annotation']},
                  statuses={'annotation': ['paused']})['total'] == 0
    assert search(db, owner, day, keyword='自主 保留')['total'] == 1
    assert search(db, owner, day, filters={'content': '任务1'})['total'] == 1
    historical = search(db, owner, day, date_from=date(2026, 11, 23), date_to=date(2026, 11, 23))
    assert historical['total'] == 2
    assert all(row['source'] == 'project' for row in historical['items'])


def test_suborder_fields_remain_searchable_and_operations_stay_separate(environment):
    from models import TranslationSubOrder
    from project_arrangement_targets import ArrangementOrderTarget
    from project_arrangement_instruction import ArrangementInstruction

    db, (owner, member, _) = environment
    day = date(2026, 11, 24)
    project = TranslationProject(id=uuid4(), order_no='TP-ROOT', project_name='主项目',
                                 customer_requirement_professional='医学专业',
                                 customer_requirement_special='保留格式')
    db.add(project)
    db.flush()
    child = TranslationSubOrder(id=uuid4(), parent_project_id=project.id,
                                sub_order_no='TP-ROOT.001', sub_project_name='子稿件')
    db.add(child)
    task = ProjectArrangement(id=uuid4(), project_id=project.id, assignee_id=owner.id,
                              assigned_by=member.id, content='核对医学文稿', work_date=day)
    db.add(task)
    db.flush()
    db.add(ArrangementOrderTarget(arrangement_id=task.id, sub_order_id=child.id,
                                 order_no=child.sub_order_no, project_name=child.sub_project_name, order_level=2))
    db.add(ArrangementInstruction(project_id=project.id, content='统一术语', updated_by=member.id))
    db.add(PersonalDailyTask(user_id=owner.id, work_date=day, report_row={
        'task_name': '状态汇报操作', 'progress_content': '隐藏任务区包装记录',
        'display_metadata': {'operation_source': 'annotation_daily_operation'},
    }))
    db.commit()
    result = search(db, owner, day, keyword='子稿件 .001', filters={'common_instruction': '术语'})
    assert result['total'] == 1
    row = result['items'][0]
    assert row['order_no'] == child.sub_order_no and row['project_name'] == child.sub_project_name
    assert row['common_instruction'] == '统一术语'
    assert row['customer_requirement_professional'] == '医学专业'
    assert search(db, owner, day, filters={'customer_requirements': '医学 格式'})['total'] == 1
    assert search(db, owner, day, filters={'execution_sequence': 'owner 医学'})['total'] == 1
    assert search(db, owner, day)['total'] == 1
