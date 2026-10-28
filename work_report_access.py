"""工作报告查看范围：仅赵震锋配置，按当前部门名册解析发送范围。"""
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Uuid, inspect, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, joinedload, mapped_column, selectinload

from chat_time import now, api_time
from models import AppUser, Base

CONFIGURATOR_USERNAME = 'williamzhao'  # 已核对：赵震锋的现有账号。
SAME_VIEWING_USERNAMES = frozenset({'williamzhao', 'lulu', 'ethan'})
SUGGESTED_VIEWERS = ['ethan', 'thomas', 'shaofei', 'lulu', 'yunjian', 'jiaming', 'cuizhen', 'yuqi', CONFIGURATOR_USERNAME]


class WorkReportAccessRule(Base):
    __tablename__ = 'work_report_access_rule'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    viewers_all: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    viewer_ids: Mapped[list] = mapped_column(JSONB().with_variant(JSON, 'sqlite'), nullable=False, default=list)
    senders_all: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    all_departments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    department_ids: Mapped[list] = mapped_column(JSONB().with_variant(JSON, 'sqlite'), nullable=False, default=list)
    sender_ids: Mapped[list] = mapped_column(JSONB().with_variant(JSON, 'sqlite'), nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    updated_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)


class AccessRuleWrite(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    viewers_all: bool = False
    viewer_ids: list[UUID] = Field(default_factory=list, max_length=2000)
    senders_all: bool = False
    all_departments: bool = False
    department_ids: list[UUID] = Field(default_factory=list, max_length=2000)
    sender_ids: list[UUID] = Field(default_factory=list, max_length=2000)
    enabled: bool = True
    revision: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def validate_scope(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError('请填写规则名称')
        if not self.viewers_all and not self.viewer_ids:
            raise ValueError('请选择有权查看人')
        if not (self.senders_all or self.all_departments or self.department_ids or self.sender_ids):
            raise ValueError('请选择发送报告人或部门')
        return self


def can_configure(user):
    return bool(user and user.is_active and not user.is_deleted and user.username == CONFIGURATOR_USERNAME)


def same_viewing_access(user):
    return bool(user and user.is_active and not user.is_deleted and user.username in SAME_VIEWING_USERNAMES)


def require_configurator(user):
    if not can_configure(user):
        raise HTTPException(403, '仅赵震锋可查看和配置工作报告设置')


def ready(db):
    return inspect(db.connection()).has_table(WorkReportAccessRule.__tablename__)


def active_people(db):
    return db.query(AppUser).filter(AppUser.is_active.is_(True), AppUser.is_deleted.is_(False))


def serialize_rule(row):
    return {key: api_time(getattr(row, key)) for key in ['id', 'name', 'viewers_all', 'viewer_ids', 'senders_all', 'all_departments', 'department_ids', 'sender_ids', 'enabled', 'revision', 'updated_at']}


def settings(db, user):
    require_configurator(user)
    from organization_service import directory
    catalog = directory(db, user)
    available = ready(db)
    people = [person for person in catalog['people'] if person['active']]
    return {
        'ready': available,
        'people': people, 'departments': catalog['items'],
        'configurator_id': str(user.id),
        'inherited_viewer_ids': [p['id'] for p in people if p['username'] in SAME_VIEWING_USERNAMES and p['username'] != CONFIGURATOR_USERNAME],
        'suggested_viewer_ids': [p['id'] for p in people if p['username'].casefold() in SUGGESTED_VIEWERS],
        'rules': [serialize_rule(row) for row in db.query(WorkReportAccessRule).order_by(WorkReportAccessRule.updated_at.desc(), WorkReportAccessRule.id).all()] if available else [],
    }


def save_rule(db, user, payload, rule_id=None):
    require_configurator(user)
    if not ready(db):
        raise HTTPException(503, '工作报告设置表尚未初始化')
    from department_models import Department
    user_ids = set(payload.viewer_ids + payload.sender_ids)
    if active_people(db).filter(AppUser.id.in_(user_ids)).count() != len(user_ids):
        raise HTTPException(422, '所选人员不存在、已停用或已删除，请重新选择')
    dept_ids = set(payload.department_ids)
    if dept_ids and db.query(Department).filter(Department.id.in_(dept_ids)).count() != len(dept_ids):
        raise HTTPException(422, '所选部门不存在，请刷新后重新选择')
    if rule_id:
        row = db.query(WorkReportAccessRule).filter_by(id=rule_id).with_for_update().first()
        if not row:
            raise HTTPException(404, '匹配规则不存在')
        if payload.revision != row.revision:
            raise HTTPException(409, '规则已被修改，请刷新后重试')
        row.revision += 1
    else:
        row = WorkReportAccessRule(revision=1)
        db.add(row)
    row.name = payload.name
    row.viewers_all = payload.viewers_all
    row.viewer_ids = list(dict.fromkeys([*(str(uid) for uid in payload.viewer_ids), str(user.id)]))
    row.senders_all = payload.senders_all
    row.all_departments = payload.all_departments
    row.department_ids = list(dict.fromkeys(str(uid) for uid in payload.department_ids))
    row.sender_ids = list(dict.fromkeys(str(uid) for uid in payload.sender_ids))
    row.enabled = payload.enabled
    row.updated_at, row.updated_by = now(), user.id
    db.commit()
    return serialize_rule(row)


def receiving_rules(db, user):
    if not user.is_active or user.is_deleted or not ready(db):
        return []
    # Lulu、Ethan 与赵震锋使用同一个查看范围，包含个人专属规则的优先级。
    # 仅共享读取能力，不开放设置修改权限。
    viewer_id = user.id
    if same_viewing_access(user) and user.username != CONFIGURATOR_USERNAME:
        configurator = active_people(db).filter(AppUser.username == CONFIGURATOR_USERNAME).first()
        if not configurator:
            return []
        viewer_id = configurator.id
    rules = [rule for rule in db.query(WorkReportAccessRule).filter_by(enabled=True).all()
             if rule.viewers_all or str(viewer_id) in rule.viewer_ids]
    return effective_rules(db, viewer_id, rules)


def effective_rules(db, viewer_id, rules):
    """单个查看人的专属范围优先于多人共享范围。"""
    configurator = active_people(db).filter(AppUser.username == CONFIGURATOR_USERNAME).first()
    return prioritize_rules(viewer_id, rules, configurator.id if configurator else None)


def prioritize_rules(viewer_id, rules, configurator_id=None):
    excluded = {str(configurator_id)} if configurator_id and viewer_id != configurator_id else set()
    personal = [rule for rule in rules if not rule.viewers_all and set(rule.viewer_ids) - excluded == {str(viewer_id)}]
    return personal or rules


def sender_ids_for_rules(db, rules):
    from department_models import Department
    from organization_service import department_condition
    conditions = []
    for rule in rules:
        if rule.senders_all:
            return {uid for uid, in active_people(db).with_entities(AppUser.id)}
        conditions.append(AppUser.id.in_([UUID(uid) for uid in rule.sender_ids]))
        if rule.all_departments or rule.department_ids:
            departments = db.query(Department)
            if not rule.all_departments:
                departments = departments.filter(Department.id.in_([UUID(uid) for uid in rule.department_ids]))
            names = [dept.name for dept in departments]
            if names:
                conditions.append(department_condition(db, names))
    if not conditions:
        return set()
    return {uid for uid, in active_people(db).with_entities(AppUser.id).filter(or_(*conditions))}


def access_context(db, user):
    from work_report_collaboration import supervisor
    statistics=can_statistics(db,user)
    return {'can_configure': can_configure(user), 'can_receive': bool(receiving_rules(db, user)) or supervisor(user) or statistics, 'can_statistics':statistics,'can_supervise':supervisor(user)}


def received_reports(db, user, date_from, date_to, sender_id, page, page_size, department_id=None, keyword=None):
    from task_models import DailyReport
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, '开始日期不能晚于结束日期')
    allowed = sender_ids_for_rules(db, receiving_rules(db, user))
    allowed=filter_people_ids(db,allowed,department_id,keyword)
    query = db.query(DailyReport).options(joinedload(DailyReport.user), selectinload(DailyReport.items)).filter(DailyReport.user_id.in_(allowed), DailyReport.status == 'finalized')
    if date_from:
        query = query.filter(DailyReport.report_date >= date_from)
    if date_to:
        query = query.filter(DailyReport.report_date <= date_to)
    if sender_id:
        query = query.filter(DailyReport.user_id == sender_id)
    total = query.count()
    rows = query.order_by(DailyReport.report_date.desc(), DailyReport.id).offset((page - 1) * page_size).limit(page_size).all()
    return {'total': total, 'items': [{'id': row.id, 'user_name': row.user.full_name or row.user.username, 'report_date': row.report_date, 'finalized_at': api_time(row.finalized_at), 'duration_minutes': sum(item.duration_minutes for item in row.items)} for row in rows]}


def received_report(db, user, report_id):
    from task_models import DailyReport
    allowed = sender_ids_for_rules(db, receiving_rules(db, user))
    row = db.query(DailyReport).filter(DailyReport.id == report_id, DailyReport.user_id.in_(allowed), DailyReport.status == 'finalized').first()
    if not row:
        raise HTTPException(404, '报告不存在或无权查看')
    from task_service import serialize_report
    return api_time(serialize_report(row))


def can_statistics(db,user):
    if not user.is_active or user.is_deleted:return False
    if same_viewing_access(user):return True
    from organization_service import department_condition
    return bool(active_people(db).filter(AppUser.id==user.id,department_condition(db,['行政部'])).first())


def filter_people_ids(db,ids,department_id=None,keyword=None):
    from department_models import Department
    from organization_service import department_condition
    from search_matching import keyword_any
    query=active_people(db).filter(AppUser.id.in_(ids))
    if department_id:
        dept=db.get(Department,department_id)
        if not dept:return set()
        query=query.filter(department_condition(db,[dept.name]))
    if keyword:query=query.filter(keyword_any([AppUser.full_name,AppUser.username],keyword))
    return {uid for uid, in query.with_entities(AppUser.id)}


def review_directory(db,user):
    from organization_service import directory
    data=directory(db,user)
    ids={uid for uid, in active_people(db).with_entities(AppUser.id)} if can_statistics(db,user) else sender_ids_for_rules(db,receiving_rules(db,user))
    people=[person for person in data['people'] if person['active'] and UUID(person['id']) in ids]
    dept_ids={dept['id'] for person in people for dept in person['departments']}
    return {'people':people,'departments':[dept for dept in data['items'] if dept['id'] in dept_ids],**access_context(db,user)}


def report_statistics(db,user,anchor,period,department_id=None,keyword=None,sender_id=None):
    if not can_statistics(db,user):raise HTTPException(403,'仅行政部及赵震锋可以统计工作报告')
    from datetime import timedelta
    from task_models import DailyReport
    from work_report_calendar import period_bounds,is_workday,CALENDARS
    start,end=period_bounds(anchor,period)
    from work_report_dates import report_business_date
    end=min(end,report_business_date(now()))
    # 校验完整范围，拒绝未知年份，避免隐式按周一至周五统计。
    days=[];day=start
    while day<=end:
        if is_workday(day):days.append(day)
        day+=timedelta(days=1)
    ids=filter_people_ids(db,{uid for uid, in active_people(db).with_entities(AppUser.id)},department_id,keyword)
    if sender_id:ids.intersection_update({sender_id})
    people=active_people(db).filter(AppUser.id.in_(ids)).order_by(AppUser.full_name,AppUser.username).all()
    confirmed={(uid,day) for uid,day in db.query(DailyReport.user_id,DailyReport.report_date).filter(DailyReport.user_id.in_(ids),DailyReport.status=='finalized',DailyReport.report_date>=start,DailyReport.report_date<=end)}
    def expected(person,day):return person.created_at is None or api_time(person.created_at).date()<=day
    daily=[]
    for day in days:
        required=[p for p in people if expected(p,day)]
        written=[str(p.id) for p in required if (p.id,day) in confirmed]
        missing=[str(p.id) for p in required if (p.id,day) not in confirmed]
        daily.append({'date':day,'expected_count':len(required),'written_ids':written,'missing_ids':missing})
    rows=[{'id':str(p.id),'name':p.full_name or p.username,'expected_count':sum(expected(p,day) for day in days),'missing_dates':[day for day in days if expected(p,day) and (p.id,day) not in confirmed]} for p in people]
    return {'date_from':start,'date_to':end if end>=start else None,'days':daily,'people':rows,'calendar_sources':list(dict.fromkeys(CALENDARS[d.year]['source'] for d in days)),'basis':'法定工作日（含调休）；仅已确认算已写；当前启用人员，自账号创建日开始统计，未来日期不计入。'}
