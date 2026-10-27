"""普通账号日常维护回归：仅内存 SQLite，不连接业务数据库。"""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from test_chat_participant_access import environment


@pytest.fixture
def daily(environment, monkeypatch):
    db, users = environment
    import resource_development_service as service
    import resource_arrangement_service as arrangements
    import resource_friend_daily_service as friends
    from resource_development_models import DevelopmentOption
    from resource_development_schemas import RecordWrite
    from database import get_db
    from routers.auth import get_current_user
    from routers.resource_development import router
    monkeypatch.setattr(service, 'lock_writes', lambda db: None)
    monkeypatch.setattr(service, 'refresh_draft', lambda *args: None)
    monkeypatch.setattr(service, 'can_delegate', lambda *args: False)
    monkeypatch.setattr(service, 'is_admin', lambda *args: False)
    monkeypatch.setattr(arrangements, 'lock_writes', lambda db: None)
    monkeypatch.setattr(friends, 'lock_writes', lambda db: None)
    monkeypatch.setattr(friends, 'can_delegate', lambda *args: False)
    monkeypatch.setattr('routers.auth.get_user_permission_codes', lambda *args: [])
    monkeypatch.setattr('routers.resource_development.can_delegate', lambda *args: False)
    monkeypatch.setattr('routers.resource_development.is_admin', lambda *args: False)
    monkeypatch.setattr('routers.resource_development.user_has_permission', lambda *args: False)
    platform = DevelopmentOption(id=uuid4(), kind='platform', category='national', name='隔离平台', code='ISOLATED')
    db.add(platform); db.commit()
    values = dict(id=uuid4(), platform_id=platform.id, owner_id=users[0].id,
                  work_date=date(2026, 10, 27), full_name='隔离资源')
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: users[2]
    with TestClient(app) as client:
        yield db, users, platform, values, service, client, app


def test_cross_person_edit_preserves_private_data_history_and_revision(daily, monkeypatch):
    db, (owner, _, editor), platform, values, service, client, app = daily
    from resource_development_schemas import RecordWrite
    from resource_development_models import DevelopmentAction, DevelopmentCustomValue, DevelopmentOption, DevelopmentFollowUp
    from resource_development_contacts import contact_data
    action_id, follow_id, field_id = uuid4(), uuid4(), uuid4()
    db.add(DevelopmentOption(id=field_id, kind='custom_field', name='受限字段', category='', description='', revision=1))
    payload = RecordWrite(**values, phone='13812345678', wechat='secret_wechat', whatsapp='secret_wa',
                          xiaohongshu='secret_red', remarks='secret_remark', follow_up='secret_legacy',
                          duplicate_note='secret_duplicate', custom_accounts=[dict(name='Telegram', value='secret_tg')],
                          custom_fields={field_id: 'secret_custom'},
                          actions=[dict(id=action_id, channel='communication', status='secret_status',
                                        action_date=values['work_date'], operator_id=owner.id)],
                          follow_ups=[dict(id=follow_id, content='secret_follow')])
    row = service.save_record(db, owner, payload); db.commit()
    row.contact_state = {'wechat': {'status': 'secret_overlay'}}
    db.commit()
    detail = client.get(f'/resource-development/records/{row.id}').json()
    assert detail['can_edit'] and detail['contact_restricted'] and not detail['audit']
    assert 'secret_' not in str(detail) and '13812345678' not in str(detail)
    assert service.filtered_records(db, editor, None, None, keyword='13812345678').count() == 0
    assert service.filtered_records(db, owner, None, None, keyword='13812345678').count() == 1
    assert service.filtered_records(db, editor, None, None, state='secret_overlay').count() == 0
    assert service.filtered_records(db, owner, None, None, state='secret_overlay').count() == 1
    assert service.record_name_duplicates(db, editor, row.full_name)['items'][0]['phone'] == ''
    malicious = payload.model_dump(mode='json') | dict(revision=row.revision, full_name='公开姓名修改',
                  phone='', wechat='******', whatsapp='', xiaohongshu='', remarks='受限内容',
                  follow_up='受限内容', custom_accounts=[], custom_fields={str(field_id): ''},
                  actions=[dict(id=str(uuid4()), channel='communication', status='已沟通',
                                action_date=str(values['work_date']), operator_id=str(editor.id))],
                  follow_ups=[dict(id=str(follow_id), content='恶意覆盖'),
                                          dict(id=str(uuid4()), content='新增普通跟进')])
    result = client.post('/resource-development/records', json=malicious)
    assert result.status_code == 200, result.text
    assert result.json()['contact_restricted'] and 'secret_' not in result.text
    db.expire_all()
    assert row.full_name == '公开姓名修改' and row.phone == '13812345678' and row.wechat == 'secret_wechat'
    assert row.remarks == 'secret_remark' and row.follow_up == 'secret_legacy'
    assert row.xiaohongshu == 'secret_red' and row.duplicate_note == 'secret_duplicate'
    assert contact_data(db, row.id)['custom_accounts'][0]['value'] == 'secret_tg'
    assert contact_data(db, row.id)['whatsapp'] == 'secret_wa'
    assert db.get(DevelopmentCustomValue, (row.id, field_id)).value == 'secret_custom'
    assert db.get(DevelopmentAction, action_id).status == 'secret_status'
    assert db.query(DevelopmentAction).filter_by(record_id=row.id).count() == 2
    assert db.get(DevelopmentFollowUp, follow_id).content == 'secret_follow'
    assert db.query(DevelopmentFollowUp).filter_by(record_id=row.id).count() == 2
    assert client.post('/resource-development/records', json=malicious).status_code == 409
    malicious.update(revision=row.revision, owner_id=str(editor.id))
    assert client.post('/resource-development/records', json=malicious).status_code == 403
    assert service.serialize_record(db, owner, row)['phone'] == '13812345678'
    monkeypatch.setattr(service, 'can_delegate', lambda *args: True)
    assert service.serialize_record(db, editor, row)['phone'] == '13812345678'


def test_zero_permission_entry_create_standard_progress_and_protected_routes(daily):
    db, users, platform, values, service, client, app = daily
    from resource_development_schemas import RecordWrite
    options = client.get('/resource-development/options')
    assert options.status_code == 200, options.text
    assert options.json()['can_write'] and not options.json()['can_configure'] and not options.json()['can_delegate']
    saved = client.post('/resource-development/records', json=RecordWrite(**values).model_dump(mode='json'))
    assert saved.status_code == 200, saved.text
    row = saved.json()
    action = dict(id=str(uuid4()), revision=row['revision'], channel='group_large', status='已发码')
    result = client.post(f"/resource-development/records/{row['id']}/group-actions", json=action)
    assert result.status_code == 200, result.text
    assert result.json()['contact_restricted'] and result.json()['progress']['group_large']['status'] == '已发码'
    assert client.get('/resource-development/days').status_code == 200
    assert client.get('/resource-development/records').json()['total'] == 1
    assert client.get('/resource-development/record-duplicates', params={'full_name': values['full_name']}).status_code == 200
    assert client.post('/resource-development/duplicates', json=RecordWrite(**values).model_dump(mode='json')).status_code == 200
    for method, path, kwargs in [
        ('delete', f"/records/{row['id']}?revision={result.json()['revision']}", {}),
        ('post', '/options', {'json': {'kind': 'account', 'name': '越权'}}),
        ('post', '/languages', {'json': {'label': '越权', 'language_type': 'language'}}),
        ('post', '/custom-fields', {'json': {'name': '越权'}}),
        ('post', '/import-preview', {}),
        ('get', '/channels', {}),
        ('post', '/friend-daily/accounts', {'json': {'channel': 'wechat', 'name': 'HR100'}}),
    ]:
        denied = client.request(method, '/resource-development' + path, **kwargs)
        assert denied.status_code == 403, (path, denied.text)
    app.dependency_overrides.clear()
    assert client.get('/resource-development/options').status_code == 401


def test_cross_person_work_can_save_without_exposing_explanation_or_screenshot(daily):
    db, (owner, _, editor), platform, values, service, client, app = daily
    from resource_development_schemas import WorkWrite
    from resource_development_models import DevelopmentScreenshot
    work = service.save_work(db, owner, WorkWrite(work_date=values['work_date'], owner_id=owner.id,
                                                periods=[], completed=False, explanation='secret_explanation'))
    screenshot = DevelopmentScreenshot(work_id=work.id, name='secret_filename', content_type='image/png',
                                       content=b'private', created_by=owner.id)
    db.add(screenshot); db.commit()
    params = {'work_date': str(values['work_date']), 'owner_id': str(owner.id)}
    data = client.get('/resource-development/work', params=params).json()
    assert data['can_edit'] and data['contact_restricted'] and data['screenshots'] == []
    assert 'secret_' not in str(data)
    payload = dict(work_date=params['work_date'], owner_id=params['owner_id'], revision=work.revision,
                   periods=[dict(start='09:00', end='10:00')], completed=True, explanation='受限内容')
    result = client.put('/resource-development/work', json=payload)
    assert result.status_code == 200, result.text
    assert result.json()['duration_minutes'] == 60
    assert work.explanation == 'secret_explanation'
    assert client.get(f'/resource-development/screenshots/{screenshot.id}').status_code == 403
    assert client.put('/resource-development/work', json=payload).status_code == 409


def test_arrangements_open_to_zero_permission_users_with_conflict_protection(daily):
    db, (owner, _, editor), platform, values, service, client, app = daily
    path = '/resource-development/arrangements/2026-10-27'
    payload = dict(revision=0, cells=[dict(platform_id=str(platform.id), owner_id=str(owner.id), role_tags=['客服'])])
    result = client.put(path, json=payload)
    assert result.status_code == 200, result.text
    assert result.json()['can_manage'] and result.json()['cells'][0]['can_edit']
    revision = result.json()['revision']
    complete = client.patch(path + f'/cells/{platform.id}/completion', json=dict(revision=revision, completed=True))
    assert complete.status_code == 200, complete.text
    assert complete.json()['cells'][0]['completed']
    assert client.put(path, json=payload).status_code == 409
    carried = client.get('/resource-development/arrangements/2026-10-28/carry-preview')
    assert carried.status_code == 200, carried.text
    payload = dict(revision=complete.json()['revision'], cells=[dict(platform_id=str(platform.id), owner_id=str(editor.id), role_tags=['HR'])])
    changed = client.put(path, json=payload)
    assert changed.status_code == 200, changed.text
    assert changed.json()['cells'][0]['owner_id'] == str(editor.id)


def test_friend_daily_write_open_but_account_configuration_stays_protected(daily, monkeypatch):
    db, users, platform, values, service, client, app = daily
    import resource_friend_daily_service as friends
    snapshot = SimpleNamespace(payload={'columns': [dict(key='w', label='HR1')], 'rows': []}, revision=1)
    monkeypatch.setattr(friends, 'locked_overview', lambda db: snapshot)
    path = '/resource-development/friend-daily/2026-10-27'
    line = dict(channel='wechat', column_key='w', language_value='__unknown__', count=3)
    result = client.put(path, json=dict(revision=0, rows=[line]))
    assert result.status_code == 200, result.text
    assert result.json()['can_write'] and not result.json()['can_configure']
    assert result.json()['totals']['wechat'] == 3 and snapshot.payload['rows'][0]['counts']['w'] == 3
    result = client.put(path, json=dict(revision=1, rows=[line | dict(count=5)]))
    assert result.status_code == 200 and snapshot.payload['rows'][0]['counts']['w'] == 5
    assert client.put(path, json=dict(revision=1, rows=[])).status_code == 409

