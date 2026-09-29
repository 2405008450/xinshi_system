"""受控云端转发；文件分块传输，不在内存拼接完整文件。"""
import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from annotation_material_service import MAX_BYTES, storage_mode

FORWARDED = 'X-Annotation-Material-Forwarded'


def remote_origin():
    mode = storage_mode()
    if mode == 'disabled':
        raise HTTPException(503, '项目资料存储尚未启用，请联系管理员')
    if mode == 'local':
        return None
    origin = os.getenv('ANNOTATION_MATERIAL_REMOTE_ORIGIN', '').strip().rstrip('/')
    try:
        parts = urlsplit(origin)
        valid = (parts.scheme == 'https' and parts.hostname and not parts.username and not parts.password
                 and not parts.path and not parts.query and not parts.fragment and parts.port in (None, 443))
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(503, '项目资料云端地址配置错误')
    return origin


def forwarding_headers(request):
    if request.headers.get(FORWARDED):
        raise HTTPException(503, '项目资料转发配置形成循环')
    authorization = request.headers.get('authorization', '')
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, '登录凭证无效或已过期')
    return {'Authorization': authorization, FORWARDED: '1', 'Accept-Encoding': 'identity'}


def client():
    return httpx.AsyncClient(timeout=httpx.Timeout(300, connect=5), verify=True,
                             follow_redirects=False, trust_env=False)


def check(response):
    if 200 <= response.status_code < 300:
        return
    messages = {400: '云端拒绝了资料请求', 403: '没有访问该资料的权限', 404: '资料不存在或已过期',
                409: '资料状态已变化，请刷新后重试', 413: '文件不能为空或超过100MB限制'}
    if response.status_code == 401:
        raise HTTPException(502, '云端资料服务认证失败，请联系管理员检查两端登录配置')
    raise HTTPException(response.status_code if response.status_code in messages else 503,
                        messages.get(response.status_code, '云端资料服务暂不可用，请稍后重试'))


async def forward_upload(origin, request, file):
    headers = forwarding_headers(request)
    # multipart 头由本服务生成；文件名不插入协议头，原名称放在 UTF-8 表单字段。
    import uuid
    boundary = uuid.uuid4().hex
    headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'

    async def body():
        yield f'--{boundary}\r\nContent-Disposition: form-data; name="original_name"\r\n\r\n'.encode()
        yield (file.filename or 'file')[:255].encode('utf-8')
        yield f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="file"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
        size = 0
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                raise HTTPException(413, '单文件不能超过100MB')
            yield chunk
        yield f'\r\n--{boundary}--\r\n'.encode()

    try:
        async with client() as connection:
            response = await connection.post(origin + '/api/projects/annotation/material-uploads', headers=headers, content=body())
            check(response)
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, '云端资料上传失败，请重试') from exc


async def forward_delete(origin, request, upload_id):
    try:
        async with client() as connection:
            response = await connection.delete(origin + f'/api/projects/annotation/material-uploads/{upload_id}', headers=forwarding_headers(request))
            check(response)
    except httpx.HTTPError as exc:
        raise HTTPException(503, '云端资料服务暂不可用') from exc


async def forward_download(origin, request, project_id, file_id, version_id):
    connection = client()
    response = None

    async def close():
        if response is not None:
            await response.aclose()
        await connection.aclose()

    try:
        upstream = connection.build_request('GET', origin + f'/api/projects/annotation/{project_id}/materials/{file_id}/versions/{version_id}/download', headers=forwarding_headers(request))
        response = await connection.send(upstream, stream=True)
        check(response)
    except BaseException as exc:
        await close()
        if isinstance(exc, httpx.HTTPError):
            raise HTTPException(503, '云端资料下载失败，请重试') from exc
        raise

    async def chunks():
        try:
            async for chunk in response.aiter_raw():
                yield chunk
        finally:
            await close()

    headers = {'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'}
    for key in ('content-length', 'content-disposition'):
        if key in response.headers:
            headers[key] = response.headers[key]
    return StreamingResponse(chunks(), media_type='application/octet-stream', headers=headers, background=BackgroundTask(close))
