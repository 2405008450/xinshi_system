from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException,Query
from sqlalchemy.exc import IntegrityError
from database import get_db
from models import TranslationProject
from routers.auth import require_any_permission
import translation_payment_service as payments

router=APIRouter(prefix='/translation-payments',tags=['笔译付款情况'])


def project(db, project_id, lock=False):
    query=db.query(TranslationProject).filter(TranslationProject.id==project_id,TranslationProject.annotation_migrated_at.is_(None))
    row=(query.with_for_update() if lock else query).first()
    if row is None:raise HTTPException(404,'项目不存在')
    return row


@router.get('/{project_id}')
def read(project_id:UUID,db=Depends(get_db),actor=Depends(require_any_permission('projects:read','finance:read'))):
    return payments.read(db,project(db,project_id))


@router.put('/{project_id}')
def write(project_id:UUID,payload:payments.PaymentWrite,db=Depends(get_db),actor=Depends(require_any_permission('projects:write','finance:write'))):
    row=project(db,project_id,True)
    try:
        result=payments.save(db,row,payload.payments,payload.version,actor.id,payload.confirmation)
        db.commit()
        return result
    except IntegrityError:
        db.rollback();raise HTTPException(409,'付款记录发生冲突，请重新打开后编辑')
    except Exception:
        db.rollback();raise


@router.get('/{project_id}/confirmation-history')
def confirmation_history(project_id:UUID,page:int=Query(1,ge=1),db=Depends(get_db),actor=Depends(require_any_permission('projects:read','finance:read'))):
    project(db,project_id)
    return payments.confirmations.history(db,project_id,page)


@router.get('/{project_id}/totals')
def totals(project_id:UUID,db=Depends(get_db),actor=Depends(require_any_permission('projects:read','finance:read'))):
    project(db,project_id)
    return payments.confirmations.project_totals(db,project_id)
