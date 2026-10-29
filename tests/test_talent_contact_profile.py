from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Column, Date, DateTime, JSON, MetaData, String, Table, Uuid, create_engine, text
from sqlalchemy.orm import Session

from resource_schemas import ResourcePersonCreate, ResourcePersonUpdate
from talent_wecom_group_status import get_talent_wecom_group_status, summarize_group_status
from tools.apply_talent_contact_profile_migration import apply_migration


@pytest.mark.parametrize('schema', [ResourcePersonCreate, ResourcePersonUpdate])
def test_contact_profile_fields_are_independent_and_can_be_cleared(schema):
    payload = schema(full_name='联系资料', wechat_groups='小群', wecom_large_groups='  大群一\n大群二  ',
                     residence_timezone='UTC+08:00', contact_availability='evening')
    assert payload.wechat_groups == '小群'
    assert payload.wecom_large_groups == '大群一\n大群二'
    assert payload.residence_timezone == 'UTC+8'
    assert payload.contact_availability == 'evening'
    assert schema(full_name='清空', wecom_large_groups=' ', residence_timezone=' ', contact_availability=None).residence_timezone is None


@pytest.mark.parametrize('value', ['UTC+14:15', 'UTC-12:15', 'UTC+8:17', 'UTC+99', 'GMT+8'])
def test_invalid_timezone_is_rejected(value):
    with pytest.raises(ValidationError):
        ResourcePersonCreate(full_name='时区', residence_timezone=value)


def test_contact_availability_and_group_limits():
    with pytest.raises(ValidationError):
        ResourcePersonCreate(full_name='时段', contact_availability='unknown')
    with pytest.raises(ValidationError):
        ResourcePersonCreate(full_name='群名', wecom_large_groups='群' * 4001)


def test_group_status_defaults_aliases_and_channel_independence():
    assert summarize_group_status([], []) == {'wecom_small_group_status': None, 'wecom_large_group_status': None}
    record = SimpleNamespace(id=uuid4(), work_date=date(2026, 10, 20), historical_markers={
        'group': {'status': '已邀进群'}, 'group_large': {'status': '已发码'},
    })
    assert summarize_group_status([record], []) == {'wecom_small_group_status': '已拉群', 'wecom_large_group_status': '已发码'}
    actions = [SimpleNamespace(id=uuid4(), channel='group', status='已退群', created_at=datetime(2026, 10, 21, 8))]
    assert summarize_group_status([record], actions)['wecom_small_group_status'] == '已退群'
    record.historical_markers = {'group': {'status': '含私人信息的原文'}}
    assert summarize_group_status([record], [])['wecom_small_group_status'] == '自定义状态'


def test_group_status_queries_linked_records_and_tracks_updates(monkeypatch):
    # 仅在内存库创建查询涉及的最小列，不连接业务数据库。
    import main  # noqa: F401
    engine = create_engine('sqlite:///:memory:')
    meta = MetaData()
    records = Table('resource_development_record', meta, Column('id', Uuid, primary_key=True),
                    Column('person_id', Uuid), Column('historical_markers', JSON), Column('work_date', Date))
    actions = Table('resource_development_action', meta, Column('id', Uuid, primary_key=True),
                    Column('record_id', Uuid), Column('channel', String), Column('status', String), Column('created_at', DateTime))
    meta.create_all(engine)
    person, inherited, other = uuid4(), uuid4(), uuid4()
    monkeypatch.setattr('talent_duplicate_service.family_ids', lambda *_: [person, inherited])
    first, second, unrelated = uuid4(), uuid4(), uuid4()
    try:
        with Session(engine) as db:
            db.execute(records.insert(), [dict(id=identifier, person_id=owner, historical_markers={}, work_date=date(2026, 10, 20))
                                         for identifier, owner in [(first, person), (second, inherited), (unrelated, other)]])
            for record_id, channel, status, hour in [(first, 'group', '已进群', 9), (second, 'group', '已退群', 10),
                                                    (second, 'group_large', '已发码', 8), (unrelated, 'group_large', '已进群', 11)]:
                db.execute(actions.insert().values(id=uuid4(), record_id=record_id, channel=channel, status=status,
                                                   created_at=datetime(2026, 10, 21, hour)))
            assert get_talent_wecom_group_status(db, person) == {'wecom_small_group_status': '已退群', 'wecom_large_group_status': '已发码'}
            db.execute(actions.insert().values(id=uuid4(), record_id=first, channel='group_large', status='已进群',
                                               created_at=datetime(2026, 10, 21, 12)))
            assert get_talent_wecom_group_status(db, person)['wecom_large_group_status'] == '已进群'
    finally:
        engine.dispose()


def test_contact_profile_migration_is_idempotent_and_preserves_existing_data():
    engine = create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE resource_person (id INTEGER PRIMARY KEY, wechat_groups TEXT)'))
            connection.execute(text("INSERT INTO resource_person VALUES (1, '原有小群')"))
            apply_migration(connection)
            connection.execute(text("UPDATE resource_person SET wecom_large_groups='新大群', residence_timezone='UTC+8', contact_availability='evening'"))
            apply_migration(connection)
            assert tuple(connection.execute(text('SELECT wechat_groups, wecom_large_groups, residence_timezone, contact_availability FROM resource_person')).one()) == ('原有小群', '新大群', 'UTC+8', 'evening')
    finally:
        engine.dispose()
