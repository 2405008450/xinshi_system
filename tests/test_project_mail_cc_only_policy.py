from types import SimpleNamespace
from uuid import uuid4

import pytest

import business_mail_service
from business_mail_models import MailRecipientGroup, ProjectMailPolicy


class _PolicyQuery:
    def __init__(self, model, groups, policy):
        self.model = model
        self.groups = groups
        self.policy = policy

    def options(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def all(self):
        return self.groups if self.model is MailRecipientGroup else []

    def first(self):
        return self.policy if self.model is ProjectMailPolicy else None


class _PolicyDb:
    def __init__(self, groups, policy):
        self.groups = groups
        self.policy = policy

    def query(self, model):
        return _PolicyQuery(model, self.groups, self.policy)

    def add(self, _item):
        pass

    def flush(self):
        pass

    def commit(self):
        pass


def test_save_project_policy_allows_only_cc_group(monkeypatch):
    group_id = uuid4()
    policy = SimpleNamespace(groups=[], updated_by=None, updated_at=None)
    db = _PolicyDb([SimpleNamespace(id=group_id, is_active=True)], policy)
    payload = SimpleNamespace(to_group_ids=[], cc_group_ids=[group_id])
    monkeypatch.setattr(
        business_mail_service,
        "ProjectMailPolicyGroup",
        lambda **values: SimpleNamespace(**values),
    )
    monkeypatch.setattr(business_mail_service, "_policy", lambda *_args: policy)

    saved = business_mail_service.save_policy(db, "translation", payload, uuid4())

    assert saved is policy
    assert [(item.group_id, item.recipient_type) for item in policy.groups] == [(group_id, "cc")]


def test_save_project_policy_still_requires_at_least_one_group():
    policy = SimpleNamespace(groups=[], updated_by=None, updated_at=None)
    db = _PolicyDb([], policy)
    payload = SimpleNamespace(to_group_ids=[], cc_group_ids=[])

    with pytest.raises(ValueError, match="主送组或抄送组"):
        business_mail_service.save_policy(db, "translation", payload, uuid4())


def test_policy_recipients_returns_cc_members_without_default_to(monkeypatch):
    cc_user = SimpleNamespace(id=uuid4())
    policy = SimpleNamespace(groups=[SimpleNamespace(
        recipient_type="cc",
        group=SimpleNamespace(
            is_active=True,
            members=[SimpleNamespace(user_id=cc_user.id)],
        ),
    )])
    monkeypatch.setattr(business_mail_service, "_policy", lambda *_args: policy)
    monkeypatch.setattr(
        business_mail_service,
        "validate_internal_users",
        lambda _db, user_ids: [cc_user] if list(user_ids) else [],
    )

    to_users, cc_users = business_mail_service.policy_recipients(object(), "translation")

    assert to_users == []
    assert cc_users == [cc_user]
