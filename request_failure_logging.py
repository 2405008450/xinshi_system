"""保留可追溯的请求校验失败日志，参数脱敏且有界。"""
import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import parse_qs

BODY_LIMIT = 32768
LOG_PATH = Path(__file__).resolve().parent / 'logs' / 'request-validation.jsonl'
_lock = threading.Lock()
_logger = None
_private_key = re.compile(
    r'password|passwd|secret|token|authorization|cookie|captcha|credential|'
    r'bank_account|account_number|tax_number|phone|mobile|email|proofs|'
    r'stamp_image|remarks|notes|content|description|^input$|^ctx$', re.I,
)
_private_value = re.compile(r'screenshot://[^\s)]+|Bearer\s+\S+', re.I)


def safe_value(value, depth=0):
    if depth >= 8:
        return '[depth limit]'
    if isinstance(value, dict):
        return {
            str(key)[:100]: '[redacted]' if _private_key.search(str(key)) else safe_value(item, depth + 1)
            for key, item in list(value.items())[:50]
        }
    if isinstance(value, (list, tuple)):
        result = [safe_value(item, depth + 1) for item in value[:50]]
        if len(value) > 50:
            result.append({'omitted_items': len(value) - 50})
        return result
    if isinstance(value, str):
        return _private_value.sub('[redacted]', value[:2048])
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return type(value).__name__


def parsed_json(body, truncated):
    if truncated:
        return {'omitted': 'body exceeds 32 KiB'}
    try:
        return safe_value(json.loads(body))
    except (ValueError, UnicodeError):
        return {'omitted': 'invalid or unavailable JSON'}


def failure_logger():
    global _logger
    with _lock:
        if _logger is None:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            logger = logging.getLogger('xinshi.request_validation')
            handler = RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.WARNING)
            logger.propagate = False
            _logger = logger
    return _logger


class RequestFailureLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_body = bytearray()
        response_body = bytearray()
        request_truncated = False
        response_truncated = False
        status = 200
        request_id = ''
        headers = dict(scope.get('headers', []))
        json_request = headers.get(b'content-type', b'').split(b';')[0].strip().lower() == b'application/json'

        async def capture_receive():
            nonlocal request_truncated
            message = await receive()
            if json_request and message['type'] == 'http.request':
                chunk = message.get('body', b'')
                remaining = BODY_LIMIT - len(request_body)
                request_body.extend(chunk[:remaining])
                request_truncated |= len(chunk) > remaining
            return message

        async def capture_send(message):
            nonlocal status, request_id, response_truncated
            if message['type'] == 'http.response.start':
                status = message['status']
                response_headers = dict(message.get('headers', []))
                request_id = response_headers.get(b'x-request-id', b'').decode('utf-8', errors='replace')
            elif message['type'] == 'http.response.body' and status in (400, 409, 422):
                chunk = message.get('body', b'')
                remaining = BODY_LIMIT - len(response_body)
                response_body.extend(chunk[:remaining])
                response_truncated |= len(chunk) > remaining
            await send(message)

        await self.app(scope, capture_receive, capture_send)
        if status not in (400, 409, 422):
            return
        try:
            state = scope.get('state', {})
            event = {
                'time': datetime.now(timezone(timedelta(hours=8))).isoformat(),
                'event': 'request_validation_failed', 'status': status,
                'request_id': request_id or state.get('failure_request_id'),
                'method': scope['method'], 'path': scope['path'],
                'actor': state.get('failure_actor'),
                'query': safe_value(parse_qs(scope.get('query_string', b'').decode('utf-8', errors='replace'))),
                'body': parsed_json(request_body, request_truncated) if json_request else {'omitted': 'non-JSON body'},
                'reason': state.get('failure_reason') or parsed_json(response_body, response_truncated),
            }
            failure_logger().warning(json.dumps(event, ensure_ascii=False, allow_nan=False))
        except Exception:
            logging.getLogger(__name__).warning('请求校验日志写入失败', exc_info=True)
