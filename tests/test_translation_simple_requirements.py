"""简单需求和明确收到回复的隔离测试；不连接业务数据库。"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from tests.test_chat_participant_access import environment
from department_models import Department, DepartmentMember
from models import AppNotification, TranslationProject
import translation_simple_requirements as service


@pytest.fixture
def context(environment, monkeypatch):
    db, (owner, member, outsider) = environment
    monkeypatch.setattr(service, 'publish', lambda notices: None)
    member.username = 'shaofei'; member.full_name = '少妃'
    dept = Department(name='笔译项目部', aliases=[])
    db.add(dept); db.flush()
    db.add(DepartmentMember(department_id=dept.id, user_id=member.id, position=''))
    row = TranslationProject(id=uuid4(), order_no='TP-REQUIREMENT-TEST', project_name='简单需求测试.docx',
                             project_status='confirmed', updated_at=datetime(2026, 10, 31, 10))
    db.add(row); db.commit()
    return db, owner, member, outsider, row, dept


def payload(row, member, **overrides):
    return service.RequirementCreate(**(dict(request_id=uuid4(), original_text='  请确认术语  ', translated_text='Please confirm.',
        chargeable=False, saved_status='simple_requirement', recipient_ids=[member.id],
        expected_project_status=row.project_status, expected_updated_at=row.updated_at) | overrides))


def test_save_status_fee_metadata_notification_and_retry(context):
    db, owner, member, _, row, _ = context
    data = payload(row, member)
    result = service.create_requirement(db, row.id, data, owner)
    assert row.project_status == 'simple_requirement'
    assert result['item']['original_text'] == '请确认术语'
    assert result['item']['chargeable'] is False
    assert result['item']['previous_status'] == 'confirmed'
    assert result['item']['actor_name'] == 'owner'
    assert result['item']['created_at'].endswith('+08:00')
    assert result['project_updated_at'].endswith('+08:00')
    notice = db.query(AppNotification).one()
    assert notice.recipient_user_id == member.id
    assert notice.related_entity_id == result['item']['id'] and notice.related_project_id == row.id
    assert service.create_requirement(db, row.id, data, owner)['item']['id'] == result['item']['id']
    assert db.query(AppNotification).count() == 1
    changed = data.model_copy(update={'chargeable':True})
    with pytest.raises(HTTPException) as error:
        service.create_requirement(db, row.id, changed, owner)
    assert error.value.status_code == 409


@pytest.mark.parametrize('overrides', [dict(chargeable=None),dict(chargeable='false'),dict(original_text='  '),dict(original_text='字'*2001),dict(recipient_ids=[]),dict(saved_status='invalid_status')])
def test_required_fields_and_charge_choice(context, overrides):
    _, _, member, _, row, _ = context
    with pytest.raises(ValidationError):
        payload(row, member, **overrides)


def test_missing_fee_rejected(context):
    _, _, member, _, row, _ = context
    raw = payload(row, member).model_dump(); del raw['chargeable']
    with pytest.raises(ValidationError): service.RequirementCreate(**raw)


def test_department_default_multi_choice_and_invalid_recipient_atomic(context):
    db, owner, member, outsider, row, dept = context
    assert service.recipient_options(db)['default_recipient_ids'] == [member.id]
    with pytest.raises(HTTPException) as error:
        service.create_requirement(db, row.id, payload(row, member, recipient_ids=[member.id, outsider.id]), owner)
    assert error.value.status_code == 422
    assert row.project_status == 'confirmed' and db.query(service.TranslationSimpleRequirement).count() == 0
    outsider.department = dept.name; db.commit()
    result = service.create_requirement(db, row.id, payload(row, member, recipient_ids=[member.id, outsider.id], chargeable=True, saved_status='source_file_simple_requirement'), owner)
    assert result['project_status'] == 'source_file_simple_requirement'
    assert result['item']['chargeable'] is True
    assert len(result['item']['recipients']) == db.query(AppNotification).count() == 2


def test_stale_version_and_status_cannot_overwrite(context):
    db, owner, member, _, row, _ = context
    for overrides in (dict(expected_project_status='pending'),dict(expected_updated_at=row.updated_at-timedelta(seconds=1))):
        with pytest.raises(HTTPException) as error: service.create_requirement(db,row.id,payload(row,member,**overrides),owner)
        assert error.value.status_code == 409
    assert row.project_status == 'confirmed' and db.query(AppNotification).count() == 0
    # 同一实际时刻的 UTC 表达应正确归一化为香港时间后比较。
    utc = row.updated_at.replace(tzinfo=timezone(timedelta(hours=8))).astimezone(timezone.utc)
    service.create_requirement(db,row.id,payload(row,member,expected_updated_at=utc),owner)


def test_read_is_not_receipt_explicit_self_only_reply_is_idempotent(context, monkeypatch):
    db, owner, member, outsider, row, _ = context
    monkeypatch.setattr('permission_service.user_has_permission',lambda *args:False)
    saved = service.create_requirement(db,row.id,payload(row,member),owner)['item']
    notification = db.query(AppNotification).one();notification.is_read=True;db.commit()
    assert service.detail(db,saved['id'],member)['recipients'][0]['received_at'] is None
    with pytest.raises(HTTPException):service.detail(db,saved['id'],outsider)
    for actor in (owner,outsider):
        with pytest.raises(HTTPException) as error:service.receive(db,saved['id'],service.RequirementReply(),actor)
        assert error.value.status_code == 403
    member.full_name='后续改名';db.commit()
    received=service.receive(db,saved['id'],service.RequirementReply(reply='收到，正在处理'),member)
    assert received['recipients'][0]['user_name']=='少妃'
    assert received['recipients'][0]['reply']=='收到，正在处理'
    assert received['recipients'][0]['received_at'].endswith('+08:00')
    assert received['can_reply'] is False
    again=service.receive(db,saved['id'],service.RequirementReply(reply='重试'),member)
    assert again['recipients']==received['recipients']
    assert db.query(AppNotification).count()==2
    response=db.query(AppNotification).filter_by(notification_type='translation_simple_requirement_receipt').one()
    assert response.recipient_user_id==owner.id and '收到，正在处理' in response.content
    from schemas import NotificationResponse
    assert NotificationResponse.model_validate(notification).model_dump(mode='json')['read_at'] is None
    assert service.detail(db,saved['id'],owner)['recipients']==received['recipients']


def test_recipient_can_reply_without_project_permissions_and_cannot_write_projects(context,monkeypatch):
    db,owner,member,_,row,_=context
    saved=service.create_requirement(db,row.id,payload(row,member),owner)['item']
    from database import get_db
    from routers.auth import get_current_user
    monkeypatch.setattr('routers.auth.user_has_permission',lambda *args:False)
    app=FastAPI();app.include_router(service.router)
    app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:member
    client=TestClient(app)
    assert client.get(f"/translation-simple-requirements/{saved['id']}").status_code==200
    assert client.get(f'/translation-simple-requirements/projects/{row.id}').status_code==403
    assert client.post(f"/translation-simple-requirements/{saved['id']}/received",json={}).status_code==200
    assert client.post(f'/translation-simple-requirements/projects/{row.id}',json=payload(row,member).model_dump(mode='json')).status_code==403


def test_repeatable_new_tables_only_migration():
    import main
    from tools.apply_translation_requirement_migration import apply_migration,TABLES
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        apply_migration(connection);apply_migration(connection)
        assert set(inspect(connection).get_table_names())==set(TABLES)
        columns={item['name']:item for item in inspect(connection).get_columns('translation_simple_requirement')}
        assert columns['chargeable']['nullable'] is False
    engine.dispose()
