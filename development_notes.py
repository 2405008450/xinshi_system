"""仅两个指定账号可访问的开发笔记；保存版本追加，附件始终鉴权读取。"""
import json
import re
from io import BytesIO
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, LargeBinary, String, UniqueConstraint, Uuid, inspect
from sqlalchemy.orm import mapped_column
from PIL import Image

from models import Base, AppUser
from database import get_db
from routers.auth import get_current_user
from chat_time import now, api_time

ACCOUNTS = {
    UUID('cf0a663d-6b69-4f8a-9603-a3dd5a106e49'): ('williamzhao', '赵震锋'),
    UUID('41309346-197a-4350-8e15-1089c59b90c9'): ('yunjian', '黄运坚'),
}
MAX_BYTES = 20 * 1024 * 1024


class DevelopmentNoteBlock(Base):
    __tablename__ = 'development_note_block'
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False, index=True)
    title = mapped_column(String(200), nullable=False, default='开发笔记')
    document = mapped_column(JSON, nullable=False, default=dict)
    attachment_ids = mapped_column(JSON, nullable=False, default=list)
    revision = mapped_column(Integer, nullable=False, default=0)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    saved_at = mapped_column(DateTime(timezone=True))


class DevelopmentNoteRevision(Base):
    __tablename__ = 'development_note_revision'
    __table_args__ = (UniqueConstraint('block_id', 'revision'),)
    request_id = mapped_column(Uuid, primary_key=True)
    block_id = mapped_column(Uuid, ForeignKey('development_note_block.id'), nullable=False, index=True)
    revision = mapped_column(Integer, nullable=False)
    snapshot = mapped_column(JSON, nullable=False)
    saved_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    saved_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


class DevelopmentNoteFile(Base):
    __tablename__ = 'development_note_file'
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    block_id = mapped_column(Uuid, ForeignKey('development_note_block.id'), nullable=False, index=True)
    filename = mapped_column(String(255), nullable=False)
    content_type = mapped_column(String(80), nullable=False)
    size = mapped_column(Integer, nullable=False)
    data = mapped_column(LargeBinary, nullable=False, deferred=True)
    uploaded_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


TABLES = [DevelopmentNoteBlock.__table__, DevelopmentNoteRevision.__table__, DevelopmentNoteFile.__table__]


def allowed(user):
    account = ACCOUNTS.get(user.id) if user else None
    return bool(account and user.is_active and not user.is_deleted and user.username == account[0])


def require_access(user):
    if not allowed(user):
        raise HTTPException(403, '仅赵震锋、黄运坚可访问开发笔记')


def require_ready(db):
    if not all(inspect(db.connection()).has_table(table.name) for table in TABLES):
        raise HTTPException(503, '开发笔记数据表尚未初始化')


def block_for(db, user, block_id, *, write=False):
    require_access(user)
    require_ready(db)
    try: block_id=UUID(str(block_id))
    except ValueError: raise HTTPException(404,'笔记不存在')
    query = db.query(DevelopmentNoteBlock).filter_by(id=block_id)
    if write: query = query.with_for_update()
    row = query.first()
    if not row or row.owner_id not in ACCOUNTS:
        raise HTTPException(404, '笔记不存在')
    if write and row.owner_id != user.id:
        raise HTTPException(403, '只能编辑自己的笔记区域')
    return row


def file_value(row):
    return dict(id=str(row.id), filename=row.filename, size=row.size, content_type=row.content_type,
                src=f'/api/development-notes/files/{row.id}', uploaded_at=api_time(row.uploaded_at).isoformat())


def block_value(db, row):
    files = db.query(DevelopmentNoteFile).filter(DevelopmentNoteFile.block_id == row.id,
        DevelopmentNoteFile.id.in_([UUID(value) for value in row.attachment_ids])).order_by(DevelopmentNoteFile.uploaded_at).all() if row.attachment_ids else []
    return dict(id=str(row.id), owner_id=str(row.owner_id), title=row.title, document=row.document,
        attachment_ids=row.attachment_ids, files=[file_value(item) for item in files], revision=row.revision,
        saved_at=api_time(row.saved_at).isoformat() if row.saved_at else None)


class CreateBlock(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID


class SaveBlock(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    revision: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    document: dict
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=100)


def validate_document(document):
    if len(json.dumps(document, ensure_ascii=False)) > 1_000_000 or document.get('type') != 'doc':
        raise HTTPException(422, '笔记正文格式错误或内容过大')
    images, count = set(), 0
    nodes = {'doc','paragraph','text','heading','bulletList','orderedList','listItem','blockquote','hardBreak','horizontalRule','codeBlock','image'}
    marks = {'bold','italic','strike','code','textColor','highlight','underline'}
    def visit(node, depth=0):
        nonlocal count
        count += 1
        if depth > 30 or count > 15000 or not isinstance(node, dict) or node.get('type') not in nodes:
            raise HTTPException(422, '笔记包含不支持的内容')
        if set(node) - {'type','content','text','marks','attrs'}:
            raise HTTPException(422, '笔记包含不支持的字段')
        attrs = node.get('attrs') or {}
        if set(attrs) - {'level','start','language','src','alt','title','width','height'}:
            raise HTTPException(422, '笔记格式属性不正确')
        if node['type'] == 'image':
            match = re.fullmatch(r'/api/development-notes/files/([0-9a-f-]{36})', str(attrs.get('src','')))
            if not match: raise HTTPException(422, '只能插入开发笔记中上传的截图')
            try: images.add(UUID(match[1]))
            except ValueError: raise HTTPException(422, '截图编号无效')
        for mark in node.get('marks', []):
            if mark.get('type') not in marks or set(mark) - {'type','attrs'}:
                raise HTTPException(422, '不支持的文字格式')
            mark_attrs = mark.get('attrs') or {}
            if set(mark_attrs) - {'color'} or ('color' in mark_attrs and not re.fullmatch(r'#[0-9a-fA-F]{6}', str(mark_attrs['color']))):
                raise HTTPException(422, '文字颜色不正确')
        for child in node.get('content', []): visit(child, depth+1)
    try: visit(document)
    except (TypeError, AttributeError, RecursionError): raise HTTPException(422, '笔记正文格式不正确')
    return images


def save_block(db, user, block_id, payload):
    row = block_for(db,user,block_id,write=True)
    previous = db.get(DevelopmentNoteRevision,payload.request_id)
    if previous:
        if previous.block_id != row.id or previous.saved_by != user.id:
            raise HTTPException(409, '保存标识已用于其他笔记')
        return block_value(db,row)
    if row.revision != payload.revision:
        raise HTTPException(409, '笔记已在另一窗口保存；当前内容保留，请重新加载后核对')
    images = validate_document(payload.document)
    ids = images | set(payload.attachment_ids)
    files = db.query(DevelopmentNoteFile).filter(DevelopmentNoteFile.id.in_(ids),DevelopmentNoteFile.block_id==row.id).all() if ids else []
    if len(files) != len(ids) or any(f.id in images and not f.content_type.startswith('image/') for f in files):
        raise HTTPException(422, '附件或截图不属于当前笔记')
    row.title = payload.title.strip()
    if not row.title: raise HTTPException(422, '请填写笔记标题')
    row.document = payload.document
    row.attachment_ids = list(dict.fromkeys(str(value) for value in payload.attachment_ids))
    row.revision += 1
    row.saved_at = now()
    db.add(DevelopmentNoteRevision(request_id=payload.request_id,block_id=row.id,revision=row.revision,
        snapshot=dict(title=row.title,document=row.document,attachment_ids=row.attachment_ids,
            files=[file_value(f) for f in files if str(f.id) in row.attachment_ids]),saved_by=user.id,saved_at=row.saved_at))
    db.commit()
    return block_value(db,row)


router = APIRouter(prefix='/development-notes', tags=['开发笔记'])


@router.get('/access')
def access(user=Depends(get_current_user)):
    return dict(allowed=allowed(user))


@router.get('')
def listing(db=Depends(get_db), user=Depends(get_current_user)):
    require_access(user); require_ready(db)
    blocks = db.query(DevelopmentNoteBlock).filter(DevelopmentNoteBlock.owner_id.in_(ACCOUNTS)).order_by(DevelopmentNoteBlock.created_at,DevelopmentNoteBlock.id).all()
    return dict(owners=[dict(id=str(uid),name=details[1],can_edit=uid==user.id,blocks=[block_value(db,row) for row in blocks if row.owner_id==uid]) for uid,details in ACCOUNTS.items()])


@router.post('/blocks', status_code=201)
def create(payload: CreateBlock, db=Depends(get_db), user=Depends(get_current_user)):
    require_access(user); require_ready(db)
    row = db.get(DevelopmentNoteBlock,payload.request_id)
    if row:
        if row.owner_id != user.id: raise HTTPException(409, '新增标识已被占用')
        return block_value(db,row)
    row = DevelopmentNoteBlock(id=payload.request_id,owner_id=user.id,title='开发笔记',document={'type':'doc','content':[{'type':'paragraph'}]})
    db.add(row); db.commit()
    return block_value(db,row)


@router.put('/blocks/{block_id}')
def update(block_id: UUID, payload: SaveBlock, db=Depends(get_db), user=Depends(get_current_user)):
    return save_block(db,user,block_id,payload)


@router.get('/blocks/{block_id}/history')
def history(block_id: UUID, skip: int=Query(0,ge=0), limit: int=Query(20,ge=1,le=50), db=Depends(get_db),user=Depends(get_current_user)):
    row=block_for(db,user,block_id)
    query = db.query(DevelopmentNoteRevision).filter_by(block_id=row.id)
    return dict(total=query.count(),items=[dict(revision=r.revision,saved_at=api_time(r.saved_at).isoformat(),saved_by=ACCOUNTS[r.saved_by][1],**r.snapshot)
        for r in query.order_by(DevelopmentNoteRevision.revision.desc()).offset(skip).limit(limit)])


@router.post('/blocks/{block_id}/files', status_code=201)
async def upload(block_id: UUID, file: UploadFile=File(...),db=Depends(get_db),user=Depends(get_current_user)):
    block_for(db,user,block_id,write=True)
    content=await file.read(MAX_BYTES+1)
    if not content or len(content)>MAX_BYTES: raise HTTPException(422,'文件不能为空，单个文件最多20MB')
    kind='application/octet-stream'
    try:
        with Image.open(BytesIO(content)) as image:
            if image.width*image.height>40_000_000: raise HTTPException(422,'图片尺寸过大')
            image.verify()
            kind={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}.get(image.format,kind)
    except HTTPException: raise
    except Exception: pass
    filename=(file.filename or '附件').replace('\\','/').rsplit('/',1)[-1][:255]
    row=DevelopmentNoteFile(block_id=block_id,filename=filename,content_type=kind,size=len(content),data=content)
    db.add(row);db.commit()
    return file_value(row)


@router.get('/files/{file_id}')
def download(file_id: UUID, db=Depends(get_db),user=Depends(get_current_user)):
    require_access(user);require_ready(db)
    row=db.get(DevelopmentNoteFile,file_id)
    if not row: raise HTTPException(404,'文件不存在')
    block_for(db,user,row.block_id)
    from urllib.parse import quote
    mode='inline' if row.content_type.startswith('image/') else 'attachment'
    return Response(row.data,media_type=row.content_type,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff',
        'Content-Disposition':f"{mode}; filename*=UTF-8''{quote(row.filename,safe='')}"})
