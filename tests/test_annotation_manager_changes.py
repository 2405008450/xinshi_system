"""经理变更的权限、事务及审计验收，只连接显式创建的本机隔离库。"""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from test_annotation_customer_progress import environment, api_client
from annotation_manager_change_models import AnnotationManagerChangeLog
from annotation_models import AnnotationProjectLanguageItem
from annotation_service import create_annotation_project, get_annotation_project, update_annotation_project
from annotation_schemas import AnnotationProjectCreate, AnnotationProjectUpdate, AnnotationProjectDetailResponse
from models import RolePermission, UserRole, Role


def reader_client(db, user):
    role_ids = db.query(UserRole.role_id).filter(UserRole.user_id == user.id)
    db.execute(delete(RolePermission).where(RolePermission.role_id.in_(role_ids), RolePermission.permission_code != 'projects:read'))
    db.commit()
    return api_client(db, user)


def patch(client, project_id, **values):
    detail = client.get(f'/projects/annotation/{project_id}').json()
    return client.patch(f'/projects/annotation/{project_id}/managers', json={'expected_updated_at': detail['updated_at'], **values})


def project_managers(detail):
    return {item['assignee_id'] for item in detail['role_assignments'] if item['role_code'] == 'project_manager' and item['assignee_id']}


def test_reader_can_assign_any_enabled_user_and_cannot_edit_other_fields(environment, monkeypatch):
    db, users, project, _child, _ = environment
    users[2].is_active = False
    client = reader_client(db, users[0])
    def leave_guard(*_args):
        raise AssertionError('标注经理分配不应调用请假限制')
    monkeypatch.setattr('leave_service.ensure_user_assignable', leave_guard)
    options = client.get('/projects/annotation/manager-options')
    assert options.status_code == 200, options.text
    assert {row['id'] for row in options.json()} == {str(user.id) for user in users[:2]}
    # 这些用户没有项目经理或客户专员角色，仍可分配为任一项目职责。
    result = patch(client, project.id, project_manager_ids=[str(users[1].id)])
    assert result.status_code == 200, result.text
    assert project_managers(result.json()) == {str(users[1].id)}
    result = patch(client, project.id, client_manager_id=str(users[0].id))
    assert result.status_code == 200, result.text
    assert project_managers(result.json()) == {str(users[1].id)}, '部分更新不能清空另一类经理'
    denied = patch(client, project.id, project_manager_ids=[str(users[2].id)], reason='分配停用账号')
    assert denied.status_code == 422
    assert client.patch(f'/projects/annotation/{project.id}/priority', json={'priority':'high'}).status_code == 403
    assert client.get('/workflow/project-manager-handover/direct/options').status_code == 403
    assert client.get('/projects/annotation/manager-change-logs').status_code == 200
    assert db.query(AnnotationManagerChangeLog).count() == 2


def test_reason_initial_assignment_clear_reassign_noop_and_stale_version(environment):
    db, users, project, _child, _ = environment
    client = reader_client(db, users[0])
    path = f'/projects/annotation/{project.id}/managers'
    assert client.patch(path, json={'project_manager_ids':[]}).status_code == 422
    first = patch(client, project.id, project_manager_ids=[str(users[1].id), str(users[2].id)])
    assert first.status_code == 200, first.text
    version = first.json()['updated_at']
    assert first.json()['manager_assignment_history']['project_manager'] is True
    same = patch(client, project.id, project_manager_ids=[str(users[2].id), str(users[1].id)])
    assert same.status_code == 200 and same.json()['updated_at'] == version
    assert db.query(AnnotationManagerChangeLog).count() == 2
    for reason in [None, '', '   ']:
        denied = patch(client, project.id, project_manager_ids=[], reason=reason)
        assert denied.status_code == 422 and '原因' in denied.text
    clear = patch(client, project.id, project_manager_ids=[], reason='调整分工')
    assert clear.status_code == 200, clear.text
    assert clear.json()['manager_assignment_history']['project_manager'] is True
    assert patch(client, project.id, project_manager_ids=[str(users[1].id)]).status_code == 422
    stale = client.patch(path, json={'expected_updated_at':version,'project_manager_ids':[str(users[1].id)],'reason':'使用旧版本'})
    assert stale.status_code == 409, stale.text
    assert patch(client, project.id, project_manager_ids=[str(users[1].id)], reason='重新安排').status_code == 200
    logs = client.get('/projects/annotation/manager-change-logs').json()['items']
    assert len(logs) == 5
    assert all(row['actor_user_id'] == str(users[0].id) and row['actor_name_snapshot'] == users[0].full_name for row in logs)
    assert all(row['changed_at'].endswith('+08:00') for row in logs)
    assert sum(row['reason'] == '首次分配' for row in logs) == 2
    # 带 Z 和 +08:00 的等价范围查询应返回同样记录。
    from datetime import datetime, timezone
    moment = datetime.fromisoformat(logs[0]['changed_at']) + timedelta(seconds=1)
    hk = client.get('/projects/annotation/manager-change-logs', params={'changed_to':moment.isoformat()}).json()
    utc = client.get('/projects/annotation/manager-change-logs', params={'changed_to':moment.astimezone(timezone.utc).isoformat()}).json()
    assert hk == utc


def test_project_creation_logs_initial_and_editor_cannot_bypass_reason(environment):
    db, users, _project, _child, _ = environment
    created = create_annotation_project(db, AnnotationProjectCreate(
        project_name='新建负责人留痕', client_manager_id=users[1].id,
        role_assignments=[{'role_code':'project_manager','assignee_id':users[2].id}],
    ), users[0].id)
    assert db.query(AnnotationManagerChangeLog).filter_by(project_id=created.id).count() == 2
    detail = AnnotationProjectDetailResponse.model_validate(created).model_dump()
    payload = AnnotationProjectUpdate.model_validate({**detail, 'client_manager_id':users[2].id, 'expected_updated_at':created.updated_at})
    with pytest.raises(ValueError, match='调整原因'):
        update_annotation_project(db, created.id, payload, users[0].id)
    db.rollback()
    payload.manager_change_reason = '客户对接分工调整'
    updated = update_annotation_project(db, created.id, payload, users[0].id)
    assert updated.client_manager_id == users[2].id
    assert db.query(AnnotationManagerChangeLog).filter_by(project_id=created.id, reason='客户对接分工调整').count() == 1


def inherited_project(db, users, parent, child):
    from interpretation_models import InterpretationLanguage
    from models import Client
    from annotation_progress_time import business_now
    language = InterpretationLanguage(label='经理继承测试'+uuid4().hex[:8])
    customer = Client(client_code='QA-'+uuid4().hex[:12], client_name='经理变更测试客户', client_short_name='经理测试客户')
    db.add_all([language, customer]); db.flush()
    parent.client_id = customer.id
    parent.task_description = '标注任务验收'
    parent.task_dispatched_at = business_now().replace(tzinfo=None)
    for project in (parent, child):
        db.add(AnnotationProjectLanguageItem(project_id=project.id, source_language_id=language.id, sequence_no=1))
    child.inheritance_overrides = ['*', 'inherit:client_manager_id', 'inherit:role_assignments']
    db.commit(); db.expire_all()


def test_inherited_changes_keep_actor_reason_and_rollback_on_failed_sync(environment, monkeypatch):
    db, users, parent, child, _ = environment
    inherited_project(db, users, parent, child)
    client = reader_client(db, users[0])
    first = patch(client, parent.id, project_manager_ids=[str(users[1].id)])
    assert first.status_code == 200, first.text
    assert project_managers(client.get(f'/projects/annotation/{child.id}').json()) == {str(users[1].id)}
    changed = patch(client, parent.id, project_manager_ids=[str(users[2].id)], reason='项目分工调整')
    assert changed.status_code == 200, changed.text
    child_logs = db.query(AnnotationManagerChangeLog).filter_by(project_id=child.id).all()
    assert len(child_logs) == 3 and all(row.actor_user_id == users[0].id for row in child_logs)
    assert sum('项目分工调整' in row.reason and parent.order_no in row.reason for row in child_logs) == 2
    count = db.query(AnnotationManagerChangeLog).count()
    def fail(*_args, **_kwargs):
        raise ValueError('模拟下级同步失败')
    monkeypatch.setattr('annotation_inheritance_service.propagate', fail)
    assert patch(client, parent.id, project_manager_ids=[], reason='回滚测试').status_code == 422
    assert db.query(AnnotationManagerChangeLog).count() == count
    assert project_managers(client.get(f'/projects/annotation/{parent.id}').json()) == {str(users[2].id)}


def test_admin_bulk_transfer_accepts_non_role_user_and_merges_existing_manager(environment, monkeypatch):
    from workflow_crud import direct_transfer_annotation_manager, direct_transfer_annotation_client_manager
    db, users, parent, child, _ = environment
    client = api_client(db, users[0])
    assert patch(client, parent.id, project_manager_ids=[str(users[1].id), str(users[2].id)], client_manager_id=str(users[1].id)).status_code == 200
    admin_role = Role(role_name='超级管理员')
    db.add(admin_role); db.flush(); db.add(UserRole(user_id=users[0].id,role_id=admin_role.id)); db.commit()
    monkeypatch.setattr('workflow_crud._push_notifications', lambda *_: None)
    request = direct_transfer_annotation_manager(db, users[0], users[1].id, users[2].id, [parent.id], '批量重新分工')
    assert request.status == 'accepted' and len(request.items) == 1
    assert project_managers(AnnotationProjectDetailResponse.model_validate(get_annotation_project(db,parent.id)).model_dump(mode='json')) == {str(users[2].id)}
    direct_transfer_annotation_client_manager(db, users[0], users[1].id, users[2].id, [parent.id], '客户对接人调整')
    assert get_annotation_project(db,parent.id).client_manager_id == users[2].id


def test_bulk_transfer_of_parent_and_child_does_not_invalidate_selected_rows(environment, monkeypatch):
    from workflow_crud import direct_transfer_annotation_manager
    db, users, parent, child, _ = environment
    inherited_project(db, users, parent, child)
    client = api_client(db, users[0])
    assigned = patch(client, parent.id, project_manager_ids=[str(users[1].id)])
    assert assigned.status_code == 200, assigned.text
    admin_role = Role(role_name='超级管理员')
    db.add(admin_role); db.flush(); db.add(UserRole(user_id=users[0].id,role_id=admin_role.id)); db.commit()
    monkeypatch.setattr('workflow_crud._push_notifications', lambda *_: None)
    request = direct_transfer_annotation_manager(db,users[0],users[1].id,users[2].id,[parent.id,child.id],'上下级统一交接')
    assert len(request.items) == 2
    for project_id in [parent.id,child.id]:
        detail = AnnotationProjectDetailResponse.model_validate(get_annotation_project(db,project_id)).model_dump(mode='json')
        assert project_managers(detail) == {str(users[2].id)}
    assert db.query(AnnotationManagerChangeLog).filter_by(source_request_id=request.id).count() == 2
