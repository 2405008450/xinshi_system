from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from auth_security_models import LoginCaptchaChallenge, LoginSecurityEvent, LoginThrottleState


logger = logging.getLogger(__name__)


def _positive_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


LOGIN_WINDOW_SECONDS = _positive_int("AUTH_LOGIN_WINDOW_SECONDS", 15 * 60, 60)
ACCOUNT_FAILURE_LIMIT = _positive_int("AUTH_LOGIN_ACCOUNT_FAILURE_LIMIT", 5, 2)
SOURCE_FAILURE_LIMIT = _positive_int("AUTH_LOGIN_SOURCE_FAILURE_LIMIT", 30, ACCOUNT_FAILURE_LIMIT)
BASE_BLOCK_SECONDS = _positive_int("AUTH_LOGIN_BASE_BLOCK_SECONDS", 60, 1)
MAX_BLOCK_SECONDS = _positive_int("AUTH_LOGIN_MAX_BLOCK_SECONDS", 15 * 60, BASE_BLOCK_SECONDS)
ESCALATION_RESET_SECONDS = _positive_int("AUTH_LOGIN_ESCALATION_RESET_SECONDS", 60 * 60, LOGIN_WINDOW_SECONDS)
AUDIT_RETENTION_DAYS = _positive_int("AUTH_LOGIN_AUDIT_RETENTION_DAYS", 90, 1)

GENERIC_CREDENTIAL_ERROR = "用户名或密码错误"
GENERIC_THROTTLE_ERROR = "登录尝试过于频繁，请稍后再试"


def _parse_trusted_proxy_networks(raw: str | None = None) -> tuple[ipaddress._BaseNetwork, ...]:
    value = raw if raw is not None else os.getenv("AUTH_TRUSTED_PROXY_CIDRS", "127.0.0.1/32,::1/128")
    networks = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            logger.warning("忽略无效的 AUTH_TRUSTED_PROXY_CIDRS 项：%s", item)
    return tuple(networks)


TRUSTED_PROXY_NETWORKS = _parse_trusted_proxy_networks()


@dataclass(frozen=True)
class LoginAttemptContext:
    account_hash: str
    source_hash: str


@dataclass(frozen=True)
class LoginThrottleDecision:
    blocked: bool
    retry_after: int = 0
    account_failure_count: int = 0
    source_failure_count: int = 0
    blocked_until: datetime | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_account(username: str) -> str:
    return (username or "").strip().casefold()


def _normalize_ip(value: str | None) -> str | None:
    try:
        return str(ipaddress.ip_address((value or "").strip()))
    except ValueError:
        return None


def _is_trusted_proxy(address: str) -> bool:
    parsed = ipaddress.ip_address(address)
    return any(parsed in network for network in TRUSTED_PROXY_NETWORKS)


def get_client_address(request: Request) -> str:
    """仅当直连节点受信任时解析 X-Forwarded-For，防止客户端伪造来源。"""

    peer = _normalize_ip(request.client.host if request.client else None) or "unknown"
    if peer == "unknown" or not _is_trusted_proxy(peer):
        return peer

    forwarded = request.headers.get("x-forwarded-for", "")
    chain = [address for address in (_normalize_ip(part) for part in forwarded.split(",")) if address]
    if not chain:
        return peer

    # 从离应用最近的一端反向剥离可信代理，首个非可信地址即真实来源。
    for address in reversed(chain):
        if not _is_trusted_proxy(address):
            return address
    return chain[0]


def hmac_fingerprint(dimension: str, value: str) -> str:
    """按维度生成不可逆指纹，供限流、审计与验证码共用同一套密钥。"""

    secret = os.getenv("AUTH_THROTTLE_HMAC_KEY") or os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError("AUTH_THROTTLE_HMAC_KEY or SECRET_KEY must be configured")
    return hmac.new(secret.encode("utf-8"), f"{dimension}:{value}".encode("utf-8"), hashlib.sha256).hexdigest()


def source_fingerprint(request: Request) -> str:
    return hmac_fingerprint("source", get_client_address(request))


def create_login_context(username: str, request: Request) -> LoginAttemptContext:
    return LoginAttemptContext(
        account_hash=hmac_fingerprint("account", normalize_account(username)),
        source_hash=source_fingerprint(request),
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _retry_after(blocked_until: datetime | None, now: datetime) -> int:
    until = _as_utc(blocked_until)
    return max(1, math.ceil((until - now).total_seconds())) if until and until > now else 0


def _advisory_lock_id(key_hash: str) -> int:
    value = int.from_bytes(bytes.fromhex(key_hash[:16]), byteorder="big", signed=False)
    return value - (1 << 64) if value >= (1 << 63) else value


def _acquire_transaction_locks(db: Session, context: LoginAttemptContext) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    for lock_id in sorted({_advisory_lock_id(context.account_hash), _advisory_lock_id(context.source_hash)}):
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})


def _load_states(db: Session, context: LoginAttemptContext) -> dict[str, LoginThrottleState]:
    rows = db.execute(
        select(LoginThrottleState)
        .where(
            ((LoginThrottleState.dimension == "account") & (LoginThrottleState.key_hash == context.account_hash))
            | ((LoginThrottleState.dimension == "source") & (LoginThrottleState.key_hash == context.source_hash))
        )
        .with_for_update()
    ).scalars()
    return {row.dimension: row for row in rows}


def _ensure_state(db: Session, dimension: str, key_hash: str) -> LoginThrottleState:
    values = {"dimension": dimension, "key_hash": key_hash, "failure_timestamps": [], "block_count": 0}
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(LoginThrottleState).values(**values).on_conflict_do_nothing(
            index_elements=["dimension", "key_hash"]
        )
    elif dialect == "sqlite":
        statement = sqlite_insert(LoginThrottleState).values(**values).on_conflict_do_nothing(
            index_elements=["dimension", "key_hash"]
        )
    else:
        existing = db.execute(
            select(LoginThrottleState).where(
                LoginThrottleState.dimension == dimension,
                LoginThrottleState.key_hash == key_hash,
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(LoginThrottleState(**values))
            db.flush()
    if dialect in {"postgresql", "sqlite"}:
        db.execute(statement)
        db.flush()
    return db.execute(
        select(LoginThrottleState)
        .where(LoginThrottleState.dimension == dimension, LoginThrottleState.key_hash == key_hash)
        .with_for_update()
    ).scalar_one()


def _current_decision(states: Iterable[LoginThrottleState], now: datetime) -> LoginThrottleDecision:
    retry_after = 0
    blocked_until = None
    counts = {"account": 0, "source": 0}
    cutoff = now - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    for state_row in states:
        # 失败时间戳只在下次失败时才会被裁剪，这里按窗口过滤，避免过期记录长期抬高计数。
        counts[state_row.dimension] = len(
            _parse_failure_timestamps(state_row.failure_timestamps or [], cutoff)
        )
        current_retry = _retry_after(state_row.blocked_until, now)
        if current_retry > retry_after:
            retry_after = current_retry
            blocked_until = _as_utc(state_row.blocked_until)
    return LoginThrottleDecision(
        blocked=retry_after > 0,
        retry_after=retry_after,
        account_failure_count=counts["account"],
        source_failure_count=counts["source"],
        blocked_until=blocked_until,
    )


def begin_login_attempt(
    db: Session,
    username: str,
    request: Request,
    *,
    now: datetime | None = None,
) -> tuple[LoginAttemptContext, LoginThrottleDecision]:
    current_time = now or utc_now()
    context = create_login_context(username, request)
    _acquire_transaction_locks(db, context)
    decision = _current_decision(_load_states(db, context).values(), current_time)
    if decision.blocked:
        _add_audit_event(db, "login_throttled", context, decision)
        db.commit()
        logger.warning(
            "login_security event=login_throttled account=%s source=%s retry_after=%s",
            context.account_hash[:12],
            context.source_hash[:12],
            decision.retry_after,
        )
    return context, decision


def _parse_failure_timestamps(values: Iterable[str], cutoff: datetime) -> list[datetime]:
    parsed = []
    for value in values:
        try:
            timestamp = _as_utc(datetime.fromisoformat(value))
        except (TypeError, ValueError):
            continue
        if timestamp and timestamp >= cutoff:
            parsed.append(timestamp)
    return parsed


def peek_source_failure_count(db: Session, request: Request, *, now: datetime | None = None) -> int:
    """只读取来源维度在当前窗口内的失败次数。

    登录页首屏用它判断是否直接展示验证码。刻意不接受用户名，
    避免外部通过「该账号是否需要验证码」探测账号是否存在。
    """

    current_time = now or utc_now()
    state_row = db.execute(
        select(LoginThrottleState).where(
            LoginThrottleState.dimension == "source",
            LoginThrottleState.key_hash == source_fingerprint(request),
        )
    ).scalar_one_or_none()
    if state_row is None:
        return 0
    cutoff = current_time - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    return len(_parse_failure_timestamps(state_row.failure_timestamps or [], cutoff))


def _record_dimension_failure(
    state_row: LoginThrottleState,
    *,
    limit: int,
    now: datetime,
) -> tuple[int, int]:
    cutoff = now - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    timestamps = _parse_failure_timestamps(state_row.failure_timestamps or [], cutoff)
    timestamps.append(now)
    state_row.failure_timestamps = [item.isoformat() for item in timestamps]

    previous_failure = _as_utc(state_row.last_failed_at)
    if previous_failure is None or previous_failure < now - timedelta(seconds=ESCALATION_RESET_SECONDS):
        state_row.block_count = 0
    state_row.last_failed_at = now

    retry_after = 0
    if len(timestamps) >= limit:
        state_row.block_count = (state_row.block_count or 0) + 1
        block_seconds = min(MAX_BLOCK_SECONDS, BASE_BLOCK_SECONDS * (2 ** (state_row.block_count - 1)))
        state_row.blocked_until = now + timedelta(seconds=block_seconds)
        retry_after = block_seconds
    state_row.updated_at = now
    return len(timestamps), retry_after


def record_login_failure(
    db: Session,
    context: LoginAttemptContext,
    *,
    now: datetime | None = None,
) -> LoginThrottleDecision:
    current_time = now or utc_now()
    # 验证码校验会在本次登录中途提交事务并释放 begin_login_attempt 取得的顾问锁，
    # 这里重新获取（同一事务内可重入），保证并发失败仍然串行入账。
    _acquire_transaction_locks(db, context)
    states = _load_states(db, context)
    account_state = states.get("account") or _ensure_state(db, "account", context.account_hash)
    source_state = states.get("source") or _ensure_state(db, "source", context.source_hash)

    account_count, account_retry = _record_dimension_failure(
        account_state, limit=ACCOUNT_FAILURE_LIMIT, now=current_time
    )
    source_count, source_retry = _record_dimension_failure(
        source_state, limit=SOURCE_FAILURE_LIMIT, now=current_time
    )
    retry_after = max(account_retry, source_retry)
    blocked_until = current_time + timedelta(seconds=retry_after) if retry_after else None
    decision = LoginThrottleDecision(
        blocked=retry_after > 0,
        retry_after=retry_after,
        account_failure_count=account_count,
        source_failure_count=source_count,
        blocked_until=blocked_until,
    )
    _add_audit_event(db, "login_blocked" if decision.blocked else "login_failed", context, decision)
    db.commit()
    logger.warning(
        "login_security event=%s account=%s source=%s account_failures=%s source_failures=%s retry_after=%s",
        "login_blocked" if decision.blocked else "login_failed",
        context.account_hash[:12],
        context.source_hash[:12],
        account_count,
        source_count,
        retry_after,
    )
    return decision


def record_login_success(db: Session, context: LoginAttemptContext) -> None:
    account_state = db.execute(
        select(LoginThrottleState)
        .where(LoginThrottleState.dimension == "account", LoginThrottleState.key_hash == context.account_hash)
        .with_for_update()
    ).scalar_one_or_none()
    if account_state is None:
        return
    source_state = db.execute(
        select(LoginThrottleState).where(
            LoginThrottleState.dimension == "source", LoginThrottleState.key_hash == context.source_hash
        )
    ).scalar_one_or_none()
    decision = LoginThrottleDecision(
        blocked=False,
        account_failure_count=len(account_state.failure_timestamps or []),
        source_failure_count=len(source_state.failure_timestamps or []) if source_state else 0,
    )
    _add_audit_event(db, "login_succeeded_after_failures", context, decision)
    db.delete(account_state)


def _add_audit_event(
    db: Session,
    event_type: str,
    context: LoginAttemptContext,
    decision: LoginThrottleDecision,
) -> None:
    db.add(
        LoginSecurityEvent(
            event_type=event_type,
            account_hash=context.account_hash,
            source_hash=context.source_hash,
            account_failure_count=decision.account_failure_count,
            source_failure_count=decision.source_failure_count,
            blocked_until=decision.blocked_until,
        )
    )


def throttle_exception(decision: LoginThrottleDecision) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=GENERIC_THROTTLE_ERROR,
        headers={
            "Retry-After": str(max(1, decision.retry_after)),
            "Cache-Control": "no-store",
        },
    )


def cleanup_login_security_data(db: Session, *, now: datetime | None = None) -> None:
    current_time = now or utc_now()
    db.execute(
        delete(LoginSecurityEvent).where(
            LoginSecurityEvent.created_at < current_time - timedelta(days=AUDIT_RETENTION_DAYS)
        )
    )
    db.execute(
        delete(LoginThrottleState).where(
            LoginThrottleState.updated_at < current_time - timedelta(days=AUDIT_RETENTION_DAYS),
            (LoginThrottleState.blocked_until.is_(None)) | (LoginThrottleState.blocked_until < current_time),
        )
    )
    db.execute(delete(LoginCaptchaChallenge).where(LoginCaptchaChallenge.expires_at < current_time))
    db.commit()
