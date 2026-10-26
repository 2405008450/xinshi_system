"""标注员情况：聊天入口和项目进度窗口共用的独立记录。"""
from fastapi import HTTPException
from sqlalchemy import inspect
from annotation_annotator_progress_models import AnnotationAnnotatorProgress
from annotation_models import AnnotationProject
from annotation_customer_progress_service import _response_rows
from annotation_progress_time import business_now

def require_available(db):
    if not inspect(db.connection()).has_table(AnnotationAnnotatorProgress.__tablename__):
        raise HTTPException(503, '标注员情况尚未初始化数据库，请联系管理员')

def list_progress(db, project_id):
    require_available(db)
    if not db.get(AnnotationProject, project_id):
        raise HTTPException(404, '标注订单不存在')
    model=AnnotationAnnotatorProgress
    rows=db.query(model).filter_by(project_id=project_id).order_by(model.effective_on.desc(),model.changed_at.desc(),model.id.desc()).all()
    return [dict(row,track='annotator') for row in _response_rows(db,rows)]

def create_progress(db, project_id, payload, user_id):
    require_available(db)
    if not db.get(AnnotationProject, project_id):
        raise HTTPException(404, '标注订单不存在')
    now=business_now()
    row=AnnotationAnnotatorProgress(project_id=project_id,change_note=payload.change_note,effective_on=payload.effective_on,changed_by=user_id,changed_at=now,updated_at=now)
    db.add(row)
    from annotation_progress_chat import enqueue,after_commit
    enqueue(db,project_id,user_id,payload.chat_delivery,track='annotator',note=payload.change_note,effective_on=payload.effective_on)
    db.commit();after_commit(db);db.refresh(row)
    return dict(_response_rows(db,[row])[0],track='annotator')
