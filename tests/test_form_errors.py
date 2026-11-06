from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from form_errors import field_error, integrity_error_detail


def test_known_database_constraint_has_safe_message_and_field_path():
    exc = SimpleNamespace(orig=SimpleNamespace(diag=SimpleNamespace(constraint_name="client_client_code_key")))
    result = integrity_error_detail(exc, "保存失败")
    assert result["fieldErrors"][0]["path"] == "client_code"
    assert "已存在" in result["message"]


def test_unknown_database_error_does_not_expose_sql_or_invent_field():
    exc = SimpleNamespace(orig=RuntimeError("SQL and private parameters"))
    assert integrity_error_detail(exc, "保存失败") == "保存失败"


def test_field_error_preserves_nested_row_index():
    assert field_error("请选择人员", ["assignees", 2, "person_id"])["fieldErrors"][0]["path"] == ["assignees", 2, "person_id"]


def test_translation_foreign_keys_identify_actual_field_and_internal_sync():
    for constraint, path in [('fk_translation_project_client', 'client_id'),
                             ('fk_translation_project_sub_client', 'sub_client_id'),
                             ('fk_translation_project_manager', 'project_manager_id')]:
        exc = SimpleNamespace(orig=SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint)))
        assert integrity_error_detail(exc, '保存失败')['fieldErrors'][0]['path'] == path
    exc = SimpleNamespace(orig=SimpleNamespace(diag=SimpleNamespace(
        constraint_name='client_project_confirmation_project_id_fkey')))
    result = integrity_error_detail(exc, '保存失败')
    assert '合作状态同步失败' in result['message']
    assert result['fieldErrors'] == []
    assert '用户' not in result['message']


@pytest.mark.parametrize('constraint', ['client_project_confirmation_project_id_fkey', 'unrecognized_fk'])
def test_translation_create_does_not_misreport_every_fk_as_invalid_user(monkeypatch, constraint):
    from routers import translation_projects as router
    from uuid import uuid4
    error = Exception('foreign key SQL private values must not reach the response')
    error.diag = SimpleNamespace(constraint_name=constraint)
    def fail(**kwargs):
        raise IntegrityError('private SQL', {}, error)
    monkeypatch.setattr(router, 'create_translation_project', fail)
    db = MagicMock()
    payload = MagicMock()
    with pytest.raises(HTTPException) as caught:
        router.create_project_endpoint(payload, db, SimpleNamespace(id=uuid4()), None)
    assert caught.value.status_code == 400
    assert '用户不存在' not in str(caught.value.detail)
    assert 'private' not in str(caught.value.detail)
    db.rollback.assert_called_once()
