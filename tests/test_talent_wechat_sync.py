"""账号、双向联系状态与统计隔离回归；局域网数据库逐例回滚。"""
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from test_resource_development import db, context, make_payload, action  # noqa: F401
from resource_development_schemas import RecordWrite
from resource_development_models import DevelopmentAction, DevelopmentAudit, DevelopmentOption
from resource_development_service import save_record, serialize_record, filtered_records, report_item
from resource_models import ResourcePerson
from resource_schemas import ResourcePersonCreate, ResourcePersonUpdate
from resource_service import create_talent, update_talent, update_recruitment_talent
from talent_wechat_accounts import person_accounts, write_talent_accounts, normalize_accounts


def edited(payload, row, **values):
    return RecordWrite(**(payload.model_dump() | {'revision': row.revision} | values))


def enrolled(db, context, **values):
    user = context[0]
    payload = make_payload(context, capabilities=['annotation'], actions=[action(user, '已添加')], **values)
    row = save_record(db, user, payload)
    return payload, row, db.get(ResourcePerson, row.person_id)


def test_array_validation_and_legacy_text_is_not_split():
    assert normalize_accounts(' HR1、历史自定义 ') == ['HR1、历史自定义']
    assert ResourcePersonCreate(full_name='测试', wechat_accounts=[' HR1 ', 'HR1', '其他']).wechat_accounts == ['HR1', '其他']
    with pytest.raises(ValidationError):
        ResourcePersonCreate(full_name='测试', wechat_accounts=['微' * 101])
    with pytest.raises(ValidationError):
        ResourcePersonCreate(full_name='测试', wechat_accounts=['HR1'] * 101)
    for values in [['已删微信'], ['已删企微'], ['微' * 101]]:
        with pytest.raises(ValidationError):
            RecordWrite(id=uuid4(), owner_id=uuid4(), platform_id=uuid4(), work_date='2026-10-08', full_name='测试', friend_accounts=values)


def test_enrollment_link_and_account_union_never_remove_existing(db, context):
    user = context[0]
    account = DevelopmentOption(id=uuid4(), kind='account', name='交换-' + uuid4().hex)
    db.add(account); db.flush()
    payload, row, person = enrolled(db, context, account_id=account.id, friend_accounts=['HR2', 'HR3企微'])
    assert person_accounts(person) == [account.name, 'HR2', 'HR3企微']
    linked = make_payload(context, full_name=person.full_name, actions=[action(user, '已添加')],
                          link_person_id=person.id, friend_accounts=['HR2', '其他账号'])
    second = save_record(db, user, linked)
    assert second.person_id == person.id
    assert person_accounts(person) == [account.name, 'HR2', 'HR3企微', '其他账号']
    row = save_record(db, user, edited(payload, row, friend_accounts=['HR4']))
    assert person_accounts(person) == [account.name, 'HR2', 'HR3企微', '其他账号', 'HR4']
    row = save_record(db, user, edited(payload, row, account_id=None, friend_accounts=[]))
    assert 'HR4' in person_accounts(person) and account.name in person_accounts(person)
    assert serialize_record(db, user, row)['friend_accounts_text'] == ''


def test_bidirectional_delete_restore_multiple_links_and_statistics(db, context):
    user, other, _ = context
    payload, row, person = enrolled(db, context, friend_accounts=['HR1', 'HR2企微'])
    linked = make_payload(context, full_name=person.full_name, link_person_id=person.id, actions=[action(user, '已添加')])
    second = save_record(db, user, linked)
    # 名字相同但没有 person_id 的记录不参与同步。
    unrelated = save_record(db, user, make_payload(context, full_name=person.full_name))
    before_count = db.query(DevelopmentAction).filter_by(record_id=row.id).count()
    before_stats = report_item(db, user.id, row.work_date)
    original_action = db.query(DevelopmentAction).filter_by(record_id=row.id).first()
    snapshot = (original_action.status, original_action.created_at, original_action.updated_at)
    write_talent_accounts(db, person, ResourcePersonUpdate(full_name=person.full_name,
        wechat_accounts=[*person_accounts(person), '已删微信', '已删企微'],
        wechat_accounts_revision=person.wechat_accounts_revision), actor=user)
    db.flush()
    for record in [row, second]:
        detail = serialize_record(db, user, record, True)
        assert detail['wechat_status'] == detail['enterprise_status'] == '（对方）已删'
        assert detail['progress']['wechat']['source'] == 'talent'
        assert record.wechat_status == '已添加'  # 统计底稿没有改动。
    assert not unrelated.contact_state
    assert db.query(DevelopmentAction).filter_by(record_id=row.id).count() == before_count
    assert (original_action.status, original_action.created_at, original_action.updated_at) == snapshot
    after_stats = report_item(db, user.id, row.work_date)
    assert before_stats == after_stats
    matched = filtered_records(db, user, None, None, state='（对方）已删').filter_by(person_id=person.id).count()
    assert matched == 2
    assert filtered_records(db, user, None, None, column_filters={'wechat_status': ['（对方）已删']}).filter_by(person_id=person.id).count() == 2
    assert filtered_records(db, user, None, None, column_filters={'friend_accounts_text': 'HR1'}).filter_by(id=row.id).count() == 1
    # 修改其他资料不重放旧的已添加历史。
    row = save_record(db, user, edited(payload, row, remarks='普通保存'))
    assert '已删微信' in person_accounts(person)
    assert serialize_record(db, user, row)['wechat_status'] == '（对方）已删'
    # 再次确认微信添加成功，只恢复微信，企微保持已删。
    row = save_record(db, user, edited(payload, row, actions=[*payload.model_dump()['actions'], action(user, '已添加')]))
    assert '已删微信' not in person_accounts(person) and '已删企微' in person_accounts(person)
    assert serialize_record(db, user, second)['wechat_status'] == '已添加'
    assert serialize_record(db, user, second)['enterprise_status'] == '（对方）已删'
    assert db.query(DevelopmentAudit).filter_by(entity_id=second.id, action='contact_sync').count() >= 3
    masked = serialize_record(db, other, second, True)
    assert masked['audit'] == [] and 'source_record_id' not in str(masked['progress'])
    # 总库取消企微删除标记，同步恢复。
    write_talent_accounts(db, person, ResourcePersonUpdate(full_name=person.full_name,
        wechat_accounts=[v for v in person_accounts(person) if v != '已删企微'],
        wechat_accounts_revision=person.wechat_accounts_revision), actor=user)
    assert serialize_record(db, user, row)['enterprise_status'] == '已添加'


def test_development_delete_only_latest_changed_action_is_synced(db, context):
    user = context[0]
    payload, row, person = enrolled(db, context, friend_accounts=['HR1'])
    deletion = edited(payload, row, actions=[*payload.model_dump()['actions'], action(user, '（对方）已删')])
    row = save_record(db, user, deletion)
    assert person_accounts(person) == ['HR1', '已删微信']
    revision = person.wechat_accounts_revision
    first = deletion.model_dump()['actions'][0] | {'status': '搜不到'}
    # 修正更早的操作不能覆盖最后的已删结论。
    row = save_record(db, user, edited(deletion, row, actions=[first, deletion.model_dump()['actions'][1]]))
    assert person.wechat_accounts_revision == revision and '已删微信' in person_accounts(person)


@pytest.mark.parametrize('writer', [update_talent, update_recruitment_talent])
def test_talent_writer_omission_legacy_and_revision_conflict(db, context, writer):
    user = context[0]
    payload, row, person = enrolled(db, context, friend_accounts=['HR1'])
    old_revision = person.wechat_accounts_revision
    payload = edited(payload, row, actions=[*payload.model_dump()['actions'], action(user, '（对方）已删')])
    row = save_record(db, user, payload)
    with pytest.raises(HTTPException) as error:
        writer(db, person.id, ResourcePersonUpdate(full_name=person.full_name, wechat_accounts=['HR2'],
            wechat_accounts_revision=old_revision), actor=user)
    assert error.value.status_code == 409
    writer(db, person.id, ResourcePersonUpdate(full_name=person.full_name, remarks='仅改备注'), actor=user)
    assert '已删微信' in person_accounts(person)
    writer(db, person.id, ResourcePersonUpdate(full_name=person.full_name, wechat_accounts=['其他'],
        wechat_accounts_revision=person.wechat_accounts_revision), actor=user)
    assert person_accounts(person) == ['其他']
    assert serialize_record(db, user, row)['wechat_status'] == '已添加'
    # 普通开拓保存不能重新填回总库主动移除的 HR1。
    row = save_record(db, user, edited(payload, row))
    assert person_accounts(person) == ['其他']
    writer(db, person.id, ResourcePersonUpdate(full_name=person.full_name, wechat_account='旧账号、原文'), actor=user)
    assert person_accounts(person) == ['旧账号、原文']


def test_sync_failure_rolls_back_accounts_versions_and_audit(db, context):
    user = context[0]
    payload, row, person = enrolled(db, context, friend_accounts=['HR1'])
    old_accounts, old_version, old_state = person_accounts(person), person.wechat_accounts_revision, dict(row.contact_state)
    audit_count = db.query(DevelopmentAudit).filter_by(entity_id=row.id).count()
    with db.begin_nested() as nested:
        with patch('talent_wechat_accounts.sync_channel', side_effect=RuntimeError('模拟同步失败')):
            with pytest.raises(RuntimeError):
                save_record(db, user, edited(payload, row, actions=[*payload.model_dump()['actions'], action(user, '（对方）已删')]))
        nested.rollback()
    assert person_accounts(person) == old_accounts and person.wechat_accounts_revision == old_version
    assert row.contact_state == old_state
    assert db.query(DevelopmentAudit).filter_by(entity_id=row.id).count() == audit_count


def test_legacy_talent_create_keeps_personal_wechat_independent(db, context):
    person = create_talent(db, ResourcePersonCreate(full_name='旧账号测试' + uuid4().hex,
        wechat_account='HR1、历史备注', wechat='personal_wechat'), commit=False, actor=context[0])
    assert person_accounts(person) == ['HR1、历史备注'] and person.wechat == 'personal_wechat'
