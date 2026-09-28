from types import SimpleNamespace

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
