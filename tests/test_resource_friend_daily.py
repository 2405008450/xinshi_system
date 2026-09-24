"""群聊日报的真实数据库事务回归；复用局域网限定、逐例回滚的测试会话。"""
from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_resource_development import db, context  # noqa: F401
from resource_friend_daily_service import FriendWrite, FriendLine, FriendAccountWrite, save_daily, get_options, add_account, serialize
from talent_overview_service import get_talent_overview
from resource_development_models import DevelopmentFriendDaily as Daily


@pytest.fixture
def setup(db, context):
    user, other, _ = context
    with patch('resource_friend_daily_service.can_delegate', side_effect=lambda _, u: u.id == user.id):
        options = get_options(db, user)
        language = next(l for l in options['languages'] if l['overview_key'])
        account = next(a for a in options['accounts'] if a['channel'] == 'wechat')
        enterprise = next(a for a in options['accounts'] if a['channel'] == 'enterprise')
        day = date(2098, 1, 2)
        # 不覆盖任何已有日报，数据写入均被外层事务回滚。
        assert db.query(Daily).filter(Daily.work_date.between(day, day + timedelta(days=10))).count() == 0
        yield user, other, day, language, account, enterprise


def line(language, account, count, **changes):
    return dict(channel=account['channel'], column_key=account['key'], language_value=language['id'], overview_key=language['overview_key'], count=count, **changes)


def value(db, language, account):
    row = next(r for r in get_talent_overview(db)['rows'] if r['overview_key'] == language['overview_key'])
    return row['counts'][account['key']] or 0


def test_delta_retry_other_day_and_remove(db, setup):
    user, _, day, lang, account, ent = setup
    base = value(db, lang, account)
    first = save_daily(db, user, day, FriendWrite(rows=[line(lang, account, 5)]))
    assert value(db, lang, account) == base + 5
    retry = FriendWrite(revision=0, rows=[{k: r.get(k) for k in FriendLine.model_fields} for r in first.rows])
    assert save_daily(db, user, day, retry).revision == 1
    assert value(db, lang, account) == base + 5
    edited = save_daily(db, user, day, FriendWrite(revision=1, rows=[line(lang, account, 7)]))
    assert edited.revision == 2 and value(db, lang, account) == base + 7
    save_daily(db, user, day + timedelta(days=1), FriendWrite(rows=[line(lang, account, 3)]))
    assert value(db, lang, account) == base + 10
    save_daily(db, user, day, FriendWrite(revision=2, rows=[]))
    assert value(db, lang, account) == base + 3
    assert len(serialize(db, edited, day, user)['audit']) == 3


def test_channels_blank_zero_and_no_talent(db, setup):
    from resource_models import ResourcePerson
    user, _, day, lang, account, ent = setup
    talent_count = db.query(ResourcePerson).count()
    baseline = value(db, lang, ent)
    row = save_daily(db, user, day, FriendWrite(rows=[line(lang, account, 0), line(lang, ent, None)]))
    assert [r['count'] for r in row.rows] == [0, None]
    row = save_daily(db, user, day, FriendWrite(revision=1, rows=[line(lang, account, 0), line(lang, ent, 9)]))
    assert value(db, lang, ent) == baseline + 9
    assert serialize(db, row, day, user)['totals'] == {'wechat': 0, 'enterprise': 9}
    assert db.query(ResourcePerson).count() == talent_count


def test_stale_and_permission(db, setup):
    user, other, day, lang, account, _ = setup
    save_daily(db, user, day, FriendWrite(rows=[line(lang, account, 2)]))
    with pytest.raises(HTTPException) as exc:
        save_daily(db, user, day, FriendWrite(rows=[line(lang, account, 8)]))
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as exc:
        save_daily(db, other, day, FriendWrite(revision=1, rows=[]))
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        add_account(db, other, FriendAccountWrite(channel='wechat', name='HR100'))
    assert exc.value.status_code == 403
    assert not get_options(db, other)['can_write']


def test_duplicates_and_channel_mismatch_rollback(db, setup):
    user, _, day, lang, account, _ = setup
    for rows in [[line(lang, account, 2), line(lang, account, 3)], [line(lang, account, 2) | {'channel': 'enterprise'}]]:
        base = value(db, lang, account)
        with db.begin_nested() as nested:
            with pytest.raises(HTTPException) as exc:
                save_daily(db, user, day, FriendWrite(rows=rows))
            assert exc.value.status_code == 422
            nested.rollback()
        assert value(db, lang, account) == base
        assert db.query(Daily).filter_by(work_date=day).count() == 0


def test_new_dialect_shared_by_two_accounts_and_rollback(db, setup):
    from interpretation_models import InterpretationLanguage
    user, _, day, lang, account, ent = setup
    name = '测试方言' + uuid4().hex[:12]
    common = dict(language_value=name, language_type='dialect', overview_key='__new__', count=4)
    baseline = len(get_talent_overview(db)['rows'])
    with db.begin_nested() as nested:
        row = save_daily(db, user, day, FriendWrite(rows=[dict(channel=a['channel'], column_key=a['key'], **common) for a in [account, ent]]))
        assert row.rows[0]['overview_key'] == row.rows[1]['overview_key']
        assert len(get_talent_overview(db)['rows']) == baseline + 1
        assert db.query(InterpretationLanguage).filter_by(label=name).one().language_type == 'dialect'
        nested.rollback()
    assert len(get_talent_overview(db)['rows']) == baseline
    assert db.query(InterpretationLanguage).filter_by(label=name).count() == 0
    assert db.query(Daily).filter_by(work_date=day).count() == 0


def test_explicit_mapping_and_account_dedup(db, setup):
    from interpretation_models import InterpretationLanguage
    user, _, day, lang, account, _ = setup
    name = '测试别称' + uuid4().hex[:12]
    payload = line(lang, account, 3) | {'language_value': name}
    row = save_daily(db, user, day, FriendWrite(rows=[payload]))
    assert row.rows[0]['overview_key'] == lang['overview_key']
    assert db.query(InterpretationLanguage).filter_by(label=name).one().talent_overview_key == lang['overview_key']
    created = add_account(db, user, FriendAccountWrite(name='测试账号' + uuid4().hex[:8], channel='enterprise'))
    again = add_account(db, user, FriendAccountWrite(name=created['label'], channel='enterprise'))
    assert again['key'] == created['key']
    assert next(c for c in get_talent_overview(db)['columns'] if c['key'] == created['key'])['group'] == 'wecom'


@pytest.mark.parametrize('count', [-1, 1.5, True, '3', 1000001])
def test_invalid_count(count):
    with pytest.raises(ValidationError):
        FriendLine(channel='wechat', column_key='hr1Sheet', language_value='英语', count=count)


def test_overview_manual_edit_and_missing_cell_protection(db, setup):
    import copy
    from talent_overview_models import TalentOverviewSnapshot
    user, _, day, lang, account, _ = setup
    save_daily(db, user, day, FriendWrite(rows=[line(lang, account, 5)]))
    snap = db.get(TalentOverviewSnapshot, 1)
    data = copy.deepcopy(snap.payload)
    target = next(r for r in data['rows'] if r['overview_key'] == lang['overview_key'])
    target['counts'][account['key']] += 20
    expected = target['counts'][account['key']] + 2
    snap.payload = data; snap.revision += 1; db.flush()
    save_daily(db, user, day, FriendWrite(revision=1, rows=[line(lang, account, 7)]))
    assert value(db, lang, account) == expected
    data = copy.deepcopy(snap.payload)
    next(r for r in data['rows'] if r['overview_key'] == lang['overview_key'])['counts'][account['key']] = 0
    snap.payload = data; db.flush()
    with pytest.raises(HTTPException) as exc:
        save_daily(db, user, day, FriendWrite(revision=2, rows=[]))
    assert exc.value.status_code == 409


def test_history_range_pagination(db, setup):
    from routers.resource_friend_daily import list_days
    user, _, day, lang, account, _ = setup
    for i in range(9):
        save_daily(db, user, day + timedelta(days=i), FriendWrite(rows=[line(lang, account, i)]))
    result = list_days(day, day + timedelta(days=8), 7, 7, db, user)
    assert result['total'] == 9 and len(result['items']) == 2
    assert [r['work_date'] for r in result['items']] == [(day + timedelta(days=1)).isoformat(), day.isoformat()]
    assert result['items'][0]['totals']['wechat'] == 1


def test_concurrent_daily_save_in_isolated_schema():
    import os
    if os.getenv('RUN_RESOURCE_DEVELOPMENT_DB_TESTS') != '1':
        pytest.skip('需要局域网 PostgreSQL')
    import main  # noqa: F401
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from database import engine
    from interpretation_models import InterpretationLanguage
    from talent_overview_service import load_talent_overview_data
    schema = 'test_friend_daily_' + uuid4().hex
    fixture = load_talent_overview_data()
    language = {'id': str(uuid4()), 'overview_key': fixture['rows'][0]['overview_key']}
    account = {'channel': 'wechat', 'key': 'hr1Sheet'}
    user = SimpleNamespace(id=uuid4())
    day = date(2098, 2, 1)
    tables = ['resource_development_friend_daily', 'resource_development_audit', 'talent_overview_snapshot', 'interpretation_language', 'interpretation_language_alias']
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            for table in tables:
                conn.execute(text(f'CREATE TABLE "{schema}".{table} (LIKE public.{table} INCLUDING ALL)'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            with Session(bind=conn) as session:
                session.add(InterpretationLanguage(id=language['id'], label=fixture['rows'][0]['language'], talent_overview_key=language['overview_key'], language_type='language', is_active=True))
                session.flush()
        def submit(count):
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
                    with Session(bind=conn) as session:
                        save_daily(session, user, day, FriendWrite(rows=[line(language, account, count)]))
                return 200
            except HTTPException as exc:
                return exc.status_code
        with patch('resource_friend_daily_service.can_delegate', return_value=True):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(submit, [3, 7]))
        assert sorted(results) == [200, 409]
        with engine.begin() as conn:
            assert conn.execute(text(f'SELECT count(*) FROM "{schema}".resource_development_friend_daily')).scalar_one() == 1
            payload = conn.execute(text(f'SELECT payload FROM "{schema}".talent_overview_snapshot')).scalar_one()
            increment = payload['rows'][0]['counts']['hr1Sheet'] - (fixture['rows'][0]['counts']['hr1Sheet'] or 0)
            assert increment in [3, 7]
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def test_http_roundtrip_and_read_only_access(db, setup):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.resource_development import router
    user, other, day, lang, account, _ = setup
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    access = router.dependencies[0].dependency
    app.dependency_overrides[access] = lambda: None
    client = TestClient(app)
    path = '/resource-development/friend-daily/' + day.isoformat()
    assert client.get(path).json()['revision'] == 0
    payload = {'revision': 0, 'rows': [line(lang, account, 6)]}
    saved = client.put(path, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()['totals']['wechat'] == 6
    assert saved.json()['updated_by_name'] == user.full_name
    assert client.put(path, json=payload).json()['revision'] == 1
    assert client.get(path).json()['rows'][0]['count'] == 6
    app.dependency_overrides[get_current_user] = lambda: other
    assert client.get(path).status_code == 200
    assert client.put(path, json={'revision': 1, 'rows': []}).status_code == 403
    del app.dependency_overrides[access]
    assert client.get(path).status_code == 403


def test_existing_hr_account_names_do_not_duplicate(db, setup):
    user, _, _, _, _, _ = setup
    opts = get_options(db, user)
    existing = next(a for a in opts['accounts'] if a['label'].startswith('HR3') and a['channel'] == 'enterprise')
    assert add_account(db, user, FriendAccountWrite(name='HR3企微', channel='enterprise'))['key'] == existing['key']
    with pytest.raises(HTTPException) as exc:
        add_account(db, user, FriendAccountWrite(name='HR3企微', channel='wechat'))
    assert exc.value.status_code == 422
