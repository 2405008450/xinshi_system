from uuid import UUID
from fastapi import APIRouter,Depends,File,Form,UploadFile,Request,HTTPException,Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from database import get_db
from models import AppUser
from routers.auth import get_current_user
from editor_screenshot_models import EditorScreenshot as Image,EditorScreenshotBlob as Blob
import editor_screenshot_service as service
from chat_image_policy import UPLOAD_MAX_BYTES, ORIGINAL_MAX_BYTES
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


@router.get('/{image_id}')
def download(image_id:UUID,request:Request,chat_message_id:str|None=Query(None),chat_kind:str|None=Query(None),db:Session=Depends(get_db),user:AppUser=Depends(get_current_user)):
    service.require_ready(db)
    tokens=request.headers.get('x-screenshot-grants','').split(',')
    if chat_message_id:service.check_chat_reference(db,user,image_id,chat_message_id,chat_kind)
    elif image_id not in service.permitted_ids(db,user.id,[image_id],tokens):raise HTTPException(403,'请先打开有权查看的业务记录后再查看截图')
    row=db.get(Image,image_id)
    if not row:raise HTTPException(404,'截图不存在')
    if row.blob_sha256 is None or (row.expires_at and service.api_time(row.expires_at)<=service.now()):raise HTTPException(410,'聊天截图已超过30天保留期，文字记录仍保留')
    blob=db.get(Blob,row.blob_sha256)
    grant,expires=service.grant(db,user.id,{image_id})
    return Response(blob.content,media_type=blob.content_type,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','X-Screenshot-Grant':grant,'X-Screenshot-Grant-Expires':str(expires)})
