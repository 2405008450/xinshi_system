from uuid import uuid4

import pytest
from sqlalchemy import event

from tests.test_chat_participant_access import environment


@pytest.mark.parametrize('schema_name,field', [('ClientCreate','client_name'),('ClientCreate','client_short_name'),
    ('ClientUpdate','client_name'),('ClientUpdate','client_short_name'),('SubClientCreate','client_short_name'),('SubClientUpdate','client_short_name')])
def test_customer_names_cannot_be_blank(schema_name, field):
    import schemas
    schema = getattr(schemas, schema_name)
    data = dict(client_name='广州信实翻译服务有限公司', client_short_name='广州信实翻译')
    if schema_name == 'SubClientCreate':
        data['parent_client_id'] = uuid4()
    for empty in ('', '  \t', None):
        with pytest.raises(ValueError):
            schema(**{**data, field: empty})
    valid = schema(**{**data, field: '  张先生  '})
    assert getattr(valid, field) == '张先生'


@pytest.mark.parametrize('service_name', ['annotation_service', 'interpretation_service', 'recruitment_service'])
def test_project_customer_creation_requires_full_name_and_preserves_existing(environment, service_name):
    import importlib
    from models import Client
    db, _ = environment
    service = importlib.import_module(service_name)
    def ids(session, *_):
        for row in session.new:
            if hasattr(row, 'id') and row.id is None:
                row.id = uuid4()
    event.listen(db, 'before_flush', ids)
    with pytest.raises(ValueError, match='客户全称'):
        service._resolve_client(db, {'client_short_name': '广州信实翻译'})
    assert db.query(Client).count() == 0
    data = {'client_short_name': '广州信实翻译', 'client_name': ' 广州信实翻译服务有限公司 '}
    service._resolve_client(db, data)
    row = db.get(Client, data['client_id'])
    assert row.client_name == '广州信实翻译服务有限公司'
    assert row.client_short_name == '广州信实翻译'
    existing = {'client_short_name': '广州信实翻译'}
    service._resolve_client(db, existing)
    assert existing['client_id'] == row.id
    assert db.query(Client).count() == 1


def test_translation_and_consultation_create_store_separate_names(environment):
    import crud
    from models import Client, SubClient
    from schemas import TranslationProjectCreate, TranslationProjectUpdate, ConsultationCreate
    db, (owner, _, _) = environment
    def ids(session, *_):
        for row in session.new:
            if hasattr(row, 'id') and row.id is None:
                row.id = uuid4()
    event.listen(db, 'before_flush', ids)
    payload = dict(project_name='客户全称测试.docx', client_short_name='广州信实翻译', created_by=owner.id)
    with pytest.raises(ValueError, match='客户全称'):
        crud.create_translation_project(db, TranslationProjectCreate(**payload), order_no='TP-261107-901')
    project = crud.create_translation_project(db, TranslationProjectCreate(**payload,
        client_name='广州信实翻译服务有限公司', sub_client_short_name='信实分公司', sub_client_name='信实翻译分公司'), order_no='TP-261107-901')
    assert db.get(Client, project.client_id).client_name == '广州信实翻译服务有限公司'
    assert db.get(SubClient, project.sub_client_id).client_name == '信实翻译分公司'
    updated = crud.update_translation_project(db, project.id, TranslationProjectUpdate(
        client_short_name='张先生', client_name='张先生', client_id=None, sub_client_id=None), actor_user_id=owner.id)
    assert db.get(Client, updated.client_id).client_name == '张先生'
    assert updated.sub_client_id is None
    assert crud._resolve_or_create_project_sub_client(db, updated.client_id, None) is None
    optional_sub_id=crud._resolve_or_create_project_sub_client(db, updated.client_id, '新子客户')
    assert db.get(SubClient,optional_sub_id).client_name=='新子客户'
    consultation = crud.create_consultation(db, ConsultationCreate(
        client_short_name='北京咨询测试', client_name='北京咨询测试有限公司', created_by=owner.id))
    assert db.get(Client, consultation.client_id).client_name == '北京咨询测试有限公司'


def test_partial_customer_updates_do_not_require_unchanged_names():
    from schemas import ClientUpdate, SubClientUpdate
    assert ClientUpdate(remarks='仅改备注').model_dump(exclude_unset=True) == {'remarks': '仅改备注'}
    assert SubClientUpdate(remarks='仅改备注').model_dump(exclude_unset=True) == {'remarks': '仅改备注'}


@pytest.mark.parametrize('schema_name',['SubClientCreate','SubClientUpdate'])
@pytest.mark.parametrize('value',[None,'','  \t'])
def test_subclient_full_name_is_optional(schema_name,value):
    import schemas
    data={'client_short_name':'分公司','client_name':value}
    if schema_name=='SubClientCreate':data['parent_client_id']=uuid4()
    assert getattr(schemas,schema_name)(**data).client_name is None


def test_subclient_create_and_update_allow_missing_full_name_without_overwriting_known_name(environment):
    import crud
    from models import Client,SubClient
    from schemas import SubClientCreate,SubClientUpdate
    from sqlalchemy import Uuid
    db,_=environment
    def ids(session,*_):
        for row in session.new:
            if hasattr(row,'id') and row.id is None and isinstance(row.__table__.c.id.type,Uuid):row.id=uuid4()
    event.listen(db,'before_flush',ids)
    parent=Client(id=uuid4(),client_name='客户全称',client_short_name='客户',client_code='CL-261110-001')
    db.add(parent);db.commit()
    child=crud.create_sub_client(db,SubClientCreate(parent_client_id=parent.id,client_short_name='分公司'))
    assert child.client_name=='分公司'
    crud.update_sub_client(db,child.id,SubClientUpdate(client_name='正式分公司全称'))
    child=crud.update_sub_client(db,child.id,SubClientUpdate(client_name='',client_short_name='新简称'))
    assert child.client_name=='正式分公司全称' and child.client_short_name=='新简称'
    assert db.query(SubClient).count()==1


def test_translation_create_edit_and_existing_subclient_accept_optional_full_name(environment):
    import crud
    from models import Client,SubClient
    from schemas import TranslationProjectCreate,TranslationProjectUpdate
    from sqlalchemy import Uuid
    db,users=environment
    def ids(session,*_):
        for row in session.new:
            if hasattr(row,'id') and row.id is None and isinstance(row.__table__.c.id.type,Uuid):row.id=uuid4()
    event.listen(db,'before_flush',ids)
    parent=Client(id=uuid4(),client_name='母客户全称',client_short_name='母客户',client_code='CL-261110-002')
    db.add(parent);db.commit()
    project=crud.create_translation_project(db,TranslationProjectCreate(project_name='选填.docx',client_id=parent.id,
        sub_client_short_name='新增子客户',created_by=users[0].id),order_no='TP-261110-981')
    assert db.get(SubClient,project.sub_client_id).client_name=='新增子客户'
    project=crud.update_translation_project(db,project.id,TranslationProjectUpdate(sub_client_id=None,
        sub_client_short_name='编辑时新增子客户',sub_client_name=''),actor_user_id=users[0].id)
    child=db.get(SubClient,project.sub_client_id)
    assert child.client_name=='编辑时新增子客户'
    child.client_name='库中已有正式全称';db.commit()
    assert crud._resolve_or_create_project_sub_client(db,parent.id,child.client_short_name)==child.id
    assert db.get(SubClient,child.id).client_name=='库中已有正式全称'
