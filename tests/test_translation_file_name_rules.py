import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from translation_file_name_rules import EXTENSIONS, normalize_single_file_name
from translation_project_identity import normalize_translation_name_payload, sync_translation_file_name

CASES = json.loads((Path(__file__).parent / 'fixtures/translation_file_name_cases.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('name', CASES['valid'])
def test_valid_single_names(name):
    assert normalize_single_file_name(name) == name


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
