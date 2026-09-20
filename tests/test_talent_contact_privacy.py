from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

import talent_privacy
from resource_schemas import ResourcePersonCreate, ResourcePersonUpdate
from routers import talents
from routers import talent_options
from talent_privacy import (
    CONTACT_MASK,
    RESOURCE_CONTACT_FIELDS,
    has_contact_values,
    preserve_contact_fields,
    serialize_with_contact_access,
)


class _ContactResponse(BaseModel):
    full_name: str
    primary_phone: str | None = None
    primary_email: str | None = None
    contact_restricted: bool = False


def test_super_admin_contact_visibility_uses_system_super_roles(monkeypatch):
    monkeypatch.setattr(
        talent_privacy,
        "get_user_roles_with_role_names",
        lambda _db, _user_id: ["超级管理员"],
    )
    assert talent_privacy.can_view_talent_contacts(object(), SimpleNamespace(id="1")) is True

    monkeypatch.setattr(
        talent_privacy,
        "get_user_roles_with_role_names",
        lambda _db, _user_id: ["项目助理"],
    )
    assert talent_privacy.can_view_talent_contacts(object(), SimpleNamespace(id="1")) is False


def test_contact_serializer_never_returns_plaintext_to_restricted_user():
    source = {
        "full_name": "测试人才",
        "primary_phone": "13800138000",
        "primary_email": "person@example.com",
    }
    restricted = serialize_with_contact_access(
        source,
        _ContactResponse,
        ("primary_phone", "primary_email"),
        contacts_visible=False,
    )
    assert restricted["primary_phone"] == CONTACT_MASK
    assert restricted["primary_email"] == CONTACT_MASK
    assert restricted["contact_restricted"] is True
    assert "13800138000" not in str(restricted)
    assert "person@example.com" not in str(restricted)

    visible = serialize_with_contact_access(
        source,
        _ContactResponse,
        ("primary_phone", "primary_email"),
        contacts_visible=True,
    )
    assert visible["primary_phone"] == "13800138000"
    assert visible["primary_email"] == "person@example.com"
    assert visible["contact_restricted"] is False


def test_restricted_update_preserves_all_existing_contact_fields():
    payload = ResourcePersonUpdate(full_name="更新后", primary_phone="000", primary_email="x@example.com")
    existing = SimpleNamespace(**{
        field: f"existing-{field}"
        for field in RESOURCE_CONTACT_FIELDS
    })
    protected = preserve_contact_fields(payload, existing, RESOURCE_CONTACT_FIELDS)
    for field in RESOURCE_CONTACT_FIELDS:
        assert getattr(protected, field) == f"existing-{field}"


def test_restricted_create_rejects_contact_values(monkeypatch):
    monkeypatch.setattr(talents, "can_view_talent_contacts", lambda _db, _user: False)
    payload = ResourcePersonCreate(full_name="测试人才", primary_phone="13800138000")
    assert has_contact_values(payload, RESOURCE_CONTACT_FIELDS) is True
    with pytest.raises(HTTPException) as exc_info:
        talents.create_talent_endpoint(
            payload,
            db=object(),
            current_user=SimpleNamespace(id="1"),
            idempotency_key=None,
        )
    assert exc_info.value.status_code == 403


def test_restricted_contact_filter_is_rejected():
    raw = '{"primary_phone":{"op":"contains","value":"138"}}'
    with pytest.raises(HTTPException) as exc_info:
        talents._field_filters(raw, allow_contact_filters=False)
    assert exc_info.value.status_code == 403


def test_restricted_duplicate_error_is_masked():
    error = talents.TalentDuplicateError([{
        "id": "1",
        "full_name": "已有人员",
        "primary_phone": "13800138000",
        "primary_email": "person@example.com",
        "match_fields": ["phone", "email"],
    }])
    detail = talents._duplicate_error_detail(error, contacts_visible=False)
    duplicate = detail["duplicates"][0]
    assert duplicate["primary_phone"] == CONTACT_MASK
    assert duplicate["primary_email"] == CONTACT_MASK
    assert "13800138000" not in str(detail)
    assert "person@example.com" not in str(detail)


def test_restricted_talent_option_keyword_does_not_search_contacts(monkeypatch):
    captured = {}
    monkeypatch.setattr(talent_options, "can_view_talent_contacts", lambda *_args: False)
    monkeypatch.setattr(
        talent_options,
        "get_talents",
        lambda _db, **filters: captured.update(filters) or [],
    )
    result = talent_options.read_talent_options(
        capability_type="written_translation",
        keyword="13800138000",
        limit=20,
        db=object(),
        current_user=SimpleNamespace(id="1"),
    )
    assert result == []
    assert captured["include_contact_search"] is False
