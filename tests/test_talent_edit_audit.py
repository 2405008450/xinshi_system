"""内存隔离库验证编辑历史、权限、版本保护和事务，不访问业务数据库。"""
from datetime import timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect, text

from test_chat_participant_access import environment


def person(db):
    from business_time import business_now
    from resource_models import ResourcePerson
    row = ResourcePerson(id=uuid4(), resource_code='AUDIT-001', full_name='编辑测试',
                         primary_phone='old-phone', remarks='旧备注', status='standby',
                         updated_at=business_now())
    db.add(row)
    db.commit()
    return row


def test_difference_permissions_pagination_and_retention(environment):
    from talent_edit_audit import begin_edit, finish_edit, edit_history, TalentEditLog
    db, users = environment
    row = person(db)
    before = begin_edit(db, row)
    row.primary_phone = 'new-phone'
    row.remarks = '新备注'
    finish_edit(db, row, before, users[0])
    db.commit()
    history = edit_history(db, row.id, contacts_visible=True)
    assert history['total'] == 1
    event = history['items'][0]
    assert event['actor_account'] == users[0].username
    assert event['created_at'].endswith('+08:00')
    assert event['changes'] == {'primary_phone': {'before': 'old-phone', 'after': 'new-phone'},
                                'remarks': {'before': '旧备注', 'after': '新备注'}}
    assert edit_history(db, row.id)['items'][0]['changes']['primary_phone']['before'] == '******'
    assert edit_history(db, row.id, skip=1)['items'] == []
    finish_edit(db, row, begin_edit(db, row), users[1])
    db.commit()
    assert db.query(TalentEditLog).count() == 1
    # 历史无需主档外键：删除主档后仍留存在审计表。
    db.delete(row)
    db.commit()
    assert db.query(TalentEditLog).one().person_name == '编辑测试'


def test_transaction_rollback_and_stale_version(environment, monkeypatch):
    from resource_service import update_talent_status
    from talent_edit_audit import begin_edit, finish_edit, TalentEditLog
    from business_time import BUSINESS_TIMEZONE
    import resource_service
    db, users = environment
    row = person(db)
    before = begin_edit(db, row)
    row.remarks = '不能保存'
    finish_edit(db, row, before, users[0])
    db.flush()
    db.rollback()
    assert db.get(type(row), row.id).remarks == '旧备注'
    assert db.query(TalentEditLog).count() == 0
    current_utc = row.updated_at.replace(tzinfo=BUSINESS_TIMEZONE).astimezone(timezone.utc)
    assert begin_edit(db, row, current_utc)['remarks'] == '旧备注'
    with pytest.raises(HTTPException) as stale:
        begin_edit(db, row, current_utc - timedelta(microseconds=1))
    assert stale.value.status_code == 409
    assert stale.value.detail['code'] == 'talent_version_conflict'
    monkeypatch.setattr(resource_service, 'lock_account_writes', lambda db: None)
    monkeypatch.setattr(resource_service, '_sync_legacy_translator', lambda *args: None)
    update_talent_status(db, row.id, 'active', actor=users[1])
    event = db.query(TalentEditLog).one()
    assert event.source == 'quick_status' and event.actor_id == users[1].id
    assert event.changes['status'] == {'before': 'standby', 'after': 'active'}


def test_nested_resume_settlement_and_no_fake_collection_ids(environment):
    from talent_edit_audit import begin_edit, finish_edit, edit_history
    from talent_resume_profile import TalentResumeProfile
    from talent_settlement import TalentSettlement
    from business_time import business_now
    db, users = environment
    row = person(db)
    db.add(TalentResumeProfile(person_id=row.id, revision=1, data={'self_assessment': '旧自评'}, updated_at=business_now()))
    db.add(TalentSettlement(person_id=row.id, revision=1, bank_account='秘密银行卡', prices=[], updated_at=business_now()))
    db.commit()
    before = begin_edit(db, row)
    resume = db.get(TalentResumeProfile, row.id)
    resume.data = {'self_assessment': '新自评'}
    db.get(TalentSettlement, row.id).bank_account = '新银行卡'
    finish_edit(db, row, before, users[0], 'resume_import')
    db.commit()
    changes = edit_history(db, row.id, contacts_visible=True)['items'][0]['changes']
    assert changes['resume_profile.self_assessment']['after'] == '新自评'
    assert changes['settlement.bank_account']['before'] == '秘密银行卡'
    masked = edit_history(db, row.id)['items'][0]['changes']
    assert masked['settlement.bank_account']['after'] == '******'
    assert masked['resume_profile.self_assessment']['after'] == '新自评'


def test_full_form_edits_and_noop_do_not_duplicate_history(environment, monkeypatch):
    import resource_service
    from resource_schemas import ResourcePersonUpdate
    from talent_edit_audit import TalentEditLog
    db, users = environment
    row = person(db)
    monkeypatch.setattr(resource_service, 'lock_account_writes', lambda db: None)
    monkeypatch.setattr(resource_service, '_sync_legacy_translator', lambda *args: None)
    payload = ResourcePersonUpdate(full_name=row.full_name, resource_code=row.resource_code,
                                   remarks='根据简历补充', expected_updated_at=row.updated_at)
    resource_service.update_talent(db, row.id, payload, actor=users[0])
    assert db.query(TalentEditLog).one().changes['remarks']['after'] == '根据简历补充'
    payload.expected_updated_at = row.updated_at
    resource_service.update_talent(db, row.id, payload, actor=users[1])
    assert db.query(TalentEditLog).count() == 1


def test_migration_idempotence_and_fail_closed_before_migration(environment):
    from talent_edit_audit import begin_edit
    from tools.apply_talent_edit_audit_migration import apply_migration
    db, _ = environment
    row = person(db)
    db.execute(text('DROP TABLE talent_edit_log'))
    with pytest.raises(HTTPException) as missing:
        begin_edit(db, row)
    assert missing.value.status_code == 503
    apply_migration(db.connection())
    apply_migration(db.connection())
    assert {item['name'] for item in inspect(db.connection()).get_indexes('talent_edit_log')} == {
        'ix_talent_edit_log_person_time', 'ix_talent_edit_log_actor_time'}
    assert begin_edit(db, row)['remarks'] == '旧备注'
