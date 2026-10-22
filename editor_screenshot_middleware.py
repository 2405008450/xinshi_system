"""业务接口授权结果携带短期截图授权；阻止伪造或反射他人的截图引用。"""
import logging
from urllib.parse import unquote
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from database import engine
import editor_screenshot_service as service


class ScreenshotDenied(Exception):pass


class EditorScreenshotMiddleware:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers={k.lower():v.decode('latin1') for k,v in scope.get('headers',[])}
        token=headers.get(b'authorization','').removeprefix('Bearer ')
        grants=headers.get(b'x-screenshot-grants','').split(',')[:64]
        checked=set();tail=b'';blocked=False;start=None;parts=[];passthrough=False
        def authorize(ids):
            from routers.auth import get_user_from_token_value
            with Session(engine) as db:
                user=get_user_from_token_value(db,token) if token else None
                return bool(user and service.permitted_ids(db,user.id,ids,grants)==ids)
        async def check(ids):
            nonlocal blocked
            needed=ids-checked
            if needed:
                if not await run_in_threadpool(authorize,needed):blocked=True;raise ScreenshotDenied()
                checked.update(needed)
        async def guarded_receive():
            nonlocal tail
            message=await receive()
            if message['type']=='http.request':
                chunk=tail+message.get('body',b'')
                await check(service.request_references(chunk));tail=chunk[-4096:]
            return message
        def make_grant(ids):
            from routers.auth import get_user_from_token_value
            with Session(engine) as db:
                user=get_user_from_token_value(db,token) if token else None
                if user and service.ready(db):
                    path=scope.get('path','')
                    if scope['method'] in {'POST','PUT','PATCH'} and not any(part in path for part in ('chat','editor-screenshots','auth')):
                        service.promote_business_references(db,checked)
                    return service.grant(db,user.id,ids)
        async def wrapped_send(message):
            nonlocal start,passthrough,parts
            if blocked:return
            if message['type']=='http.response.start':
                start=message
                content=dict(message.get('headers',[])).get(b'content-type',b'')
                passthrough=not (200<=message['status']<300 and b'application/json' in content and token)
                if passthrough:await send(message)
            elif message['type']=='http.response.body' and not passthrough:
                parts.append(message.get('body',b''))
                if sum(map(len,parts))>8*1024*1024:
                    passthrough=True;await send(start);await send({'type':'http.response.body','body':b''.join(parts),'more_body':message.get('more_body',False)});parts=[];return
                if not message.get('more_body',False):
                    body=b''.join(parts);ids=service.valid_references(body)
                    if ids or checked:
                        try:
                            result=await run_in_threadpool(make_grant,ids)
                            if result:start['headers']=[*start.get('headers',[]),(b'x-screenshot-grant',result[0].encode()),(b'x-screenshot-grant-expires',str(result[1]).encode())]
                        except Exception:logging.getLogger(__name__).exception('生成业务截图读取授权失败')
                    await send(start);await send({'type':'http.response.body','body':body,'more_body':False})
            else:await send(message)
        try:
            await check(service.request_references(unquote(scope.get('query_string',b'').decode('utf-8',errors='ignore'))))
            await self.app(scope,guarded_receive,wrapped_send)
        except ScreenshotDenied:blocked=True
        if blocked:await JSONResponse({'detail':'没有读取所引用截图的权限，请重新打开原记录后重试'},status_code=403)(scope,receive,send)
