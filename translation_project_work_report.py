"""项目新增保存后的工作报告：通过创建审计和日报记录追踪，无需新增表。"""
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from models import AppUser, TranslationProject
from project_audit_models import ProjectOperationAudit
from task_models import DailyReport, DailyReportItem
from consultation_work_report import ConsultationReportWrite, publish_report_update
from chat_time import now
from work_report_dates import report_business_date

SOURCE = 'translation_project_creation'
LABELS = {'translation': '笔译', 'interpretation': '口译', 'recruitment': '招聘', 'annotation': '标注'}


def model(project_type):
    from interpretation_models import InterpretationProject
    from recruitment_models import RecruitmentProject
    from annotation_models import AnnotationProject
    models = dict(translation=TranslationProject, interpretation=InterpretationProject,
                  recruitment=RecruitmentProject, annotation=AnnotationProject)
    if project_type not in models:
        raise HTTPException(422, '不支持的项目类型')
    return models[project_type]


def source(project_type):
    return project_type + '_project_creation'


def _clean_text(value):
    return str(value).strip() if value is not None else ''


def name(project, project_type):
    if project_type == 'translation':
        source_file_name = _clean_text(getattr(project, 'source_file_name', None))
        if source_file_name:
            return source_file_name
    project_name = _clean_text(getattr(project, 'project_name', None))
    if project_name:
        return project_name
    if project_type == 'recruitment':
        parts = [
            _clean_text(getattr(project, 'client_short_name', None)),
            _clean_text(getattr(project, 'position_title', None)),
        ]
        fallback = '-'.join(part for part in parts if part)
        if fallback:
            return fallback
    return _clean_text(getattr(project, 'order_no', None))



def captures(db, user, project_type='translation'):
    project_model = model(project_type)
    return db.query(ProjectOperationAudit).join(project_model, project_model.id == ProjectOperationAudit.project_id).filter(
        ProjectOperationAudit.project_type == project_type, ProjectOperationAudit.operation_type == 'create',
        ProjectOperationAudit.actor_user_id == user.id,
        ProjectOperationAudit.project_snapshot['work_report_required'].as_boolean().is_(True))


def saved_item(db, user, capture, project_type='translation'):
    return db.query(DailyReportItem).join(DailyReport, DailyReport.id == DailyReportItem.report_id).filter(
        DailyReport.user_id == user.id, DailyReportItem.display_metadata['source'].as_string() == source(project_type),
        DailyReportItem.display_metadata['capture_id'].as_string() == str(capture.id)).first()


def pending(db, user, project_type='translation'):
    completed = select(DailyReportItem.id).join(DailyReport, DailyReport.id == DailyReportItem.report_id).where(
        DailyReport.user_id == user.id, DailyReportItem.source_id == ProjectOperationAudit.project_id,
        DailyReportItem.display_metadata['source'].as_string() == source(project_type)).exists()
    return [{'id': row.project_id, 'order_no': row.order_no} for row in
            captures(db, user, project_type).filter(~completed).order_by(ProjectOperationAudit.occurred_at, ProjectOperationAudit.id).limit(100)]


def owned_capture(db, user, project_id, project_type='translation'):
    row = captures(db, user, project_type).filter(ProjectOperationAudit.project_id == project_id).first()
    if row is None:
        raise HTTPException(404, '待填写的项目工作报告不存在')
    return row


def capture_context(db, user, project_id, project_type='translation'):
    capture = owned_capture(db, user, project_id, project_type)
    project = db.get(model(project_type), project_id)
    item = saved_item(db, user, capture, project_type)
    return {'project_id': project.id, 'order_no': project.order_no,
            'task_name': name(project, project_type), 'progress_content': '客户来稿',
            'completed': item is not None, 'report_date': report_business_date()}


def submit(db, user, project_id, payload: ConsultationReportWrite, project_type='translation'):
    db.execute(select(AppUser.id).where(AppUser.id == user.id).with_for_update()).first()
    capture = owned_capture(db, user, project_id, project_type)
    existing = saved_item(db, user, capture, project_type)
    if existing:
        report = db.get(DailyReport, existing.report_id)
        return {'report_id': report.id, 'report_date': report.report_date, 'already_saved': True}
    project = db.get(model(project_type), project_id)
    instant = now()
    day = report_business_date(instant)
    report = db.query(DailyReport).filter_by(user_id=user.id, report_date=day).with_for_update().first()
    if report is None:
        report = DailyReport(id=uuid4(), user_id=user.id, report_date=day, status='draft',
            generated_at=instant.replace(tzinfo=None), created_at=instant.replace(tzinfo=None), updated_at=instant.replace(tzinfo=None))
        db.add(report)
        db.flush()
    order_no = _clean_text(getattr(project, 'order_no', None)) or payload.order_no
    task_name = name(project, project_type) or payload.task_name
    item = DailyReportItem(id=uuid4(), report_id=report.id, source_type='manual', source_id=project.id,
        task_type='项目工作', task_name=task_name,
        progress_content=payload.progress_content, duration_minutes=payload.duration_minutes,
        sort_order=max((row.sort_order for row in report.items), default=-1) + 1,
        display_metadata={'report_types': [LABELS[project_type] + '项目'], 'project_type': project_type, 'order_no': order_no,
            'quantity': payload.quantity, 'quantity_unit': payload.quantity_unit, 'source': source(project_type),
            'capture_id': str(capture.id), 'added_at': instant.isoformat(), '_feedback_key': str(uuid4())})
    report.items.append(item)
    report.updated_at = instant.replace(tzinfo=None)
    db.commit()
    try:
        publish_report_update(db, report)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('项目新增工作报告已保存，实时通知暂未完成')
    return {'report_id': report.id, 'report_date': day, 'already_saved': False}


def install_routes(router, project_type):
    from uuid import UUID
    from fastapi import Depends
    from database import get_db
    from routers.auth import get_current_user

    @router.get('/work-report/pending', name=project_type + '_pending_creation_reports')
    def read_pending(db=Depends(get_db), user=Depends(get_current_user)):
        return pending(db, user, project_type)

    @router.get('/{project_id}/work-report', name=project_type + '_creation_report_context')
    def read_context(project_id: UUID, db=Depends(get_db), user=Depends(get_current_user)):
        return capture_context(db, user, project_id, project_type)

    @router.post('/{project_id}/work-report', name=project_type + '_save_creation_report')
    def save_report(project_id: UUID, payload: ConsultationReportWrite, db=Depends(get_db), user=Depends(get_current_user)):
        return submit(db, user, project_id, payload, project_type)
