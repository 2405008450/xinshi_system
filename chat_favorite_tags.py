from uuid import UUID
import hashlib
import unicodedata
from fastapi import HTTPException
from sqlalchemy import String,cast,func,inspect,select
from sqlalchemy.exc import IntegrityError
from chat_favorite_tag_models import ChatFavoriteTag as Tag,ChatFavoriteMessageTag as Assignment

COLORS=('#2563eb','#0891b2','#059669','#7c3aed','#d97706','#db2777','#4f46e5','#b45309')

def ready(db):
    schema=inspect(db.connection())
    return schema.has_table(Tag.__tablename__) and schema.has_table(Assignment.__tablename__)

def require_ready(db):
    if not ready(db):raise HTTPException(503,'消息收藏标签尚未初始化')

def serialize(tag):return dict(id=str(tag.id),name=tag.name,color=tag.color)

def catalog(db):
    require_ready(db)
    return [serialize(row) for row in db.query(Tag).order_by(Tag.name_key,Tag.id)]

def create(db,user,name):
    require_ready(db)
    name=' '.join(unicodedata.normalize('NFKC',name).split())
    if not name or len(name)>60:raise HTTPException(422,'标签名称须为 1～60 个字符')
    key=name.casefold()
    if len(key)>120:raise HTTPException(422,'标签名称规范化后过长，请缩短名称')
    existing=db.query(Tag).filter_by(name_key=key).first()
    if existing:return serialize(existing)
    color=COLORS[int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%len(COLORS)]
    row=Tag(name=name,name_key=key,color=color,created_by=user.id)
    try:db.add(row);db.commit()
    except IntegrityError:
        db.rollback();row=db.query(Tag).filter_by(name_key=key).first()
        if row is None:raise
    return serialize(row)

def message_scope(db,user,kind,cid,mid,lock=False):
    from chat_message_interactions import scope,message_ids
    query,model,_=scope(db,kind,cid,user)
    identifier=message_ids(kind,[mid])[0]
    query=query.filter(model.id==identifier)
    row=(query.with_for_update() if lock else query).first()
    if not row or row.recalled_at:raise HTTPException(404,'消息不存在或已撤回')
    if kind=='discussion':
        from discussion_chat_models import DiscussionMessageAction
        action=db.get(DiscussionMessageAction,(identifier,user.id))
        favorited=bool(action and action.favorited_at)
    else:
        from models import ChatProjectMessageFavorite
        favorited=db.query(ChatProjectMessageFavorite.id).filter_by(message_id=identifier,user_id=user.id).first() is not None
    return str(identifier),favorited

def message_tags(db,user,kind,cid,mid,tag_ids=None):
    require_ready(db)
    mid,favorited=message_scope(db,user,kind,cid,mid,lock=tag_ids is not None)
    query=db.query(Assignment).filter_by(user_id=user.id,conversation_kind=kind,conversation_id=cid,message_id=mid)
    if tag_ids is not None:
        if not favorited:raise HTTPException(409,'请先收藏这条消息，再设置标签')
        ids=set(tag_ids)
        if db.query(Tag.id).filter(Tag.id.in_(ids)).count()!=len(ids):raise HTTPException(422,'部分标签已不存在，请重新选择')
        existing={row.tag_id:row for row in query.with_for_update()}
        for tid,row in existing.items():
            if tid not in ids:db.delete(row)
        for tid in ids-existing.keys():db.add(Assignment(user_id=user.id,conversation_kind=kind,conversation_id=cid,message_id=mid,tag_id=tid))
        db.commit()
    tags=db.query(Tag).join(Assignment,Assignment.tag_id==Tag.id).filter(Assignment.user_id==user.id,
        Assignment.conversation_kind==kind,Assignment.conversation_id==cid,Assignment.message_id==mid).order_by(Tag.name_key).all() if favorited else []
    return dict(favorited=favorited,tags=[serialize(row) for row in tags])

def matches_tag(user_id,kind,cid,mid,tag_id):
    return select(Assignment.tag_id).where(Assignment.user_id==user_id,Assignment.conversation_kind==kind,
        Assignment.conversation_id==cid,func.replace(Assignment.message_id,'-','')==func.replace(cast(mid,String),'-',''),Assignment.tag_id==tag_id).exists()

def decorate(db,user_id,items):
    for row in items:row['tags']=[]
    if not items or not ready(db):return
    mids={str(row['message_id']) for row in items}
    rows=db.query(Assignment,Tag).join(Tag,Tag.id==Assignment.tag_id).filter(Assignment.user_id==user_id,Assignment.message_id.in_(mids)).order_by(Tag.name_key).all()
    grouped={}
    for assignment,tag in rows:grouped.setdefault((assignment.conversation_kind,str(assignment.conversation_id),assignment.message_id),[]).append(serialize(tag))
    for row in items:row['tags']=grouped.get((row['project_type'],str(row['project_id']),str(row['message_id'])),[])
