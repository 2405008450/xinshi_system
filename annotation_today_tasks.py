"""今日任务中的本人标注项目：实时读取经理归属及状态，不生成重复任务。"""
from sqlalchemy import exists

from annotation_models import AnnotationProject
from workflow_models import ProjectWorkbenchResponsibility


EXCLUDED_STATUSES = frozenset({
    'consultation_no_result', 'resource_sourcing_cancelled', 'sent_to_client',
    'cancelled', 'actively_abandoned', 'paused', 'ended',
})


def managed_projects(db, user, page=1, page_size=10):
    manager = ProjectWorkbenchResponsibility
    query = db.query(AnnotationProject).filter(
        exists().where(
            manager.annotation_project_id == AnnotationProject.id,
            manager.role_code == 'project_manager',
            manager.assignee_id == user.id,
        ),
        AnnotationProject.project_status.notin_(EXCLUDED_STATUSES),
    )
    total = query.count()
    rows = query.order_by(AnnotationProject.order_no.desc(), AnnotationProject.id).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {'total': total, 'items': [
        {'id': str(row.id), 'orderNo': row.order_no, 'projectName': row.project_name,
         'projectStatus': row.project_status, 'taskDescription': row.task_description}
        for row in rows
    ]}
