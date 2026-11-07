from uuid import uuid4

import pytest
from sqlalchemy import event

from tests.test_chat_participant_access import environment


@pytest.mark.parametrize('schema_name', ['ClientCreate', 'ClientUpdate', 'SubClientCreate', 'SubClientUpdate'])
@pytest.mark.parametrize('field', ['client_name', 'client_short_name'])
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
    with pytest.raises(ValueError, match='子客户全称'):
        crud._resolve_or_create_project_sub_client(db, updated.client_id, '新子客户')
    consultation = crud.create_consultation(db, ConsultationCreate(
        client_short_name='北京咨询测试', client_name='北京咨询测试有限公司', created_by=owner.id))
    assert db.get(Client, consultation.client_id).client_name == '北京咨询测试有限公司'


def test_partial_customer_updates_do_not_require_unchanged_names():
    from schemas import ClientUpdate, SubClientUpdate
    assert ClientUpdate(remarks='仅改备注').model_dump(exclude_unset=True) == {'remarks': '仅改备注'}
    assert SubClientUpdate(remarks='仅改备注').model_dump(exclude_unset=True) == {'remarks': '仅改备注'}
