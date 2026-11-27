"""会议安排：当前账号访问范围、参会人员快照、班次提示、原子通知与回执。"""
from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import inspect, or_, func
from sqlalchemy.exc import IntegrityError
from models import AppUser, AppNotification, EmployeeLeave
from chat_time import now, api_time, BUSINESS_TIMEZONE
from meeting_models import Meeting, MeetingParticipant
from search_matching import keyword_any
from meeting_numbering import allocate, code_for, codes_query

TYPES = ('项目会议', '管理会议', '部门会议', '培训会议', '客户会议', '开发会议', '其他会议')
LOCATIONS = ('广州公司内会议室（+线上）', '广州公司外会议室（+线上）', '线上')
STATUS_LABELS = {'pending': '待开始', 'in_progress': '进行中', 'ended': '已结束', 'cancelled': '已取消'}


def meeting_state(row):
    value = (row.association or {}).get('lifecycle') or {}
    return {'status': value.get('status', 'pending'), 'status_started_at': value.get('started_at'), 'status_version': value.get('version', 0)}


class StatusWrite(BaseModel):
    status: Literal['pending', 'in_progress', 'ended', 'cancelled']
    version: int = Field(ge=0)


def change_status(db, user, meeting_id, data):
    require_ready(db)
    row = db.query(Meeting).filter_by(id=meeting_id).with_for_update().first()
    if not row or row.organizer_id != user.id:
        raise HTTPException(403, '仅召开人可调整会议状态')
    state = meeting_state(row)
    if state['status_version'] != data.version:
        raise HTTPException(409, '会议状态已更新，请刷新后重试')
    if data.status == state['status']:
        return detail(db, user, row.id)
    moment = now()
    lifecycle = {'status': data.status, 'version': data.version+1, 'updated_at': moment.isoformat(),
                 'started_at': moment.isoformat() if data.status == 'in_progress' else state['status_started_at']}
    if data.status == 'pending':
        lifecycle['started_at'] = None
    row.association = {**(row.association or {}), 'lifecycle': lifecycle}
    targets = [uid for uid, in db.query(MeetingParticipant.user_id).filter_by(meeting_id=row.id)]
    events = notify(db, targets, row, f'会议状态 · {code_for(db, row)}', f'{row.topic}：{STATUS_LABELS[data.status]}', 'meeting_invitation')
    db.commit()
    publish(events)
    return detail(db, user, row.id)


def location_conflicts(db, location, start_at, end_at):
    require_ready(db)
    start_at, end_at = stamp(start_at), stamp(end_at)
    if location not in LOCATIONS or end_at <= start_at:
        raise HTTPException(422, '请填写有效的地点和起止时间')
    codes = codes_query(db)
    rows = db.query(Meeting, codes.c.meeting_no).join(codes, codes.c.meeting_id == Meeting.id).filter(
        Meeting.location == location, Meeting.start_at < end_at, Meeting.end_at > start_at,
        func.coalesce(Meeting.association['lifecycle']['status'].as_string(), 'pending') != 'cancelled').order_by(Meeting.start_at).all()
    return api_time([{'id': row.id, 'meeting_no': code, 'topic': row.topic, 'start_at': row.start_at, 'end_at': row.end_at} for row, code in rows])


def stamp(value):
    return value.replace(tzinfo=BUSINESS_TIMEZONE) if value.tzinfo is None else value.astimezone(BUSINESS_TIMEZONE)


def lead_minutes(start, end):
    minutes = (stamp(end) - stamp(start)).total_seconds() / 60
    return 10 if minutes <= 30 else 15 if minutes <= 60 else 20


class PeopleSelection(BaseModel):
    all_people: bool = False
    department_ids: list[UUID] = Field(default_factory=list, max_length=500)
    user_ids: list[UUID] = Field(default_factory=list, max_length=2000)


class AgendaWrite(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    same_people: bool = True
    user_ids: list[UUID] = Field(default_factory=list, max_length=2000)

    @model_validator(mode='after')
    def check_content(self):
        if not self.content.strip():
            raise ValueError('请填写议程内容')
        if not self.same_people and not self.user_ids:
            raise ValueError('请为议程选择参与人员')
        return self


class MeetingWrite(PeopleSelection):
    client_id: UUID
    meeting_type: Literal['项目会议', '管理会议', '部门会议', '培训会议', '客户会议', '开发会议', '其他会议']
    location: Literal['广州公司内会议室（+线上）', '广州公司外会议室（+线上）', '线上']
    start_at: datetime
    end_at: datetime
    topic: str = Field(default='', max_length=500)
    note: str = Field(default='', max_length=10000)
    project_type: str = Field(default='', max_length=30)
    project_id: UUID | None = None
    client_ids: list[UUID] = Field(default_factory=list, max_length=50)
    technical_task_id: UUID | None = None
    task_name: str = Field(default='', max_length=255)
    agendas: list[AgendaWrite] = Field(default_factory=list, max_length=50)

    @model_validator(mode='after')
    def check_time(self):
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError('会议时间必须携带UTC+8时区')
        self.start_at, self.end_at = stamp(self.start_at), stamp(self.end_at)
        if self.end_at <= self.start_at or self.end_at - self.start_at > timedelta(days=7):
            raise ValueError('结束时间必须晚于开始时间，单次会议最多7天')
        if self.meeting_type == '其他会议' and not self.topic.strip():
            raise ValueError('请填写自定义会议内容')
        if self.meeting_type == '开发会议' and not self.task_name.strip():
            raise ValueError('请填写开发任务名称')
        if sum(len(a.content) for a in self.agendas) > 8000:
            raise ValueError('会议议程内容合计最多8000字，方便完整写入工作报告')
        return self


class ReceiptWrite(BaseModel):
    response: Literal['attending', 'declined']
    reason: str = Field(default='', max_length=2000)
    version: int = Field(ge=0)

    @model_validator(mode='after')
    def check_reason(self):
        if self.response == 'declined' and not self.reason.strip():
            raise ValueError('不能参加时必须说明事由')
        return self


def require_ready(db):
    if not all(inspect(db.connection()).has_table(name) for name in ('meeting_arrangement', 'meeting_participant', 'meeting_action_task')):
        raise HTTPException(503, '会议安排表尚未初始化')


def directory(db):
    from department_models import Department, DepartmentMember
    from organization_service import ready
    people = db.query(AppUser).filter(AppUser.is_active.is_(True), AppUser.is_deleted.is_(False)).order_by(AppUser.full_name, AppUser.username).all()
    departments = db.query(Department).order_by(Department.name).all() if ready(db) else []
    links = db.query(DepartmentMember).all() if departments else []
    by_id = {d.id: d for d in departments}
    groups = {}
    for link in links:
        if link.department_id in by_id:
            groups.setdefault(link.user_id, set()).add(link.department_id)
    for person in people:
        for d in departments:
            if person.department in [d.name, *(d.aliases or [])]:
                groups.setdefault(person.id, set()).add(d.id)
    return people, departments, groups


def context(db):
    people, departments, groups = directory(db)
    return {'people': [{'id': p.id, 'name': p.full_name or p.username, 'username': p.username,
                        'department_ids': list(groups.get(p.id, [])), 'department': p.department or ''} for p in people],
            'departments': [{'id': d.id, 'name': d.name} for d in departments], 'types': TYPES, 'locations': LOCATIONS}


def resolve_people(db, selection):
    people, departments, groups = directory(db)
    department_ids, user_ids = set(selection.department_ids), set(selection.user_ids)
    if department_ids - {d.id for d in departments} or user_ids - {p.id for p in people}:
        raise HTTPException(422, '人员或部门已停用/不存在，请刷新重选')
    targets = [p for p in people if selection.all_people or p.id in user_ids or groups.get(p.id, set()) & department_ids]
    names = [d.name for d in departments if d.id in department_ids or any(d.id in groups.get(p.id, set()) for p in targets)]
    return targets, names


def availability(db, start_at, end_at):
    from attendance_service import shifts_for, intervals, merged
    from attendance_models import AttendanceLeave
    start_at, end_at = stamp(start_at), stamp(end_at)
    if end_at <= start_at or end_at - start_at > timedelta(days=7):
        raise HTTPException(422, '请填写有效会议起止时间（最多7天）')
    people, _, _ = directory(db)
    windows = {p.id: [] for p in people}
    labels = {p.id: set() for p in people}
    day = start_at.date() - timedelta(days=1)
    while day <= end_at.date():
        shifts = shifts_for(db, people, day)
        for p in people:
            shift = shifts.get(str(p.id))
            if shift:
                windows[p.id].extend(intervals(day, shift))
                labels[p.id].add(shift.get('name') or shift.get('label') or shift.get('code', '已排班'))
        day += timedelta(days=1)
    leave_ids = set()
    for model, uid, left, right in [(AttendanceLeave, AttendanceLeave.user_id, AttendanceLeave.start_at, AttendanceLeave.end_at),
                                    (EmployeeLeave, EmployeeLeave.employee_id, EmployeeLeave.start_date, EmployeeLeave.end_date)]:
        if inspect(db.connection()).has_table(model.__tablename__):
            # 旧请假字段存业务本地时间，新请假字段为实际时刻。
            start, end = (start_at.replace(tzinfo=None), end_at.replace(tzinfo=None)) if model is EmployeeLeave else (start_at, end_at)
            leave_ids.update(value for value, in db.query(uid).filter(left < end, right > start).distinct())
    return [{'user_id': p.id, 'shift': '、'.join(sorted(labels[p.id])) or '未排班/休息',
             'in_shift': any(left <= start_at and right >= end_at for left, right in merged(windows[p.id])),
             'on_leave': p.id in leave_ids} for p in people]


def visible_query(db, user):
    member = db.query(MeetingParticipant.meeting_id).filter(MeetingParticipant.user_id == user.id)
    return db.query(Meeting).filter(or_(Meeting.organizer_id == user.id, Meeting.id.in_(member)))


def get_meeting(db, user, meeting_id):
    row = visible_query(db, user).filter(Meeting.id == meeting_id).first()
    if not row:
        raise HTTPException(404, '会议不存在或无权查看')
    return row


def notify(db, recipients, row, title, content, kind):
    moment = now()
    events = []
    for uid in set(recipients):
        record = AppNotification(id=uuid4(), recipient_user_id=uid, title=title, content=content,
                                 notification_type=kind, related_entity_id=row.id, is_read=False, created_at=moment.replace(tzinfo=None))
        db.add(record)
        events.append((uid, api_time({'type': 'notification', 'notification': {'id': str(record.id), 'title': title, 'content': content,
            'notification_type': kind, 'related_entity_id': str(row.id), 'is_read': False, 'created_at': moment}})))
    return events


def publish(events):
    from notification_ws import broadcast_to_users
    from fastapi.encoders import jsonable_encoder
    import logging
    for uid, payload in events:
        try:
            broadcast_to_users([uid], jsonable_encoder(payload))
        except Exception:
            logging.getLogger(__name__).exception('会议通知已入库，实时推送失败')


def create(db, user, data):
    require_ready(db)
    existing = db.query(Meeting).filter_by(client_id=data.client_id).first()
    if existing:
        if existing.organizer_id != user.id:
            raise HTTPException(409, '重复请求编号')
        return detail(db, user, existing.id)
    if data.start_at <= now():
        raise HTTPException(422, '会议开始时间必须晚于当前时间')
    targets, names = resolve_people(db, data)
    if not targets:
        raise HTTPException(422, '请至少选择一名参会人员')
    target_ids = {p.id for p in targets}
    agendas = []
    for agenda in data.agendas:
        ids = target_ids if agenda.same_people else set(agenda.user_ids)
        if not ids <= target_ids:
            raise HTTPException(422, '议程参与人员须在会议参与人员名单内')
        agendas.append({'content': agenda.content.strip(), 'same_people': agenda.same_people, 'user_ids': sorted(str(uid) for uid in ids)})
    association = {}
    if data.meeting_type == '项目会议' and data.project_id:
        from report_project_picker import resolve
        if data.project_type not in ('笔译项目', '口译项目', '标注项目', '招聘项目'):
            raise HTTPException(422, '请选择四类项目之一')
        association['project'] = resolve(db, data.project_type, data.project_id)
    if data.meeting_type == '客户会议':
        from models import Client
        if not data.client_ids:
            raise HTTPException(422, '请选择客户名称')
        clients = db.query(Client).filter(Client.id.in_(set(data.client_ids))).all()
        if len(clients) != len(set(data.client_ids)):
            raise HTTPException(422, '客户不存在')
        association['clients'] = [{'id': str(c.id), 'name': c.client_short_name or c.client_name} for c in clients]
    if data.meeting_type in ('部门会议', '培训会议'):
        if not names:
            raise HTTPException(422, '所选人员未设置部门，请先选择部门')
        association['department_names'] = names
    if data.meeting_type == '开发会议':
        association['task_name'] = data.task_name.strip()
        if data.technical_task_id:
            import technical_development as tech
            tech.require_user(user, db)
            task = db.get(tech.DevelopmentTask, data.technical_task_id)
            if not task:
                raise HTTPException(404, '技术开发任务不存在')
            association['technical_task_id'] = str(task.id)
            from technical_task_management import numbers
            association['technical_task_number'] = numbers(db).get(task.id) or ''
    topic = '、'.join(names) + data.meeting_type if data.meeting_type in ('部门会议', '培训会议') else data.topic.strip()
    topic = topic or association.get('task_name') or (association.get('project') or {}).get('project_name') or '、'.join(c['name'] for c in association.get('clients', [])) or data.meeting_type
    conflicts = location_conflicts(db, data.location, data.start_at, data.end_at)
    created_at = now()
    association['meeting_no'] = allocate(db, created_at)
    row = Meeting(created_at=created_at, id=uuid4(), client_id=data.client_id, organizer_id=user.id, topic=topic[:500], meeting_type=data.meeting_type,
                  location=data.location, start_at=data.start_at, end_at=data.end_at, note=data.note,
                  agendas=agendas,
                  selection=data.model_dump(mode='json', include={'all_people', 'department_ids', 'user_ids'}), association=association)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(Meeting).filter_by(client_id=data.client_id, organizer_id=user.id).first()
        if existing:
            return detail(db, user, existing.id)
        raise
    for p in targets:
        db.add(MeetingParticipant(meeting_id=row.id, user_id=p.id, name=p.full_name or p.username))
    events = notify(db, [p.id for p in targets], row, f'会议安排 · {code_for(db, row)}',
                    f'{row.topic}；{data.start_at:%Y年%m月%d日 %H:%M} 至 {data.end_at:%Y年%m月%d日 %H:%M}（UTC+8）；{row.location}。请在会议安排中提交参会回执。', 'meeting_invitation')
    db.commit()
    publish(events)
    result = detail(db, user, row.id)
    result['location_conflicts'] = conflicts
    return result


def serialize(row, user, members, organizer_name, meeting_no):
    mine = next((p for p in members if p.user_id == user.id), None)
    return api_time({**meeting_state(row), 'server_now': now(), 'id': row.id, 'number': row.number, 'meeting_no': meeting_no, 'organizer_id': row.organizer_id, 'organizer_name': organizer_name,
        'is_organizer': row.organizer_id == user.id, 'topic': row.topic, 'meeting_type': row.meeting_type,
        'location': row.location, 'start_at': row.start_at, 'end_at': row.end_at, 'note': row.note, 'association': row.association,
        'remind_before_minutes': lead_minutes(row.start_at, row.end_at), 'participant_count': len(members),
        'pending_count': sum(p.response == 'pending' for p in members),
        'unread_receipts': sum(p.response_version > p.organizer_seen_version for p in members) if row.organizer_id == user.id else 0,
        'my_response': mine.response if mine else None, 'my_reason': mine.reason if mine else '', 'my_version': mine.response_version if mine else None,
        'created_at': row.created_at, 'agendas': row.agendas,
        'actual_start_at': row.actual_start_at, 'actual_end_at': row.actual_end_at,
        'actual_user_ids': row.actual_user_ids, 'confirmed_at': row.confirmed_at,
        'record_content': row.record_content, 'record_version': row.record_version})


def period_bounds(period, anchor):
    day = anchor or now().date()
    if period == 'week':
        start = day - timedelta(days=day.weekday()); end = start + timedelta(days=7)
    elif period == 'month':
        start = day.replace(day=1); end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    elif period == 'year':
        start = day.replace(month=1, day=1); end = start.replace(year=start.year+1)
    else:
        start = day; end = day + timedelta(days=1)
    return datetime.combine(start, time.min, BUSINESS_TIMEZONE), datetime.combine(end, time.min, BUSINESS_TIMEZONE)


def listing(db, user, keyword='', page=1, page_size=10, period='day', anchor=None):
    require_ready(db)
    left, right = period_bounds(period, anchor)
    codes = codes_query(db)
    query = db.query(Meeting).join(codes, codes.c.meeting_id == Meeting.id).filter(
        Meeting.start_at < right, Meeting.end_at > left,
        keyword_any([Meeting.topic, Meeting.meeting_type, Meeting.location, codes.c.meeting_no, func.cast(Meeting.number, __import__('sqlalchemy').String)], keyword))
    total = query.count()
    rows = query.add_columns(codes.c.meeting_no).order_by(Meeting.start_at.desc(), Meeting.number.desc()).offset((page-1)*page_size).limit(page_size).all()
    ids = [r.id for r, code in rows]
    members = db.query(MeetingParticipant).filter(MeetingParticipant.meeting_id.in_(ids)).all() if ids else []
    users = {p.id: p.full_name or p.username for p in db.query(AppUser).filter(AppUser.id.in_({r.organizer_id for r, code in rows})).all()} if rows else {}
    return api_time({'total': total, 'server_now': now(), 'range_start': left, 'range_end': right, 'items': [serialize(r, user, [p for p in members if p.meeting_id == r.id], users.get(r.organizer_id, ''), code) for r, code in rows]})


def detail(db, user, meeting_id):
    require_ready(db)
    row = get_meeting(db, user, meeting_id)
    members = db.query(MeetingParticipant).filter_by(meeting_id=row.id).order_by(MeetingParticipant.name, MeetingParticipant.user_id).all()
    organizer = db.get(AppUser, row.organizer_id)
    data = serialize(row, user, members, organizer.full_name or organizer.username if organizer else '', code_for(db, row))
    # 不能参加的个人事由仅向召开人及本人展示。
    data['participants'] = [api_time({'user_id': p.user_id, 'name': p.name, 'response': p.response,
        'reason': p.reason if row.organizer_id == user.id or p.user_id == user.id else '', 'responded_at': p.responded_at,
        'response_version': p.response_version}) for p in members]
    from meeting_records import serialize as serialize_actions
    from meeting_models import MeetingActionTask
    actions = db.query(MeetingActionTask).filter_by(meeting_id=row.id)
    if row.organizer_id != user.id:
        actions = actions.filter_by(assignee_id=user.id)
    data['actions'] = serialize_actions(db, actions.order_by(MeetingActionTask.assigned_at, MeetingActionTask.id).all())
    return data


def receipt(db, user, meeting_id, data):
    require_ready(db)
    row = get_meeting(db, user, meeting_id)
    member = db.query(MeetingParticipant).filter_by(meeting_id=row.id, user_id=user.id).with_for_update().first()
    if not member:
        raise HTTPException(403, '只有参会人员可以提交回执')
    reason = data.reason.strip() if data.response == 'declined' else ''
    if member.response == data.response and member.reason == reason:
        return detail(db, user, row.id)
    if member.response_version != data.version:
        raise HTTPException(409, '回执已更新，请刷新后重试')
    member.response, member.reason, member.responded_at = data.response, reason, now()
    member.response_version += 1
    db.commit()
    return detail(db, user, row.id)


def read_receipts(db, user, meeting_id, versions):
    row = get_meeting(db, user, meeting_id)
    if row.organizer_id != user.id:
        raise HTTPException(403, '仅召开人可标记已读回执')
    for uid, version in versions.items():
        member = db.get(MeetingParticipant, (row.id, uid))
        if member:
            member.organizer_seen_version = max(member.organizer_seen_version, min(version, member.response_version))
    db.commit()


def summary(db, user):
    require_ready(db)
    invitations = db.query(MeetingParticipant).filter_by(user_id=user.id, response='pending').count()
    receipts = db.query(MeetingParticipant).join(Meeting, Meeting.id == MeetingParticipant.meeting_id).filter(
        Meeting.organizer_id == user.id, MeetingParticipant.response_version > MeetingParticipant.organizer_seen_version).count()
    state = func.coalesce(Meeting.association['lifecycle']['status'].as_string(), 'pending')
    upcoming = db.query(Meeting).filter(Meeting.organizer_id == user.id, or_(state == 'in_progress', (state == 'pending') & (Meeting.end_at > now()))).order_by(Meeting.start_at).all()
    unread = db.query(AppNotification).filter(AppNotification.recipient_user_id == user.id, AppNotification.is_read.is_(False),
        AppNotification.notification_type.in_(['meeting_invitation', 'meeting_task'])).count()
    return api_time({'pending': invitations, 'unread_receipts': receipts, 'unread_notifications': unread, 'server_now': now(),
        'upcoming': [{**meeting_state(r), 'meeting_no': code_for(db, r), 'id': r.id, 'number': r.number, 'topic': r.topic, 'start_at': r.start_at, 'end_at': r.end_at,
                      'remind_before_minutes': lead_minutes(r.start_at, r.end_at)} for r in upcoming]})
