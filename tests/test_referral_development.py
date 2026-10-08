"""推荐拓展 API 与真实 PostgreSQL 回归；每个用例在外层事务中回滚。"""
from datetime import date
from io import BytesIO
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from test_resource_development import db, context  # noqa: F401
from database import get_db
from routers.auth import get_current_user
from routers.referral_development import router
from referral_development_models import ReferralRecord, ReferralImage, ReferralAudit
from referral_development_schemas import RecordWrite, PaymentWrite


@pytest.fixture
def api(db, context):
    user, other, _ = context
    current = [user]
    delegate, admin, write = [False], [False], [True]
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current[0]
    with patch('routers.auth.get_user_permission_codes', side_effect=lambda *args: ['talents:read', *(['talents:write'] if write[0] else [])]), \
         patch('referral_development_service.can_delegate', side_effect=lambda *args: delegate[0]), \
         patch('referral_development_service.is_admin', side_effect=lambda *args: admin[0]), \
         patch('referral_development_service.can_write', side_effect=lambda *args: write[0]), \
         patch('routers.referral_development.can_delegate', side_effect=lambda *args: delegate[0]), \
         patch('routers.referral_development.is_admin', side_effect=lambda *args: admin[0]), \
         patch('routers.referral_development.can_write', side_effect=lambda *args: write[0]), TestClient(app) as client:
        yield client, current, delegate, admin, write


def payload(**changes):
    return {**dict(id=str(uuid4()), work_date='2026-08-26', full_name='推荐人' + uuid4().hex,
                   wechat='wx_' + uuid4().hex, amount='6.25', remarks='初始备注'), **changes}


def save(client, data):
    response = client.post('/referral-development/records', json=data)
    assert response.status_code == 200, response.text
    return response.json()


def png():
    out = BytesIO()
    Image.new('RGB', (20, 20), 'white').save(out, 'PNG')
    return out.getvalue()


def upload(client, row, category='pull', image_id=None, content=None):
    return client.post(f'/referral-development/records/{row["id"]}/images',
                       data=dict(category=category, image_id=image_id or str(uuid4()), revision=row['revision']),
                       files={'file': ('凭证.png', png() if content is None else content, 'image/png')})


def test_amount_identity_and_payment_schema():
    common = payload()
    assert str(RecordWrite(**common).amount) == '6.25'
    for amount in ['-1', '1.234', 'NaN', 'Infinity', True, '10000000000.00', '']:
        with pytest.raises(ValidationError):
            RecordWrite(**{**common, 'amount': amount})
    assert RecordWrite(**{**common, 'amount': '0'}).amount == 0
    for extra in [{'created_by': str(uuid4())}, {'created_at': '2000-01-01'}, {'updated_by': str(uuid4())}]:
        with pytest.raises(ValidationError):
            RecordWrite(**common, **extra)
    with pytest.raises(ValidationError):
        PaymentWrite(revision=1, payment_status='paid')
    assert PaymentWrite(revision=1, payment_status='unpaid', payment_date='2026-08-26').payment_date is None


def test_create_idempotent_update_and_history(api, db, context):
    client, current, *_ = api
    data = payload()
    row = save(client, data)
    assert row['amount'] == '6.25' and row['created_by'] == str(current[0].id)
    assert row['payment_status'] == 'unpaid' and row['work_date'] == '2026-08-26'
    assert row['created_at'].endswith('+08:00') and row['audit'][0]['action'] == 'create'
    first_time = row['created_at']
    retried = save(client, data)
    assert retried['revision'] == 1 and len(retried['audit']) == 1
    edited = save(client, {**data, 'revision': 1, 'amount': '0.10', 'remarks': '更正备注'})
    assert edited['amount'] == '0.10' and edited['created_at'] == first_time
    assert edited['audit'][0]['before']['amount'] == '6.25' and edited['audit'][0]['after']['amount'] == '0.10'
    stale = client.post('/referral-development/records', json={**data, 'revision': 1})
    assert stale.status_code == 409
    assert db.get(ReferralRecord, current_record_id(row)).amount == RecordWrite(**{**data, 'amount': '0.10'}).amount
    current[0] = context[1]
    denied = client.post('/referral-development/records', json={**data, 'revision': 2})
    assert denied.status_code == 403


def current_record_id(row):
    from uuid import UUID
    return UUID(row['id'])


def test_payment_clear_date_and_edit_paid_amount(api):
    client, *_ = api
    data = payload()
    row = save(client, data)
    url = f'/referral-development/records/{row["id"]}/payment'
    assert client.put(url, json=dict(revision=1, payment_status='paid')).status_code == 422
    paid = client.put(url, json=dict(revision=1, payment_status='paid', payment_date='2026-08-27')).json()
    assert paid['payment_status'] == 'paid' and paid['payment_date'] == '2026-08-27'
    edited = save(client, {**data, 'revision': paid['revision'], 'amount': '8.00'})
    assert edited['payment_status'] == 'paid' and edited['payment_date'] == '2026-08-27'
    cleared = client.put(url, json=dict(revision=edited['revision'], payment_status='unpaid', payment_date='2026-08-28'))
    assert cleared.status_code == 200
    row = cleared.json()
    assert row['payment_date'] is None
    assert row['audit'][0]['before']['payment_date'] == '2026-08-27'
    assert row['audit'][0]['actor_id'] == row['updated_by']
    assert client.put(url, json=dict(revision=1, payment_status='paid', payment_date='2026-08-29')).status_code == 409


def test_private_search_detail_images_and_write_roles(api, context):
    client, current, delegate, admin, write = api
    row = save(client, payload())
    row = upload(client, row).json()
    image_url = '/referral-development/images/' + row['images'][0]['id']
    assert client.get(image_url).status_code == 200
    current[0] = context[1]
    detail = client.get('/referral-development/records/' + row['id']).json()
    assert detail['wechat'] == '******' and not detail['images'] and not detail['can_edit']
    assert all('wechat' not in h['after'] and 'images' not in h['after'] for h in detail['audit'])
    assert client.get(image_url).status_code == 403
    assert client.get('/referral-development/records', params={'keyword': row['wechat']}).json()['total'] == 0
    assert client.get('/referral-development/records', params={'keyword': row['full_name']}).json()['total'] == 1
    delegate[0] = True
    assert client.get(image_url).status_code == 200
    assert client.get('/referral-development/records', params={'keyword': row['wechat']}).json()['total'] == 1
    assert client.get('/referral-development/records/' + row['id']).json()['can_edit']
    assert client.delete('/referral-development/records/' + row['id'], params={'revision': row['revision']}).status_code == 403
    write[0] = False
    assert client.put('/referral-development/records/' + row['id'] + '/payment', json=dict(revision=row['revision'], payment_status='paid', payment_date='2026-08-26')).status_code == 403
    assert not client.get('/referral-development/records/' + row['id']).json()['can_edit']


def test_multiple_images_replace_retry_validation_and_conflict(api, db):
    client, *_ = api
    row = save(client, payload())
    image_id = str(uuid4())
    original = row.copy()
    row = upload(client, row, image_id=image_id).json()
    retry = upload(client, original, image_id=image_id)
    assert retry.status_code == 200 and retry.json()['revision'] == row['revision']
    row = upload(client, row, category='pull').json()
    row = upload(client, row, category='moments').json()
    row = upload(client, row, category='groups').json()
    assert len(row['images']) == 4
    assert upload(client, original).status_code == 409
    before_revision = row['revision']
    assert upload(client, row, content=b'not-an-image').status_code == 422
    assert upload(client, row, content=b'x' * (5 * 1024 * 1024 + 1)).status_code == 422
    assert db.get(ReferralRecord, current_record_id(row)).revision == before_revision
    row = upload(client, row, category='qr').json()
    old_id = next(i['id'] for i in row['images'] if i['category'] == 'qr')
    row = upload(client, row, category='qr').json()
    assert len([i for i in row['images'] if i['category'] == 'qr']) == 1
    assert client.get('/referral-development/images/' + old_id).status_code == 404
    assert row['audit'][0]['action'] == 'image_replace'
    assert row['audit'][0]['before']['images'][0]['id'] == old_id
    deleted_id = row['images'][0]['id']
    response = client.delete(f'/referral-development/records/{row["id"]}/images/{deleted_id}', params={'revision': row['revision']})
    assert response.status_code == 200
    assert response.json()['audit'][0]['action'] == 'image_delete'


def test_filters_duplicate_candidates_and_deletion_retains_audit(api, db):
    client, *_ = api
    data = payload()
    row = save(client, data)
    same = save(client, {**data, 'id': str(uuid4())})
    assert len(client.get('/referral-development/duplicates', params={k: data[k] for k in ['work_date','full_name','wechat']}).json()['items']) == 2
    assert not client.get('/referral-development/duplicates', params={'work_date': data['work_date'], 'full_name': data['full_name']}).json()['items']
    query = {'start': data['work_date'], 'end': data['work_date'], 'creator_id': row['created_by'], 'keyword': data['wechat'], 'limit': 1}
    listing = client.get('/referral-development/records', params=query).json()
    assert listing['total'] == 2 and len(listing['items']) == 1
    assert client.get('/referral-development/records', params={**query, 'skip': 1}).json()['items'][0]['id'] != listing['items'][0]['id']
    assert client.get('/referral-development/records', params={'start': '2026-08-27', 'end': '2026-08-26'}).status_code == 422
    assert client.get('/referral-development/records', params={'keyword': '%'}).json()['total'] == 0
    row = upload(client, row).json()
    url = '/referral-development/records/' + row['id']
    assert client.delete(url, params={'revision': 1}).status_code == 409
    assert client.delete(url, params={'revision': row['revision']}).status_code == 200
    assert client.get(url).status_code == 404
    assert db.query(ReferralImage).filter_by(record_id=current_record_id(row)).count() == 0
    deletion = db.query(ReferralAudit).filter_by(record_id=current_record_id(row), action='delete').one()
    assert deletion.before['full_name'] == data['full_name'] and deletion.before['images']
