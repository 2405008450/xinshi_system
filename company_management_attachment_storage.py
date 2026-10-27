"""共享数据库部署时，公司普通附件统一由指定源站保存和读取。"""

import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from company_management_attachment_service import MAX_FILE_BYTES

SERVICE_ERROR = "公司附件服务暂不可用，请稍后重试"
TIMEOUT = httpx.Timeout(connect=5, read=120, write=120, pool=5)
FORWARDED = "X-Company-Attachment-Forwarded"


def remote_origin():
    mode = os.getenv("COMPANY_MANAGEMENT_ATTACHMENT_STORAGE_MODE", "local").strip().lower()
    if mode == "local":
        return None
    if mode != "remote":
        raise HTTPException(503, "公司附件存储模式配置错误")
    origin = os.getenv("COMPANY_MANAGEMENT_ATTACHMENT_REMOTE_ORIGIN", "").strip().rstrip("/")
    try:
        parsed = urlsplit(origin)
        valid = (parsed.scheme == "https" and parsed.hostname and not parsed.username
                 and not parsed.password and not parsed.path and not parsed.query
                 and not parsed.fragment and parsed.port in (None, 443))
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(503, "公司附件远程服务地址配置错误")
    return origin


def request_headers(request):
    if request.headers.get(FORWARDED):
        raise HTTPException(503, "公司附件服务转发配置形成循环")
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "登录凭证无效或已过期")
    return {"Authorization": authorization, FORWARDED: "1", "Accept-Encoding": "identity"}


def make_client():
    return httpx.AsyncClient(timeout=TIMEOUT, verify=True, follow_redirects=False, trust_env=False)


def check_response(response, expected):
    if response.status_code == expected:
        return
    if response.status_code == 401:
        raise HTTPException(502, "云端公司附件服务认证失败，请联系管理员检查两端登录配置")
    if response.status_code in {400, 403, 404, 409, 413, 422}:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = None
        raise HTTPException(response.status_code, detail if isinstance(detail, str) else SERVICE_ERROR)
    raise HTTPException(503, SERVICE_ERROR)


def url(origin, path):
    return origin + "/api/company-management" + path


async def forward_upload(origin, request, path, upload):
    try:
        content = await upload.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(413, "单个附件不能超过20MB")
        async with make_client() as client:
            response = await client.post(url(origin, path), headers=request_headers(request),
                files={"file": (upload.filename or "未命名文件", content, upload.content_type)})
            check_response(response, 201)
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, SERVICE_ERROR) from exc
    finally:
        await upload.close()


async def forward_delete(origin, request, path):
    try:
        async with make_client() as client:
            response = await client.delete(url(origin, path), headers=request_headers(request))
            check_response(response, 204)
    except httpx.HTTPError as exc:
        raise HTTPException(503, SERVICE_ERROR) from exc


async def forward_download(origin, request, path):
    client = make_client()
    response = None

    async def close():
        if response is not None:
            await response.aclose()
        await client.aclose()

    try:
        response = await client.send(client.build_request("GET", url(origin, path),
            headers=request_headers(request)), stream=True)
        if response.status_code != 200:
            await response.aread()
        check_response(response, 200)
        if int(response.headers.get("content-length", "0")) > MAX_FILE_BYTES:
            raise HTTPException(503, SERVICE_ERROR)
    except BaseException as exc:
        await close()
        if isinstance(exc, (httpx.HTTPError, ValueError)):
            raise HTTPException(503, SERVICE_ERROR) from exc
        raise

    async def chunks():
        size = 0
        try:
            async for chunk in response.aiter_raw():
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    raise RuntimeError("公司附件响应超过容量限制")
                yield chunk
        finally:
            await close()

    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    for name in ("content-length", "content-disposition"):
        if name in response.headers:
            headers[name] = response.headers[name]
    return StreamingResponse(chunks(), media_type="application/octet-stream", headers=headers,
                             background=BackgroundTask(close))
