"""标注会话分析任务、工作日调度与进度入库。"""
import calendar
import logging
import os
from datetime import datetime, time, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import inspect, select, text, update

import annotation_chat_service
import thoughts_ai_service
from annotation_annotator_progress_models import AnnotationAnnotatorProgress
from annotation_annotator_progress_service import require_available as require_annotator_progress
from annotation_chat_ai_inference import AnalysisError, analyze_chunk, chunks
from annotation_chat_ai_models import AnnotationChatAnalysis as Job
from annotation_customer_progress_models import AnnotationCustomerProgress
from annotation_customer_progress_service import require_customer_progress
from annotation_models import AnnotationProject
from annotation_ops_models import AnnotationProjectStatusHistory
from business_time import business_iso, business_now
from chat_access_service import visible_ids
from models import AppUser, ChatProjectMessage
from permission_service import user_has_permission
from work_report_calendar import is_workday


PROGRESS_MODELS = {
    'customer': AnnotationCustomerProgress,
    'project': AnnotationProjectStatusHistory,
    'annotator': AnnotationAnnotatorProgress,
}
logger = logging.getLogger(__name__)


def schedule_enabled():
    return os.getenv('ANNOTATION_CHAT_AI_SCHEDULE_ENABLED', 'false').lower() == 'true'


def storage_available(db):
    return inspect(db.connection()).has_table(Job.__tablename__)


def require_storage(db):
    if not storage_available(db):
        raise HTTPException(503, '标注聊天 AI 分析尚未初始化数据库')


def manual_range(period, moment):
    if period == 'day':
        return datetime.combine(moment.date() - timedelta(days=1), time.min), moment
    if period == 'week':
        return moment - timedelta(days=7), moment
    if period == 'month':
        year, month = (moment.year, moment.month - 1) if moment.month > 1 else (moment.year - 1, 12)
        return moment.replace(year=year, month=month, day=min(moment.day, calendar.monthrange(year, month)[1])), moment
    if period == 'all':
        return None, moment
    raise ValueError('无效分析时段')


def scheduled_range(day):
    previous = day - timedelta(days=1)
    while not is_workday(previous):
        previous -= timedelta(days=1)
    return datetime.combine(previous, time.min), datetime.combine(day, time.min)


def require_writer(db, user):
    if not user_has_permission(db, user.id, 'projects:write'):
        raise HTTPException(403, '没有写入项目进度的权限')


def message_project_ids(start, end):
    message = ChatProjectMessage
    query = select(message.annotation_project_id).where(
        message.annotation_project_id.is_not(None), message.created_at < end,
        message.recalled_at.is_(None), message.message_type == 'user', message.content != '',
    )
    if start is not None:
        query = query.where(message.created_at >= start)
    return query


def enqueue_manual(db, project_id, user, period, auto_apply, all_visible):
    annotation_chat_service.require_project(db, project_id, user)
    require_storage(db)
    if not thoughts_ai_service.enabled():
        raise HTTPException(503, '数据分析 AI 服务尚未启用')
    if auto_apply:
        require_writer(db, user)
    moment = business_now()
    start, end = manual_range(period, moment)
    projects = [project_id]
    if all_visible:
        projects = db.scalars(select(AnnotationProject.id).where(
            AnnotationProject.id.in_(visible_ids(db, 'annotation', user).statement),
            AnnotationProject.id.in_(message_project_ids(start, end)),
        )).all()
    jobs = [Job(project_id=pid, requested_by=user.id, period=period, auto_apply=auto_apply,
                range_start=start, range_end=end, created_at=moment, updated_at=moment) for pid in projects]
    db.add_all(jobs)
    db.commit()
    return {'queued': len(jobs)}


def advisory_lock(db, key):
    if db.get_bind().dialect.name != 'postgresql':
        return True
    return db.scalar(text('SELECT pg_try_advisory_xact_lock(:key)'), {'key': key})


def enqueue_scheduled(db, moment):
    day = moment.date()
    if moment.time() < time(11) or not is_workday(day):
        return 0
    if not advisory_lock(db, 2611111100):
        return 0
    if db.scalar(select(Job.id).where(Job.scheduled_on == day).limit(1)):
        return 0
    start, end = scheduled_range(day)
    projects = db.scalars(select(AnnotationProject.id).where(
        AnnotationProject.id.in_(message_project_ids(start, end)),
    )).all()
    db.add_all([Job(project_id=pid, scheduled_on=day, period='workday', range_start=start,
                    range_end=end, created_at=moment, updated_at=moment) for pid in projects])
    db.commit()
    return len(projects)


def claim(db, moment, *, allow_scheduled):
    if not advisory_lock(db, 2611111101):
        return None
    db.execute(update(Job).where(Job.state == 'running', Job.updated_at < moment - timedelta(minutes=8))
               .values(state='failed', error='分析中断，请重新运行', updated_at=moment))
    if db.scalar(select(Job.id).where(Job.state == 'running').limit(1)):
        db.commit()
        return None
    query = select(Job).where(Job.state == 'queued')
    if not allow_scheduled:
        query = query.where(Job.scheduled_on.is_(None))
    job = db.scalar(query.order_by(Job.created_at, Job.id).limit(1).with_for_update())
    if job is None:
        db.commit()
        return None
    job.state, job.updated_at = 'running', moment
    job_id = job.id
    db.commit()
    return job_id


def actor_for_job(db, job):
    if job.scheduled_on:
        return None
    actor = db.get(AppUser, job.requested_by) if job.requested_by else None
    if actor is None or not actor.is_active or actor.is_deleted:
        raise HTTPException(403, '发起人的账号已失效')
    annotation_chat_service.require_project(db, job.project_id, actor)
    return actor


def result_identity(project_id, result):
    identity = ':'.join([str(project_id), result['category'], *result['sources'], result['summary']])
    return uuid5(NAMESPACE_URL, f'xinshi:annotation-chat-ai:{identity}')


def import_progress(db, job, actor):
    require_writer(db, actor)
    if job.state != 'succeeded':
        raise HTTPException(409, '分析完成后才能加入项目进度')
    project = db.scalar(select(AnnotationProject).where(AnnotationProject.id == job.project_id).with_for_update())
    if project is None:
        raise HTTPException(404, '标注项目不存在')
    imported = {entry['result_id'] for entry in job.imports}
    pending = [item for item in job.results if item['category'] in PROGRESS_MODELS and item['id'] not in imported]
    sources = {UUID(source) for item in pending for source in item['sources']}
    if sources:
        valid = set()
        ordered = sorted(sources)
        for offset in range(0, len(ordered), 500):
            valid.update(db.scalars(select(ChatProjectMessage.id).where(
                ChatProjectMessage.annotation_project_id == job.project_id,
                ChatProjectMessage.id.in_(ordered[offset:offset + 500]),
                ChatProjectMessage.recalled_at.is_(None),
            )).all())
        if sources != valid:
            raise HTTPException(409, '部分依据消息已撤回或删除，请重新分析后再加入项目进度')
    categories = {item['category'] for item in pending}
    if 'customer' in categories:
        require_customer_progress(db)
    if 'annotator' in categories:
        require_annotator_progress(db)
    moment = business_now()
    audit = list(job.imports)
    count = 0
    for item in pending:
        track = item['category']
        model = PROGRESS_MODELS[track]
        record_id = UUID(item['id'])
        created = db.get(model, record_id) is None
        if created:
            effective = datetime.fromisoformat(item['effective_at'])
            aware = track != 'project'
            timestamp = datetime.fromisoformat(business_iso(moment)) if aware else moment
            row = model(
                id=record_id, project_id=job.project_id,
                change_note=f"【AI 分析】{item['summary']}\n分析批次：{job.id}",
                effective_on=effective if aware else effective.replace(tzinfo=None),
                changed_at=timestamp, updated_at=timestamp, changed_by=actor.id,
            )
            if track == 'project':
                row.from_status = project.project_status
                row.to_status = project.project_status
                row.entry_kind = 'progress'
            db.add(row)
            count += 1
        audit.append({
            'result_id': item['id'], 'record_id': str(record_id), 'track': track,
            'actor_id': str(actor.id), 'actor_name': actor.full_name or actor.username,
            'at': business_iso(moment), 'operation': 'ai_progress_created' if created else 'ai_progress_reused',
        })
    job.imports = audit
    job.import_error = None
    return count


def process(session_factory, job_id, stopping=lambda: False):
    def keep_alive():
        if stopping():
            raise AnalysisError('服务停止，分析已中断，请重新运行')
        with session_factory.begin() as db:
            job = db.get(Job, job_id)
            if job is None or job.state != 'running':
                raise AnalysisError('分析任务已结束')
            actor_for_job(db, job)
            job.updated_at = business_now()

    try:
        with session_factory() as db:
            job = db.get(Job, job_id)
            if job is None:
                return
            project_id, start, end = job.project_id, job.range_start, job.range_end
        results = {}
        for chunk in chunks(session_factory, project_id, start, end):
            for result in analyze_chunk(chunk, keep_alive):
                key = str(result_identity(project_id, result))
                results[key] = dict(result, id=key)
        with session_factory.begin() as db:
            job = db.get(Job, job_id, with_for_update=True)
            if job is None or job.state != 'running':
                return
            actor = actor_for_job(db, job)
            job.results = list(results.values())
            job.state, job.updated_at = 'succeeded', business_now()
            if job.auto_apply:
                try:
                    with db.begin_nested():
                        import_progress(db, job, actor)
                except Exception as exc:
                    error = str(exc.detail) if isinstance(exc, HTTPException) else '自动加入项目进度失败，可在结果中重试'
                    job.import_error = error[:500]
    except Exception as exc:
        error = str(exc) if isinstance(exc, AnalysisError) else (
            str(exc.detail) if isinstance(exc, HTTPException) else '分析处理失败，请重新运行')
        with session_factory.begin() as db:
            job = db.get(Job, job_id, with_for_update=True)
            if job is not None and job.state == 'running':
                job.state, job.error, job.updated_at = 'failed', error[:500], business_now()
        return


def public_job(job, *, include_results=False):
    data = {
        'id': str(job.id), 'period': job.period, 'state': job.state,
        'range_start': business_iso(job.range_start), 'range_end': business_iso(job.range_end),
        'created_at': business_iso(job.created_at), 'updated_at': business_iso(job.updated_at),
        'error': job.error, 'auto_apply': job.auto_apply, 'import_error': job.import_error,
        'scheduled_on': job.scheduled_on,
    }
    if include_results:
        data.update(results=job.results, imports=job.imports)
    return data
