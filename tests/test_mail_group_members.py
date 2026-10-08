from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
import annotation_ops_models  # 注册 ORM 关系依赖，确保独立执行时模型完整。
import workflow_models
import resource_development_models
import manuscript_models
from sqlalchemy import Column, JSON, MetaData, Table, create_engine
from sqlalchemy.orm import Session

import business_mail_service as project_mail
import crud
import daily_report_mail_service as daily_mail
import mail_group_members
from business_mail_schemas import MailRecipientGroupResponse, MailRecipientGroupWrite
from business_mail_models import MailRecipientGroup, MailRecipientGroupMember
from mail_group_members import available_group_members
from models import AppUser
from schemas import AppUserUpdate


def user(active=True, email="member@example.com"):
    return SimpleNamespace(id=uuid4(), is_active=active, email=email,
                           full_name="成员", username="member", department=None)


def group(users):
    return SimpleNamespace(id=uuid4(), name="测试组", description=None, is_active=True,
                           members=[SimpleNamespace(user_id=item.id, user=item) for item in users],
                           created_at=datetime.now(), updated_at=datetime.now())


def test_legacy_members_are_filtered_and_empty_group_response_is_valid():
    valid = user()
    row = group([valid, user(False), user(email=None), user(email="invalid")])
    result = project_mail.serialize_group(row)
    assert result["user_ids"] == [valid.id]
    assert [item["user_id"] for item in result["members"]] == [valid.id]
    MailRecipientGroupResponse(**result)
    row.members = row.members[1:]
    assert available_group_members(row) == []
    MailRecipientGroupResponse(**project_mail.serialize_group(row))
    assert MailRecipientGroupWrite(name="空组", user_ids=[]).user_ids == []


class Query:
    def __init__(self, rows):
        self.rows = rows

    def options(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def all(self):
        return self.rows


@pytest.mark.parametrize("change", [{"is_active": False}, {"email": None}])
def test_user_update_removes_memberships_before_commit(monkeypatch, change):
    monkeypatch.setattr(mail_group_members, "joinedload", lambda *_args: None)
    target = user()
    rows = [group([target]), group([target])]
    memberships = [row.members[0] for row in rows]
    for row, member in zip(rows, memberships):
        member.group = row
    calls = []

    def commit():
        assert all(row.members == [] for row in rows)
        calls.append("commit")

    db = SimpleNamespace(query=lambda *_args: Query(memberships), commit=commit,
                         refresh=lambda *_args: None)
    monkeypatch.setattr(crud, "get_user", lambda *_args: target)
    assert crud.update_user(db, target.id, AppUserUpdate(**change)) is target
    assert calls == ["commit"]


def test_email_reassignment_does_not_transfer_group_membership(monkeypatch):
    target = user()
    db = SimpleNamespace(query=lambda *_args: pytest.fail("有效用户不应清理关联"),
                         commit=lambda: None, refresh=lambda *_args: None)
    monkeypatch.setattr(crud, "get_user", lambda *_args: target)
    crud.update_user(db, target.id, AppUserUpdate(email="new@example.com"))
    assert target.email == "new@example.com"


def test_project_and_daily_report_skip_legacy_invalid_members(monkeypatch):
    valid = user()
    row = group([valid, user(False), user(email=None)])
    policy = SimpleNamespace(groups=[SimpleNamespace(group=row, recipient_type="to")])
    monkeypatch.setattr(project_mail, "_policy", lambda *_args: policy)
    monkeypatch.setattr(daily_mail, "_policy", lambda *_args: policy)
    db = SimpleNamespace(query=lambda *_args: Query([valid]))
    assert project_mail.policy_recipients(db, "translation") == ([valid], [])
    assert daily_mail._policy_recipients(db, uuid4()) == ([valid], [])
    row.members = row.members[1:]
    with pytest.raises(ValueError, match="没有可用用户"):
        project_mail.policy_recipients(db, "translation")
    with pytest.raises(ValueError, match="没有可用收件人"):
        daily_mail._policy_recipients(db, uuid4())


def test_explicit_invalid_recipient_still_rejected():
    inactive = user(False)
    db = SimpleNamespace(query=lambda *_args: Query([inactive]))
    with pytest.raises(ValueError, match="已停用"):
        project_mail.validate_internal_users(db, [inactive.id])


@pytest.mark.parametrize("change", [{"is_active": False}, {"email": None}])
def test_membership_deletion_is_persisted_and_not_restored_on_reactivation(change):
    # 隔离 SQLite 仅建立相关三张表，JSONB 用 JSON 替代，不连接业务数据库。
    engine = create_engine("sqlite://")
    Table("app_user", MetaData(), *[
        Column(column.name, JSON if column.name == "fixed_tasks" else column.type,
               primary_key=column.primary_key, nullable=column.nullable)
        for column in AppUser.__table__.columns
    ]).create(engine)
    MailRecipientGroup.__table__.create(engine)
    MailRecipientGroupMember.__table__.create(engine)
    with Session(engine) as db:
        old = AppUser(id=uuid4(), username="old", password_hash="test", email="reused@example.com", is_active=True)
        new = AppUser(id=uuid4(), username="new", password_hash="test", email=None, is_active=True)
        db.add_all([old, new])
        rows = [MailRecipientGroup(id=uuid4(), name=f"组{index}", is_active=True,
                                  members=[MailRecipientGroupMember(id=uuid4(), user_id=old.id)])
                for index in range(2)]
        db.add_all(rows)
        db.commit()
        assert db.query(MailRecipientGroupMember).count() == 2
        crud.update_user(db, old.id, AppUserUpdate(**change))
        assert db.query(MailRecipientGroupMember).count() == 0
        crud.update_user(db, old.id, AppUserUpdate(email=None))
        crud.update_user(db, new.id, AppUserUpdate(email="reused@example.com"))
        crud.update_user(db, old.id, AppUserUpdate(is_active=True, email="old-new@example.com"))
        db.expire_all()
        assert db.query(MailRecipientGroupMember).count() == 0
        assert all(row.members == [] for row in rows)
    engine.dispose()
