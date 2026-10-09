"""所有写入只使用内存 SQLite，业务表不连接日常服务数据库。"""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import crud
import annotation_ops_models  # 注册共享 ORM 关系，单独运行本文件时不依赖其他测试的导入顺序。
import routers.translation_projects as router
from concurrency import StaleUpdateError
from inline_text_update import TextFieldUpdate
from models import TranslationProject
from schemas import TranslationProjectCreate, TranslationProjectUpdate
from manuscript_schemas import ManuscriptDispatchCreate
from manuscript_service import _sync_entity_file_name


@pytest.fixture
def isolated_db(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    @event.listens_for(engine, 'connect')
    def configure(connection, _):
        connection.create_function('gen_random_uuid', 0, lambda: uuid4().hex)
    TranslationProject.__table__.create(engine)
    # 名称写入保留真实 CRUD 与事务，隔离工作流、人员目录及计费等旁支。
    monkeypatch.setattr(crud, 'get_translation_project', lambda db, key: db.get(TranslationProject, key))
    monkeypatch.setattr(router, 'get_translation_project', lambda db, key: db.get(TranslationProject, key))
    monkeypatch.setattr(crud, '_resolve_or_create_project_client', lambda *_args, **_kwargs: (None, None, False))
    monkeypatch.setattr(crud, '_sync_project_role_assignments', lambda *_: None)
    monkeypatch.setattr(crud, '_replace_customer_charge_items', lambda *_args, **_kwargs: None)
    monkeypatch.setattr(crud, 'record_project_operation', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('word_count_service.save_created_entity_matrix', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('workflow_crud.init_workflow', lambda *_args, **_kwargs: None)
    with Session(engine) as db:
        yield db
    engine.dispose()


def create(db, **values):
    return crud.create_translation_project(db, TranslationProjectCreate(
        project_name='旧客户，中译英，10月9日18点回稿', **values,
    ), order_no=f'TP-261009-{uuid4().hex[:6]}')


def test_full_create_and_edit_persist_two_names_without_overwriting_subject(isolated_db):
    db = isolated_db
    row = create(db, source_file_name='  正文.docx；附件.pdf  ', email_subject_preview='手工邮件主题')
    saved_subject = row.email_subject_preview
    assert row.project_name == row.source_file_name == '正文.docx；附件.pdf'
    version = row.updated_at
    updated = crud.update_translation_project(db, row.id, TranslationProjectUpdate(
        source_file_name='新文件.xlsx', project_name='应被文件名替换', expected_updated_at=version,
    ))
    db.expire_all()
    persisted = db.get(TranslationProject, updated.id)
    assert persisted.project_name == persisted.source_file_name == '新文件.xlsx'
    assert persisted.email_subject_preview == saved_subject
    with pytest.raises(StaleUpdateError):
        crud.update_translation_project(db, row.id, TranslationProjectUpdate(
            source_file_name='过期更新.docx', expected_updated_at=version - timedelta(seconds=2),
        ))
    assert persisted.source_file_name == '新文件.xlsx'


@pytest.mark.parametrize('field', ['source_file_name', 'project_name'])
def test_inline_edit_syncs_in_one_transaction_and_rejects_blank(isolated_db, field):
    db = isolated_db
    row = create(db, source_file_name='旧文件.docx', email_subject_preview='人工主题')
    original_subject = row.email_subject_preview
    updated = router.update_project_text_field(row.id, TextFieldUpdate(
        field=field, value='  合同原文.pdf；附件.docx ', expected_updated_at=row.updated_at,
    ), db)
    db.expire_all()
    assert updated.project_name == updated.source_file_name == '合同原文.pdf；附件.docx'
    assert updated.email_subject_preview == original_subject
    for invalid in [' ', 'a' * 256]:
        with pytest.raises(HTTPException) as exc:
            router.update_project_text_field(row.id, TextFieldUpdate(
                field=field, value=invalid, expected_updated_at=updated.updated_at,
            ), db)
        assert exc.value.status_code == 400
        assert db.get(TranslationProject, row.id).source_file_name == '合同原文.pdf；附件.docx'


def test_inline_repairs_same_file_name_alias_and_keeps_version_monotonic(isolated_db):
    db = isolated_db
    row = create(db, source_file_name='合同.docx')
    row.project_name = '历史摘要'
    row.updated_at = datetime.now() + timedelta(days=1)
    db.commit()
    version = row.updated_at
    router.update_project_text_field(row.id, TextFieldUpdate(
        field='source_file_name', value='合同.docx', expected_updated_at=version,
    ), db)
    assert row.project_name == row.source_file_name
    assert row.updated_at > version


def test_legacy_creation_and_unrelated_progress_updates_do_not_require_file_name(isolated_db):
    db = isolated_db
    row = create(db)
    legacy_name = row.project_name
    crud.update_translation_project(db, row.id, TranslationProjectUpdate(translator_delivery_progress='50'))
    assert row.source_file_name is None
    assert row.project_name == legacy_name
    assert row.translator_delivery_progress == '50%'
    with pytest.raises(ValueError):
        crud.update_translation_project(db, row.id, TranslationProjectUpdate(source_file_name=' '))
    db.rollback()
    assert row.project_name == legacy_name


def test_legacy_summary_only_update_cannot_overwrite_existing_file_name(isolated_db):
    row = create(isolated_db, source_file_name='合同.docx')
    crud.update_translation_project(isolated_db, row.id, TranslationProjectUpdate(project_name='旧调用方业务摘要'))
    assert row.project_name == row.source_file_name == '合同.docx'


def test_file_name_limit_retains_extensions_and_multi_file_format(isolated_db):
    name = '文' * 250 + '.docx'
    row = create(isolated_db, source_file_name=name)
    assert row.project_name == name
    with pytest.raises(ValueError):
        create(isolated_db, source_file_name='文' * 251 + '.docx')


def test_manuscript_file_writeback_persists_two_names_together(isolated_db):
    db = isolated_db
    row = create(db, source_file_name='旧文件.docx', email_subject_preview='手工主题')
    original_subject = row.email_subject_preview
    # 其他派稿字段已在稿件测试中校验，这里仅隔离验证实际订单回写和事务。
    payload = ManuscriptDispatchCreate.model_construct(file_name='稿件原文.pdf；附件.xlsx')
    _sync_entity_file_name(payload, row, None)
    db.rollback()
    assert row.project_name == row.source_file_name == '旧文件.docx'
    _sync_entity_file_name(payload, row, None)
    db.commit()
    db.expire_all()
    persisted = db.get(TranslationProject, row.id)
    assert persisted.project_name == persisted.source_file_name == '稿件原文.pdf；附件.xlsx'
    assert persisted.email_subject_preview == original_subject
