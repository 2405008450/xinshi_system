"""安排状态沿用最近一次人工选择；日报进度与耗时仍按天隔离。"""
from sqlalchemy import func, select
from annotation_work_status_models import AnnotationWorkDay


def latest_states(db, user_id, day):
    latest = db.query(AnnotationWorkDay.project_id.label('project_id'),
        func.max(AnnotationWorkDay.work_date).label('work_date')).filter(
        AnnotationWorkDay.user_id == user_id, AnnotationWorkDay.work_date <= day
    ).group_by(AnnotationWorkDay.project_id).subquery()
    return {row.project_id: row for row in db.query(AnnotationWorkDay).join(latest,
        (AnnotationWorkDay.project_id == latest.c.project_id) &
        (AnnotationWorkDay.work_date == latest.c.work_date)
    ).filter(AnnotationWorkDay.user_id == user_id)}


def latest_status_expression(user_id, day, project_id):
    return select(AnnotationWorkDay.arrangement_status).where(
        AnnotationWorkDay.user_id == user_id, AnnotationWorkDay.project_id == project_id,
        AnnotationWorkDay.work_date <= day,
    ).order_by(AnnotationWorkDay.work_date.desc()).limit(1).correlate_except(AnnotationWorkDay).scalar_subquery()
