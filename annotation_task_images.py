"""具体任务截图复用项目资料暂存、授权下载和生命周期。"""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import HTTPException
from annotation_material_models import AnnotationMaterialUpload as Upload, AnnotationMaterialFile as Material, AnnotationMaterialVersion as Version, AnnotationMaterialFolder as Folder

IMAGE_TYPES={'image/png','image/jpeg','image/gif','image/webp'}


def upload_utc_now():
    # 复用既有资料暂存的 UTC 无时区存储语义，仅用于到期与消费，不用作业务展示时间。
    return datetime.now(timezone.utc).replace(tzinfo=None)


def apply_images(db, project, ids, user_id):
    if ids is None:return
    ids=list(dict.fromkeys(ids))
    if len(ids)>9:raise ValueError('具体任务最多添加9张截图')
    existing={UUID(str(uid)) for uid in (project.task_image_upload_ids or [])}
    for uid in ids:
        upload=db.query(Upload).filter_by(id=uid).with_for_update().first()
        if not upload or upload.content_type not in IMAGE_TYPES or upload.file_size>10*1024*1024:
            raise ValueError('任务截图不存在、不是支持的图片或超过10MB')
        linked=db.query(Version).join(Material,Material.id==Version.file_id).filter(Material.project_id==project.id,Version.upload_id==uid).first()
        if linked and uid in existing:continue
        if upload.uploaded_by!=user_id or upload.consumed_at is not None or upload.expires_at<=upload_utc_now():
            raise ValueError('任务截图已过期、已使用或不属于当前账号，请重新上传')
        folder=db.query(Folder).filter_by(project_id=project.id,parent_id=None,name='具体任务截图').first()
        if not folder:
            folder=Folder(id=uuid4(),project_id=project.id,name='具体任务截图');db.add(folder);db.flush()
        material=Material(id=uuid4(),project_id=project.id,category='project',folder_id=folder.id)
        db.add(material);db.flush()
        db.add(Version(id=uuid4(),file_id=material.id,upload_id=uid,version_no=1));upload.consumed_at=upload_utc_now()
    project.task_image_upload_ids=[str(uid) for uid in ids]
    db.flush()


def image_rows(db, project):
    return db.query(Upload,Material.id,Version.id).join(Version,Version.upload_id==Upload.id).join(Material,Material.id==Version.file_id).filter(Material.project_id==project.id,Upload.id.in_([UUID(str(uid)) for uid in project.task_image_upload_ids or []])).all()


def chat_attachments(db, project, user_id):
    from models import ChatProjectAttachment
    rows=[]
    for upload,_,_ in image_rows(db,project):
        row=ChatProjectAttachment(id=uuid4(),annotation_project_id=project.id,uploaded_by=user_id,original_name=upload.original_name,storage_name=f'material:{upload.id.hex}:{uuid4().hex}',content_type=upload.content_type,file_size=upload.file_size)
        db.add(row);rows.append(row.id)
    db.flush();return rows


async def download_chat_image(db, project_id, storage_name, request):
    from routers.annotation_materials import download
    try:uid=UUID(storage_name.split(':')[1])
    except (ValueError,IndexError):raise HTTPException(404,'任务截图不存在')
    linked=db.query(Material.id,Version.id).join(Version,Version.file_id==Material.id).filter(Material.project_id==project_id,Version.upload_id==uid).first()
    if not linked:raise HTTPException(404,'任务截图不属于当前订单')
    return await download(project_id,linked[0],linked[1],request,db)
