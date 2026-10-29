from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, text

from resource_schemas import ResourcePersonCreate, ResourcePersonUpdate, ResourcePersonListResponse
from talent_privacy import RESOURCE_CONTACT_FIELDS, serialize_with_contact_access
from tools.apply_talent_identity_migration import apply_migration


@pytest.mark.parametrize('schema',[ResourcePersonCreate,ResourcePersonUpdate])
def test_identity_and_eyesight_preserve_text_and_allow_clear(schema):
    payload=schema(full_name='身份资料',identity_number='  0012345X  ',eyesight='  左4.8，右4.9  ')
    assert payload.identity_number=='0012345X'
    assert payload.eyesight=='左4.8，右4.9'
    assert schema(full_name='清空',identity_number=' ',eyesight=' ').identity_number is None
    with pytest.raises(ValidationError):schema(full_name='限制',identity_number='x'*51)


def test_identity_is_restricted_and_not_used_as_contact_identifier():
    from talent_duplicate_service import contact_identifiers
    assert 'identity_number' in RESOURCE_CONTACT_FIELDS
    person=SimpleNamespace(identity_number='not-a-contact@example.test')
    assert not any(contact_identifiers(person).values())


def test_identity_filter_requires_contact_access():
    import json
    from routers.talents import _field_filters
    with pytest.raises(HTTPException) as failure:
        _field_filters(json.dumps({'identity_number':{'op':'contains','value':'001'}}),allow_contact_filters=False)
    assert failure.value.status_code==403


def test_identity_migration_idempotent_preserves_existing_fields():
    engine=create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE resource_person (id INTEGER PRIMARY KEY, full_name TEXT)'))
            connection.execute(text("INSERT INTO resource_person VALUES (1,'旧资料')"))
            apply_migration(connection)
            connection.execute(text("UPDATE resource_person SET identity_number='0012345X',eyesight='已矫正'"))
            apply_migration(connection)
            assert tuple(connection.execute(text('SELECT full_name,identity_number,eyesight FROM resource_person')).one())==('旧资料','0012345X','已矫正')
    finally:engine.dispose()
