"""移除安排的权限、并发版本、下级订单及审计/报告保留；仅隔离数据库。"""
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_project_arrangement import create, completion
from tests.test_arrangement_order_targets import orders, batch
import project_arrangement as service
import project_arrangement_history as history
import project_arrangement_targets as targets


def test_remove_permission_and_stale_version(environment):
    db, (owner, member, outsider) = environment
    project, task = create(db, owner, member)
    for actor, version, can_assign, status in [(member, 1, False, 403), (outsider, 1, False, 403), (owner, 2, True, 409)]:
        with pytest.raises(HTTPException) as error:
            service.remove_task(db, actor, task['id'], service.TaskRemove(revision=version), can_assign)
        assert error.value.status_code == status
        db.rollback()
    result = service.remove_task(db, owner, task['id'], service.TaskRemove(revision=1), True)
    assert result['tasks'] == []
    assert result['history'][0]['operation'] == 'remove'
    assert result['history'][0]['before_snapshot']['tasks'][0]['content'] == task['content']
    assert result['history'][0]['after_snapshot']['tasks'] == []
    assert db.get(history.ArrangementPlan, project.id).ordered_task_ids == []
    with pytest.raises(HTTPException) as missing:
        service.remove_task(db, owner, task['id'], service.TaskRemove(revision=1), True)
    assert missing.value.status_code == 404


def test_remove_one_child_assignment_keeps_other_and_snapshots(environment):
    db, (owner, member, _) = environment
    root, child, third, _ = orders(db, owner)
    tasks = service.create_assignments(db, owner, root.id, batch(member, [child.id, third.id]))
    removed, retained = tasks
    result = service.remove_task(db, owner, removed['id'], service.TaskRemove(revision=1), True)
    assert [row['id'] for row in result['tasks']] == [retained['id']]
    assert service.serialize(db, db.get(service.ProjectArrangement, retained['id']))['execution_step'] == 1
    assert db.get(targets.ArrangementOrderTarget, removed['id']) is None
    assert db.get(targets.ArrangementOrderTarget, retained['id']) is not None
    assert result['history'][0]['before_snapshot']['tasks'][0]['order_no'] == child.sub_order_no


def test_remove_completed_keeps_report(environment):
    db, (owner, member, _) = environment
    project, task = create(db, owner, member)
    completed = service.complete_task(db, member, task['id'], completion())
    report = db.query(service.DailyReportItem).one()
    result = service.remove_task(db, owner, task['id'], service.TaskRemove(revision=completed['revision']), True)
    assert not result['tasks']
    assert db.query(service.DailyReportItem).one().id == report.id
    assert report.display_metadata['arrangement_id'] == str(task['id'])
    assert result['history'][0]['before_snapshot']['tasks'][0]['status'] == 'completed'
