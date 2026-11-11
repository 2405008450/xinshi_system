from datetime import date, datetime, time, timedelta
import re
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from database import get_db
from routers.auth import get_current_user
from business_numbering import BusinessNumberLease, BusinessNumberDeletionHistory, allocate, spec, ready, live, history_ready, SPECS
from chat_time import now, api_time, BUSINESS_TIMEZONE

router = APIRouter(prefix='/business-numbers', tags=['business_numbers'])

class Reserve(BaseModel):
    kind: str
    window_id: UUID
    parent_id: UUID | None = None
    business_date: date | None = None

def history_access(kind,db,user):
    from routers.auth import require_any_permission
    if kind not in {*SPECS,'translation_suborder','annotation_suborder','subclient','technical_subtask','greeting'}:
        raise HTTPException(422,'不支持的编号类型')
    if kind=='hr_requirement':
        from hr_access import require_hr
        require_hr(db,user)
    elif kind in ('technical_task','technical_subtask','feedback'):
        from technical_development import require_user
        require_user(user,db)
    else:
        permissions = ('clients:read','clients:write','projects:read','projects:write') if kind in ('client','subclient') else ('talents:read','talents:write','translators:read','translators:write','recruitment_talents:read','recruitment_talents:write') if kind=='talent' else ('consultations:read','consultations:write') if kind=='consultation' else ('resources:read','resources:write','projects:read','projects:write') if kind in ('resource_request','greeting') else ('projects:read','projects:write')
        require_any_permission(*permissions)(current_user=user,db=db)

@router.get('/history')
def history(kind:str,keyword:str='',skip:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(get_current_user),*,order_no:str='',client_name:str='',deleted_from:date|None=None,deleted_to:date|None=None,include_children:bool=False):
    history_access(kind,db,user)
    if not history_ready(db):raise HTTPException(503,'编号删除记录表尚未初始化')
    from sqlalchemy import or_,select,func,cast,String
    from sqlalchemy.orm import aliased
    from search_matching import keyword_any
    H=BusinessNumberDeletionHistory
    scopes=[H.scope==kind,H.scope.startswith(kind+':',autoescape=True)]
    if include_children and kind=='translation':scopes.append(H.scope.startswith('translation_suborder:',autoescape=True))
    # 旧记录优先使用删除快照；子订单可回溯母订单删除快照，再兼容仍存在的客户档案。
    # 不改写历史数据，当前客户名称只作为缺少名称快照时的回退。
    from models import Client,TranslationProject
    parent=aliased(H)
    def parent_value(field):
        return select(parent.snapshot[field].as_string()).where(parent.entity_type=='translation_project',parent.entity_id==H.snapshot['parent_project_id'].as_string()).order_by(parent.deleted_at.desc()).limit(1).correlate(H).scalar_subquery()
    live_parent_client=select(cast(TranslationProject.client_id,String)).where(func.replace(cast(TranslationProject.id,String),'-','')==func.replace(H.snapshot['parent_project_id'].as_string(),'-','')).limit(1).correlate(H).scalar_subquery()
    client_id=func.coalesce(H.snapshot['client_id'].as_string(),parent_value('client_id'),live_parent_client)
    def customer_value(field):
        current=select(getattr(Client,field)).where(func.replace(cast(Client.id,String),'-','')==func.replace(client_id,'-','')).limit(1).correlate(H).scalar_subquery()
        return func.coalesce(func.nullif(H.snapshot[field].as_string(),''),func.nullif(parent_value(field),''),current,'')
    full_name,short_name=customer_value('client_name'),customer_value('client_short_name')
    query=db.query(H,full_name.label('client_name'),short_name.label('client_short_name')).filter(or_(*scopes),keyword_any([H.number,H.entity_name,H.actor_name,full_name,short_name],keyword),keyword_any([H.number],order_no),keyword_any([full_name,short_name],client_name))
    if deleted_from and deleted_to and deleted_from>deleted_to:raise HTTPException(422,'删除时间范围的开始日期不能晚于结束日期')
    if deleted_from:query=query.filter(H.deleted_at>=datetime.combine(deleted_from,time.min,tzinfo=BUSINESS_TIMEZONE))
    if deleted_to:
        if deleted_to==date.max:query=query.filter(H.deleted_at<=datetime.combine(deleted_to,time.max,tzinfo=BUSINESS_TIMEZONE))
        else:query=query.filter(H.deleted_at<datetime.combine(deleted_to+timedelta(days=1),time.min,tzinfo=BUSINESS_TIMEZONE))
    total=query.count()
    rows=query.order_by(H.deleted_at.desc(),H.id).offset(skip).limit(limit).all()
    return api_time({'items':[{'id':str(row.id),'number':row.number,'entity_id':row.entity_id,'entity_name':row.entity_name,'actor_name':row.actor_name or '未记录','deleted_at':row.deleted_at,'client_name':full_name,'client_short_name':short_name,'snapshot':{**row.snapshot,**({'client_name':full_name,'client_short_name':short_name} if full_name or short_name else {})}} for row,full_name,short_name in rows],'total':total})

@router.post('/reserve')
def reserve(payload: Reserve, db=Depends(get_db), user=Depends(get_current_user)):
    from routers.auth import require_any_permission
    if payload.kind == 'hr_requirement':
        from hr_access import require_hr
        require_hr(db, user)
    elif payload.kind in ('technical_task','technical_subtask','feedback'):
        from technical_development import require_user
        require_user(user, db)
    else:
        require_any_permission('projects:write','clients:write','resources:write','talents:write','translators:write','recruitment_talents:write','consultations:write')(current_user=user, db=db)
    db.info['number_actor'] = user.id
    scope, prefix, minimum, width = spec(db, payload.kind, payload.parent_id, payload.business_date)
    if not ready(db):
        raise HTTPException(503, '业务编号占用表尚未初始化')
    # 同一窗口网络重试幂等；重新打开窗口会产生全新的 window_id。
    from business_numbering import lock_scope
    lock_scope(db, scope)
    existing = db.query(BusinessNumberLease).filter_by(owner_id=user.id, window_id=payload.window_id, scope=scope).first()
    if existing and live(existing):
        return {'token': str(existing.id), 'number': existing.number}
    db.info['number_reserve'] = payload.window_id
    number = allocate(db, scope, prefix, minimum, width)
    row = db.info['number_reserved_row']
    db.commit()
    return {'token': str(row.id), 'number': number}

@router.post('/{token}/heartbeat')
def heartbeat(token: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    row = db.query(BusinessNumberLease).filter_by(id=token, owner_id=user.id).with_for_update().first()
    if not row or not live(row):
        raise HTTPException(409, '编号占用已失效，请重新打开新增窗口')
    row.expires_at = now() + timedelta(minutes=15)
    db.commit()
    return {'ok': True}

@router.post('/{token}/skip')
def skip_number(token: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    from business_numbering import lock_scope
    from routers.auth import require_any_permission

    row = db.query(BusinessNumberLease).filter_by(id=token, owner_id=user.id).first()
    if not row or not live(row):
        raise HTTPException(409, '当前编号已失效或已被使用，请先检查列表，避免重复录入')
    kind = row.scope.split(':', 1)[0]
    if kind not in {*SPECS, 'translation_suborder', 'annotation_suborder', 'subclient', 'technical_subtask', 'greeting'}:
        raise HTTPException(422, '不支持的编号类型')
    require_any_permission('projects:write','clients:write','resources:write','talents:write','translators:write','recruitment_talents:write','consultations:write')(current_user=user, db=db)
    lock_scope(db, row.scope)
    row = db.query(BusinessNumberLease).filter_by(id=token, owner_id=user.id).with_for_update().first()
    if not row or not live(row):
        raise HTTPException(409, '当前编号已失效或已被使用，请先检查列表，避免重复录入')
    parent_id = UUID(row.scope.split(':', 1)[1]) if ':' in row.scope else None
    date_match = re.search(r'-(\d{6})-', row.number)
    business_date = datetime.strptime(date_match.group(1), '%y%m%d').date() if date_match else None
    old_number = row.number
    row.state = 'released'
    db.flush()
    db.info['number_actor'] = user.id
    db.info['number_reserve'] = uuid4()
    scope, prefix, minimum, width = spec(db, kind, parent_id, business_date)
    db.info['number_excluded'] = {old_number}
    try:
        number = allocate(db, scope, prefix, minimum, width)
    finally:
        db.info.pop('number_excluded', None)
    replacement = db.info['number_reserved_row']
    db.commit()
    return {'token': str(replacement.id), 'number': number}

@router.post('/{token}/release')
def release(token: UUID, db=Depends(get_db), user=Depends(get_current_user)):
    row = db.query(BusinessNumberLease).filter_by(id=token, owner_id=user.id).with_for_update().first()
    if row and row.state == 'active':
        row.state = 'released'
        row.expires_at = now()
        db.commit()
    return {'ok': True}
