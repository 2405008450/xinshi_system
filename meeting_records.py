"""会议纯记录及多人执行任务，同一事务保存。"""
from meeting_numbering import code_for
from datetime import datetime
from uuid import UUID, uuid4
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import inspect
from meeting_models import Meeting, MeetingParticipant, MeetingActionTask
from meeting_service import get_meeting, notify, publish, stamp
from chat_time import now, api_time
from models import AppUser
from search_matching import keyword_any


class ActionWrite(BaseModel):
    client_id: UUID
    user_ids: list[UUID] = Field(min_length=1, max_length=2000)
    category: Literal['project', 'non_project']
    content: str = Field(min_length=1, max_length=10000)
    due_at: datetime
    project_type: str = ''
    project_id: UUID | None = None

    @model_validator(mode='after')
    def validate_action(self):
        if not self.content.strip():
            raise ValueError('请填写具体任务')
        if self.due_at.tzinfo is None:
            raise ValueError('完成时间须携带UTC+8时区')
        if self.category == 'project' and (not self.project_id or self.project_type not in ('笔译项目', '口译项目', '标注项目', '招聘项目')):
            raise ValueError('项目任务须选择关联项目')
        self.due_at = stamp(self.due_at)
        return self


class RecordWrite(BaseModel):
    content: str = Field(default='', max_length=30000)
    version: int = Field(ge=0)
    actions: list[ActionWrite] = Field(default_factory=list, max_length=100)


def serialize(db, rows):
    ids = {uid for row in rows for uid in (row.arranger_id, row.assignee_id)}
    names = {u.id: u.full_name or u.username for u in db.query(AppUser).filter(AppUser.id.in_(ids))} if ids else {}
    memberships = {(p.meeting_id, p.user_id) for p in db.query(MeetingParticipant).filter(MeetingParticipant.meeting_id.in_({r.meeting_id for r in rows}))} if rows else set()
    return [api_time({key: getattr(row, key) for key in ('id', 'meeting_id', 'assignee_id', 'arranger_id', 'category', 'content', 'project', 'due_at', 'assigned_at', 'status', 'completed_at', 'revision')} | {
        'arranger_name': names.get(row.arranger_id, ''), 'assignee_name': names.get(row.assignee_id, ''),
        'can_view_meeting': (row.meeting_id, row.assignee_id) in memberships or row.arranger_id == row.assignee_id}) for row in rows]


def save(db, user, meeting_id, data):
    row = db.query(Meeting).filter_by(id=meeting_id, organizer_id=user.id).with_for_update().first()
    if not row:
        raise HTTPException(404, '会议不存在或不是召开人')
    if row.record_version != data.version:
        raise HTTPException(409, '会议记录已有新版本，请刷新后核对，原草稿仍保留')
    active = {u.id for u in db.query(AppUser).filter(AppUser.is_active.is_(True), AppUser.is_deleted.is_(False))}
    total = sum(len(set(a.user_ids)) for a in data.actions)
    if total > 2000:
        raise HTTPException(422, '一次最多安排2000个人次任务，请分批保存')
    prepared = []
    for action in data.actions:
        if not set(action.user_ids) <= active:
            raise HTTPException(422, '请选择在职的任务执行人')
        project = {}
        if action.category == 'project':
            from report_project_picker import resolve
            project = resolve(db, action.project_type, action.project_id)
        prepared.append((action, project))
    events = []
    for action, project in prepared:
        for uid in set(action.user_ids):
            existing = db.query(MeetingActionTask).filter_by(client_id=action.client_id, assignee_id=uid).first()
            if existing:
                if existing.meeting_id != row.id:
                    raise HTTPException(409, '任务请求编号重复')
                continue
            task = MeetingActionTask(id=uuid4(), client_id=action.client_id, meeting_id=row.id, assignee_id=uid,
                arranger_id=user.id, category=action.category, content=action.content.strip(), project=project, due_at=action.due_at)
            db.add(task)
            events.extend(notify(db, [uid], row, f'会议任务安排 · {code_for(db, row)}',
                f'{user.full_name or user.username}安排：{action.content[:200]}；完成时间：{action.due_at:%Y年%m月%d日 %H:%M}（UTC+8）。请到我的任务与思考查看。', 'meeting_task'))
    row.record_content, row.record_version = data.content, row.record_version+1
    db.commit()
    publish(events)
    return {'version': row.record_version}


def tasks(db, user, category, keyword, page, page_size):
    if not inspect(db.connection()).has_table('meeting_action_task'):
        raise HTTPException(503, '会议任务表尚未初始化')
    query = db.query(MeetingActionTask).filter_by(assignee_id=user.id)
    if category:
        query = query.filter_by(category=category)
    query = query.filter(keyword_any([MeetingActionTask.content], keyword))
    total = query.count()
    rows = query.order_by(MeetingActionTask.due_at, MeetingActionTask.id).offset((page-1)*page_size).limit(page_size).all()
    return {'items': serialize(db, rows), 'total': total}


class StatusWrite(BaseModel):
    status: Literal['pending', 'in_progress', 'completed']
    revision: int = Field(ge=1)


def status(db, user, task_id, data):
    row = db.query(MeetingActionTask).filter_by(id=task_id, assignee_id=user.id).with_for_update().first()
    if not row:
        raise HTTPException(404, '任务不存在或不属于本人')
    if row.revision != data.revision:
        raise HTTPException(409, '任务已更新，请刷新后重试')
    row.status, row.revision = data.status, row.revision+1
    row.completed_at = now() if data.status == 'completed' else None
    db.commit()
    return serialize(db, [row])[0]
