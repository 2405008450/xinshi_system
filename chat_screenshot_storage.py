"""聊天截图保存到共享图片存储；业务交接附件沿用永久保存路径。"""
from io import BytesIO
from uuid import UUID,uuid4
from datetime import timedelta
from PIL import Image,ImageOps,UnidentifiedImageError
from fastapi import HTTPException
from fastapi.responses import Response
from models import ChatProjectAttachment,ChatProjectMessage,ChatProjectMessageAttachment
from chat_time import now,api_time
import editor_screenshot_service as screenshots


def save_attachment(db,user,content,filename,*,scope=None,project_id=None):
    try:
        with Image.open(BytesIO(content)) as source:
            if source.width*source.height>40_000_000:raise ValueError('截图像素过大')
            image=ImageOps.exif_transpose(source);image.thumbnail((1920,1920))
            output=BytesIO();image.convert('RGBA' if 'A' in image.getbands() else 'RGB').save(output,'WEBP',quality=85)
        saved=screenshots.save_image(db,user.id,output.getvalue(),'image/webp','chat')
    except (ValueError,UnidentifiedImageError,OSError) as error:raise HTTPException(422,str(error)) from error
    row=ChatProjectAttachment(id=uuid4(),uploaded_by=user.id,original_name=(filename or '截图')[:255],storage_name=f"screenshot:{saved['id']}",content_type=saved['contentType'],file_size=saved['size'],created_at=now().replace(tzinfo=None))
    if scope=='annotation':row.annotation_project_id=project_id
    if scope=='direct':row.direct_conversation_id=project_id
    db.add(row);db.commit()
    return row


def check_retention(db,attachment):
    if not attachment.content_type.startswith('image/'):return
    from workflow_models import WorkflowHandoverAttachment
    if db.query(WorkflowHandoverAttachment).filter_by(attachment_id=attachment.id).first():return
    rows=db.query(ChatProjectMessage.created_at).join(ChatProjectMessageAttachment,ChatProjectMessageAttachment.message_id==ChatProjectMessage.id).filter(ChatProjectMessageAttachment.attachment_id==attachment.id).all()
    # 业务交接中没有聊天消息关联的图片不属于聊天截图保留策略。
    if rows and all(created and api_time(created)<=now()-timedelta(days=30) for created, in rows):
        raise HTTPException(410,'聊天截图已超过30天保留期，文字记录仍保留')


def read_attachment(db,attachment):
    """调用方须先通过原会话附件权限验证。"""
    check_retention(db,attachment)
    if not attachment.storage_name.startswith('screenshot:'):return None
    from editor_screenshot_models import EditorScreenshot,EditorScreenshotBlob
    row=db.get(EditorScreenshot,UUID(attachment.storage_name.split(':',1)[1]))
    if not row or not row.blob_sha256 or row.expires_at and api_time(row.expires_at)<=now():
        raise HTTPException(410,'聊天截图已超过30天保留期，文字记录仍保留')
    blob=db.get(EditorScreenshotBlob,row.blob_sha256)
    return Response(blob.content,media_type=blob.content_type,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
