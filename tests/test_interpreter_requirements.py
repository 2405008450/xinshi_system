from uuid import uuid4
import pytest
from sqlalchemy import inspect
from pydantic import ValidationError
from tests.test_chat_participant_access import environment
from interpretation_models import InterpretationProject
from interpretation_schemas import InterpreterRequirementsInput
from interpretation_interpreter_requirements import InterpretationInterpreterRequirements,save,attach


def test_requirements_round_trip_partial_update_clear_and_legacy_preserve(environment):
    db,_=environment
    from tools.apply_interpreter_requirements_migration import apply_migration
    before=set(inspect(db.connection()).get_table_names());apply_migration(db.connection());apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names())==before
    project=InterpretationProject(id=uuid4(),order_no='IP-REQS',project_name='译员要求测试')
    other=InterpretationProject(id=uuid4(),order_no='IP-REQS2',project_name='其他项目')
    db.add_all([project,other]);db.commit()
    values={key:' '+key+'要求 ' for key in InterpreterRequirementsInput.model_fields}
    save(db,project,InterpreterRequirementsInput(**values));db.commit();db.expire_all();attach(db,[project,other])
    assert project.interpreter_requirements=={key:value.strip() for key,value in values.items()}
    assert other.interpreter_requirements=={}
    save(db,project,None);db.commit();attach(db,[project])
    assert project.interpreter_requirements['passport']=='passport要求'
    save(db,project,InterpreterRequirementsInput(passport='新护照要求'));db.commit();attach(db,[project])
    assert project.interpreter_requirements['passport']=='新护照要求'
    assert project.interpreter_requirements['visa']=='visa要求'
    save(db,project,InterpreterRequirementsInput(visa=''));db.commit();attach(db,[project])
    assert project.interpreter_requirements['visa']==''
    save(db,project,InterpreterRequirementsInput(photos='回滚内容'));db.flush();db.rollback();attach(db,[project])
    assert project.interpreter_requirements['photos']=='photos要求'
    assert db.query(InterpretationInterpreterRequirements).count()==1


def test_requirement_validation_rejects_unknown_and_overlong_fields():
    with pytest.raises(ValidationError):InterpreterRequirementsInput(photos='x'*5001)
    with pytest.raises(ValidationError):InterpreterRequirementsInput(unknown='非法字段')
    assert InterpreterRequirementsInput(driving_license='  C1  ').driving_license=='C1'
