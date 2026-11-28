"""每个账号独立的五级会话目录；整理目录不授予会话访问权限。"""
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import ForeignKey,Integer,JSON,Uuid
from sqlalchemy.orm import mapped_column
from models import Base,ChatDirectMember
from database import get_db
from routers.auth import get_current_user
from chat_access_service import visible_ids

class ChatPersonalFolders(Base):
    __tablename__='chat_personal_folders'
    user_id=mapped_column(Uuid,ForeignKey('app_user.id',ondelete='CASCADE'),primary_key=True)
    revision=mapped_column(Integer,nullable=False,default=0)
    nodes=mapped_column(JSON,nullable=False,default=list)

class Write(BaseModel):
    revision:int=Field(ge=0)
    nodes:list[dict]=Field(default_factory=list,max_length=1000)

router=APIRouter(prefix='/chat/personal-folders',tags=['个人会话目录'])

def validate_nodes(nodes):
    by_id={}
    cleaned=[]
    for node in nodes:
        uid=str(UUID(node.get('id','')))
        if uid in by_id:raise ValueError('目录标识重复')
        name=str(node.get('name','')).strip()
        if not name or len(name)>120:raise ValueError('名称应为1至120个字')
        parent=node.get('parent_id',node.get('parentId'))
        item=dict(id=uid,parentId=str(UUID(parent)) if parent else None,name=name)
        if node.get('session'):
            session=node['session'];kind=session.get('project_type',session.get('projectType'))
            if kind not in ('annotation','translation','discussion','direct'):raise ValueError('会话类型不正确')
            cid=str(UUID(session.get('project_id',session.get('projectId',''))))
            item['session']=dict(projectType=kind,projectId=cid,key=f'{kind}:{cid}',title=name,subtitle=str(session.get('subtitle',''))[:120])
        by_id[uid]=item;cleaned.append(item)
    for node in cleaned:
        visited={node['id']};current=node;depth=0 if node.get('session') else 1
        while current['parentId']:
            current=by_id.get(current['parentId'])
            if not current or current.get('session'):raise ValueError('上级文件夹不存在')
            if current['id'] in visited:raise ValueError('不能移动到自身子目录')
            visited.add(current['id']);depth+=1
        if depth>5:raise ValueError('最多创建5级文件夹')
    return cleaned

def allowed_keys(db,user):
    keys=set()
    for kind in ('annotation','translation','discussion'):
        keys.update(f'{kind}:{cid}' for cid, in visible_ids(db,kind,user))
    keys.update(f'direct:{cid}' for cid, in db.query(ChatDirectMember.conversation_id).filter_by(user_id=user.id))
    return keys

def read(db,user):
    row=db.get(ChatPersonalFolders,user.id)
    allowed=allowed_keys(db,user)
    return dict(revision=row.revision if row else 0,nodes=[node for node in (row.nodes if row else []) if not node.get('session') or node['session']['key'] in allowed])

@router.get('')
def get(db=Depends(get_db),user=Depends(get_current_user)):
    return read(db,user)

@router.put('')
def save(payload:Write,db=Depends(get_db),user=Depends(get_current_user)):
    try:nodes=validate_nodes(payload.nodes)
    except (ValueError,TypeError,KeyError,AttributeError) as exc:raise HTTPException(422,str(exc) or '目录格式不正确')
    allowed=allowed_keys(db,user)
    if any(node.get('session') and node['session']['key'] not in allowed for node in nodes):raise HTTPException(403,'只能整理本人可访问的会话')
    # 用户行作为首次保存和后续修改的统一互斥锁。
    from models import AppUser
    db.query(AppUser).filter_by(id=user.id).with_for_update().first()
    row=db.get(ChatPersonalFolders,user.id)
    if (row.revision if row else 0)!=payload.revision:raise HTTPException(409,'目录已在其他窗口修改，请重新打开后重试')
    if not row:row=ChatPersonalFolders(user_id=user.id,revision=0,nodes=[]);db.add(row)
    row.nodes=nodes;row.revision+=1;db.commit()
    return dict(revision=row.revision,nodes=row.nodes)
