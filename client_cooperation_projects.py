"""客户合作项目摘要：按客户主键精确关联，不按名称模糊匹配。"""
from sqlalchemy import or_, select

from models import SubClient, TranslationProject
from interpretation_models import InterpretationProject
from annotation_models import AnnotationProject
from recruitment_models import RecruitmentProject


def client_project_groups(db, client_id):
    sub_clients = select(SubClient.id).where(SubClient.parent_client_id == client_id)
    groups = []
    for module, label, model in (
        ('translation', '笔译项目', TranslationProject),
        ('interpretation', '口译项目', InterpretationProject),
        ('annotation', '标注项目', AnnotationProject),
        ('recruitment', '招聘项目', RecruitmentProject),
    ):
        rows = db.query(model.id, model.order_no, model.project_name, model.project_status).filter(
            or_(model.client_id == client_id, model.sub_client_id.in_(sub_clients)),
        ).order_by(model.order_no.desc(), model.id.desc()).all()
        if rows:
            groups.append({'module': module, 'label': label, 'items': [
                {'id': str(row.id), 'order_no': row.order_no,
                 'project_name': row.project_name, 'project_status': row.project_status}
                for row in rows
            ]})
    return {'groups': groups}
