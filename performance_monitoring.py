"""轻量请求与数据库性能观测，不记录 SQL 参数或业务数据。"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool


logger = logging.getLogger("xinshi.performance")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(logging.StreamHandler())
BUSINESS_TZ = timezone(timedelta(hours=8))
_loop_lag_ms = 0.0


def log_time():
    return datetime.now(BUSINESS_TZ).isoformat(timespec='milliseconds')


def current_metrics():
    return _current_metrics.get()


class ObservedQueuePool(QueuePool):
    def _do_get(self):
        started = time.perf_counter()
        try:
            return super()._do_get()
        finally:
            metrics = current_metrics()
            if metrics is not None:
                # 包括池等待及新连接建立，不把它误记为 SQL 执行耗时。
                metrics.pool_acquire_ms += (time.perf_counter() - started) * 1000


async def monitor_event_loop(stop):
    global _loop_lag_ms
    loop = asyncio.get_running_loop()
    while not stop.is_set():
        started = loop.time()
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.1)
        except asyncio.TimeoutError:
            pass
        _loop_lag_ms = max(0.0, (loop.time() - started - 0.1) * 1000)


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


REQUEST_SLOW_MS = _env_int("PERF_SLOW_REQUEST_MS", 300)
SQL_SLOW_MS = _env_int("PERF_SLOW_SQL_MS", 100)
LOG_ALL_REQUESTS = os.getenv("PERF_LOG_ALL_REQUESTS", "").strip().lower() in {
    "1", "true", "yes", "on",
}


@dataclass
class RequestPerformance:
    request_id: str
    started_at: float = field(default_factory=time.perf_counter)
    db_ms: float = 0.0
    sql_count: int = 0
    capacity_wait_ms: float = 0.0
    pool_acquire_ms: float = 0.0
    loop_lag_ms: float = 0.0
    _query_starts: list[float] = field(default_factory=list)


_current_metrics: ContextVar[Optional[RequestPerformance]] = ContextVar(
    "xinshi_request_performance",
    default=None,
)
_instrumented_engines: set[int] = set()
_whitespace = re.compile(r"\s+")


def begin_request(request_id: Optional[str] = None) -> tuple[RequestPerformance, Token]:
    metrics = RequestPerformance(request_id=request_id or uuid.uuid4().hex, loop_lag_ms=_loop_lag_ms)
    return metrics, _current_metrics.set(metrics)


def end_request(token: Token) -> None:
    _current_metrics.reset(token)


def _sql_fingerprint(statement: str) -> tuple[str, str]:
    normalized = _whitespace.sub(" ", statement).strip()
    operation = (normalized.split(" ", 1)[0] if normalized else "UNKNOWN").upper()
    digest = hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:12]
    return operation, digest


def install_sqlalchemy_performance_hooks(engine: Engine) -> None:
    """每个 Engine 只注册一次事件监听。"""
    engine_key = id(engine)
    if engine_key in _instrumented_engines:
        return
    _instrumented_engines.add(engine_key)

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(_conn, _cursor, _statement, _parameters, _context, _many):
        metrics = _current_metrics.get()
        if metrics is None:
            return
        metrics.sql_count += 1
        metrics._query_starts.append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(_conn, _cursor, statement, _parameters, _context, _many):
        metrics = _current_metrics.get()
        if metrics is None or not metrics._query_starts:
            return
        elapsed_ms = (time.perf_counter() - metrics._query_starts.pop()) * 1000
        metrics.db_ms += elapsed_ms
        if SQL_SLOW_MS and elapsed_ms >= SQL_SLOW_MS:
            operation, fingerprint = _sql_fingerprint(statement)
            logger.warning(
                "slow_sql at=%s request_id=%s operation=%s fingerprint=%s duration_ms=%.2f",
                log_time(),
                metrics.request_id,
                operation,
                fingerprint,
                elapsed_ms,
            )

    @event.listens_for(engine, "handle_error")
    def _handle_error(_exception_context):
        metrics = _current_metrics.get()
        if metrics is not None and metrics._query_starts:
            metrics.db_ms += (time.perf_counter() - metrics._query_starts.pop()) * 1000


def finish_request_log(request: Request, metrics: RequestPerformance, status_code: int) -> float:
    metrics.loop_lag_ms = max(metrics.loop_lag_ms, _loop_lag_ms)
    total_ms = (time.perf_counter() - metrics.started_at) * 1000
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    log_method = logger.info if LOG_ALL_REQUESTS or total_ms >= REQUEST_SLOW_MS else logger.debug
    log_method(
        "request at=%s request_id=%s method=%s route=%s status=%s duration_ms=%.2f db_ms=%.2f sql_count=%s capacity_wait_ms=%.2f pool_acquire_ms=%.2f loop_lag_ms=%.2f",
        log_time(),
        metrics.request_id,
        request.method,
        route_path,
        status_code,
        total_ms,
        metrics.db_ms,
        metrics.sql_count,
        metrics.capacity_wait_ms,
        metrics.pool_acquire_ms,
        max(metrics.loop_lag_ms, _loop_lag_ms),
    )
    return total_ms
