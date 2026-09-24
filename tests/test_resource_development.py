"""开拓核心回归；数据库测试仅在显式启用的局域网调试库运行，逐例回滚。"""
import os
from datetime import date, datetime
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from resource_development_schemas import RecordWrite, WorkWrite


def test_work_period_validation():
    common = dict(work_date=date(2026, 9, 24), owner_id=uuid4())
    good = WorkWrite(**common, periods=[dict(start="09:00", end="10:30"), dict(start="11:00", end="12:00")], deduction=15)
    assert good.duration_minutes == 135
    for periods, deduction in [([dict(start="10:00", end="09:00")], 0),
                                ([dict(start="09:00", end="11:00"), dict(start="10:00", end="12:00")], 0),
                                ([dict(start="09:00", end="10:00")], 61),
                                ([dict(start="25:00", end="26:00")], 0)]:
        with pytest.raises(ValidationError):
            WorkWrite(**common, periods=periods, deduction=deduction)
    with pytest.raises(ValidationError):
        WorkWrite(**common, completed=False, explanation=" ")


def test_dates_and_report_merge():
    from resource_development_service import previous_workday
    from task_service import merge_daily_report_items
    assert previous_workday(date(2026, 9, 28)) == date(2026, 9, 25)
    assert previous_workday(date(2026, 9, 27)) == date(2026, 9, 25)
    assert previous_workday(date(2026, 9, 24)) == date(2026, 9, 23)
    source = dict(source_type="system_event", source_id=uuid4(), duration_minutes=70, display_metadata={"source": "resource_development"})
    result = merge_daily_report_items([{**source, "duration_minutes": 999}, dict(source_type="manual", duration_minutes=5)], [source])
    assert [r["duration_minutes"] for r in result] == [5, 70]
    assert merge_daily_report_items([], [dict(source_type="system_event", duration_minutes=99)])[0]["duration_minutes"] == 0


@pytest.fixture
def db():
    if os.getenv("RUN_RESOURCE_DEVELOPMENT_DB_TESTS") != "1":
        pytest.skip("数据库回归需在局域网显式启用")
    # 注册应用所有 ORM 类型；不运行 startup，不触发邮件或项目任务。
    import main  # noqa: F401
    from database import engine
    from sqlalchemy.orm import Session
    with engine.connect() as conn:
        transaction = conn.begin()
        session = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def context(db):
    from models import AppUser
    from resource_development_models import DevelopmentOption
    user = AppUser(id=uuid4(), username="development_test_" + uuid4().hex, full_name="开拓测试人员", password_hash="not-a-login", is_active=True)
    other = AppUser(id=uuid4(), username="development_test_" + uuid4().hex, full_name="其他测试人员", password_hash="not-a-login", is_active=True)
    platform = DevelopmentOption(id=uuid4(), kind="platform", category="national", name="测试平台" + uuid4().hex, code="TEST" + uuid4().hex[:12])
    db.add_all([user, other, platform]); db.flush()
    return user, other, platform


def make_payload(context, **kwargs):
    user, _, platform = context
    return RecordWrite(**(dict(id=uuid4(), platform_id=platform.id, work_date=date(2026, 9, 24), owner_id=user.id,
                               full_name="测试资源" + uuid4().hex, phone="", wechat="") | kwargs))


def test_historical_import_and_edit_never_enroll(db, context):
    from resource_development_service import save_record, serialize_record
    user, other, _ = context
    payload = make_payload(context, actions=[action(user, "已添加")])
    with patch("resource_development_service.create_talent") as create:
        row = save_record(db, user, payload, historical_markers={"wechat": {"status": "已添加", "raw": "原本标注员"}})
        assert row.historical_only and row.person_id is None
        assert save_record(db, user, payload).id == row.id
        edited = payload.model_copy(update={"revision": row.revision, "remarks": "修改历史记录"})
        save_record(db, user, edited)
        create.assert_not_called()
    assert serialize_record(db, other, row)["historical_markers"] == {}
    undated = save_record(db, user, make_payload(context), historical_markers={"wechat": {"status": "已添加", "raw": "原本标注员"}})
    assert undated.wechat_status == "已添加"
    assert serialize_record(db, user, undated)["progress"]["wechat"]["action_date"] is None
    with pytest.raises(ValidationError):
        RecordWrite(**(payload.model_dump() | {"historical_only": True}))


def action(user, status="已发请求", channel="wechat"):
    return dict(id=uuid4(), channel=channel, status=status, action_date=date(2026, 9, 24), operator_id=user.id)


def test_numbering_ownership_actions_and_idempotency(db, context):
    from resource_development_service import save_record, serialize_record
    from resource_development_models import DevelopmentRecord, DevelopmentAction
    user, other, _ = context
    payload = make_payload(context, phone="13912340000", remarks="有联系方式的备注", actions=[action(user), action(user)])
    row = save_record(db, user, payload)
    assert row.greeting_no.endswith("-260924-001")
    assert db.query(DevelopmentAction).filter_by(record_id=row.id).count() == 2
    assert save_record(db, user, payload).id == row.id
    assert db.query(DevelopmentRecord).filter_by(owner_id=user.id).count() == 1
    detail = serialize_record(db, user, row, True)
    assert [a["request_number"] for a in detail["actions"]] == [1, 2]
    masked = serialize_record(db, other, row, True)
    assert masked["phone"] == "******" and masked["remarks"] == "受限内容" and masked["audit"] == []
    update = payload.model_copy(update={"revision": row.revision, "work_date": date(2026, 9, 23)})
    original = row.greeting_no
    assert save_record(db, user, update).greeting_no == original
    with pytest.raises(HTTPException) as exc:
        save_record(db, other, update.model_copy(update={"owner_id": other.id}))
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        save_record(db, user, update)
    assert exc.value.status_code == 409


def test_enrollment_duplicates_and_transaction(db, context):
    from resource_development_service import save_record, duplicates
    from resource_models import ResourcePerson
    user, _, _ = context
    payload = make_payload(context, capabilities=["annotation", "recruitment"], actions=[action(user, "已添加")])
    row = save_record(db, user, payload)
    person = db.get(ResourcePerson, row.person_id)
    assert person.resource_code and person.career_profile is not None
    assert person.capabilities[0].capability_type == "annotation"
    updated = payload.model_copy(update={"revision": row.revision, "actions": [*payload.actions, type(payload.actions[0])(**action(user, "已添加", "enterprise"))]})
    assert save_record(db, user, updated).person_id == person.id
    candidate = duplicates(db, payload.full_name, "", "")
    assert candidate[0]["match_fields"] == ["name"] and "primary_phone" not in candidate[0]
    linked = make_payload(context, full_name=payload.full_name, actions=[action(user, "已添加")], link_person_id=person.id)
    assert save_record(db, user, linked).person_id == person.id
    same_name = make_payload(context, full_name=payload.full_name, actions=[action(user, "已添加")], duplicate_note="确认不是同一人", capabilities=["annotation"])
    assert save_record(db, user, same_name).person_id != person.id
    person.wechat = "unique_" + uuid4().hex; db.flush()
    conflict = make_payload(context, wechat=person.wechat, actions=[action(user, "已添加")], duplicate_note="不能绕过", capabilities=["annotation"])
    with db.begin_nested() as nested:
        with pytest.raises(HTTPException) as exc:
            save_record(db, user, conflict)
        assert exc.value.status_code == 409
        nested.rollback()
    # 人才创建已 flush 后发生异常，外层事务仍可完整回滚。
    rollback_payload = make_payload(context, actions=[action(user, "已添加")], capabilities=["annotation"])
    with db.begin_nested() as nested:
        created = save_record(db, user, rollback_payload); created_person_id = created.person_id
        nested.rollback()
    assert db.get(ResourcePerson, created_person_id) is None


def test_independent_progress_preserves_history_and_does_not_enroll(db, context):
    from resource_development_service import save_record, serialize_record
    from resource_development_models import DevelopmentAction
    from resource_development_schemas import ActionWrite
    user, other, _ = context
    payload = make_payload(context, actions=[action(user)])
    row = save_record(db, user, payload)
    first = db.get(DevelopmentAction, payload.actions[0].id)
    original_audit = (first.updated_by, first.updated_at)
    additions = [ActionWrite(**action(other, status, channel)) for channel, status in [
        ('group', '已邀进群'), ('communication', '已沟通'), ('project', '已入项')]]
    updated = payload.model_copy(update={'revision': row.revision, 'actions': [*payload.actions, *additions]})
    save_record(db, user, updated)
    assert row.person_id is None and row.wechat_status == '已发请求'
    assert (first.updated_by, first.updated_at) == original_audit
    detail = serialize_record(db, user, row, True)
    assert set(detail['progress']) == {'wechat', 'group', 'communication', 'project'}
    assert detail['progress']['project']['operator_name'] == other.full_name
    assert detail['latest_follow_up'].endswith('入项')
    assert len(detail['actions']) == 4
    with pytest.raises(HTTPException) as error:
        save_record(db, other, updated.model_copy(update={'revision': row.revision}))
    assert error.value.status_code == 403


def test_delegate_permission_is_module_scoped_and_preserves_owner(db, context):
    from models import Role, RolePermission, UserRole
    from resource_development_service import save_record, serialize_record, filtered_records, report_item
    from routers.resource_development import options, delete_record
    from talent_privacy import can_view_talent_contacts
    user, operator, _ = context
    role = Role(id=uuid4(), role_name='代录回归_' + uuid4().hex)
    db.add(role); db.flush()
    db.add_all([RolePermission(role_id=role.id, permission_code='resource_development:delegate'), UserRole(user_id=user.id, role_id=role.id)])
    db.flush()
    assert options(db, user)['can_delegate'] and options(db, user)['can_write']
    assert not can_view_talent_contacts(db, user)
    payload = make_payload(context, owner_id=operator.id, phone='13977771234', actions=[action(operator, '已沟通', 'communication')])
    row = save_record(db, user, payload)
    assert row.owner_id == operator.id and row.created_by == user.id
    detail = serialize_record(db, user, row, True)
    assert detail['phone'] == '13977771234' and detail['can_edit'] and not detail['can_delete']
    assert detail['actions'][0]['created_by'] == str(user.id)
    assert detail['actions'][0]['operator_id'] == str(operator.id)
    assert filtered_records(db, user, payload.work_date, payload.work_date, keyword='13977771234').count() == 1
    assert report_item(db, user.id, payload.work_date) is None
    assert report_item(db, operator.id, payload.work_date) is not None
    edited = payload.model_copy(update={'revision': row.revision, 'phone': '13977774321'})
    save_record(db, user, edited)
    assert row.phone == '13977774321' and row.owner_id == operator.id and row.updated_by == user.id
    with pytest.raises(HTTPException) as error:
        delete_record(row.id, row.revision, db, user)
    assert error.value.status_code == 403
    db.query(RolePermission).filter_by(role_id=role.id).delete(); db.flush()
    assert serialize_record(db, user, row)['phone'] == '******'
    with pytest.raises(HTTPException):
        save_record(db, user, payload.model_copy(update={'revision': row.revision}))


def test_column_filters_combine_and_match_latest_progress(db, context):
    from resource_development_service import save_record, filtered_records
    from routers.resource_development import days, records
    user, other, platform = context
    first = make_payload(context, full_name='筛选甲', phone='13855556666', actions=[action(user, '已邀进群', 'group'), action(user, '未处理', 'group')])
    save_record(db, user, first)
    save_record(db, user, make_payload(context, full_name='筛选乙', actions=[action(user, '已沟通', 'communication')]))
    params = dict(start=first.work_date, end=first.work_date, keyword=None, owner_id=None, platform_id=None, account_id=None, state=None,
                  column_filters={'platform_name':[str(platform.id)], 'full_name':'筛选', 'communication_status':['已沟通']})
    result = days(params, 0, 7, db, user)
    assert result['items'][0]['count'] == 1 and result['items'][0]['people'][0]['count'] == 1
    assert records(params, 0, 1, db, user)['total'] == 1
    assert filtered_records(db,user,first.work_date,first.work_date,column_filters={'group_status':['已邀进群']}).count() == 0
    assert filtered_records(db,user,first.work_date,first.work_date,column_filters={'phone':'5555'}).count() == 1
    assert filtered_records(db,other,first.work_date,first.work_date,column_filters={'phone':'5555'}).count() == 0
    assert filtered_records(db,user,first.work_date,first.work_date,column_filters={'latest_follow_up':user.full_name}).count() == 2


def test_filtered_totals_contact_search_work_and_report(db, context):
    from resource_development_service import save_record, filtered_records, save_work, report_item, refresh_draft
    from task_models import DailyReport
    user, other, _ = context
    for i in range(3):
        save_record(db, user, make_payload(context, phone="13988880000"))
    params = dict(start=date(2026, 9, 24), end=date(2026, 9, 24), owner_id=user.id)
    assert filtered_records(db, user, **params).count() == 3
    assert len(filtered_records(db, user, **params).limit(2).all()) == 2
    assert filtered_records(db, other, **params, keyword="13988880000").count() == 0
    assert filtered_records(db, user, **params, keyword="13988880000").count() == 3
    work = save_work(db, user, WorkWrite(work_date=params['start'], owner_id=user.id, periods=[dict(start="09:00",end="10:30")], deduction=10, completed=False, explanation="继续联系"))
    assert report_item(db, user.id, params['start'])["duration_minutes"] == 80
    report = DailyReport(user_id=user.id, report_date=params['start'], status="draft")
    db.add(report); db.flush()
    refresh_draft(db, user.id, params['start']); db.flush()
    refresh_draft(db, user.id, params['start']); db.flush()
    assert len(report.items) == 1 and report.items[0].duration_minutes == 80
    report.status = "finalized"; db.flush()
    save_work(db, user, WorkWrite(work_date=params['start'], owner_id=user.id, revision=work.revision, periods=[dict(start="09:00",end="11:00")]))
    assert report.items[0].duration_minutes == 80
    with pytest.raises(HTTPException):
        save_work(db, other, WorkWrite(work_date=params['start'], owner_id=user.id))


def test_grouped_day_totals_and_work_only_days(db, context):
    from resource_development_service import save_record, save_work
    from routers.resource_development import days
    user, _, _ = context
    for i in range(3):
        save_record(db, user, make_payload(context))
    save_work(db, user, WorkWrite(work_date=date(2026,9,23), owner_id=user.id))
    params = dict(start=date(2026,9,23), end=date(2026,9,24), keyword=None, owner_id=user.id, platform_id=None, account_id=None, state=None)
    result = days(params=params, skip=0, limit=7, db=db, user=user)
    assert result['total'] == 2
    assert [d['count'] for d in result['items']] == [3, 0]
    assert result['items'][0]['people'][0]['count'] == 3


def test_screenshot_and_delete_permissions(db, context):
    from io import BytesIO
    from PIL import Image
    from starlette.datastructures import UploadFile
    from resource_development_service import save_record, save_work
    from routers.resource_development import upload_screenshot, read_screenshot, delete_screenshot, delete_record
    from resource_development_models import DevelopmentRecord, DevelopmentScreenshot
    user, other, _ = context
    row = save_record(db, user, make_payload(context))
    work = save_work(db, user, WorkWrite(work_date=row.work_date, owner_id=user.id))
    image = BytesIO(); Image.new('RGB', (5, 5)).save(image, format='PNG'); image.seek(0)
    result = upload_screenshot(work.id, UploadFile(filename='test.png', file=image), db, user)
    from uuid import UUID
    screenshot_id = UUID(result['id'])
    assert read_screenshot(screenshot_id, db, user).media_type == 'image/png'
    with pytest.raises(HTTPException) as exc:
        read_screenshot(screenshot_id, db, other)
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException):
        upload_screenshot(work.id, UploadFile(filename='bad.png', file=BytesIO(b'not an image')), db, user)
    with pytest.raises(HTTPException):
        delete_record(row.id, row.revision, db, other)
    with patch('resource_development_service.is_admin', return_value=True):
        assert read_screenshot(screenshot_id, db, other).status_code == 200
    delete_screenshot(screenshot_id, db, user)
    assert db.get(DevelopmentScreenshot, screenshot_id) is None
    row_id = row.id
    delete_record(row_id, row.revision, db, user)
    assert db.get(DevelopmentRecord, row_id) is None


def test_concurrent_numbering_in_isolated_schema():
    if os.getenv('RUN_RESOURCE_DEVELOPMENT_DB_TESTS') != '1':
        pytest.skip('需要局域网 PostgreSQL')
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from database import engine
    from resource_development_service import allocate_greeting
    schema = 'test_development_' + uuid4().hex
    platform = SimpleNamespace(id=uuid4(), code='BOSS1')
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'CREATE TABLE "{schema}".resource_development_counter (platform_id uuid, work_date date, value integer NOT NULL, PRIMARY KEY(platform_id,work_date))'))
        def allocate(_):
            with engine.begin() as conn:
                conn.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
                with Session(bind=conn) as session:
                    return allocate_greeting(session, platform, date(2026,9,24))
        with ThreadPoolExecutor(max_workers=6) as pool:
            numbers = list(pool.map(allocate, range(18)))
        assert len(set(numbers)) == 18
        assert set(numbers) == {f'BOSS1-260924-{i:03d}' for i in range(1,19)}
        with engine.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".resource_development_counter SET value=999'))
        assert allocate(0) == 'BOSS1-260924-1000'
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

@pytest.mark.parametrize('channel,status', [('wechat','已添加'),('enterprise','已添加'),('group','已进群')])
@pytest.mark.parametrize('historical', [False, True])
def test_private_entry_new_followup_enrolls_once(db, context, channel, status, historical):
    from resource_development_service import save_record
    from resource_models import ResourcePerson
    from resource_development_schemas import ActionWrite
    user, _, _ = context
    payload = make_payload(context, capabilities=['annotation'])
    row = save_record(db, user, payload, historical_markers={} if historical else None)
    confirmed = ActionWrite(**action(user, status, channel))
    changed = payload.model_copy(update={'revision':row.revision, 'actions':[confirmed]})
    row = save_record(db, user, changed)
    person_id = row.person_id
    assert person_id and db.get(ResourcePerson, person_id).full_name == payload.full_name
    assert row.historical_only == historical
    # 另一渠道成功以及重复提交不重复建档。
    changed = changed.model_copy(update={'revision':row.revision, 'actions':[confirmed, ActionWrite(**action(user,'已添加','enterprise'))]})
    assert save_record(db, user, changed).person_id == person_id
    assert db.query(ResourcePerson).filter_by(full_name=payload.full_name).count() == 1
    # 撤销成功状态不删除已关联的人才。
    changed = changed.model_copy(update={'revision':row.revision, 'actions':[a.model_copy(update={'status':'未处理'}) for a in changed.actions]})
    assert save_record(db, user, changed).person_id == person_id
    assert db.get(ResourcePerson, person_id)


def test_historical_correction_only_status_triggers(db, context):
    from resource_development_service import save_record
    user, _, _ = context
    payload = make_payload(context, actions=[action(user,'已邀进群','group')], capabilities=['annotation'])
    row = save_record(db,user,payload,historical_markers={'wechat':{'status':'已添加'}})
    edited = payload.model_copy(update={'revision':row.revision,'remarks':'只修正备注','actions':[payload.actions[0].model_copy(update={'action_date':date(2026,9,20)})]})
    save_record(db,user,edited)
    assert row.person_id is None
    edited = edited.model_copy(update={'revision':row.revision,'actions':[edited.actions[0].model_copy(update={'status':'已进群'})]})
    assert save_record(db,user,edited).person_id


@pytest.mark.parametrize('channel,status', [('group','已邀进群'),('group','已添加'),('communication','已沟通'),('project','已入项'),('wechat','自定义已添加好友')])
def test_non_private_states_do_not_enroll(db, context, channel, status):
    from resource_development_service import save_record
    user, _, _ = context
    assert save_record(db,user,make_payload(context,actions=[action(user,status,channel)])).person_id is None


def test_private_entry_final_status_and_transaction_rollback(db, context):
    from resource_development_service import save_record
    from resource_models import ResourcePerson
    from resource_development_models import DevelopmentAction, DevelopmentRecord
    user, _, _ = context
    # 同次提交最后状态不是成功时不建档。
    row = save_record(db,user,make_payload(context,actions=[action(user,'已进群','group'),action(user,'未处理','group')]))
    assert row.person_id is None
    payload = make_payload(context,actions=[action(user,'已进群','group')])
    with db.begin_nested() as nested:
        with pytest.raises(HTTPException) as exc:
            save_record(db,user,payload)
        assert exc.value.status_code == 422
        nested.rollback()
    assert db.get(DevelopmentRecord,payload.id) is None
    assert db.query(DevelopmentAction).filter_by(record_id=payload.id).count() == 0
    with db.begin_nested() as nested:
        created = save_record(db,user,payload.model_copy(update={'capabilities':['annotation']}))
        person_id = created.person_id
        nested.rollback()
    assert db.get(ResourcePerson,person_id) is None
    assert db.get(DevelopmentRecord,payload.id) is None
