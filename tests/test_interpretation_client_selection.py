from uuid import uuid4
from sqlalchemy import inspect
from tests.test_chat_participant_access import environment
from models import Translator
from interpretation_models import InterpretationProject, InterpretationProjectInterpreter
from interpretation_schemas import InterpretationInterpreterInput,InterpretationInterpreterResponse
from interpretation_client_selection import InterpretationClientSelectedInterpreter,save,attach


def test_selected_state_survives_reorder_legacy_edits_and_uncheck(environment):
    db,_=environment
    from tools.apply_interpretation_client_selection_migration import apply_migration
    before=set(inspect(db.connection()).get_table_names());apply_migration(db.connection());apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names())==before
    people=[Translator(id=uuid4(),translator_name=name) for name in ['译员甲','译员乙']]
    project=InterpretationProject(id=uuid4(),order_no='IP-SELECTED',project_name='客户选定测试')
    project.interpreter_assignments=[InterpretationProjectInterpreter(id=uuid4(),sequence_no=i+1,translator=person) for i,person in enumerate(people)]
    db.add(project);db.commit()
    ids={person.id:person.id for person in people}
    items=[InterpretationInterpreterInput(translator_id=people[0].id,client_selected=True),InterpretationInterpreterInput(translator_id=people[1].id,client_selected=False)]
    save(db,project,items,ids);db.commit();attach(db,[project])
    assert [item.client_selected for item in project.interpreter_assignments]==[True,False]
    result=InterpretationInterpreterResponse.model_validate(project.interpreter_assignments[0])
    assert result.client_selected is True
    legacy=[InterpretationInterpreterInput(translator_id=person.id) for person in reversed(people)]
    save(db,project,legacy,ids);db.commit();attach(db,[project])
    assert project.interpreter_assignments[0].client_selected is True
    items[0].client_selected=False;save(db,project,items,ids);db.commit();attach(db,[project])
    assert not any(item.client_selected for item in project.interpreter_assignments)
    assert db.query(InterpretationClientSelectedInterpreter).count()==0
    items[0].client_selected=True;save(db,project,items,ids);db.commit()
    save(db,project,[items[1]],ids);db.commit()
    assert db.query(InterpretationClientSelectedInterpreter).count()==0


def test_inline_talent_registration_uses_pool_name_contact_and_resume_fields(environment):
    from resource_service import create_talent
    from resource_schemas import ResourcePersonCreate
    db,users=environment
    # SQLite隔离夹具不带PostgreSQL的gen_random_uuid默认值，仅在测试中补齐。
    from sqlalchemy import event,Uuid
    def uuid_defaults(session,_context,_instances):
        for row in session.new:
            column=row.__table__.c.get('id')
            if column is not None and isinstance(column.type,Uuid) and row.id is None:row.id=uuid4()
    event.listen(db,'before_flush',uuid_defaults)
    saved=create_talent(db,ResourcePersonCreate(full_name='测试新译员',chinese_name='测试新译员',nickname='测试别名',
        other_names=['其他测试名字'],primary_phone='13800000000',wechat='test-wechat',resume_path='C:/resumes/test.docx',
        capabilities=[{'capability_type':'interpretation','status':'active'}]),actor=users[0],idempotency_key='isolated-inline-talent')
    assert saved.chinese_name=='测试新译员' and saved.nickname=='测试别名'
    assert saved.primary_phone=='13800000000' and saved.wechat=='test-wechat'
    assert saved.resume_path=='C:/resumes/test.docx'
    assert saved.resource_code
