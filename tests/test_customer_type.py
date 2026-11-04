"""客户类型两端保存、同客户项目回显及子客户隔离；仅隔离 SQLite。"""
from uuid import uuid4
import pytest
from pydantic import ValidationError
from tests.test_chat_participant_access import environment
from models import Client, SubClient, TranslationProject
from schemas import ClientUpdate, SubClientUpdate, TranslationProjectUpdate, TranslationProjectCreate
import crud
import translation_customer_type as service


def test_project_client_sync_and_subclient_isolation(environment):
    db, (actor, _, _) = environment
    client = Client(id=uuid4(), client_code='CL-TYPE-001', client_name='类型测试客户', client_short_name='类型测试')
    db.add(client); db.flush()
    sub = SubClient(id=uuid4(), parent_client_id=client.id, sub_client_code='CL-TYPE-001.001', client_name='子客户', client_short_name='子客户')
    projects = [TranslationProject(id=uuid4(), order_no=f'TP-261104-{index:03}', project_name='测试.docx', source_file_name='测试.docx', client_id=client.id, created_by=actor.id) for index in range(1, 4)]
    projects[2].sub_client_id = sub.id
    db.add_all([sub, *projects]); db.commit()
    crud.update_translation_project(db, projects[0].id, TranslationProjectUpdate(customer_type='企业客户'), actor.id)
    assert crud.get_client(db, client.id).customer_type == '企业客户'
    assert crud.get_translation_project(db, projects[1].id).customer_type == '企业客户'
    crud.update_client(db, client.id, ClientUpdate(customer_type='国际组织'))
    assert crud.get_translation_project(db, projects[0].id).customer_type == '国际组织'
    crud.update_translation_project(db, projects[2].id, TranslationProjectUpdate(customer_type='NGO'), actor.id)
    assert crud.get_sub_client(db, sub.id).customer_type == 'NGO'
    assert crud.get_client(db, client.id).customer_type == '国际组织'
    crud.update_sub_client(db, sub.id, SubClientUpdate(customer_type='社会团体'))
    assert crud.get_translation_project(db, projects[2].id).customer_type == '社会团体'
    crud.update_translation_project(db, projects[0].id, TranslationProjectUpdate(customer_type=None), actor.id)
    assert crud.get_client(db, client.id).customer_type is None
    assert crud.get_translation_project(db, projects[1].id).customer_type is None
    assert crud.get_translation_project(db, projects[2].id).customer_type == '社会团体'


@pytest.mark.parametrize('value', ['个人客户','企业客户','行政/事业单位','社会团体','国际组织','NGO'])
def test_values_and_migration_are_valid(environment, value):
    db, _ = environment
    from tools.apply_translation_customer_type_migration import apply_migration
    service.ClientCustomerType.__table__.drop(db.connection())
    apply_migration(db.connection()); apply_migration(db.connection())
    assert TranslationProjectCreate(project_name='文件.docx', customer_type=value).customer_type == value
    with pytest.raises(ValidationError):
        ClientUpdate(customer_type='不支持的类型')
