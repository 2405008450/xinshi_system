"""会后确认与逐人报告追加在同一事务完成；可删除、不重复生成。"""
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator
from fastapi import HTTPException
from models import AppUser
from task_models import DailyReport, DailyReportItem
from meeting_models import Meeting, MeetingParticipant
from meeting_service import stamp, require_ready
from chat_time import now
from work_report_dates import report_business_date


class ActualWrite(BaseModel):
    start_at: datetime
    end_at: datetime
    user_ids: list[UUID] = Field(min_length=1, max_length=2000)

    @model_validator(mode='after')
    def validate_time(self):
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError('请使用UTC+8会议时间')
        self.start_at, self.end_at = stamp(self.start_at), stamp(self.end_at)
        if self.end_at <= self.start_at or self.end_at - self.start_at > timedelta(hours=24):
            raise ValueError('实际耗时须为1分钟至24小时')
        if (self.end_at-self.start_at).total_seconds() < 60:
            raise ValueError('实际耗时至少1分钟')
        return self


def confirm(db, user, meeting_id, data):
    require_ready(db)
    row = db.query(Meeting).filter_by(id=meeting_id, organizer_id=user.id).with_for_update().first()
    if not row:
        raise HTTPException(404, '会议不存在或不是召开人')
    if row.confirmed_at:
        return {'already_confirmed': True, 'written_count': len(row.actual_user_ids)}
    if data.end_at > now():
        raise HTTPException(422, '会议尚未结束，不能确认实际结束时间')
    members = db.query(MeetingParticipant).filter_by(meeting_id=row.id).all()
    ids = set(data.user_ids)
    if not ids <= {p.user_id for p in members}:
        raise HTTPException(422, '实际参与人员须在会议邀请名单内，可剔除未到人员')
    users = db.query(AppUser).filter(AppUser.id.in_(ids)).order_by(AppUser.id).with_for_update().all()
    from math import ceil
    minutes = ceil((data.end_at-data.start_at).total_seconds()/60)
    day = report_business_date(data.start_at)
    moment = now()
    reports = []
    actor_name = user.full_name or user.username
    association = row.association or {}
    project = association.get('project') or {}
    for person in users:
        report = db.query(DailyReport).filter_by(user_id=person.id, report_date=day).with_for_update().first()
        if not report:
            report = DailyReport(id=uuid4(), user_id=person.id, report_date=day, status='draft', generated_at=moment.replace(tzinfo=None), created_at=moment.replace(tzinfo=None), updated_at=moment.replace(tzinfo=None))
            db.add(report); db.flush()
        agendas = [a['content'] for a in row.agendas if str(person.id) in a['user_ids']]
        content = f'{actor_name}召开的会议：第{row.number}个会议 · {row.topic}'
        if agendas:
            content += '\n会议议程：\n' + '\n'.join(f'{i+1}. {text}' for i, text in enumerate(agendas))
        training = row.meeting_type == '培训会议'
        metadata = {'report_types': ['培训工作::培训会议' if training else '会议::'+row.meeting_type],
                    'order_no': project.get('order_no') or association.get('technical_task_number') or '',
                    'quantity': 1, 'quantity_unit': '次', 'source': 'meeting', 'meeting_id': str(row.id),
                    '_feedback_key': str(uuid4()), 'added_at': moment.isoformat(),
                    'actual_start_at': data.start_at.isoformat(), 'actual_end_at': data.end_at.isoformat()}
        if project:
            metadata.update(project_id=project['id'], selected_project_type=project['project_type'])
        if association.get('technical_task_id'):
            metadata['technical_task_id'] = association['technical_task_id']
        entry = DailyReportItem(id=uuid4(), report_id=report.id, source_type='manual', source_id=row.id,
            task_type='培训工作' if training else '会议', task_name=(project.get('project_name') or association.get('task_name') or row.topic)[:255],
            progress_content=content, duration_minutes=minutes, sort_order=max((i.sort_order for i in report.items),default=-1)+1,
            display_metadata=metadata, created_at=moment.replace(tzinfo=None))
        report.items.append(entry)
        report.updated_at = moment.replace(tzinfo=None)
        reports.append(report)
    row.actual_start_at, row.actual_end_at = data.start_at, data.end_at
    row.actual_user_ids, row.confirmed_at = sorted(str(uid) for uid in ids), moment
    db.commit()
    from consultation_work_report import publish_report_update
    import logging
    for report in reports:
        try:
            publish_report_update(db, report)
        except Exception:
            logging.getLogger(__name__).exception('会议报告已落库，实时推送失败')
    return {'already_confirmed': False, 'written_count': len(reports), 'report_date': day, 'duration_minutes': minutes}
