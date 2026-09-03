import datetime
from types import SimpleNamespace
from uuid import uuid4

import workflow_crud
from task_schemas import WorkItemResponse


def _arrangement(project_id, *, sub_order_id=None, translator_id=None, name='测试译员',
                 return_time=None, remarks=None, status='sent'):
    return SimpleNamespace(
        id=uuid4(),
        dispatch_id=uuid4(),
        translation_project_id=project_id,
        sub_order_id=sub_order_id,
        translator_id=translator_id or uuid4(),
        translator_name_snapshot=name,
        cooperation_type_snapshot='兼职',
        status=status,
        translation_scope=None,
        planned_delivery_at=return_time,
        completion_remarks=remarks,
    )


def test_project_assistant_execution_uses_child_status_and_deadline():
    now = datetime.datetime(2026, 9, 3, 11, 0)
    project_id = uuid4()
    overdue_sub_id = uuid4()
    returned_sub_id = uuid4()
    confirmed_sub_id = uuid4()
    missing_time_sub_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        order_no='TP-260903-001',
        project_status='translator_returned',
    )
    sub_orders = [
        SimpleNamespace(id=overdue_sub_id, parent_project_id=project_id, sub_order_no='TP-260903-001.001', sub_project_name='待回稿', status='sent_to_translator'),
        SimpleNamespace(id=returned_sub_id, parent_project_id=project_id, sub_order_no='TP-260903-001.002', sub_project_name='已回稿', status='translator_returned'),
        SimpleNamespace(id=confirmed_sub_id, parent_project_id=project_id, sub_order_no='TP-260903-001.003', sub_project_name='已确认', status='confirmed'),
        SimpleNamespace(id=missing_time_sub_id, parent_project_id=project_id, sub_order_no='TP-260903-001.004', sub_project_name='缺少时间', status='sent_to_translator'),
    ]
    arrangements = [
        _arrangement(project_id, sub_order_id=overdue_sub_id, name='成鹤', return_time=datetime.datetime(2026, 9, 2, 19, 0)),
        _arrangement(project_id, sub_order_id=overdue_sub_id, name='译员乙', return_time=datetime.datetime(2026, 9, 3, 18, 0)),
        _arrangement(project_id, sub_order_id=returned_sub_id, name='译员丙', return_time=datetime.datetime(2026, 9, 3, 10, 0), remarks='术语已统一'),
        _arrangement(project_id, sub_order_id=confirmed_sub_id, status='cancelled'),
    ]
    task = {
        'project_type': 'translation',
        'translation_project_id': project_id,
        'entity_type': 'project',
        'current_stage_role_code': 'project_assistant',
    }

    workflow_crud._apply_translator_execution(
        [task], [project], sub_orders, arrangements, now=now
    )

    execution = task['translator_execution']
    assert execution['attention_count'] == 2
    assert execution['overdue_count'] == 1
    assert execution['next_return_time'] == datetime.datetime(2026, 9, 2, 19, 0)
    by_id = {item['entity_id']: item for item in execution['items']}
    assert by_id[overdue_sub_id]['needs_attention'] is True
    assert by_id[returned_sub_id]['needs_attention'] is False
    assert by_id[confirmed_sub_id]['needs_attention'] is False
    assert by_id[returned_sub_id]['assigned_translators'][0]['completion_remarks'] == '术语已统一'
    assert by_id[confirmed_sub_id]['assigned_translators'] == []


def test_suborder_work_item_only_receives_its_own_execution_details():
    project_id = uuid4()
    target_sub_id = uuid4()
    other_sub_id = uuid4()
    project = SimpleNamespace(id=project_id, order_no='TP-002', project_status='confirmed')
    target = SimpleNamespace(id=target_sub_id, parent_project_id=project_id, sub_order_no='TP-002.001', sub_project_name='目标', status='sent_to_translator')
    other = SimpleNamespace(id=other_sub_id, parent_project_id=project_id, sub_order_no='TP-002.002', sub_project_name='其他', status='sent_to_translator')
    task = {
        'project_type': 'translation',
        'translation_project_id': project_id,
        'sub_order_id': target_sub_id,
        'entity_type': 'suborder',
        'current_stage_role_code': 'project_assistant',
    }

    workflow_crud._apply_translator_execution(
        [task],
        [project],
        [target, other],
        [_arrangement(project_id, sub_order_id=target_sub_id), _arrangement(project_id, sub_order_id=other_sub_id)],
        now=datetime.datetime(2026, 9, 3, 11, 0),
    )

    assert [item['entity_id'] for item in task['translator_execution']['items']] == [target_sub_id]
    assert task['translator_execution']['attention_count'] == 1


def test_non_translation_task_is_not_enriched():
    task = {'project_type': 'interpretation', 'project_id': uuid4()}
    workflow_crud._apply_translator_execution([task], [], [], [])
    assert 'translator_execution' not in task


def test_translation_task_without_arrangement_or_attention_is_not_enriched():
    project_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        order_no='TP-EMPTY',
        project_status='confirmed',
    )
    task = {
        'project_type': 'translation',
        'translation_project_id': project_id,
        'entity_type': 'project',
        'current_stage_role_code': 'project_manager',
    }

    workflow_crud._apply_translator_execution([task], [project], [], [])

    assert 'translator_execution' not in task


def test_work_item_schema_accepts_translator_execution_payload():
    project_id = uuid4()
    payload = WorkItemResponse.model_validate({
        'source_type': 'project',
        'source_id': uuid4(),
        'task_type': '稿件安排',
        'task_name': '示例项目',
        'status': 'translator_returned',
        'translator_execution': {
            'attention_count': 1,
            'overdue_count': 1,
            'next_return_time': '2026-09-02T19:00:00',
            'items': [{
                'entity_type': 'suborder',
                'entity_id': project_id,
                'order_no': 'TP-003.001',
                'status': 'sent_to_translator',
                'needs_attention': True,
                'assigned_translators': [],
            }],
        },
    })
    assert payload.translator_execution.attention_count == 1
    assert payload.translator_execution.items[0].needs_attention is True
