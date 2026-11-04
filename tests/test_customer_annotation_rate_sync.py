from uuid import uuid4
from decimal import Decimal

import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_customer_finance_sync import allowed, oral_setup, oral_rate
from annotation_models import AnnotationProject, AnnotationProjectPriceItem
from models import Client
from customer_annotation_rates import CustomerAnnotationRate
import customer_finance_sync as sync
import interpretation_customer_finance as oral


def setup(db):
    client = Client(id=uuid4(), client_code='CL-SYNC', client_name='客户', client_short_name='客户')
    project = AnnotationProject(id=uuid4(), client_id=client.id, order_no='AP-SYNC', project_name='标注测试', project_types=['audio_annotation'])
    price = AnnotationProjectPriceItem(id=uuid4(), project_id=project.id, sequence_no=1, amount=Decimal('1.123456'), currency='CNY', unit='元/分钟')
    db.add_all([client, project, price]); db.commit()
    return client, project, price


def request(row, **extra):
    return sync.SyncWrite(**{key: row[key] for key in ('project_id', 'order_id', 'version', 'customer_version')}, direction='project_to_client', **extra)


def test_annotation_import_confirmation_stale_versions_and_preserves_source(environment, allowed):
    db, (user, _, _) = environment
    client, project, price = setup(db)
    row = sync.differences('annotation', client.id, page=1, db=db, user=user)['items'][0]
    assert row['project_rates'][0]['unit'] == 'minute'
    assert row['project_rates'][0]['project_type'] == 'audio_annotation'
    assert not row['sync_blocked_reason']
    with pytest.raises(HTTPException) as unconfirmed:
        sync.sync('annotation', client.id, request(row), db=db, user=user)
    assert unconfirmed.value.status_code == 422
    sync.sync('annotation', client.id, request(row, confirmed=True), db=db, user=user)
    saved = db.query(CustomerAnnotationRate).one()
    assert saved.amount == Decimal('1.123456') and saved.currency == 'CNY' and saved.unit == 'minute'
    assert price.amount == Decimal('1.123456') and price.unit == '元/分钟'
    assert sync.differences('annotation', client.id, page=1, db=db, user=user)['total'] == 0
    with pytest.raises(HTTPException) as stale:
        sync.sync('annotation', client.id, request(row, confirmed=True), db=db, user=user)
    assert stale.value.status_code == 409
    price.amount = Decimal('2.000001'); db.commit()
    changed = sync.differences('annotation', client.id, page=1, db=db, user=user)['items'][0]
    sync.sync('annotation', client.id, request(changed, confirmed=True), db=db, user=user)
    assert db.query(CustomerAnnotationRate).count() == 1
    assert db.query(CustomerAnnotationRate).one().revision == 2


def test_annotation_invalid_source_permissions_and_customer_boundary(environment, allowed, monkeypatch):
    db, (user, _, _) = environment
    client, project, price = setup(db)
    project.project_types = ['audio_annotation', 'text_annotation']; db.commit()
    row = sync.differences('annotation', client.id, page=1, db=db, user=user)['items'][0]
    assert row['sync_blocked_reason']
    with pytest.raises(HTTPException) as invalid:
        sync.sync('annotation', client.id, request(row, confirmed=True), db=db, user=user)
    assert invalid.value.status_code == 422
    other = Client(id=uuid4(), client_code='CL-OTHER', client_name='同名客户', client_short_name='同名客户')
    db.add(other); db.commit()
    assert sync.differences('annotation', other.id, page=1, db=db, user=user)['total'] == 0
    with pytest.raises(HTTPException) as wrong_client:
        sync.sync('annotation', other.id, request(row, confirmed=True), db=db, user=user)
    assert wrong_client.value.status_code == 404
    monkeypatch.setattr(sync, 'user_has_permission', lambda *_: False)
    with pytest.raises(HTTPException) as denied:
        sync.differences('annotation', client.id, page=1, db=db, user=user)
    assert denied.value.status_code == 403


def test_reference_quantity_is_one_project_quantity_preserved(environment, allowed):
    db, (user, _, _) = environment
    client, projects = oral_setup(db)
    result = oral.save(db, user, 'client', client.id, oral.FinanceWrite(revision=0, rates=[oral_rate(quantity=99)]))
    assert result['payload']['rates'][0]['quantity'] == '1'
    project = oral.context(db, 'project', projects[0].id)
    result = oral.save(db, user, 'project', projects[0].id, oral.FinanceWrite(revision=project['revision'], rates=[oral_rate(quantity=3)]))
    assert result['payload']['rates'][0]['quantity'] == '3'
