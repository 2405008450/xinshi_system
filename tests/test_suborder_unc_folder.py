from pathlib import Path
import pytest
from project_file_service import inspect_suborder_shared_folder
from tests.test_chat_participant_access import environment
from tests.test_translation_direction_children import case, create


def test_unc_listing_preserves_first_level_paths_and_whitelist(tmp_path, monkeypatch):
    import project_file_service as service
    monkeypatch.setenv('OPENPATH_ALLOWED_ROOTS',r'\\Test-server\Projects')
    for name in ['合同.docx','附件.pdf','desktop.ini']:(tmp_path/name).write_text('test')
    (tmp_path/'子目录').mkdir();(tmp_path/'子目录'/'下层.docx').write_text('nested')
    monkeypatch.setattr(service,'Path',lambda _:tmp_path)
    result=inspect_suborder_shared_folder(r'\\Test-server\Projects\客户')
    assert {row['name'] for row in result['files']}=={'合同.docx','附件.pdf'}
    assert all(row['network_file_path']==r'\\Test-server\Projects\客户'+'\\'+row['name'] for row in result['files'])
    with pytest.raises(ValueError):inspect_suborder_shared_folder(r'D:\客户')
    with pytest.raises(ValueError):inspect_suborder_shared_folder(r'\\Other-server\Projects')
    with pytest.raises(ValueError):inspect_suborder_shared_folder(r'\\Test-server\Projects\..\Secrets')


def test_bulk_unc_rechecks_files_and_saves_individual_paths(case,monkeypatch):
    import project_file_service
    from schemas import TranslationSubOrderBulkCreate
    from models import TranslationSubOrder
    db,user,crud=case;root=create(case)
    monkeypatch.setenv('OPENPATH_ALLOWED_ROOTS',r'\\Test-server\Projects')
    prefix=r'\\Test-server\Projects\客户'
    monkeypatch.setattr(project_file_service,'inspect_suborder_shared_folder',lambda _:dict(storage_path=prefix,files=[dict(name=name,network_file_path=prefix+'\\'+name) for name in ['新一.docx','新二.pdf']]))
    created,skipped=crud.create_sub_orders_bulk(db,TranslationSubOrderBulkCreate(parent_project_id=root.id,source_folder_path=prefix,sub_project_names=['新一.docx','新二.pdf']),created_by=user.id)
    assert len(created)==2 and not skipped
    assert {row.network_file_path for row in created}=={prefix+r'\新一.docx',prefix+r'\新二.pdf'}
    before=db.query(TranslationSubOrder).count()
    with pytest.raises(ValueError,match='重新读取'):
        crud.create_sub_orders_bulk(db,TranslationSubOrderBulkCreate(parent_project_id=root.id,source_folder_path=prefix,sub_project_names=['不存在.pdf']),created_by=user.id)
    db.rollback()
    assert db.query(TranslationSubOrder).count()==before
