import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from tests.test_chat_participant_access import environment

from translation_file_name_rules import EXTENSIONS, normalize_single_file_name
from translation_project_identity import normalize_translation_name_payload, sync_translation_file_name

CASES = json.loads((Path(__file__).parent / 'fixtures/translation_file_name_cases.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('name', CASES['valid'])
def test_valid_single_names(name):
    assert normalize_single_file_name(name) == name


def test_parent_name_only_exempt_with_children_and_still_rejects_multiple_files():
    data={'project_name':'项目母订单'}
    normalize_translation_name_payload(data,has_sub_orders=True)
    assert data['source_file_name']=='项目母订单'
    with pytest.raises(ValueError):normalize_translation_name_payload({'project_name':'项目母订单'})
    with pytest.raises(ValueError):normalize_translation_name_payload({'project_name':'甲.pdf；乙.docx'},has_sub_orders=True)
    from schemas import TranslationProjectCreate
    with pytest.raises(ValueError):TranslationProjectCreate(project_name='母订单',initial_sub_order_names=['子文件无后缀'])


def test_create_parent_and_initial_children_in_one_transaction(environment):
    import crud
    from models import Client
    from schemas import TranslationProjectCreate,TranslationProjectUpdate
    db,(owner,_,_)=environment
    from sqlalchemy import event
    def sqlite_generated_ids(session,*args):
        for row in session.new:
            if hasattr(row,'id') and row.id is None:row.id=uuid4()
    event.listen(db,'before_flush',sqlite_generated_ids)
    client=Client(id=uuid4(),client_name='项目名称规则测试');db.add(client);db.flush()
    payload=TranslationProjectCreate(project_name='母订单项目',client_id=client.id,created_by=owner.id,
        initial_sub_order_names=['子文件甲.docx','子文件乙.pdf'])
    result=crud.create_translation_project(db,payload,order_no='TP-261102-900')
    assert result.project_name=='母订单项目'
    assert {row.sub_project_name for row in result.sub_orders}=={'子文件甲.docx','子文件乙.pdf'}
    updated=crud.update_translation_project(db,result.id,TranslationProjectUpdate(project_name='更名母订单'),actor_user_id=owner.id)
    assert updated.project_name=='更名母订单'


@pytest.mark.parametrize('name', CASES['invalid'])
def test_bad_extension_or_multiple_files_rejected(name):
    with pytest.raises(ValueError):
        normalize_single_file_name(name)


@pytest.mark.parametrize('extension', sorted(EXTENSIONS))
def test_every_catalog_extension_is_recognized(extension):
    name = '单个文件.' + extension
    assert normalize_single_file_name(name) == name


def test_root_alias_and_bulk_children_cannot_bypass_rule():
    from schemas import TranslationSubOrderBulkCreate
    for key in ['source_file_name', 'project_name']:
        with pytest.raises(ValueError):
            normalize_translation_name_payload({key: '合同.pdf；附件.xlsx'})
        data = {key: '合同.pdf'}
        normalize_translation_name_payload(data)
        assert data['source_file_name'] == data['project_name'] == '合同.pdf'
    project = SimpleNamespace(source_file_name='原文.docx', project_name='原文.docx')
    with pytest.raises(ValueError):
        sync_translation_file_name(project, '原文.docx，附件.pdf')
    assert project.source_file_name == '原文.docx'
    with pytest.raises(ValueError, match='第 2 条'):
        TranslationSubOrderBulkCreate(parent_project_id=uuid4(), sub_project_names=['原文.docx','无后缀文件'])


def test_dispatch_updates_parent_and_child_follow_same_rule():
    from manuscript_service import _sync_entity_file_name
    from manuscript_schemas import ManuscriptDispatchCreate
    payload = ManuscriptDispatchCreate.model_construct(file_name='A.pdf；B.docx', _fields_set={'file_name'})
    project = SimpleNamespace(source_file_name='旧文件.pdf', project_name='旧文件.pdf')
    child = SimpleNamespace(sub_project_name='旧子文件.pdf')
    for target in [None, child]:
        with pytest.raises(ValueError):
            _sync_entity_file_name(payload, project, target)
    assert project.source_file_name == '旧文件.pdf'
    assert child.sub_project_name == '旧子文件.pdf'


def test_child_create_and_update_validate_before_writing(monkeypatch):
    import crud
    from schemas import TranslationSubOrderCreate, TranslationSubOrderUpdate
    with pytest.raises(ValueError, match='一个订单号'):
        crud.create_sub_order(None, TranslationSubOrderCreate(parent_project_id=uuid4(), sub_project_name='A.pdf；B.docx'))
    child = SimpleNamespace(sub_project_name='原文.pdf')
    monkeypatch.setattr(crud, 'get_sub_order', lambda *args: child)
    with pytest.raises(ValueError, match='一个订单号'):
        crud.update_sub_order(None, uuid4(), TranslationSubOrderUpdate(sub_project_name='A.pdf；B.docx'))
    assert child.sub_project_name == '原文.pdf'
