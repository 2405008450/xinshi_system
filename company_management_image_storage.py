"""共享数据库部署时，将正文图片及正文保存交给云端唯一文件存储。"""
import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from company_management_image_service import MAX_IMAGE_BYTES

SERVICE_ERROR = "正文图片服务暂不可用，请稍后重试"
TIMEOUT = httpx.Timeout(connect=5, read=120, write=120, pool=5)


def remote_origin():
    mode = os.getenv("COMPANY_MANAGEMENT_IMAGE_STORAGE_MODE", "local").strip().lower()
    if mode == "local":
        return None
    if mode != "remote":
        raise HTTPException(503, "正文图片存储模式配置错误")
    origin = os.getenv("COMPANY_MANAGEMENT_IMAGE_REMOTE_ORIGIN", "").strip().rstrip("/")
    try:
        parsed = urlsplit(origin)
        valid = (parsed.scheme == "https" and parsed.hostname and not parsed.username
                 and not parsed.password and not parsed.path and not parsed.query
                 and not parsed.fragment and parsed.port in (None, 443))
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(503, "正文图片远程服务地址配置错误")
    return origin


def request_headers(request):
    if request.headers.get("X-Company-Image-Forwarded"):
        raise HTTPException(503, "正文图片服务转发配置形成循环")
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "登录凭证无效或已过期")
    return {"Authorization": authorization, "X-Company-Image-Forwarded": "1", "Accept-Encoding": "identity"}


def make_client():
    # 只访问管理员配置的HTTPS源站，不携带机器代理、不跟随重定向。
    return httpx.AsyncClient(timeout=TIMEOUT, verify=True, follow_redirects=False, trust_env=False)


def check_response(response, expected):
    if response.status_code == expected:
        return
    if response.status_code == 401:
        # 上游认证失败不能让前端清除仍然有效的局域网登录。
        raise HTTPException(502, "云端正文图片服务认证失败，请联系管理员检查两端登录配置")
    if response.status_code in {400, 403, 404, 409, 413, 422}:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = None
        raise HTTPException(response.status_code, detail if isinstance(detail, (str, list)) else SERVICE_ERROR)
    raise HTTPException(503, SERVICE_ERROR)


async def forward_json(origin, request, method, path, *, payload=None, upload=None):
    headers = request_headers(request)
    try:
        content = None
        if upload is not None:
            content = await upload.read(MAX_IMAGE_BYTES + 1)
            if len(content) > MAX_IMAGE_BYTES:
                raise HTTPException(413, "单张正文图片不能超过20MB")
        async with make_client() as client:
            response = await client.request(method, origin + "/api/company-management" + path,
                headers=headers, json=payload,
                files={"file": (upload.filename or "粘贴图片", content, upload.content_type)} if upload else None)
            check_response(response, 201 if upload else (204 if method == "DELETE" else 200))
            return None if method == "DELETE" else response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, SERVICE_ERROR) from exc
    finally:
        if upload is not None:
            await upload.close()


async def forward_image(origin, request, path):
    headers = request_headers(request)
    client = make_client()
    response = None

    async def close():
        if response is not None:
            await response.aclose()
        await client.aclose()

    try:
        response = await client.send(client.build_request("GET", origin + "/api/company-management" + path,
                                                       headers=headers), stream=True)
        if response.status_code != 200:
            await response.aread()
        check_response(response, 200)
        mime = response.headers.get("content-type", "").split(";")[0].lower()
        if mime not in {"image/png", "image/jpeg", "image/webp"}:
            raise HTTPException(503, SERVICE_ERROR)
        if int(response.headers.get("content-length", "0")) > MAX_IMAGE_BYTES:
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
                if size > MAX_IMAGE_BYTES:
                    raise RuntimeError("正文图片响应超过容量限制")
                yield chunk
        finally:
            await close()

    result_headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    if "content-length" in response.headers:
        result_headers["content-length"] = response.headers["content-length"]
    return StreamingResponse(chunks(), media_type=mime, headers=result_headers, background=BackgroundTask(close))
