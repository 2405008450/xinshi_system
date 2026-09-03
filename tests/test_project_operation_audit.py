from types import SimpleNamespace
from uuid import uuid4

from models import AppUser, TranslationProject
from project_audit_models import ProjectOperationAudit
from project_audit_service import record_project_operation


class AuditDb:
    def __init__(self, actor):
        self.actor = actor
        self.added = []

    def get(self, model, key):
        return self.actor if model is AppUser and key == self.actor.id else None

    def add(self, value):
        self.added.append(value)


def test_project_audit_keeps_actor_and_project_snapshots():
    actor = SimpleNamespace(id=uuid4(), username="auditor", full_name="审计管理员")
    project = TranslationProject(
        id=uuid4(), order_no="TP-260903-015", project_name="待删除项目",
        project_status="confirmed",
    )
    db = AuditDb(actor)

    row = record_project_operation(
        db,
        project_type="translation",
        operation_type="delete",
        project=project,
        actor_user_id=actor.id,
        operation_source="project_delete",
    )

    assert db.added == [row]
    assert row.order_no == "TP-260903-015"
    assert row.actor_username_snapshot == "auditor"
    assert row.actor_name_snapshot == "审计管理员"
    assert row.project_snapshot["order_no"] == "TP-260903-015"
    assert row.project_snapshot["project_name"] == "待删除项目"


def test_project_audit_project_id_has_no_business_foreign_key():
    foreign_key_columns = {
        column.name
        for constraint in ProjectOperationAudit.__table__.foreign_key_constraints
        for column in constraint.columns
    }

    assert foreign_key_columns == {"actor_user_id"}
