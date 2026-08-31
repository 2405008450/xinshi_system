from types import SimpleNamespace
from uuid import uuid4

import manuscript_service


def _user(user_id=None, name="项目助理甲"):
    return SimpleNamespace(
        id=user_id or uuid4(),
        full_name=name,
        username=name,
    )


def _assignment(user):
    return SimpleNamespace(
        assignee_id=user.id,
        assignee=user,
    )


def _workflow(stage_key, assignee=None):
    return SimpleNamespace(
        current_stage_key=stage_key,
        current_assignee_id=assignee.id if assignee else None,
        current_assignee=assignee,
    )


def test_fixed_project_assistant_can_manage_manuscript_at_any_stage():
    actor = _user()

    result = manuscript_service._project_assistant_responsibility_summary(
        actor,
        fixed_assignment=_assignment(actor),
        workflow=_workflow("project_manager"),
        actor_state=(True, None, False),
    )

    assert result["can_manage_manuscript"] is True
    assert result["project_assistant_assignment_type"] == "direct"
    assert result["project_assistant_id"] == actor.id


def test_any_project_assistant_can_manage_without_replacing_fixed_role():
    fixed_assistant = _user(name="固定项目助理")
    temporary_assistant = _user(name="临时项目助理")

    result = manuscript_service._project_assistant_responsibility_summary(
        temporary_assistant,
        fixed_assignment=_assignment(fixed_assistant),
        workflow=_workflow("project_manager"),
        actor_state=(True, None, False),
    )

    assert result["can_manage_manuscript"] is True
    assert result["project_assistant_id"] == fixed_assistant.id
    assert result["project_assistant_name"] == "固定项目助理"
    assert "可操作全部项目" in result["manuscript_access_reason"]


def test_claimed_project_assistant_role_pool_task_can_manage_by_role():
    actor = _user()

    result = manuscript_service._project_assistant_responsibility_summary(
        actor,
        fixed_assignment=None,
        workflow=_workflow("project_assistant", actor),
        actor_state=(True, None, False),
    )

    assert result["can_manage_manuscript"] is True
    assert result["project_assistant_assignment_type"] == "role_pool"
    assert "可操作全部项目" in result["manuscript_access_reason"]


def test_unclaimed_project_assistant_role_pool_task_does_not_block_management():
    actor = _user()

    result = manuscript_service._project_assistant_responsibility_summary(
        actor,
        fixed_assignment=None,
        workflow=_workflow("project_assistant"),
        actor_state=(True, None, False),
    )

    assert result["can_manage_manuscript"] is True
    assert "可操作全部项目" in result["manuscript_access_reason"]


def test_project_assistant_can_manage_at_an_unrelated_workflow_stage():
    actor = _user()

    result = manuscript_service._project_assistant_responsibility_summary(
        actor,
        fixed_assignment=None,
        workflow=_workflow("project_manager", actor),
        actor_state=(True, None, False),
    )

    assert result["can_manage_manuscript"] is True
    assert "可操作全部项目" in result["manuscript_access_reason"]


def test_missing_role_or_active_leave_blocks_manuscript_authority(monkeypatch):
    actor = _user()
    monkeypatch.setattr(
        manuscript_service,
        "get_user_roles_with_role_names",
        lambda db, user_id: ["项目经理"],
    )

    eligible, reason, is_super_admin = manuscript_service._project_assistant_actor_state(
        object(), actor
    )

    assert eligible is False
    assert is_super_admin is False
    assert "项目助理" in reason

    monkeypatch.setattr(
        manuscript_service,
        "get_user_roles_with_role_names",
        lambda db, user_id: ["项目助理"],
    )
    monkeypatch.setattr(
        manuscript_service,
        "get_active_leave",
        lambda db, user_id: SimpleNamespace(),
    )
    monkeypatch.setattr(
        manuscript_service,
        "assignment_disabled_reason",
        lambda leave: "当前处于请假状态",
    )

    eligible, reason, is_super_admin = manuscript_service._project_assistant_actor_state(
        object(), actor
    )

    assert eligible is False
    assert is_super_admin is False
    assert reason == "当前处于请假状态"


def test_super_admin_can_manage_manuscript_without_project_assistant_role(monkeypatch):
    actor = _user(name="超级管理员")
    monkeypatch.setattr(
        manuscript_service,
        "get_user_roles_with_role_names",
        lambda db, user_id: ["超级管理员"],
    )

    actor_state = manuscript_service._project_assistant_actor_state(object(), actor)
    result = manuscript_service._project_assistant_responsibility_summary(
        actor,
        fixed_assignment=None,
        workflow=_workflow("reception"),
        actor_state=actor_state,
    )

    assert result["can_manage_manuscript"] is True
    assert result["manuscript_access_reason"] == "超级管理员应急操作权限"


def test_suborder_uses_parent_project_fixed_assistant_and_own_workflow(monkeypatch):
    actor = _user()
    project = SimpleNamespace(id=uuid4())
    sub_order = SimpleNamespace(id=uuid4())
    calls = {}

    def get_assignment(db, project_id):
        calls["project_id"] = project_id
        return _assignment(actor)

    def get_workflow(db, project_id, sub_order_id):
        calls["workflow_ids"] = (project_id, sub_order_id)
        return _workflow("project_assistant", actor)

    monkeypatch.setattr(
        manuscript_service, "_get_project_assistant_assignment", get_assignment
    )
    monkeypatch.setattr(
        manuscript_service, "_get_entity_workflow", get_workflow
    )
    monkeypatch.setattr(
        manuscript_service,
        "_project_assistant_actor_state",
        lambda db, current_user: (True, None, False),
    )

    result = manuscript_service._resolve_manuscript_responsibility(
        object(), project, sub_order, actor
    )

    assert result["can_manage_manuscript"] is True
    assert calls["project_id"] == project.id
    assert calls["workflow_ids"] == (project.id, sub_order.id)
