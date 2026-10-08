"""文字跟进回归；与开拓测试共用逐例回滚的局域网数据库。"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from test_resource_development import db, context, make_payload, action  # noqa: F401
from resource_development_schemas import FollowUpWrite, RecordWrite
from resource_development_models import DevelopmentFollowUp, DevelopmentAudit
from resource_development_service import save_record, serialize_record, filtered_records


def test_text_validation_and_server_metadata():
    for content in [' ', '', '文' * 20001]:
        with pytest.raises(ValidationError):
            FollowUpWrite(id=uuid4(), content=content)
    assert FollowUpWrite(id=uuid4(), content=' 首次联系\n约定明天回复 ').content == '首次联系\n约定明天回复'
    for forged in [{'operator_id': str(uuid4())}, {'created_at': '2000-01-01'}]:
        with pytest.raises(ValidationError):
            FollowUpWrite(id=uuid4(), content='沟通记录', **forged)
    entry = dict(id=uuid4(), content='一条记录')
    with pytest.raises(ValidationError):
        RecordWrite(id=uuid4(), platform_id=uuid4(), owner_id=uuid4(), work_date='2026-10-08',
                    full_name='测试', follow_ups=[entry, entry])


def test_append_actual_operator_order_and_no_enrollment(db, context):
    user, other, _ = context
    drafts = [dict(id=uuid4(), content='首次联系'), dict(id=uuid4(), content='已添加，等待回复')]
    payload = make_payload(context, owner_id=other.id, follow_up='旧表原文', follow_ups=drafts)
    before = datetime.now(timezone(timedelta(hours=8)))
    with patch('resource_development_service.can_delegate', return_value=True):
        row = save_record(db, user, payload)
        detail = serialize_record(db, user, row, True)
        assert row.person_id is None and row.wechat_status == '未处理'
        assert detail['follow_up'] == '旧表原文' and detail['follow_up_count'] == 2
        assert [entry['content'] for entry in detail['follow_ups']] == ['已添加，等待回复', '首次联系']
        assert all(entry['operator_name'] == user.full_name for entry in detail['follow_ups'])
        assert datetime.fromisoformat(detail['follow_ups'][0]['created_at']) >= before
        saved = db.get(DevelopmentFollowUp, drafts[0]['id'])
        original = (saved.content, saved.created_at, saved.operator_id)
        follow = FollowUpWrite(id=uuid4(), content='第三次跟进')
        row = save_record(db, user, payload.model_copy(update={'revision': row.revision, 'follow_ups': [follow]}))
        detail = serialize_record(db, user, row, True)
        assert detail['latest_follow_up'] == '第三次跟进' and detail['follow_up_count'] == 3
        assert (saved.content, saved.created_at, saved.operator_id) == original
        assert db.query(DevelopmentAudit).filter_by(entity_id=follow.id, action='create').count() == 1
        row = save_record(db, user, payload.model_copy(update={'revision': row.revision, 'follow_ups': [follow]}))
        assert serialize_record(db, user, row)['follow_up_count'] == 3
        assert db.query(DevelopmentAudit).filter_by(entity_id=follow.id, action='create').count() == 1


def test_immutable_history_conflict_permissions_and_atomicity(db, context):
    user, other, _ = context
    entry = FollowUpWrite(id=uuid4(), content='原内容')
    payload = make_payload(context, follow_ups=[entry], follow_up='历史原文')
    row = save_record(db, user, payload)
    with pytest.raises(HTTPException) as error:
        save_record(db, other, payload.model_copy(update={'revision': row.revision}))
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        save_record(db, user, payload.model_copy(update={'revision': row.revision - 1 or 99}))
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        save_record(db, user, payload.model_copy(update={'revision': row.revision, 'follow_up': '改写原文'}))
    assert error.value.status_code == 422
    version = row.revision
    with db.begin_nested() as nested:
        with pytest.raises(HTTPException) as error:
            save_record(db, user, payload.model_copy(update={'revision': version,
                'full_name': '不能保存的改名', 'follow_ups': [entry.model_copy(update={'content': '改历史'})]}))
        assert error.value.status_code == 409
        nested.rollback()
    assert row.revision == version and row.full_name == payload.full_name
    assert db.get(DevelopmentFollowUp, entry.id).content == '原内容'
    with db.begin_nested() as nested:
        with pytest.raises(HTTPException) as error:
            save_record(db, user, make_payload(context, follow_ups=[entry]))
        assert error.value.status_code == 409
        nested.rollback()
    # 不提交历史 ID 不代表删除历史。
    row = save_record(db, user, payload.model_copy(update={'revision': row.revision, 'follow_ups': []}))
    assert serialize_record(db, user, row)['follow_up_count'] == 1


def test_latest_filter_legacy_masking_and_day_totals(db, context):
    from routers.resource_development import days, records
    user, other, _ = context
    old = make_payload(context, follow_up='旧表备注私密137', actions=[action(user, '已沟通', 'communication')])
    row = save_record(db, user, old)
    def matches(actor, value):
        return filtered_records(db, actor, row.work_date, row.work_date,
                                column_filters={'latest_follow_up': value}).filter_by(id=row.id).count()
    assert matches(user, '旧表备注私密137') == 1
    row = save_record(db, user, old.model_copy(update={'revision': row.revision,
        'follow_ups': [FollowUpWrite(id=uuid4(), content='第一次私密138'), FollowUpWrite(id=uuid4(), content='最新私密139')]}))
    detail = serialize_record(db, user, row, True)
    latest = datetime.fromisoformat(detail['latest_follow_up_entry']['created_at'])
    for value in ['最新私密139', user.full_name, latest.strftime('%Y-%m-%d'), latest.strftime('%Y年%m月%d日')]:
        assert matches(user, value) == 1
    for value in ['第一次私密138', '旧表备注私密137', '已沟通']:
        assert matches(user, value) == 0
    masked = serialize_record(db, other, row, True)
    assert masked['follow_up'] == '受限内容' and masked['latest_follow_up'] == '受限内容'
    assert all(entry['content'] == '受限内容' for entry in masked['follow_ups']) and masked['audit'] == []
    assert matches(other, '最新私密139') == 0
    params = dict(start=row.work_date, end=row.work_date, keyword=None, owner_id=None, platform_id=None,
                  account_id=None, state=None, column_filters={'latest_follow_up': '最新私密139'})
    listed = records(params=params, skip=0, limit=20, db=db, user=user)
    grouped = days(params=params, skip=0, limit=20, db=db, user=user)
    assert listed['total'] == 1 and sum(day['count'] for day in grouped['items']) == 1


def test_create_retry_and_cascade_delete(db, context):
    from resource_development_models import DevelopmentRecord
    user, _, _ = context
    payload = make_payload(context, follow_ups=[dict(id=uuid4(), content='首次跟进')])
    row = save_record(db, user, payload)
    save_record(db, user, payload)
    assert db.query(DevelopmentFollowUp).filter_by(record_id=row.id).count() == 1
    # 用 ORM 删除验证数据库级级联；外层测试事务仍会回滚。
    rid = row.id
    db.delete(row); db.flush()
    assert db.get(DevelopmentRecord, rid) is None
    assert db.query(DevelopmentFollowUp).filter_by(record_id=rid).count() == 0
