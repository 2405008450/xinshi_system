"""人才档案状态的接口及隔离数据库约束验证。"""
import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Column, MetaData, String, Table, create_engine
from sqlalchemy.exc import IntegrityError

from resource_models import ResourcePerson, TALENT_STATUSES
from resource_schemas import CapabilityInput, ResourcePersonCreate, ResourcePersonStatusUpdate


@pytest.mark.parametrize('status', TALENT_STATUSES)
def test_talent_status_is_accepted_by_payload_and_database(status):
    assert ResourcePersonCreate(full_name='状态验证', status=status).status == status
    assert ResourcePersonStatusUpdate(status=status).status == status
    constraint = next(item for item in ResourcePerson.__table__.constraints
                      if item.name == 'ck_resource_person_status')
    table = Table('status_test', MetaData(), Column('status', String(20)),
                  CheckConstraint(str(constraint.sqltext)))
    engine = create_engine('sqlite:///:memory:')
    try:
        table.create(engine)
        with engine.begin() as connection:
            connection.execute(table.insert().values(status=status))
            with pytest.raises(IntegrityError):
                connection.execute(table.insert().values(status='unknown'))
    finally:
        engine.dispose()


def test_talent_status_does_not_expand_capability_status():
    with pytest.raises(ValidationError):
        CapabilityInput(capability_type='annotation', status='blacklisted')
    with pytest.raises(ValidationError):
        ResourcePersonStatusUpdate(status='unknown')
