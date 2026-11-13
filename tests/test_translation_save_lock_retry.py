"""锁冲突回滚和有限重试；仅使用隔离内存数据库。"""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError
from tests.test_chat_participant_access import environment
from tests.test_translation_direction_children import case


@pytest.mark.parametrize('code', ['55P03', '40P01'])
def test_aborted_transaction_retries_without_duplicate_projects(environment, monkeypatch, code):
    from routers.translation_projects import _save_with_lock_retry
    from models import TranslationProject
    db, _ = environment
    calls = []
    class Conflict(Exception):
        pgcode = code
    def save():
        calls.append(1)
        row = TranslationProject(id=uuid4(), order_no='TP-261113-999', project_name='锁冲突回归')
        db.add(row); db.flush()
        if len(calls) < 3:
            raise OperationalError(None, None, Conflict())
        db.commit()
        return row
    _save_with_lock_retry(db, save)
    assert len(calls) == 3
    assert db.query(TranslationProject).count() == 1


def test_exhausted_lock_has_actionable_error_and_other_failures_are_not_retried(environment):
    from routers.translation_projects import _save_with_lock_retry
    db, _ = environment
    calls = []
    class Conflict(Exception):
        pgcode = '55P03'
    def save():
        calls.append(1)
        raise OperationalError(None, None, Conflict())
    with pytest.raises(HTTPException) as error:
        _save_with_lock_retry(db, save)
    assert error.value.status_code == 503 and '尚未保存' in error.value.detail
    assert len(calls) == 3
    calls.clear()
    Conflict.pgcode = '08006'
    with pytest.raises(OperationalError):
        _save_with_lock_retry(db, save)
    assert len(calls) == 1


def test_unchanged_inherited_fields_skip_tree_write(case, monkeypatch):
    from models import TranslationProject
    from schemas import TranslationProjectUpdate
    db, actor, crud = case
    row = TranslationProject(id=uuid4(), order_no='TP-261113-998', project_name='无需同步.docx',
        service_content='翻译', language_pair='中文→英语', project_status='confirmed')
    db.add(row); db.commit()
    def unexpected(*args):
        raise AssertionError('未改继承字段不应写入订单继承树')
    monkeypatch.setattr('translation_order_inheritance.prepare', unexpected)
    saved = crud.update_translation_project(db, row.id, TranslationProjectUpdate(
        project_name='更改项目名称.docx', service_content='翻译', language_pair='中文→英语', project_status='confirmed'), actor_user_id=actor.id)
    assert saved.project_name == '更改项目名称.docx'
