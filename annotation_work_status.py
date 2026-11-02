"""每日累计用时汇报：项目进度、工作报告在同一事务内同步。"""
from datetime import datetime, time
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import exists, inspect

from annotation_models import AnnotationProject
from annotation_ops_models import AnnotationProjectStatusHistory
from annotation_today_tasks import EXCLUDED_STATUSES
from annotation_work_status_models import AnnotationWorkDay, AnnotationWorkSubmission, AnnotationWorkReminder, AnnotationWorkAvailability
from chat_time import now, api_time, BUSINESS_TIMEZONE
from models import AppUser
from task_models import DailyReport, DailyReportItem
from task_schemas import DailyReportItemInput
from workflow_models import ProjectWorkbenchResponsibility
from work_report_dates import report_business_date
from annotation_work_arrangement import latest_states

SLOTS = ('11', '15', '18', '21', 'end_shift')
REMAINING = ('under_30', '30_60', '1_2h', '2_5h', '5_10h', 'over_10h')
REMAINING_LABELS = dict(zip(REMAINING, ('30分钟内', '30-60分钟', '1-2小时', '2-5小时', '5-10小时', '10小时以上')))
IDLE_LABELS = {'undetermined':'未定', **{key:REMAINING_LABELS[key] for key in REMAINING[:4]}}


class AvailabilityWrite(BaseModel):
    slot: Literal['11', '15', '18', '21', 'end_shift']
    revision: int = Field(ge=0)
    is_idle: bool = Field(strict=True)
    expected_idle_time: Literal['undetermined', 'under_30', '30_60', '1_2h', '2_5h'] | None = None

    @model_validator(mode='after')
    def idle_estimate_required(self):
        if self.is_idle and not self.expected_idle_time:
            raise ValueError('请选择预计空闲时间')
        if not self.is_idle:
            self.expected_idle_time = None
        return self


class ArrangementWrite(BaseModel):
    revision: int = Field(ge=0)
    arrangement_status: Literal['in_progress', 'not_today']
    remaining_time: Literal['under_30', '30_60', '1_2h', '2_5h', '5_10h', 'over_10h']


class SubmissionWrite(ArrangementWrite):
    slot: Literal['11', '15', '18', '21', 'end_shift']
    progress_note: str = Field(min_length=1, max_length=1800)
    cumulative_minutes: int = Field(gt=0, le=1440, strict=True)

    @field_validator('progress_note')
    @classmethod
    def text_required(cls, value):
        if not value.strip():
            raise ValueError('请填写今日目前已完成进度')
        if 'screenshot://' in value.lower() or 'data:image/' in value.lower():
            raise ValueError('请填写文字进度')
        return value.strip()


def ready(db):
    catalog = inspect(db.connection())
    return all(catalog.has_table(model.__tablename__) for model in (AnnotationWorkDay, AnnotationWorkSubmission, AnnotationWorkReminder, AnnotationWorkAvailability))


def require_ready(db):
    if not ready(db):
        raise HTTPException(503, '标注状态汇报表尚未初始化')


def manager_query(db, user):
    role = ProjectWorkbenchResponsibility
    return db.query(AnnotationProject).filter(exists().where(
        role.annotation_project_id == AnnotationProject.id,
        role.role_code == 'project_manager', role.assignee_id == user.id,
    ))


def lock_user(db, user):
    db.query(AppUser).filter_by(id=user.id).with_for_update().populate_existing().one()


def project_for(db, user, project_id):
    # 锁定项目后复核经理归属，防止与经理交接并发。
    project = db.query(AnnotationProject).filter_by(id=project_id).with_for_update().populate_existing().first()
    if not project or not manager_query(db, user).filter(AnnotationProject.id == project_id).first():
        raise HTTPException(404, '未找到本人负责的标注项目')
    return project


def state_for(db, user, project, stamp, revision):
    day = report_business_date(stamp)
    previous = latest_states(db, user.id, day).get(project.id)
    row = previous if previous and previous.work_date == day else None
    if (previous.revision if previous else 0) != revision:
        raise HTTPException(409, '项目进度已更新，请刷新后重试')
    if row is None:
        row = AnnotationWorkDay(id=uuid4(), user_id=user.id, project_id=project.id, work_date=day,
                                arrangement_status=previous.arrangement_status if previous else 'in_progress',
                                remaining_time=previous.remaining_time if previous else None,
                                entered_at=stamp if not previous or previous.arrangement_status == 'in_progress' else None,
                                revision=previous.revision if previous else 0, updated_at=stamp)
        db.add(row)
    return row


def update_state(row, payload, stamp):
    row.arrangement_status, row.remaining_time = payload.arrangement_status, payload.remaining_time
    if payload.arrangement_status == 'in_progress' and row.entered_at is None:
        row.entered_at = stamp
    row.updated_at, row.revision = stamp, row.revision + 1


def state_data(db, row, day=None):
    day = day or report_business_date(now())
    current = row if row and row.work_date == day else None
    submissions = db.query(AnnotationWorkSubmission).filter_by(work_day_id=row.id).order_by(
        AnnotationWorkSubmission.submitted_at, AnnotationWorkSubmission.id
    ).all() if current else []
    return api_time({
        'revision': row.revision if row else 0,
        'arrangement_status': row.arrangement_status if row else 'in_progress',
        'remaining_time': row.remaining_time if row else None,
        'entered_at': current.entered_at if current else (datetime.combine(day, time(hour=7), tzinfo=BUSINESS_TIMEZONE) if not row or row.arrangement_status == 'in_progress' else None),
        'cumulative_minutes': max((entry.cumulative_minutes for entry in submissions), default=0),
        'submissions': [dict(slot=entry.slot, progress_note=entry.progress_note,
                             cumulative_minutes=entry.cumulative_minutes,
                             submitted_at=entry.submitted_at) for entry in submissions],
    })


def context(db, user, project_id=None):
    if not ready(db):
        return {'ready': False, 'items': []}
    stamp = now()
    day = report_business_date(stamp)
    states = latest_states(db, user.id, day)
    query = manager_query(db, user)
    if project_id is not None:
        query = query.filter(AnnotationProject.id == project_id)
    projects = query.order_by(AnnotationProject.order_no.desc()).all()
    # 今日曾经进行中的项目保留到下班汇报，切换“暂不进行”不丢失当天耗时。
    projects = [row for row in projects if row.project_status not in EXCLUDED_STATUSES or
                (row.id in states and states[row.id].work_date == day and states[row.id].entered_at is not None)]
    available = [slot for slot in SLOTS if slot == 'end_shift' or stamp >= slot_time(day, slot)]
    availability = db.query(AnnotationWorkAvailability).filter_by(user_id=user.id, work_date=day).all()
    return api_time({'ready': True, 'work_date': day, 'server_time': stamp, 'available_slots': available,
                    'availability': {row.slot: dict(is_idle=row.is_idle, expected_idle_time=row.expected_idle_time, revision=row.revision) for row in availability},
                    'current_slot': next((slot for slot in reversed(SLOTS[:-1]) if slot in available), 'end_shift'),
                    'items': [dict(id=str(row.id), orderNo=row.order_no, projectName=row.project_name,
                                   projectStatus=row.project_status, **state_data(db, states.get(row.id), day)) for row in projects]})


def slot_time(day, slot):
    return datetime.combine(day, time(hour=int(slot)), tzinfo=BUSINESS_TIMEZONE)


def save_arrangement(db, user, project_id, payload):
    require_ready(db)
    lock_user(db, user)
    project = project_for(db, user, project_id)
    stamp = now()
    if project.project_status in EXCLUDED_STATUSES and payload.arrangement_status == 'in_progress':
        raise HTTPException(409, '该项目当前状态不再属于今日任务，请刷新')
    row = state_for(db, user, project, stamp, payload.revision)
    update_state(row, payload, stamp)
    db.commit()
    return state_data(db, row)


def save_availability(db, user, payload):
    require_ready(db)
    from annotation_chat_service import annotation_department_member
    if not annotation_department_member(db, user) and not manager_query(db, user).first():
        raise HTTPException(403, '仅标注项目部成员或标注项目经理可汇报')
    stamp = now()
    day = report_business_date(stamp)
    if payload.slot != 'end_shift' and stamp < slot_time(day, payload.slot):
        raise HTTPException(422, '尚未到该汇报时点')
    lock_user(db, user)
    row = db.query(AnnotationWorkAvailability).filter_by(user_id=user.id, work_date=day, slot=payload.slot).first()
    if (row.revision if row else 0) != payload.revision:
        raise HTTPException(409, '空闲状态已更新，请刷新后重试')
    report = db.query(DailyReport).filter_by(user_id=user.id, report_date=day).with_for_update().populate_existing().first()
    if report and report.status == 'finalized':
        raise HTTPException(409, '当天工作报告已确认，请先撤回再汇报')
    if row is None:
        row = AnnotationWorkAvailability(id=uuid4(), user_id=user.id, work_date=day, slot=payload.slot, revision=0)
        db.add(row)
    row.is_idle, row.expected_idle_time = payload.is_idle, payload.expected_idle_time
    row.revision, row.updated_at = row.revision + 1, stamp
    naive = stamp.replace(tzinfo=None)
    if report is None:
        report = DailyReport(id=uuid4(), user_id=user.id, report_date=day, status='draft',
            generated_at=naive, created_at=naive, updated_at=naive)
        db.add(report)
    db.flush()
    report.supplemental_note = availability_note(db, user.id, day, report.supplemental_note)
    report.updated_at = naive
    db.commit()
    return {'is_idle': row.is_idle, 'expected_idle_time': row.expected_idle_time, 'revision': row.revision}


def submit(db, user, project_id, payload):
    require_ready(db)
    lock_user(db, user)
    project = project_for(db, user, project_id)
    stamp = now()
    day = report_business_date(stamp)
    if payload.slot != 'end_shift' and stamp < slot_time(day, payload.slot):
        raise HTTPException(422, '尚未到该汇报时点')
    row = state_for(db, user, project, stamp, payload.revision)
    if row.entered_at is None:
        raise HTTPException(422, '请先将项目调整为今日进行中')
    previous = db.query(AnnotationWorkSubmission).filter_by(work_day_id=row.id).all()
    if any(entry.slot == payload.slot for entry in previous):
        raise HTTPException(409, '本时点已汇报，请使用新的汇报时点')
    if payload.cumulative_minutes < max((entry.cumulative_minutes for entry in previous), default=0):
        raise HTTPException(422, '今日累计用时不能小于此前汇报的累计用时')
    report = db.query(DailyReport).filter_by(user_id=user.id, report_date=day).with_for_update().populate_existing().first()
    if report and report.status == 'finalized':
        raise HTTPException(409, '当天工作报告已确认，请先撤回再汇报')
    entry = AnnotationWorkSubmission(id=uuid4(), work_day_id=row.id, slot=payload.slot,
        progress_note=payload.progress_note, cumulative_minutes=payload.cumulative_minutes,
        arrangement_status=payload.arrangement_status, remaining_time=payload.remaining_time, submitted_at=stamp)
    db.add(entry)
    update_state(row, payload, stamp)
    slot_label = '下班汇报' if payload.slot == 'end_shift' else f'{payload.slot}:00汇报'
    note = f'【{slot_label}】{payload.progress_note}\n今日累计用时：{payload.cumulative_minutes}分钟；安排状态：{"今日进行中" if payload.arrangement_status == "in_progress" else "今日暂不进行"}；预计还需时间：{REMAINING_LABELS[payload.remaining_time]}'
    availability = db.query(AnnotationWorkAvailability).filter_by(user_id=user.id, work_date=day, slot=payload.slot).first()
    if availability:
        note += '\n空闲状态：' + ('是；预计空闲时间：' + IDLE_LABELS[availability.expected_idle_time] if availability.is_idle else '否')
    db.add(AnnotationProjectStatusHistory(id=uuid4(), project_id=project.id,
        from_status=project.project_status, to_status=project.project_status,
        effective_on=stamp.replace(tzinfo=None), changed_at=stamp.replace(tzinfo=None),
        updated_at=stamp.replace(tzinfo=None), changed_by=user.id, change_note=note, entry_kind='progress'))
    naive = stamp.replace(tzinfo=None)
    if report is None:
        report = DailyReport(id=uuid4(), user_id=user.id, report_date=day, status='draft',
                             generated_at=naive, created_at=naive, updated_at=naive)
        db.add(report)
        db.flush()
    notes = [f'【{"下班" if item.slot == "end_shift" else item.slot + ":00"}】{item.progress_note}' for item in [*sorted(previous, key=lambda item: api_time(item.submitted_at)), entry]]
    data = DailyReportItemInput(source_type='manual', source_id=project.id, task_type='项目工作',
        task_name=(project.project_name or project.order_no)[:255], progress_content='\n'.join(notes),
        duration_minutes=payload.cumulative_minutes, display_metadata={
            'source': 'annotation_work_status', 'report_types': ['标注项目'], 'project_type': 'annotation',
            'project_id': str(project.id), 'project_name': project.project_name, 'order_no': project.order_no, 'quantity': '1', 'quantity_unit': '项',
            '_feedback_key': str(row.id), 'annotation_work_day_id': str(row.id),
        })
    report_item = next((item for item in report.items if (item.display_metadata or {}).get('annotation_work_day_id') == str(row.id)), None)
    if report_item is None:
        report_item = DailyReportItem(id=uuid4(), sort_order=max((item.sort_order for item in report.items), default=-1) + 1,
                                      created_at=naive, **data.model_dump())
        report.items.append(report_item)
    else:
        for key, value in data.model_dump().items():
            setattr(report_item, key, value)
    report.updated_at = naive
    db.commit()
    return state_data(db, row)


def on_duty(db, user, stamp):
    from attendance_service import shift_for, intervals, ready as attendance_ready
    from attendance_models import AttendanceDay
    from models import EmployeeLeave
    shift = shift_for(db, user, stamp.date())
    if not any(left <= stamp <= right for left, right in intervals(stamp.date(), shift)):
        return False
    if attendance_ready(db):
        attendance = db.query(AttendanceDay).filter_by(user_id=user.id, day=stamp.date()).first()
        if attendance and attendance.check_out:
            return False
    local = stamp.replace(tzinfo=None)
    if db.query(EmployeeLeave).filter(EmployeeLeave.employee_id == user.id,
        EmployeeLeave.start_date <= local, EmployeeLeave.end_date > local).first():
        return False
    return True


def claim_reminder(db, user):
    if not ready(db):
        return {'remind': False}
    from annotation_chat_service import annotation_department_member
    if not annotation_department_member(db, user) and not manager_query(db, user).first():
        return {'remind': False}
    stamp = now()
    # 只提醒当前时点，短暂离线后补提醒；不会在次日补发旧提醒。
    slot = next((str(hour) for hour in (21, 18, 15, 11) if 0 <= (stamp - slot_time(stamp.date(), str(hour))).total_seconds() < 3600), None)
    if slot is None or not on_duty(db, user, stamp):
        return {'remind': False}
    lock_user(db, user)
    if db.query(AnnotationWorkReminder).filter_by(user_id=user.id, work_date=stamp.date(), slot=slot).first():
        return {'remind': False}
    db.add(AnnotationWorkReminder(id=uuid4(), user_id=user.id, work_date=stamp.date(), slot=slot, reminded_at=stamp))
    db.commit()
    return {'remind': True, 'slot': slot, 'work_date': stamp.date()}


def availability_note(db, user_id, day, original_note):
    if not inspect(db.connection()).has_table(AnnotationWorkAvailability.__tablename__):
        return original_note
    records = db.query(AnnotationWorkAvailability).filter_by(user_id=user_id, work_date=day).all()
    if not records:
        return original_note
    start, end = '【状态汇报·空闲状态】', '【空闲状态汇报结束】'
    summary = '\n'.join(f'{"下班汇报" if item.slot == "end_shift" else item.slot + ":00"}：空闲状态 {"是，预计空闲时间：" + IDLE_LABELS[item.expected_idle_time] if item.is_idle else "否"}' for item in sorted(records, key=lambda item: SLOTS.index(item.slot)))
    import re
    original = re.sub(re.escape(start) + r'.*?' + re.escape(end), '', original_note or '', flags=re.S).strip()
    return f'{original}\n{start}\n{summary}\n{end}'.strip()
