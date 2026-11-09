from translation_folder_orders import FolderImport
import translation_mother_split  # 注册模型；启动不执行迁移。
from form_errors import integrity_error_detail
import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import get_db
from crud import (
    get_sub_order, get_sub_orders_by_project, get_all_sub_orders,
    create_sub_order, create_sub_orders_bulk, update_sub_order, delete_sub_order
)
from schemas import (
    TranslationFolderImportResponse,
    TranslationSubOrderBulkCreate,
    TranslationSubOrderBulkResponse,
    TranslationSubOrderCreate,
    TranslationSubOrderUpdate,
    TranslationSubOrderResponse,
)
from models import AppUser, TranslationSubOrder
from routers.auth import get_current_user, require_module_access, require_any_permission

router = APIRouter(prefix="/sub-orders", tags=["sub-orders"], dependencies=[Depends(require_module_access("projects:read", "projects:write"))])
logger = logging.getLogger(__name__)


@router.post('/import-list/parse',dependencies=[Depends(require_any_permission('projects:write'))])
async def parse_order_list(file:UploadFile=File(...)):
    from translation_order_list_import import parse_document,MAX_BYTES
    from starlette.concurrency import run_in_threadpool
    content=await file.read(MAX_BYTES+1)
    try:return await run_in_threadpool(parse_document,file.filename or '',content)
    except ValueError as error:raise HTTPException(400,str(error)) from error
    finally:await file.close()


from translation_order_list_import import ListPreview


@router.post('/import-list/preview',dependencies=[Depends(require_any_permission('projects:write'))])
def preview_order_list(payload:ListPreview):
    from translation_order_list_import import analyze
    try:return analyze(payload)
    except ValueError as error:raise HTTPException(400,str(error)) from error


@router.post("/", response_model=TranslationSubOrderResponse, status_code=status.HTTP_201_CREATED)
def create_sub_order_endpoint(
    sub_order: TranslationSubOrderCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(
        default=None, alias="X-Idempotency-Key", min_length=8, max_length=128,
    ),
):
    if idempotency_key:
        existing = db.query(TranslationSubOrder).filter(
            TranslationSubOrder.idempotency_key == idempotency_key
        ).first()
        if existing:
            return get_sub_order(db, existing.id)
    try:
        return create_sub_order(
            db=db,
            sub_order=sub_order.model_copy(update={"created_by": current_user.id}),
            idempotency_key=idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            existing = db.query(TranslationSubOrder).filter(
                TranslationSubOrder.idempotency_key == idempotency_key
            ).first()
            if existing:
                return get_sub_order(db, existing.id)
        logger.exception("创建子订单时触发数据库约束")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=integrity_error_detail(exc, "子订单数据不符合保存要求，请检查后重试"))
    except Exception:
        db.rollback()
        logger.exception("创建子订单时发生未知异常")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="子订单保存失败，请稍后重试")


@router.post("/bulk", response_model=TranslationSubOrderBulkResponse, status_code=status.HTTP_201_CREATED)
def create_sub_orders_bulk_endpoint(
    payload: TranslationSubOrderBulkCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        created, skipped = create_sub_orders_bulk(db, payload, created_by=current_user.id)
        return {
            "created_count": len(created),
            "skipped_count": len(skipped),
            "created": created,
            "skipped": skipped,
        }
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except IntegrityError as exc:
        db.rollback()
        logger.exception("批量创建子订单时触发数据库约束")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=integrity_error_detail(exc, "子订单数据不符合保存要求，请检查后重试"))
    except Exception:
        db.rollback()
        logger.exception("批量创建子订单时发生未知异常")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="批量创建子订单失败，请稍后重试")


@router.get("/project/{project_id}/folder-import-records")
def folder_import_records(project_id: UUID,db: Session = Depends(get_db)):
    from translation_folder_orders import import_records
    return {'items':import_records(db,project_id)}


@router.get("/project/{project_id}/export")
def export_suborder_hierarchy(project_id: UUID,db: Session = Depends(get_db)):
    from crud import get_translation_project
    from translation_suborder_export import build_workbook
    from fastapi.responses import Response
    from urllib.parse import quote
    root=get_translation_project(db,project_id)
    if not root:raise HTTPException(404,'母订单不存在')
    from translation_folder_orders import import_records
    return Response(build_workbook(root,import_records(db,project_id,None)),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(root.order_no+'-订单层级与统计.xlsx')})


@router.get("/shared-folder/tree")
def inspect_shared_suborder_tree(storage_path: str = Query(min_length=1,max_length=2000)):
    from translation_folder_orders import inspect_tree
    try:return inspect_tree(storage_path)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc


@router.post("/folders/import",response_model=TranslationFolderImportResponse,dependencies=[Depends(require_any_permission("projects:write"))])
def import_suborder_folders(payload: "FolderImport", db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user), idempotency_key: Optional[str] = Header(default=None,alias="X-Idempotency-Key",min_length=8,max_length=128)):
    from translation_folder_orders import import_folders
    if not payload.parent_project_id:
        raise HTTPException(400,'新增项目的目录应先应用到表单，点击项目窗口的保存后才正式登记；请刷新页面后重试')
    try:return import_folders(db,payload,current_user.id,idempotency_key)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400,str(exc)) from exc

    except (IntegrityError,HTTPException) as exc:
        db.rollback()
        if idempotency_key and not payload.parent_project_id:
            from models import TranslationProject
            old=db.query(TranslationProject).filter_by(idempotency_key=idempotency_key,created_by=current_user.id).first()
            if old:return import_folders(db,payload,current_user.id,idempotency_key)
        if isinstance(exc,HTTPException):raise
        raise HTTPException(400,integrity_error_detail(exc,'目录订单保存失败，请重新读取后重试')) from exc


@router.get("/shared-folder/inspect")
def inspect_shared_suborder_folder(storage_path: str = Query(min_length=1, max_length=2000)):
    from project_file_service import inspect_suborder_shared_folder
    try:
        return inspect_suborder_shared_folder(storage_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/", response_model=List[TranslationSubOrderResponse])
def read_all_sub_orders(
    skip: int = 0,
    limit: int = Query(200, ge=1, le=500),
    sub_order_no: Optional[str] = None,
    project_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    return get_all_sub_orders(db, skip=skip, limit=limit, sub_order_no=sub_order_no, project_name=project_name)


@router.get("/project/{project_id}", response_model=List[TranslationSubOrderResponse])
def read_sub_orders_by_project(project_id: UUID, db: Session = Depends(get_db)):
    """获取指定母订单下的所有子订单"""
    return get_sub_orders_by_project(db, parent_project_id=project_id)


@router.get("/{sub_order_id}", response_model=TranslationSubOrderResponse)
def read_sub_order(sub_order_id: UUID, db: Session = Depends(get_db)):
    db_sub = get_sub_order(db, sub_order_id=sub_order_id)
    if db_sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子订单不存在")
    return db_sub


@router.put("/{sub_order_id}", response_model=TranslationSubOrderResponse)
def update_sub_order_endpoint(
    sub_order_id: UUID,
    sub_order_update: TranslationSubOrderUpdate,
    db: Session = Depends(get_db)
):
    try:
        db_sub = update_sub_order(db, sub_order_id=sub_order_id, sub_order_update=sub_order_update)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if db_sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子订单不存在")
    return db_sub


@router.delete("/{sub_order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sub_order_endpoint(sub_order_id: UUID, db: Session = Depends(get_db)):
    try:success = delete_sub_order(db, sub_order_id=sub_order_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400,str(exc)) from exc
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="子订单不存在")
    return None
