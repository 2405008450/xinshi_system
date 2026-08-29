from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

# 注册 Base 上跨模块的字符串关系，避免单文件测试时 mapper 缺少目标类。
import business_mail_models  # noqa: F401
import interpretation_models  # noqa: F401
import manuscript_models  # noqa: F401
import recruitment_models  # noqa: F401
import resource_request_models  # noqa: F401
import task_models  # noqa: F401
import word_count_models  # noqa: F401
import workflow_models  # noqa: F401
import annotation_ops_service as service
from annotation_ops_models import (
    AnnotationAccountAssignment,
    AnnotationAccountPasswordHistory,
    AnnotationCredentialAccessLog,
    AnnotationPlatformAccount,
)
from annotation_ops_schemas import AccountBatchWrite, AccountReleaseWrite, AccountWrite
from permission_registry import PERMISSION_CODES


def _index(model, name):
    return next(item for item in model.__table__.indexes if item.name == name)


def test_platform_account_duplicate_scope_is_platform_wide():
    constraint = next(
        item for item in AnnotationPlatformAccount.__table__.constraints
        if item.name == "uq_annotation_account_login_normalized"
    )
    assert [column.name for column in constraint.columns] == [
        "platform_id", "login_account_normalized"
    ]


def test_only_one_active_assignment_is_enforced_by_partial_unique_index():
    index = _index(AnnotationAccountAssignment, "uq_annotation_assignment_active")
    assert index.unique is True
    assert "released_on IS NULL" in str(index.dialect_options["postgresql"]["where"])


def test_release_payload_allows_reassignment_flow_and_rejects_unknown_reason():
    payload = AccountReleaseWrite(
        released_on=date(2026, 8, 27), release_reason="reassigned"
    )
    assert payload.release_reason == "reassigned"
    with pytest.raises(ValueError, match="释放原因"):
        AccountReleaseWrite(release_reason="invalid")


def test_account_update_accepts_blank_secrets_as_no_change():
    payload = AccountWrite(platform_id=uuid4(), login_account="", password="")
    assert payload.login_account is None
    assert payload.password is None


def test_account_list_response_redacts_credentials_by_default():
    now = datetime(2026, 8, 27)
    account = SimpleNamespace(
        id=uuid4(), platform_id=uuid4(), parent_account_id=None, owner_id=None,
        owner=None, nickname="测试账号", login_account="plain-login",
        password="plain-password", account_status="available",
        registration_status="registered", account_source="client_provided",
        expires_on=None, remarks=None, sequence_no=1, custom_values={},
        password_updated_at=now, assignments=[], created_at=now, updated_at=now,
        platform=SimpleNamespace(
            platform_name="测试平台", platform_url="https://example.com",
            client_id=uuid4(), sub_client_id=None,
        ),
    )

    response = service._account_dict(account)

    assert response["login_account"] is None
    assert response["password"] is None
    assert response["has_login_account"] is True
    assert response["has_password"] is True
    assert response["masked_login_account"]


def test_account_dict_includes_plaintext_when_revealed():
    now = datetime(2026, 8, 27)
    account = SimpleNamespace(
        id=uuid4(), platform_id=uuid4(), parent_account_id=None, owner_id=None,
        owner=None, nickname="测试账号", login_account="plain-login",
        password="plain-password", account_status="available",
        registration_status="registered", account_source="client_provided",
        expires_on=None, remarks=None, sequence_no=1, custom_values={},
        password_updated_at=now, assignments=[], created_at=now, updated_at=now,
        platform=SimpleNamespace(
            platform_name="测试平台", platform_url="https://example.com",
            client_id=uuid4(), sub_client_id=None,
        ),
    )

    response = service._account_dict(account, reveal=True)

    assert response["login_account"] == "plain-login"
    assert response["password"] == "plain-password"


def test_password_history_and_reveal_audit_models_keep_plaintext_and_actor():
    history_columns = AnnotationAccountPasswordHistory.__table__.c
    audit_columns = AnnotationCredentialAccessLog.__table__.c
    assert history_columns.password.nullable is False
    assert "encryption_key_version" not in history_columns
    assert "changed_by" in history_columns
    assert {"account_id", "user_id", "accessed_at", "access_reason", "client_ip"} <= set(audit_columns.keys())


def test_password_update_archives_previous_plaintext(monkeypatch):
    platform_id, account_id, user_id = uuid4(), uuid4(), uuid4()
    platform = SimpleNamespace(id=platform_id)
    account = SimpleNamespace(
        id=account_id, platform_id=platform_id, parent_account_id=None,
        nickname="旧昵称", login_account="old-login",
        login_account_normalized="old-login", password="old-password",
        password_updated_at=datetime(2026, 8, 1),
        created_at=datetime(2026, 7, 1), custom_values={}, sequence_no=1,
    )

    class EmptyQuery:
        def filter(self, *args): return self
        def first(self): return None

    class ResultQuery:
        def filter(self, *args): return self
        def one(self): return account

    class FakeDb:
        def __init__(self): self.added=[]
        def get(self, model, value):
            return platform if value == platform_id else account if value == account_id else None
        def query(self, *args): return EmptyQuery()
        def add(self, row): self.added.append(row)
        def commit(self): pass

    monkeypatch.setattr(service, "_ensure_unique_login", lambda *args: None)
    monkeypatch.setattr(service, "validate_custom_values", lambda *args: {})
    monkeypatch.setattr(service, "_account_query", lambda *args, **kwargs: ResultQuery())
    monkeypatch.setattr(service, "_account_dict", lambda row: {"id": row.id})
    monkeypatch.setattr(service, "validate_custom_values", lambda _db, _table, _project, values, _existing=None: values)
    payload = AccountWrite(
        platform_id=platform_id, nickname="新昵称", password="new-password",
        account_status="available",
    )
    db = FakeDb()

    assert service.save_account(db, payload, user_id, account_id) == {"id": account_id}
    history = next(item for item in db.added if isinstance(item, AnnotationAccountPasswordHistory))
    assert history.password == "old-password"
    assert history.changed_by == user_id
    assert account.password == "new-password"


def test_reveal_adds_database_audit_row(monkeypatch):
    account_id, user_id = uuid4(), uuid4()
    account = SimpleNamespace(
        id=account_id,
        login_account="login",
        password="password",
    )

    class FakeDb:
        def __init__(self):
            self.added = []
            self.committed = False

        def get(self, model, value):
            assert model is AnnotationPlatformAccount
            assert value == account_id
            return account

        def add(self, row):
            self.added.append(row)

        def commit(self):
            self.committed = True

    db = FakeDb()
    result = service.reveal_credential(
        db, account_id, SimpleNamespace(id=user_id), "工单核查", "127.0.0.1"
    )

    assert result == {"login_account": "login", "password": "password"}
    assert db.committed is True
    assert len(db.added) == 1
    assert db.added[0].account_id == account_id
    assert db.added[0].user_id == user_id
    assert db.added[0].access_reason == "工单核查"


def test_batch_save_does_not_create_pseudo_assignment_for_unassigned_row(monkeypatch):
    client_id, platform_id, user_id = uuid4(), uuid4(), uuid4()
    project_id, language_id = uuid4(), uuid4()
    saved_accounts = {}

    class Savepoint:
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ResultQuery:
        def filter(self, *args): return self
        def one(self): return next(iter(saved_accounts.values()))

    class FakeDb:
        contexts = []

        def get(self, model, value):
            if model is service.AnnotationPlatform and value == platform_id:
                return SimpleNamespace(id=platform_id, client_id=client_id)
            if model is service.AnnotationProject and value == project_id:
                return SimpleNamespace(id=project_id, client_id=client_id)
            return None
        def add(self, row): self.contexts.append(row)
        def begin_nested(self): return Savepoint()
        def flush(self): pass
        def commit(self): self.committed = True

    def apply_account(db, payload, created_by, account_id=None, **kwargs):
        if payload.nickname == "重复账号":
            raise ValueError("当前平台已存在相同登录账号")
        account = SimpleNamespace(
            id=account_id or uuid4(), platform_id=platform_id,
            account_status=payload.account_status, updated_at=None,
        )
        saved_accounts[account.id] = account
        return account

    monkeypatch.setattr(service, "_apply_account", apply_account)
    monkeypatch.setattr(service, "_validate_assignment_languages", lambda _db, _project_id, values: list(values))
    monkeypatch.setattr(service, "_active_assignment_for_update", lambda *args: None)
    monkeypatch.setattr(service, "_account_query", lambda *args, **kwargs: ResultQuery())
    monkeypatch.setattr(service, "_account_dict", lambda row: {"id": row.id})
    monkeypatch.setattr(service, "validate_custom_values", lambda _db, _table, _project, values, _existing=None: values)
    payload = AccountBatchWrite(client_id=client_id, rows=[
        {
            "row_key": "ok",
            "account": {"platform_id": platform_id, "nickname": "正常账号"},
            "project_id": project_id,
            "language_item_ids": [language_id],
        },
        {"row_key": "bad", "account": {"platform_id": platform_id, "nickname": "重复账号"}},
    ])

    result = service.batch_save_accounts(FakeDb(), client_id, payload.rows, user_id)

    assert result["results"][0]["success"] is True
    assert len(result.get("results", [])) == 2
    assert FakeDb.contexts == []
    assert result["results"][1] == {
        "row_key": "bad", "success": False, "error": "当前平台已存在相同登录账号",
    }


def test_batch_save_rejects_person_binding_without_project_and_language():
    client_id, platform_id, person_id = uuid4(), uuid4(), uuid4()

    class Savepoint:
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class FakeDb:
        def get(self, model, value):
            if model is service.AnnotationPlatform and value == platform_id:
                return SimpleNamespace(id=platform_id, client_id=client_id)
            return None
        def begin_nested(self): return Savepoint()
        def commit(self): pass

    payload = AccountBatchWrite(client_id=client_id, rows=[{
        "row_key": "missing-context",
        "account": {"platform_id": platform_id, "nickname": "账号一"},
        "person_id": person_id,
    }])

    result = service.batch_save_accounts(FakeDb(), client_id, payload.rows, None)

    assert result["results"][0]["success"] is False
    assert result["results"][0]["error"] == "绑定标注员时必须选择项目"


def test_batch_unassign_flushes_release_before_recomputing_account_status(monkeypatch):
    client_id, platform_id, account_id = uuid4(), uuid4(), uuid4()
    account = SimpleNamespace(id=account_id, account_status="assigned", updated_at=None)
    assignment = SimpleNamespace(released_on=None)

    class Savepoint:
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ResultQuery:
        def filter(self, *args): return self
        def one(self): return account

    class FakeDb:
        release_flushed = False

        def get(self, model, value):
            if model is service.AnnotationPlatform and value == platform_id:
                return SimpleNamespace(id=platform_id, client_id=client_id)
            return None
        def begin_nested(self): return Savepoint()
        def flush(self):
            if assignment.released_on is not None:
                self.release_flushed = True
        def commit(self): pass

    db = FakeDb()

    def apply_account(*_args, **_kwargs):
        return account

    def active_assignment(*_args):
        return None if db.release_flushed else assignment

    def apply_release(_db, released_account, payload):
        assignment.released_on = payload.released_on
        released_account.account_status = "available"

    monkeypatch.setattr(service, "_apply_account", apply_account)
    monkeypatch.setattr(service, "_active_assignment_for_update", active_assignment)
    monkeypatch.setattr(service, "_apply_release", apply_release)
    monkeypatch.setattr(service, "_account_query", lambda *args, **kwargs: ResultQuery())
    monkeypatch.setattr(service, "_account_dict", lambda row: {"id": row.id, "account_status": row.account_status})
    payload = AccountBatchWrite(client_id=client_id, rows=[{
        "row_key": "unassign",
        "id": account_id,
        "account": {"platform_id": platform_id, "account_status": "available"},
    }])

    result = service.batch_save_accounts(db, client_id, payload.rows, None)

    assert db.release_flushed is True
    assert result["results"][0]["account"]["account_status"] == "available"


def test_batch_save_rejects_duplicate_annotator_project_language_in_same_batch(monkeypatch):
    client_id, platform_id = uuid4(), uuid4()
    person_id, project_id, language_id = uuid4(), uuid4(), uuid4()
    saved_accounts = {}

    class Savepoint:
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class ResultQuery:
        def filter(self, *args): return self
        def one(self): return next(iter(saved_accounts.values()))

    class FakeDb:
        def get(self, model, value):
            if model is service.AnnotationPlatform and value == platform_id:
                return SimpleNamespace(id=platform_id, client_id=client_id)
            if model is service.AnnotationProject and value == project_id:
                return SimpleNamespace(id=project_id, client_id=client_id)
            return None
        def begin_nested(self): return Savepoint()
        def flush(self): pass
        def commit(self): pass

    def apply_account(_db, payload, _created_by, account_id=None, **_kwargs):
        account = SimpleNamespace(
            id=account_id or uuid4(), platform_id=payload.platform_id,
            account_status=payload.account_status, updated_at=None,
        )
        saved_accounts[account.id] = account
        return account

    monkeypatch.setattr(service, "_apply_account", apply_account)
    monkeypatch.setattr(service, "_validate_assignment_languages", lambda _db, _project_id, values: list(values))
    monkeypatch.setattr(service, "_active_assignment_for_update", lambda *_args: None)
    monkeypatch.setattr(service, "_apply_assignment", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_account_query", lambda *args, **kwargs: ResultQuery())
    monkeypatch.setattr(service, "_account_dict", lambda row: {"id": row.id})
    payload = AccountBatchWrite(client_id=client_id, rows=[
        {
            "row_key": "first", "account": {"platform_id": platform_id, "nickname": "账号一"},
            "person_id": person_id, "project_id": project_id,
            "language_item_ids": [language_id],
        },
        {
            "row_key": "second", "account": {"platform_id": platform_id, "nickname": "账号二"},
            "person_id": person_id, "project_id": project_id,
            "language_item_ids": [language_id],
        },
    ])

    result = service.batch_save_accounts(FakeDb(), client_id, payload.rows, None)

    assert result["results"][0]["success"] is True
    assert result["results"][1]["success"] is False
    assert "同一批次中" in result["results"][1]["error"]


def test_list_and_count_share_the_same_filter_builder():
    session = Session()
    filters = {
        "client_id": uuid4(),
        "project_id": uuid4(),
        "assignment_state": "assigned",
        "registration_status": "registered",
        "keyword": "张三",
    }
    list_sql = str(service._account_query(session, **filters).statement.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    ))
    count_sql = str(service._account_query(session, eager=False, **filters).with_entities(
        service.func.count(AnnotationPlatformAccount.id)
    ).statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

    for fragment in (
        "annotation_platform.client_id",
        "annotation_account_assignment.project_id",
        "annotation_account_assignment.person_id IS NOT NULL",
        "annotation_platform_account.registration_status",
        "resource_person.full_name ILIKE",
    ):
        assert fragment in list_sql
        assert fragment in count_sql


def test_pool_stats_query_groups_all_statuses_and_expiry():
    sql = str(service._account_stats_query(Session(), uuid4()).statement.compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    ))
    for status in ("available", "assigned", "suspended", "banned", "retired"):
        assert status in sql
    assert "expires_on" in sql
    assert "GROUP BY annotation_platform.id" in sql


def test_release_all_updates_reverse_holdings_and_account_status():
    account = SimpleNamespace(account_status="assigned", updated_at=None)
    assignment = SimpleNamespace(
        assigned_on=date(2026, 8, 1), released_on=None, release_reason=None,
        assignment_note=None, updated_at=None, account=account,
    )

    class Query:
        def filter(self, *args): return self
        def all(self): return [assignment]

    class FakeDb:
        def query(self, *args): return Query()
        def commit(self): self.committed=True

    db = FakeDb()
    payload = AccountReleaseWrite(
        released_on=date(2026, 8, 27), release_reason="person_left",
        assignment_note="离职统一回收",
    )
    assert service.release_all_person_accounts(db, uuid4(), payload) == 1
    assert assignment.released_on == date(2026, 8, 27)
    assert assignment.release_reason == "person_left"
    assert account.account_status == "available"


def test_annotation_account_permissions_are_independent():
    assert {
        "annotation_accounts:read",
        "annotation_accounts:write",
        "annotation_accounts:reveal",
    } <= PERMISSION_CODES
    assert "annotation_accounts:reveal" != "projects:write"


def test_account_person_profile_exposes_locale_fields_and_computes_age(monkeypatch):
    person_id = uuid4()
    person = SimpleNamespace(
        id=person_id, resource_code="AN-001", full_name="方言标注员", gender="女",
        birth_date=date(2000, 9, 1), native_place="福建泉州",
        residence_address="福建厦门", dialects=["闽南语"], dialect_regions=["泉州石狮"],
        nationality="中国", ethnicity="汉族", cooperation_type="兼职", status="active",
        annotation_profile=SimpleNamespace(
            task_types=["音频标注"], data_modalities=["音频"], tools=["自研平台"],
            quality_score="A", remarks="熟悉地方口音",
        ),
    )

    class Query:
        def options(self, *args): return self
        def filter(self, *args): return self
        def first(self): return person

    result = service.get_account_person_profile(SimpleNamespace(query=lambda *_: Query()), person_id)

    assert result["full_name"] == "方言标注员"
    assert result["native_place"] == "福建泉州"
    assert result["dialects"] == ["闽南语"]
    assert result["annotation_task_types"] == ["音频标注"]
    assert result["age"] in {25, 26}
