"""全系统已保存数据失效通知；不发送字段内容，不新增业务表。"""
from contextvars import ContextVar
from collections import defaultdict
from hashlib import sha256
from threading import RLock
from uuid import uuid4
import re
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import Table,event,text,bindparam
from sqlalchemy.orm import Session
from sqlalchemy.sql import visitors
from starlette.middleware.base import BaseHTTPMiddleware
from database import get_db
from routers.auth import get_current_user

reads=ContextVar('saved_data_read_resources',default=None)
lock=RLock();versions=defaultdict(int);instance=str(uuid4())
WRITE_KEY='saved_data_changed_tables'
IGNORED=('chat_presence','chat_message_read','app_notification','chat_notification','editor_draft')
router=APIRouter(prefix='/saved-data-sync',tags=['已保存数据同步'])

def valid(value):return isinstance(value,str) and bool(re.fullmatch(r'[a-z][a-z0-9_]{0,100}',value))
def record_read(state):
    target=reads.get()
    if target is None or not state.is_select:return
    try:target.update(node.name for node in visitors.iterate(state.statement) if isinstance(node,Table))
    except (AttributeError,NotImplementedError):pass

def record_write(session,flush_context,instances):
    changed=session.info.setdefault(WRITE_KEY,set())
    for row in [*session.new,*session.dirty,*session.deleted]:
        table=getattr(row,'__table__',None)
        if table is not None and not table.name.startswith(IGNORED):changed.add(table.name)

def after_commit(session):
    if session.in_nested_transaction():return
    changed=session.info.pop(WRITE_KEY,set())
    if not changed:return
    with lock:
        versions['__all__']+=1
        for name in changed:versions[name]+=1
    from notification_ws import dispatch_saved_data
    dispatch_saved_data(sorted(changed))

def after_rollback(session):session.info.pop(WRITE_KEY,None)

event.listen(Session,'do_orm_execute',record_read)
event.listen(Session,'before_flush',record_write)
event.listen(Session,'after_commit',after_commit)
event.listen(Session,'after_rollback',after_rollback)

class SavedReadMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        track=request.method=='GET' and not request.url.path.startswith(('/saved-data-sync','/health','/openapi','/notifications'))
        collected=set();token=reads.set(collected if track else None)
        try:
            response=await call_next(request)
            if track and response.status_code==200:response.headers['X-Saved-Resources']=','.join(sorted(collected)) or '__all__'
            return response
        finally:reads.reset(token)

class VersionRequest(BaseModel):
    resources:list[str]=Field(max_length=500)

@router.post('/versions')
def resource_versions(data:VersionRequest,db:Session=Depends(get_db),user=Depends(get_current_user)):
    names=set(data.resources)
    if any(name!='__all__' and not valid(name) for name in names):raise HTTPException(422,'数据范围无效')
    database_counts={}
    # PostgreSQL统计覆盖其他服务进程写入；只读取计数，响应中仅返回不透明版本。
    if names and db.bind.dialect.name=='postgresql':
        query=text("SELECT relname,n_tup_ins+n_tup_upd+n_tup_del FROM pg_stat_user_tables WHERE schemaname=current_schema() AND relname IN :names").bindparams(bindparam('names',expanding=True))
        database_counts=dict(db.execute(query,{'names':list(names-{'__all__'})}).all())
    with lock:
        result={name:sha256(f'{instance}:{versions[name]}:{database_counts.get(name,0)}'.encode()).hexdigest()[:24] for name in names}
    return {'versions':result}
