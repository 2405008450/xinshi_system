"""邮件正文图片上传与预览接口。"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from mail_inline_image_models import MailInlineImage, MailInlineImageBinding
from mail_inline_image_schemas import MailInlineImageResponse
from mail_inline_image_service import MAX_INLINE_IMAGE_BYTES, cleanup_orphan_inline_images, delete_draft_image, inline_image_path, save_uploaded_image, serialize_inline_image
from models import AppUser
from routers.auth import get_current_user, require_any_permission


router = APIRouter(
    prefix="/mail-inline-images",
    tags=["mail-inline-images"],
    dependencies=[Depends(require_any_permission(
        "consultations:read", "consultations:write",
        "projects:read", "projects:write", "reports:read",
    ))],
)


def _raise(exc: Exception):
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        code = 413 if "2MB" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    raise exc


@router.post("", response_model=MailInlineImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_inline_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        cleanup_orphan_inline_images(db)
        content = await file.read(MAX_INLINE_IMAGE_BYTES + 1)
        record = save_uploaded_image(
            db,
            uploaded_by=current_user.id,
            filename=file.filename,
            content_type=(file.content_type or "").lower(),
            content=content,
        )
        return serialize_inline_image(record)
    except Exception as exc:
        db.rollback()
        _raise(exc)
    finally:
        await file.close()


@router.get("/{image_id}/content")
def read_inline_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    image = db.query(MailInlineImage).filter(MailInlineImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="正文图片不存在")
    if image.uploaded_by != current_user.id:
        # 已绑定图片可由具备系统访问权的登录用户预览；具体业务操作权限仍由邮件接口校验。
        binding = db.query(MailInlineImageBinding.id).filter(MailInlineImageBinding.image_id == image_id).first()
        if not binding:
            raise HTTPException(status_code=403, detail="无权查看该正文图片")
    path = inline_image_path(image.storage_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="正文图片文件不存在")
    return FileResponse(path, media_type=image.content_type, filename=image.original_name, content_disposition_type="inline")


@router.delete("/{image_id}", status_code=204)
def remove_inline_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        if not delete_draft_image(db, image_id, current_user.id):
            raise HTTPException(status_code=404, detail="正文图片不存在")
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        _raise(exc)
