"""沟通附件远程转发；只连接管理员配置的 HTTPS 附件服务。"""
import os
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from schemas import ProjectChatAttachmentResponse

SERVICE_ERROR = '图片服务暂不可用，请稍后重试'
TIMEOUT = httpx.Timeout(connect=5, read=45, write=45, pool=5)


def remote_attachment_url():
    mode = os.getenv('CHAT_STORAGE_MODE', 'local').strip().lower()
    if mode == 'local':
        return None
    if mode != 'remote':
        raise HTTPException(503, '图片存储模式配置错误')
    origin = os.getenv('CHAT_REMOTE_ORIGIN', '').strip().rstrip('/')
    try:
        parsed = urlsplit(origin)
        valid = (parsed.scheme == 'https' and parsed.hostname and not parsed.username
                 and not parsed.password and not parsed.path and not parsed.query
                 and not parsed.fragment and parsed.port in (None, 443))
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(503, '图片远程服务地址配置错误')
    return origin + '/api/project-chat/attachments'


def make_client():
    # 不读取机器上的代理配置，不跟随重定向，避免凭证发送给其他地址。
    return httpx.AsyncClient(timeout=TIMEOUT, verify=True, follow_redirects=False, trust_env=False)


def request_headers(authorization, forwarded):
    if forwarded:
        raise HTTPException(503, '图片服务转发配置形成循环')
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, '登录凭证无效或已过期')
    return {'Authorization': authorization, 'X-Chat-Attachment-Forwarded': '1', 'Accept-Encoding': 'identity'}


def check_response(response, expected):
    if response.status_code == expected:
        return
    details = {401: '登录凭证无效或已过期', 403: '没有访问图片的权限',
               404: '图片不存在或文件缺失', 413: '单张图片不能超过 10MB',
               415: '仅支持 JPEG、PNG、GIF、WebP 图片', 400: '图片请求无效'}
    raise HTTPException(response.status_code if response.status_code in details else 503,
                        details.get(response.status_code, SERVICE_ERROR))


async def upload_remote_attachment(url, content, filename, content_type, authorization, forwarded):
    headers = request_headers(authorization, forwarded)
    try:
        async with make_client() as client:
            response = await client.post(url, headers=headers,
                                         files={'file': (filename or 'image', content, content_type)})
            check_response(response, 201)
            # 不返回上游任意响应，验证现有附件契约后再交给前端。
            return ProjectChatAttachmentResponse.model_validate(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, SERVICE_ERROR) from exc


async def read_remote_attachment(url, attachment_id: UUID, authorization, forwarded):
    headers = request_headers(authorization, forwarded)
    client = make_client()
    response = None

    async def close():
        if response is not None:
            await response.aclose()
        await client.aclose()

    try:
        request = client.build_request('GET', f'{url}/{attachment_id}', headers=headers)
        response = await client.send(request, stream=True)
        check_response(response, 200)
        content_type = response.headers.get('content-type', '').split(';')[0].lower()
        if content_type not in {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}:
            raise HTTPException(503, SERVICE_ERROR)
    except BaseException as exc:
        await close()
        if isinstance(exc, httpx.HTTPError):
            raise HTTPException(503, SERVICE_ERROR) from exc
        raise

    async def chunks():
        try:
            async for chunk in response.aiter_raw():
                yield chunk
        finally:
            await close()

    # 保留长度让客户端识别中途断流，禁止共享代理缓存带鉴权的图片。
    result_headers = {'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'}
    for name in ('content-length', 'content-disposition'):
        if name in response.headers:
            result_headers[name] = response.headers[name]
    return StreamingResponse(chunks(), media_type=content_type, headers=result_headers,
                             background=BackgroundTask(close))
