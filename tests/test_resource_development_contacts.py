"""联系方式拆分防止渠道串列、占位词和第三方 ID 误入本人字段。"""
from types import SimpleNamespace

from resource_development_contacts import classify_contact
from tools.reconcile_resource_development_contacts_20261026 import proposed_changes


def test_labeled_xiaohongshu_stays_out_of_phone_and_wechat():
    parsed = classify_contact("18724142714（小红书号）")
    assert parsed["xiaohongshu"] == "18724142714"
    assert parsed["phone"] == parsed["wechat"] == ""
    old = SimpleNamespace(phone="18724142714", wechat="18724142714（小红书号）", xiaohongshu="")
    changes, conflicts = proposed_changes(old, "18724142714（小红书号）", parsed)
    assert not conflicts
    assert changes["phone"]["after"] == ""
    assert changes["wechat"]["after"] == ""
    assert changes["xiaohongshu"]["after"] == "18724142714"


def test_missing_and_third_party_are_not_person_contacts():
    for raw in ("未提供", "他推的朋友id：dionvdam（陈大伟）"):
        parsed = classify_contact(raw)
        assert not any(parsed[field] for field in ("phone", "wechat", "xiaohongshu"))
        assert parsed["other"] == raw


def test_explicit_phone_and_wechat_split():
    parsed = classify_contact("电话：15858725540微信：Ix0814xI")
    assert parsed["phone"] == "15858725540"
    assert parsed["wechat"] == "Ix0814xI"


def test_existing_distinct_contact_is_kept():
    parsed = classify_contact("JamieFromTheUK（小红书号）")
    old = SimpleNamespace(phone="", wechat="existing_wechat", xiaohongshu="")
    changes, conflicts = proposed_changes(old, "JamieFromTheUK（小红书号）", parsed)
    assert not conflicts
    assert "wechat" not in changes
    assert changes["xiaohongshu"]["after"] == "JamieFromTheUK"

"""只使用隔离内存库验证扩展账号；不访问业务数据库。"""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from resource_development_schemas import RecordWrite
from test_chat_participant_access import environment


def payload(**extra):
    return RecordWrite(id=uuid4(), platform_id=uuid4(), owner_id=uuid4(), work_date=date(2026, 10, 26), full_name='隔离测试', **extra)


def test_contact_validation_limits_and_unique_names():
    row = payload(whatsapp='  +852 1234 5678 ', custom_accounts=[{'name': ' Telegram ', 'value': ' abc '}])
    assert row.whatsapp == '+852 1234 5678'
    assert row.custom_accounts[0].model_dump() == {'name': 'Telegram', 'value': 'abc'}
    for extra in [dict(whatsapp='x' * 101), dict(custom_accounts=[{'name': '', 'value': 'a'}]),
                  dict(custom_accounts=[{'name': 'Telegram', 'value': 'a'}, {'name': 'telegram', 'value': 'b'}]),
                  dict(custom_accounts=[{'name': 'WhatsApp', 'value': 'a'}]),
                  dict(custom_accounts=[{'name': 'Skype', 'value': ''}])]:
        with pytest.raises(ValidationError):
            payload(**extra)


def test_migration_save_reload_mask_audit_clear_and_legacy_preservation():
    import main  # 注册模型，不调用 startup。
    from resource_development_models import DevelopmentAudit, DevelopmentResourceContact
    from resource_development_contacts import save_contacts, contact_data
    from tools.apply_resource_development_contacts_migration import apply_migration
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE resource_development_record (id CHAR(32) PRIMARY KEY)'))
        connection.execute(text('INSERT INTO resource_development_record (id) VALUES (:id)'), {'id': 'a' * 32})
        DevelopmentAudit.__table__.create(connection)
        apply_migration(connection)
        apply_migration(connection)
        assert len(inspect(connection).get_columns('resource_development_record')) == 1
        assert connection.execute(text('SELECT count(*) FROM resource_development_record')).scalar() == 1
    with Session(engine) as db:
        actor, record_id = SimpleNamespace(id=uuid4()), uuid4()
        save_contacts(db, actor, record_id, payload(whatsapp='wa', custom_accounts=[{'name': 'Telegram', 'value': 'tg'}]))
        db.commit(); db.expire_all()
        assert contact_data(db, record_id)['whatsapp'] == 'wa'
        assert contact_data(db, record_id)['custom_accounts'] == [{'name': 'Telegram', 'value': 'tg'}]
        assert contact_data(db, record_id, False)['whatsapp'] == '******'
        assert contact_data(db, record_id, False)['custom_accounts_text'] == '资源Telegram号：******'
        save_contacts(db, actor, record_id, payload())
        db.commit()
        assert contact_data(db, record_id)['whatsapp'] == 'wa'
        assert db.query(DevelopmentAudit).count() == 1
        save_contacts(db, actor, record_id, payload(whatsapp='', custom_accounts=[]))
        db.commit(); db.expire_all()
        assert contact_data(db, record_id)['custom_accounts'] == []
        assert contact_data(db, record_id)['whatsapp'] == ''
        assert db.query(DevelopmentAudit).count() == 2
        assert db.query(DevelopmentResourceContact).count() == 1
    engine.dispose()


def test_options_default_is_current_hong_kong_date(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from unittest.mock import MagicMock
    from routers import resource_development as router
    now = datetime(2026, 10, 26, 12, tzinfo=timezone(timedelta(hours=8)))
    monkeypatch.setattr(router, 'business_now', lambda: now)
    monkeypatch.setattr(router, 'arrangement_platforms', lambda db: [])
    monkeypatch.setattr(router, 'is_admin', lambda *args: False)
    monkeypatch.setattr(router, 'can_delegate', lambda *args: False)
    monkeypatch.setattr(router, 'user_has_permission', lambda *args: False)
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value = []
    result = router.options(db, SimpleNamespace(id=uuid4()))
    assert result['default_date'] == '2026-10-26'


def test_record_service_roundtrip_search_and_privacy(environment, monkeypatch):
    db, users = environment
    owner, _, outsider = users
    from resource_development_models import DevelopmentOption
    import resource_development_service as service
    from routers.resource_development import filters
    platform = DevelopmentOption(id=uuid4(), kind='platform', category='national', name='isolated contacts', code='ISOLATED')
    db.add(platform); db.commit()
    monkeypatch.setattr(service, 'lock_writes', lambda db: None)
    monkeypatch.setattr(service, 'refresh_draft', lambda *args: None)
    monkeypatch.setattr(service, 'can_delegate', lambda db, user: False)
    monkeypatch.setattr(service, 'is_admin', lambda db, user: False)
    values = dict(id=uuid4(), platform_id=platform.id, owner_id=owner.id, work_date=date(2026, 10, 26), full_name='contacts resource')
    row = service.save_record(db, owner, RecordWrite(**values, whatsapp='WA%_123', custom_accounts=[{'name':'Telegram', 'value':'TG456'}]))
    db.commit()
    assert service.serialize_record(db, owner, row, True)['whatsapp'] == 'WA%_123'
    assert service.serialize_record(db, outsider, row, True)['custom_accounts'][0]['value'] == '******'
    query = lambda user, **kw: service.filtered_records(db, user, None, None, **kw)
    assert query(owner, keyword='WA%_123').count() == 1
    assert query(outsider, keyword='WA%_123').count() == 0
    assert query(owner, column_filters={'custom_accounts_text':'TG456'}).count() == 1
    assert query(outsider, column_filters={'custom_accounts_text':'TG456'}).count() == 0
    service.save_record(db, owner, RecordWrite(**values, revision=row.revision))
    db.commit()
    assert service.serialize_record(db, owner, row)['whatsapp'] == 'WA%_123'
    service.save_record(db, owner, RecordWrite(**values, revision=row.revision, whatsapp='', custom_accounts=[]))
    db.commit()
    assert service.serialize_record(db, owner, row)['whatsapp'] == ''
