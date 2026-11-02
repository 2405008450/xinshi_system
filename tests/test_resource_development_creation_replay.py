"""旧草稿创建标识冲突回归；只使用隔离内存 SQLite。"""
from test_resource_development_daily_access import daily
from test_chat_participant_access import environment


def test_stale_draft_cannot_report_other_record_as_created(daily):
    db, users, platform, values, service, client, app = daily
    from resource_development_schemas import RecordWrite
    from resource_development_models import DevelopmentRecord

    original = RecordWrite(**values).model_dump(mode='json')
    first = client.post('/resource-development/records', json=original)
    assert first.status_code == 200, first.text
    retry = client.post('/resource-development/records', json=original)
    assert retry.status_code == 200 and retry.json()['id'] == first.json()['id']

    stale = dict(original, full_name='Maksim Belonogov')
    result = client.post('/resource-development/records', json=stale)
    assert result.status_code == 409, result.text
    assert result.json()['detail']['code'] == 'creation_id_conflict'
    assert db.query(DevelopmentRecord).count() == 1
    db.expire_all()
    assert db.query(DevelopmentRecord).one().full_name == original['full_name']

    from uuid import uuid4
    stale['id'] = str(uuid4())
    saved = client.post('/resource-development/records', json=stale)
    assert saved.status_code == 200, saved.text
    assert saved.json()['full_name'] == stale['full_name']
    assert db.query(DevelopmentRecord).count() == 2


def test_other_user_cannot_replay_existing_creation_identifier(daily):
    db, users, platform, values, service, client, app = daily
    from resource_development_schemas import RecordWrite
    from routers.auth import get_current_user
    original = RecordWrite(**values).model_dump(mode='json')
    assert client.post('/resource-development/records', json=original).status_code == 200
    app.dependency_overrides[get_current_user] = lambda: users[0]
    result = client.post('/resource-development/records', json=original)
    assert result.status_code == 409
    assert result.json()['detail']['code'] == 'creation_id_conflict'
