import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from resource_schemas import ResourcePersonCreate, ResourcePersonUpdate, ResourcePersonListResponse
from tools.apply_talent_grade_migration import apply_migration


@pytest.mark.parametrize('grade', ['S', 'A', 'B', 'C', 'pending'])
def test_talent_grade_payload(grade):
    assert ResourcePersonCreate(full_name='分级测试', talent_grade=grade).talent_grade == grade
    assert ResourcePersonUpdate(full_name='分级测试', talent_grade=grade).talent_grade == grade


def test_talent_grade_defaults_and_rejects_unknown():
    assert ResourcePersonCreate(full_name='未评定').talent_grade == 'pending'
    assert ResourcePersonListResponse.model_fields['talent_grade'].default == 'pending'
    with pytest.raises(ValidationError):
        ResourcePersonCreate(full_name='无效分级', talent_grade='D')


def test_migration_initializes_existing_records_and_preserves_grades_on_rerun():
    engine = create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE resource_person (id INTEGER PRIMARY KEY)'))
            connection.execute(text('INSERT INTO resource_person (id) VALUES (1), (2)'))
            apply_migration(connection)
            assert connection.execute(text('SELECT talent_grade FROM resource_person ORDER BY id')).scalars().all() == ['pending', 'pending']
            connection.execute(text("UPDATE resource_person SET talent_grade='S' WHERE id=1"))
            apply_migration(connection)
            connection.execute(text('INSERT INTO resource_person (id) VALUES (3)'))
            assert connection.execute(text('SELECT talent_grade FROM resource_person ORDER BY id')).scalars().all() == ['S', 'pending', 'pending']
            with pytest.raises(IntegrityError):
                connection.execute(text("UPDATE resource_person SET talent_grade='D' WHERE id=1"))
            with pytest.raises(IntegrityError):
                connection.execute(text('UPDATE resource_person SET talent_grade=NULL WHERE id=1'))
    finally:
        engine.dispose()
