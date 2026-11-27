"""会议安排、回执、会后报告使用隔离 SQLite，不访问业务数据库。"""
from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_chat_participant_access import environment
from chat_time import now
from models import AppNotification
from meeting_models import Meeting, MeetingParticipant, MeetingActionTask
import meeting_service as service
from meeting_reports import ActualWrite, confirm


@pytest.fixture
def setup(environment, monkeypatch):
    db, users = environment
    # 使用真实可重复迁移创建两张表，包含SQLite自增编号及约束。
    MeetingActionTask.__table__.drop(db.connection()); MeetingParticipant.__table__.drop(db.connection()); Meeting.__table__.drop(db.connection())
    from tools.apply_meeting_migration import apply_migration
    apply_migration(db.connection()); apply_migration(db.connection())
    for user in users:
        user.is_deleted = False
    db.commit()
    monkeypatch.setattr(service, 'publish', lambda events: None)
    return db, users


def payload(users, **values):
    return service.MeetingWrite(client_id=uuid4(),meeting_type='管理会议',location='线上',
        start_at=now()+timedelta(hours=1), end_at=now()+timedelta(hours=1,minutes=30),user_ids=[users[1].id],
        **values)


def test_invitation_idempotency_receipts_visibility_and_read_versions(setup):
    db,(owner,member,outsider)=setup
    data=payload([owner,member,outsider],agendas=[{'content':'检查进展','same_people':True}])
    result=service.create(db,owner,data)
    assert result['number']==1 and len(result['participants'])==1
    assert service.create(db,owner,data)['id']==result['id']
    assert db.query(AppNotification).count()==1
    assert service.summary(db,member)['pending']==1
    assert service.listing(db,outsider,anchor=result['start_at'].date())['total']==1
    with pytest.raises(HTTPException):service.detail(db,outsider,result['id'])
    with pytest.raises(ValidationError):service.ReceiptWrite(response='declined',reason=' ',version=0)
    response=service.receipt(db,member,result['id'],service.ReceiptWrite(response='declined',reason='已有客户安排',version=0))
    assert db.query(AppNotification).count()==1  # 回执不再新增通知，原邀请仍保留
    assert response['my_version']==1
    assert service.summary(db,owner)['unread_receipts']==1
    service.read_receipts(db,owner,result['id'],{member.id:0})
    assert service.summary(db,owner)['unread_receipts']==1
    service.read_receipts(db,owner,result['id'],{member.id:1})
    assert service.summary(db,owner)['unread_receipts']==0
    with pytest.raises(HTTPException):service.receipt(db,owner,result['id'],service.ReceiptWrite(response='attending',version=0))
    with pytest.raises(HTTPException):service.receipt(db,member,result['id'],service.ReceiptWrite(response='attending',version=0))
    assert db.query(Meeting).count()==1


def test_agenda_people_validation_and_all_people_dedup(setup):
    db,users=setup;owner,member,outsider=users
    data=payload(users,all_people=True,department_ids=[],agendas=[{'content':'全体议程'}, {'content':'成员专场','same_people':False,'user_ids':[member.id]}])
    result=service.create(db,owner,data)
    assert len(result['participants'])==3
    assert len(result['agendas'][0]['user_ids'])==3
    assert result['agendas'][1]['user_ids']==[str(member.id)]
    with pytest.raises(HTTPException):service.create(db,owner,payload(users,agendas=[{'content':'错误人员','same_people':False,'user_ids':[outsider.id]}]))
    assert db.query(Meeting).count()==1


@pytest.mark.parametrize('minutes,expected',[(15,10),(30,10),(31,15),(60,15),(61,20),(180,20)])
def test_reminder_boundaries(minutes,expected):
    start=now();assert service.lead_minutes(start,start+timedelta(minutes=minutes))==expected


def test_actual_confirm_appends_to_finalized_report_once_and_can_delete(setup,monkeypatch):
    db,users=setup;owner,member,outsider=users
    result=service.create(db,owner,payload(users,all_people=True,agendas=[{'content':'全体议程'}, {'content':'仅成员议程','same_people':False,'user_ids':[member.id]}]))
    from task_models import DailyReport,DailyReportItem
    from work_report_dates import report_business_date
    start=now()-timedelta(hours=2);end=start+timedelta(minutes=31)
    day=report_business_date(start)
    existing=DailyReport(id=uuid4(),user_id=member.id,report_date=day,status='finalized')
    db.add(existing);db.commit()
    import consultation_work_report
    monkeypatch.setattr(consultation_work_report,'publish_report_update',lambda *args:None)
    actual=ActualWrite(start_at=start,end_at=end,user_ids=[member.id,owner.id])
    with pytest.raises(HTTPException):confirm(db,outsider,result['id'],actual)
    saved=confirm(db,owner,result['id'],actual)
    assert saved['written_count']==2 and saved['duration_minutes']==31
    assert existing.status=='finalized'
    entries=db.query(DailyReportItem).all()
    assert len(entries)==2
    own_entry=next(e for e in entries if e.report.user_id==owner.id)
    member_entry=next(e for e in entries if e.report.user_id==member.id)
    assert '仅成员议程' not in own_entry.progress_content
    assert '仅成员议程' in member_entry.progress_content
    assert member_entry.source_type=='manual'
    assert member_entry.display_metadata['report_types']==['会议::管理会议']
    assert member_entry.display_metadata['quantity']==1
    assert member_entry.display_metadata['quantity_unit']=='次'
    db.delete(member_entry);db.commit()
    assert confirm(db,owner,result['id'],actual)['already_confirmed']
    assert db.query(DailyReportItem).count()==1


def test_custom_categories_and_layout_presets_stay_private(environment,monkeypatch):
    db,(owner,member,_)=environment
    import work_report_categories as categories
    monkeypatch.setattr(categories,'can_add_project_category',lambda *a:False)
    categories.add_category_group(db,owner,'客户研究','资料核对')
    categories.add_category(db,owner,'非项目工作','跨部门整理')
    db.add(categories.WorkReportCategory(scope=str(owner.id),parent=categories.LAYOUT_PRESET_PARENT,name='个人固定选项'));db.commit()
    owner_catalog=categories.category_catalog(db,owner)
    assert owner_catalog['work_categories']['客户研究']==['资料核对']
    assert '跨部门整理' in owner_catalog['work_categories']['非项目工作']
    catalog=categories.category_catalog(db,member)
    assert '客户研究' not in catalog['work_categories']
    assert '跨部门整理' not in catalog['work_categories']['非项目工作']
    assert '个人固定选项' not in catalog['layout_task_presets']
    assert '培训会议' not in catalog['work_categories']['会议']
    assert '培训会议' in catalog['work_categories']['培训工作']


def test_pure_minutes_and_multi_person_action_tasks_are_atomic_and_personal(setup):
    db,users=setup;owner,member,outsider=users
    from meeting_records import RecordWrite, save, tasks, status, StatusWrite
    result=service.create(db,owner,payload(users))
    meeting_id=result['id']
    assert save(db,owner,meeting_id,RecordWrite(content='仅记录讨论，无任务',version=0))['version']==1
    assert tasks(db,member,'','',1,10)['total']==0
    with pytest.raises(HTTPException):save(db,member,meeting_id,RecordWrite(content='越权',version=1))
    action={'client_id':uuid4(),'user_ids':[member.id,outsider.id],'category':'non_project','content':'整理会议结论','due_at':now()+timedelta(days=1)}
    save(db,owner,meeting_id,RecordWrite(content='会议结论',version=1,actions=[action]))
    assert tasks(db,member,'non_project','整理 结论',1,10)['total']==1
    assert tasks(db,outsider,'non_project','',1,10)['total']==1
    assert tasks(db,owner,'','',1,10)['total']==0
    saved=tasks(db,member,'','',1,10)['items'][0]
    assert saved['arranger_id']==owner.id and saved['arranger_name']==owner.full_name
    with pytest.raises(HTTPException):status(db,outsider,saved['id'],StatusWrite(status='completed',revision=1))
    assert status(db,member,saved['id'],StatusWrite(status='completed',revision=1))['completed_at']
    with pytest.raises(HTTPException):save(db,owner,meeting_id,RecordWrite(content='旧记录',version=1))
    assert service.detail(db,owner,meeting_id)['record_content']=='会议结论'


def test_availability_checks_entire_meeting_shift_and_leave_overlap(setup,monkeypatch):
    db,(owner,member,_)=setup
    import attendance_service
    from models import EmployeeLeave
    moment=now().replace(hour=9,minute=0,second=0,microsecond=0)
    monkeypatch.setattr(attendance_service,'shifts_for',lambda _db,people,day:{str(p.id):{'name':'早班','periods':['09:00–12:00']} for p in people})
    db.add(EmployeeLeave(id=uuid4(),employee_id=member.id,employee_name=member.full_name,start_date=moment.replace(tzinfo=None)+timedelta(minutes=15),end_date=moment.replace(tzinfo=None)+timedelta(minutes=45)))
    db.commit()
    rows={r['user_id']:r for r in service.availability(db,moment,moment+timedelta(hours=1))}
    assert rows[owner.id]['in_shift'] and not rows[owner.id]['on_leave']
    assert rows[member.id]['on_leave']
    assert not {r['user_id']:r for r in service.availability(db,moment,moment+timedelta(hours=4))}[owner.id]['in_shift']


def test_meeting_numbers_daily_sequence_legacy_search_and_all_organizers(setup, monkeypatch):
    from datetime import datetime, date
    from chat_time import BUSINESS_TIMEZONE
    from meeting_numbering import code_for, codes_query
    from sqlalchemy.dialects import postgresql
    from types import SimpleNamespace
    db, users = setup
    owner, member, outsider = users
    clock = datetime(2026, 11, 26, 9, tzinfo=BUSINESS_TIMEZONE)
    monkeypatch.setattr(service, 'now', lambda: clock)
    def new(organizer):
        return service.create(db, organizer, service.MeetingWrite(client_id=uuid4(), meeting_type='管理会议', location='线上', topic='编号验证',
            start_at=clock+timedelta(hours=1), end_at=clock+timedelta(hours=2), user_ids=[member.id]))
    first = new(owner)
    row = db.query(Meeting).filter_by(id=first['id']).one()
    row.association = {}; db.commit()  # 兼容此前没有编号快照的会议
    assert code_for(db, row) == 'MT-261126-001'
    second = new(outsider)
    assert second['meeting_no'] == 'MT-261126-002'
    assert service.listing(db, member, anchor=date(2026, 11, 26))['total'] == 2
    found = service.listing(db, owner, 'MT-261126-002', anchor=date(2026, 11, 26))
    assert found['total'] == 1 and found['items'][0]['organizer_id'] == outsider.id
    assert not found['items'][0]['is_organizer'] and found['items'][0]['my_response'] is None
    with pytest.raises(HTTPException): service.detail(db, owner, second['id'])
    clock += timedelta(days=1)
    third = new(owner)
    assert third['meeting_no'] == 'MT-261127-001'
    assert service.listing(db, member, period='week', anchor=date(2026, 11, 26))['total'] == 3
    assert service.listing(db, member, period='month', anchor=date(2026, 11, 1))['total'] == 3
    assert service.listing(db, member, period='year', anchor=date(2026, 1, 1))['total'] == 3
    assert service.listing(db, member, anchor=date(2026, 11, 28))['total'] == 0
    compiled = str(codes_query(SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name='postgresql')))).select().compile(dialect=postgresql.dialect()))
    assert 'timezone(' in compiled and 'row_number() OVER' in compiled and ' || ' in compiled


def test_meeting_range_utc8_week_month_year_boundaries():
    from datetime import date
    for period, anchor, left, right in [
        ('day', date(2026,11,26), '2026-11-26', '2026-11-27'),
        ('week', date(2026,11,29), '2026-11-23', '2026-11-30'),
        ('month', date(2024,2,15), '2024-02-01', '2024-03-01'),
        ('year', date(2026,12,31), '2026-01-01', '2027-01-01'),
    ]:
        start, end = service.period_bounds(period, anchor)
        assert start.date().isoformat() == left and end.date().isoformat() == right
        assert start.utcoffset() == end.utcoffset() == timedelta(hours=8)


def test_manual_status_clock_conflict_boundaries_and_permissions(setup, monkeypatch):
    from datetime import datetime
    from chat_time import BUSINESS_TIMEZONE
    db, users = setup
    owner, member, outsider = users
    clock = datetime(2026,11,26,9,tzinfo=BUSINESS_TIMEZONE)
    monkeypatch.setattr(service, 'now', lambda: clock)
    data = service.MeetingWrite(client_id=uuid4(), meeting_type='管理会议', location='线上', topic='状态测试',
        start_at=clock+timedelta(hours=1), end_at=clock+timedelta(hours=2), user_ids=[member.id])
    meeting = service.create(db,owner,data)
    assert meeting['status']=='pending' and meeting['status_started_at'] is None
    assert len(service.location_conflicts(db,'线上',data.start_at,data.end_at)) == 1
    assert service.location_conflicts(db,'线上',data.end_at,data.end_at+timedelta(hours=1)) == []
    assert service.location_conflicts(db,'广州公司内会议室（+线上）',data.start_at,data.end_at) == []
    for user in (member, outsider):
        with pytest.raises(HTTPException): service.change_status(db,user,meeting['id'],service.StatusWrite(status='in_progress',version=0))
    running=service.change_status(db,owner,meeting['id'],service.StatusWrite(status='in_progress',version=0))
    assert running['status_started_at'] == clock.isoformat()
    assert running['status_version']==1 and running['meeting_no']==meeting['meeting_no']
    clock+=timedelta(days=1)
    assert service.summary(db,owner)['upcoming'][0]['status']=='in_progress'  # 不随计划结束时间自动结束
    with pytest.raises(HTTPException): service.change_status(db,owner,meeting['id'],service.StatusWrite(status='ended',version=0))
    ended=service.change_status(db,owner,meeting['id'],service.StatusWrite(status='ended',version=1))
    assert ended['status']=='ended' and service.summary(db,owner)['upcoming']==[]
    cancelled=service.change_status(db,owner,meeting['id'],service.StatusWrite(status='cancelled',version=2))
    assert cancelled['status']=='cancelled'
    assert service.location_conflicts(db,'线上',data.start_at,data.end_at)==[]
    reset=service.change_status(db,owner,meeting['id'],service.StatusWrite(status='pending',version=3))
    assert reset['status_started_at'] is None
    assert len(service.location_conflicts(db,'线上',data.start_at,data.end_at))==1
    again=service.change_status(db,owner,meeting['id'],service.StatusWrite(status='in_progress',version=4))
    assert again['status_started_at']==clock.isoformat()
    assert len(service.location_conflicts(db,'线上',data.start_at+timedelta(minutes=1),data.end_at))==1
