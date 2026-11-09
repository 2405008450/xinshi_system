"""客户联系方式按部门授权；不按管理员角色额外放行。"""
import json
from sqlalchemy import inspect
from department_models import Department, DepartmentMember

ALLOWED_DEPARTMENTS = {'客户部','客户','销售部','销售','行政部','行政'}


def can_view_client_contacts(db,user):
    if not user or not getattr(user,'is_active',True) or getattr(user,'is_deleted',False):return False
    normalize=lambda value:str(value or '').strip()
    if normalize(getattr(user,'department',None)) in ALLOWED_DEPARTMENTS:return True
    if not getattr(user,'id',None) or not hasattr(db,'connection'):return False
    inspector=inspect(db.connection())
    if not inspector.has_table(Department.__tablename__) or not inspector.has_table(DepartmentMember.__tablename__):return False
    rows=db.query(Department).join(DepartmentMember,Department.id==DepartmentMember.department_id).filter(DepartmentMember.user_id==user.id).all()
    return any(ALLOWED_DEPARTMENTS.intersection(normalize(name) for name in [row.name,*(row.aliases or [])]) for row in rows)


def redact_client_contacts(value):
    if isinstance(value,list):return [redact_client_contacts(item) for item in value]
    if not isinstance(value,dict):return value
    result={key:redact_client_contacts(item) for key,item in value.items()}
    sensitive={'manager_contact','managerContact','client_contact_method','clientContactMethod','contact_method','contactMethod'}
    for key in sensitive.intersection(result):result[key]=''
    if sensitive.intersection(result) or 'contact_people' in result or 'contactPeople' in result:
        result['contact_restricted']=True
    # 历史邮件主题可能拼接了客户联系方式，受限响应不回传历史主题。
    for key in ('email_subject_preview','emailSubjectPreview'):
        if key in result:result[key]=None
    return result


class ClientContactPrivacyMiddleware:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        state=scope.setdefault('state',{})
        state['client_contacts_visible']=False
        start=None;parts=[];buffer=False
        async def protected_send(message):
            nonlocal start,buffer
            if message['type']=='http.response.start':
                headers=dict(message.get('headers',[]))
                buffer=b'application/json' in headers.get(b'content-type',b'') and b'content-encoding' not in headers
                if buffer:start=message;return
            elif message['type']=='http.response.body' and buffer:
                parts.append(message.get('body',b''))
                if message.get('more_body',False):return
                body=b''.join(parts)
                markers=(b'manager_contact',b'managerContact',b'contact_method',b'contactMethod',b'contact_people',b'contactPeople',b'email_subject_preview',b'emailSubjectPreview')
                if any(marker in body for marker in markers):
                    if not state.get('client_contacts_visible',False):
                        body=json.dumps(redact_client_contacts(json.loads(body)),ensure_ascii=False,separators=(',',':')).encode()
                    start={**start,'headers':[(k,v) for k,v in start['headers'] if k.lower() not in (b'content-length',b'etag',b'cache-control')]+[(b'content-length',str(len(body)).encode()),(b'cache-control',b'private, no-store')]}
                await send(start);await send({**message,'body':body});return
            await send(message)
        await self.app(scope,receive,protected_send)
