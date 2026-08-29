import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

os.environ.setdefault("SECRET_KEY", "unit-test-secret-not-for-production")

import auth_security
import main as _main  # 导入完整模型注册表，避免仅加载局部模型时关系解析不完整。
from auth_security_models import LoginSecurityEvent, LoginThrottleState
from database import get_db
from routers import auth as auth_router


def _request(peer="198.51.100.20", forwarded_for=None):
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login/json",
            "headers": headers,
            "client": (peer, 45678),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    LoginThrottleState.__table__.create(engine)
    LoginSecurityEvent.__table__.create(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _configure_limits(monkeypatch, *, account=3, source=10):
    monkeypatch.setattr(auth_security, "ACCOUNT_FAILURE_LIMIT", account)
    monkeypatch.setattr(auth_security, "SOURCE_FAILURE_LIMIT", source)
    monkeypatch.setattr(auth_security, "LOGIN_WINDOW_SECONDS", 300)
    monkeypatch.setattr(auth_security, "BASE_BLOCK_SECONDS", 10)
    monkeypatch.setattr(auth_security, "MAX_BLOCK_SECONDS", 60)
    monkeypatch.setattr(auth_security, "ESCALATION_RESET_SECONDS", 600)


def test_account_limit_returns_retry_after_and_exponential_relock(monkeypatch):
    _configure_limits(monkeypatch)
    sessions = _session_factory()
    started = datetime(2026, 8, 29, tzinfo=timezone.utc)

    with sessions() as db:
        for offset in range(3):
            context, initial = auth_security.begin_login_attempt(
                db, " Gray_User ", _request(), now=started + timedelta(seconds=offset)
            )
            assert initial.blocked is False
            decision = auth_security.record_login_failure(
                db, context, now=started + timedelta(seconds=offset)
            )

        assert decision.blocked is True
        assert decision.retry_after == 10
        assert decision.account_failure_count == 3

        _, blocked = auth_security.begin_login_attempt(
            db, "gray_user", _request(), now=started + timedelta(seconds=3)
        )
        assert blocked.blocked is True
        assert blocked.retry_after == 9

        context, recovered = auth_security.begin_login_attempt(
            db, "gray_user", _request(), now=started + timedelta(seconds=12)
        )
        assert recovered.blocked is False
        relocked = auth_security.record_login_failure(
            db, context, now=started + timedelta(seconds=12)
        )
        assert relocked.blocked is True
        assert relocked.retry_after == 20


def test_success_clears_account_failures_but_not_shared_source(monkeypatch):
    _configure_limits(monkeypatch, account=5, source=10)
    sessions = _session_factory()
    started = datetime(2026, 8, 29, tzinfo=timezone.utc)

    with sessions() as db:
        context, _ = auth_security.begin_login_attempt(db, "gray_user", _request(), now=started)
        auth_security.record_login_failure(db, context, now=started)
        context, _ = auth_security.begin_login_attempt(
            db, "gray_user", _request(), now=started + timedelta(seconds=1)
        )
        auth_security.record_login_success(db, context)
        db.commit()

        states = db.execute(select(LoginThrottleState)).scalars().all()
        assert [state.dimension for state in states] == ["source"]
        assert len(states[0].failure_timestamps) == 1
        event_types = db.execute(select(LoginSecurityEvent.event_type)).scalars().all()
        assert event_types == ["login_failed", "login_succeeded_after_failures"]


def test_source_limit_covers_multiple_account_names(monkeypatch):
    _configure_limits(monkeypatch, account=99, source=3)
    sessions = _session_factory()
    started = datetime(2026, 8, 29, tzinfo=timezone.utc)

    with sessions() as db:
        for offset, username in enumerate(("gray_a", "gray_b", "gray_c")):
            context, allowed = auth_security.begin_login_attempt(
                db, username, _request(), now=started + timedelta(seconds=offset)
            )
            assert allowed.blocked is False
            decision = auth_security.record_login_failure(
                db, context, now=started + timedelta(seconds=offset)
            )
        assert decision.source_failure_count == 3
        assert decision.blocked is True

        _, blocked = auth_security.begin_login_attempt(
            db, "another-account", _request(), now=started + timedelta(seconds=3)
        )
        assert blocked.blocked is True
        assert blocked.retry_after == 9


def test_forwarded_address_is_used_only_for_trusted_proxy(monkeypatch):
    monkeypatch.setattr(
        auth_security,
        "TRUSTED_PROXY_NETWORKS",
        auth_security._parse_trusted_proxy_networks("127.0.0.1/32,10.0.0.0/8"),
    )
    assert auth_security.get_client_address(
        _request("127.0.0.1", "203.0.113.8, 10.0.0.9")
    ) == "203.0.113.8"
    assert auth_security.get_client_address(
        _request("198.51.100.7", "203.0.113.8")
    ) == "198.51.100.7"


def test_json_login_switches_from_401_to_429_with_retry_after(monkeypatch):
    _configure_limits(monkeypatch, account=3, source=20)
    sessions = _session_factory()
    app = FastAPI()
    app.include_router(auth_router.router)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(auth_router, "get_user_by_username", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_router, "verify_password", lambda *_args, **_kwargs: False)

    with TestClient(app) as client:
        responses = [
            client.post(
                "/auth/login/json",
                json={"username": "gray_noaccess", "password": "GRAY-REG-WRONG"},
            )
            for _ in range(3)
        ]

    assert [response.status_code for response in responses] == [401, 401, 429]
    assert responses[0].json() == {"detail": auth_security.GENERIC_CREDENTIAL_ERROR}
    assert responses[2].json() == {"detail": auth_security.GENERIC_THROTTLE_ERROR}
    assert responses[2].headers["retry-after"] == "10"
    assert responses[2].headers["cache-control"] == "no-store"
