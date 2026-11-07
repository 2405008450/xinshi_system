from uuid import uuid4
import pytest
from sqlalchemy import create_engine, event, inspect, text
from tests.test_chat_participant_access import environment


def test_contact_tables_migration_is_repeatable_and_only_creates_new_tables():
    from tools.apply_translation_project_contact_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        for name in ['client','sub_client','app_user','translation_project']:
            connection.execute(text(f'CREATE TABLE {name} (id UUID PRIMARY KEY)'))
        apply_migration(connection);apply_migration(connection)
        assert set(inspect(connection).get_table_names())=={'client','sub_client','app_user','translation_project','client_contact_person','translation_project_contact'}
        assert len(inspect(connection).get_check_constraints('client_contact_person'))==1


def test_project_and_client_contact_lists_sync_without_reusing_phone(environment):
    import crud
    from client_contact_people import ClientContactPerson, names_for, replace
    from models import Client,SubClient
    from schemas import TranslationProjectCreate,TranslationProjectUpdate,ClientUpdate
    from routers.client_contact_people import options
    db,(owner,_,_)=environment
    def ids(session,*_):
        for row in session.new:
            if hasattr(row,'id') and row.id is None:row.id=uuid4()
    event.listen(db,'before_flush',ids)
    client=Client(id=uuid4(),client_code='CL-CONTACT',client_name='联系人测试公司',client_short_name='联系人测试',manager_contact='13800000000')
    other=Client(id=uuid4(),client_code='CL-OTHER',client_name='另一客户',client_short_name='其他')
    db.add_all([client,other]);db.flush()
    replace(db,client,['张先生',' 李女士 ','张先生']);db.commit()
    assert crud.get_client(db,client.id).contact_names==['张先生','李女士']
    project=crud.create_translation_project(db,TranslationProjectCreate(project_name='测试.docx',client_id=client.id,contact_name='王经理',created_by=owner.id),order_no='TP-261107-901')
    assert project.contact_name=='王经理'
    assert names_for(db,client)==['张先生','李女士','王经理']
    assert names_for(db,other)==[]
    assert client.manager_contact=='13800000000'
    assert options(client_id=client.id,db=db)['contact_names']==['张先生','李女士','王经理']
    crud.update_client(db,client.id,ClientUpdate(contact_names=['张先生','赵女士']))
    assert crud.get_client(db,client.id).contact_names==['张先生','赵女士']
    assert crud.get_translation_project(db,project.id).contact_name=='王经理'
    crud.update_translation_project(db,project.id,TranslationProjectUpdate(contact_name='王经理'),actor_user_id=owner.id)
    assert names_for(db,client)==['张先生','赵女士']
    changed=crud.update_translation_project(db,project.id,TranslationProjectUpdate(contact_name='赵女士'),actor_user_id=owner.id)
    assert changed.contact_name=='赵女士'
    assert db.query(ClientContactPerson).filter_by(contact_name='王经理').one().is_active is False
    sub=SubClient(id=uuid4(),parent_client_id=client.id,sub_client_code='CL-CONTACT.001',client_name='子客户',client_short_name='子')
    db.add(sub);db.commit();replace(db,sub,['子客户联系人']);db.commit()
    assert options(client_id=client.id,sub_client_id=sub.id,db=db)['contact_names']==['子客户联系人']
    assert names_for(db,client)==['张先生','赵女士']
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as mismatch:options(client_id=other.id,sub_client_id=sub.id,db=db)
    assert mismatch.value.status_code==400


def test_contact_names_validation():
    from client_contact_people import normalize_names
    assert normalize_names(['Alice','alice',' 李女士 '])==['Alice','李女士']
    for names in [[''],['  '],['a'*101]]:
        with pytest.raises(ValueError):normalize_names(names)
