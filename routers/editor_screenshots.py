from uuid import UUID
from fastapi import APIRouter,Depends,File,Form,UploadFile,Request,HTTPException,Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from database import get_db
from models import AppUser
from routers.auth import get_current_user
from editor_screenshot_models import EditorScreenshot as Image,EditorScreenshotBlob as Blob
import editor_screenshot_service as service
from chat_image_policy import UPLOAD_MAX_BYTES, ORIGINAL_MAX_BYTES, make_chat_thumbnail
from starlette.concurrency import run_in_threadpool

router=APIRouter(prefix='/editor-screenshots',tags=['editor_screenshots'])


@router.get('/capabilities')
def capabilities(db:Session=Depends(get_db),user:AppUser=Depends(get_current_user)):
    return {'ready':service.ready(db),'maxImages':9,'maxBytes':2*1024*1024,'chatMaxUploadBytes':UPLOAD_MAX_BYTES,'chatOriginalMaxBytes':ORIGINAL_MAX_BYTES,'businessRetention':'permanent','chatRetentionDays':30}


@router.post('',status_code=201)
async def upload(file:UploadFile=File(...),retention:str=Form('business'),db:Session=Depends(get_db),user:AppUser=Depends(get_current_user)):
    limit = UPLOAD_MAX_BYTES if retention == 'chat' else 2*1024*1024
    content=await file.read(limit+1)
    if len(content) > limit:
        raise HTTPException(413, '单张聊天图片不能超过 20MB' if retention == 'chat' else '单张正文图片不能超过 2MB')
    def persist():
        return service.save_image(db,user.id,content,file.content_type,retention)
    try:return await run_in_threadpool(persist)
    except ValueError as error:raise HTTPException(422,str(error)) from error


@router.post('/invoice-pdf', status_code=201)
async def upload_invoice_pdf(file: UploadFile = File(...), request_id: UUID | None = Form(None), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return await upload_invoice_file(file, request_id, db, user, 'pdf')


@router.post('/invoice-ofd', status_code=201)
async def upload_invoice_ofd(file: UploadFile = File(...), request_id: UUID | None = Form(None), db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    return await upload_invoice_file(file, request_id, db, user, 'ofd')


async def upload_invoice_file(file, request_id, db, user, extension):
    from routers.auth import get_user_permission_codes
    if request_id is not None:
        from invoice_workflow import require_invoice_recipient
        require_invoice_recipient(db, request_id, user)
    elif not {'*', 'projects:write', 'finance:write'}.intersection(get_user_permission_codes(db, user.id)):
        raise HTTPException(403, '无权上传发票文件')
    content = await file.read(service.MAX_INVOICE_FILE_BYTES + 1)
    try:
        return service.save_invoice_file(db, user.id, content, extension)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get('/{image_id}')
def download(image_id:UUID,request:Request,chat_message_id:str|None=Query(None),chat_kind:str|None=Query(None),variant:str|None=Query(None),db:Session=Depends(get_db),user:AppUser=Depends(get_current_user)):
    service.require_ready(db)
    tokens=request.headers.get('x-screenshot-grants','').split(',')
    if chat_message_id:service.check_chat_reference(db,user,image_id,chat_message_id,chat_kind)
    elif image_id not in service.permitted_ids(db,user.id,[image_id],tokens):raise HTTPException(403,'请先打开有权查看的业务记录后再查看截图')
    row=db.get(Image,image_id)
    if not row:raise HTTPException(404,'截图不存在')
    if row.blob_sha256 is None or (row.expires_at and service.api_time(row.expires_at)<=service.now()):raise HTTPException(410,'聊天截图已超过30天保留期，文字记录仍保留')
    want_thumb = (variant or '').strip().lower() == 'thumb'
    etag = f'"{row.blob_sha256}:{"thumb" if want_thumb else "orig"}"'
    grant,expires=service.grant(db,user.id,{image_id})
    headers = {'Cache-Control':'private, no-store','ETag':etag,'Vary':'Authorization','X-Content-Type-Options':'nosniff','X-Screenshot-Grant':grant,'X-Screenshot-Grant-Expires':str(expires)}
    if_none_match = request.headers.get('if-none-match', '')
    if if_none_match and (etag in {item.strip() for item in if_none_match.split(',')}):
        return Response(status_code=304, headers=headers)
    blob=db.get(Blob,row.blob_sha256)
    body, media_type = (
        make_chat_thumbnail(blob.content, blob.content_type, cache_key=row.blob_sha256)
        if want_thumb else (blob.content, blob.content_type)
    )
    if media_type in ('application/pdf', 'application/ofd'):
        extension = media_type.split('/')[1]
        headers['Content-Disposition'] = f'attachment; filename="invoice.{extension}"'
    return Response(body, media_type=media_type, headers=headers)
