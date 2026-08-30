import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

os.environ.setdefault("SECRET_KEY", "unit-test-secret-not-for-production")

import auth_security
import login_captcha
import main as _main  # 导入完整模型注册表，避免仅加载局部模型时关系解析不完整。
from auth_security_models import (
    LoginCaptchaChallenge,
    LoginSecurityEvent,
    LoginThrottleState,
    RevokedAccessToken,
)
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
    RevokedAccessToken.__table__.create(engine)
    LoginCaptchaChallenge.__table__.create(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _configure_limits(monkeypatch, *, account=3, source=10, captcha=99):
    monkeypatch.setattr(auth_security, "ACCOUNT_FAILURE_LIMIT", account)
    monkeypatch.setattr(auth_security, "SOURCE_FAILURE_LIMIT", source)
    monkeypatch.setattr(auth_security, "LOGIN_WINDOW_SECONDS", 300)
    monkeypatch.setattr(auth_security, "BASE_BLOCK_SECONDS", 10)
    monkeypatch.setattr(auth_security, "MAX_BLOCK_SECONDS", 60)
    monkeypatch.setattr(auth_security, "ESCALATION_RESET_SECONDS", 600)
    # 默认把验证码阈值抬高，让限流用例不受图形验证码干扰。
    monkeypatch.setattr(login_captcha, "CAPTCHA_THRESHOLD", captcha)


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


def test_revoked_access_token_is_rejected(monkeypatch):
    sessions = _session_factory()
    user = type("User", (), {"is_active": True})()
    monkeypatch.setattr(auth_router, "get_user_by_username", lambda *_args, **_kwargs: user)
    token = auth_router.create_access_token({"sub": "gray_user"})
    payload = auth_router.jwt.decode(
        token, auth_router.SECRET_KEY, algorithms=[auth_router.ALGORITHM]
    )
    assert payload.get("jti")

    with sessions() as db:
        assert auth_router.get_user_from_token_value(db, token) is user
        auth_router.logout(token=token, db=db)
        auth_router.logout(token=token, db=db)
        assert auth_router.get_user_from_token_value(db, token) is None


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


CAPTCHA_HEADER = login_captcha.CAPTCHA_REQUIRED_HEADER.lower()
WRONG_CREDENTIALS = {"username": "gray_user", "password": "GRAY-REG-WRONG"}


def _login_app(sessions):
    app = FastAPI()
    app.include_router(auth_router.router)

    def override_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return app


def test_captcha_is_required_only_after_repeated_failures(monkeypatch):
    _configure_limits(monkeypatch, account=10, source=20, captcha=2)
    sessions = _session_factory()
    monkeypatch.setattr(auth_router, "get_user_by_username", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_router, "verify_password", lambda *_args, **_kwargs: False)

    with TestClient(_login_app(sessions)) as client:
        first = client.post("/auth/login/json", json=WRONG_CREDENTIALS)
        second = client.post("/auth/login/json", json=WRONG_CREDENTIALS)
        third = client.post("/auth/login/json", json=WRONG_CREDENTIALS)

    assert first.status_code == 401
    assert CAPTCHA_HEADER not in first.headers
    # 第二次失败后计数达到阈值，提前告知前端下一次需要验证码。
    assert second.status_code == 401
    assert second.headers[CAPTCHA_HEADER] == "1"
    assert third.status_code == 400
    assert third.json() == {"detail": login_captcha.CAPTCHA_ERROR}
    assert third.headers[CAPTCHA_HEADER] == "1"


def test_captcha_requirement_endpoint_tracks_source_failures(monkeypatch):
    _configure_limits(monkeypatch, account=10, source=20, captcha=2)
    sessions = _session_factory()
    monkeypatch.setattr(auth_router, "get_user_by_username", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_router, "verify_password", lambda *_args, **_kwargs: False)

    with TestClient(_login_app(sessions)) as client:
        assert client.get("/auth/captcha/required").json() == {"required": False}
        client.post("/auth/login/json", json=WRONG_CREDENTIALS)
        assert client.get("/auth/captcha/required").json() == {"required": False}
        client.post("/auth/login/json", json=WRONG_CREDENTIALS)
        requirement = client.get("/auth/captcha/required")

    assert requirement.json() == {"required": True}
    assert requirement.headers["cache-control"] == "no-store"


def test_wrong_captcha_is_rejected_without_counting_as_login_failure(monkeypatch):
    _configure_limits(monkeypatch, account=10, source=20, captcha=2)
    monkeypatch.setattr(login_captcha, "_generate_code", lambda: "AB34")
    sessions = _session_factory()
    monkeypatch.setattr(auth_router, "get_user_by_username", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_router, "verify_password", lambda *_args, **_kwargs: False)

    with TestClient(_login_app(sessions)) as client:
        client.post("/auth/login/json", json=WRONG_CREDENTIALS)
        client.post("/auth/login/json", json=WRONG_CREDENTIALS)
        challenge = client.get("/auth/captcha").json()
        rejected = client.post(
            "/auth/login/json",
            json={**WRONG_CREDENTIALS, "captcha_id": challenge["captcha_id"], "captcha_code": "XXXX"},
        )

    assert challenge["image"].startswith("data:image/svg+xml;base64,")
    assert rejected.status_code == 400
    assert rejected.json() == {"detail": login_captcha.CAPTCHA_ERROR}

    with sessions() as db:
        account_state = db.execute(
            select(LoginThrottleState).where(LoginThrottleState.dimension == "account")
        ).scalar_one()
        # 图形码输错不应把用户自己的账号推向锁定。
        assert len(account_state.failure_timestamps) == 2


def test_correct_captcha_allows_login_to_proceed(monkeypatch):
    _configure_limits(monkeypatch, account=10, source=20, captcha=2)
    monkeypatch.setattr(login_captcha, "_generate_code", lambda: "AB34")
    sessions = _session_factory()

    user = type(
        "User",
        (),
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "username": "gray_user",
            "full_name": "Gray User",
            "is_active": True,
            "password_hash": "$2b$12$" + "x" * 53,
        },
    )()
    monkeypatch.setattr(auth_router, "get_user_by_username", lambda *_args, **_kwargs: user)
    monkeypatch.setattr(
        auth_router, "verify_password", lambda plain, _hashed: plain == "GRAY-REG-RIGHT"
    )
    monkeypatch.setattr(auth_router, "get_user_roles_with_role_names", lambda *_args: ["gray"])
    monkeypatch.setattr(auth_router, "get_user_permission_codes", lambda *_args: [])

    with TestClient(_login_app(sessions)) as client:
        client.post("/auth/login/json", json=WRONG_CREDENTIALS)
        client.post("/auth/login/json", json=WRONG_CREDENTIALS)
        challenge = client.get("/auth/captcha").json()
        accepted = client.post(
            "/auth/login/json",
            json={
                "username": "gray_user",
                "password": "GRAY-REG-RIGHT",
                "captcha_id": challenge["captcha_id"],
                # 校验大小写不敏感。
                "captcha_code": " ab34 ",
            },
        )

    assert accepted.status_code == 200
    assert accepted.json()["username"] == "gray_user"


def test_captcha_cannot_be_replayed_or_used_after_expiry(monkeypatch):
    monkeypatch.setattr(login_captcha, "_generate_code", lambda: "AB34")
    monkeypatch.setattr(login_captcha, "CAPTCHA_TTL_SECONDS", 120)
    sessions = _session_factory()
    started = datetime(2026, 8, 29, tzinfo=timezone.utc)

    with sessions() as db:
        issued = login_captcha.issue_captcha(db, _request(), now=started)
        assert login_captcha.verify_captcha(db, _request(), issued.captcha_id, "ab34", now=started)
        assert not login_captcha.verify_captcha(db, _request(), issued.captcha_id, "ab34", now=started)

        stale = login_captcha.issue_captcha(db, _request(), now=started)
        assert not login_captcha.verify_captcha(
            db, _request(), stale.captcha_id, "AB34", now=started + timedelta(seconds=121)
        )


def test_captcha_is_bound_to_source_and_issue_is_rate_limited(monkeypatch):
    monkeypatch.setattr(login_captcha, "_generate_code", lambda: "AB34")
    monkeypatch.setattr(login_captcha, "CAPTCHA_ISSUE_LIMIT_PER_MINUTE", 2)
    sessions = _session_factory()
    started = datetime(2026, 8, 29, tzinfo=timezone.utc)

    with sessions() as db:
        issued = login_captcha.issue_captcha(db, _request(), now=started)
        assert not login_captcha.verify_captcha(
            db, _request("203.0.113.9"), issued.captcha_id, "AB34", now=started
        )

        login_captcha.issue_captcha(db, _request(), now=started + timedelta(seconds=1))
        with pytest.raises(HTTPException) as excinfo:
            login_captcha.issue_captcha(db, _request(), now=started + timedelta(seconds=2))

    assert excinfo.value.status_code == 429


def test_failures_outside_window_stop_requiring_captcha(monkeypatch):
    _configure_limits(monkeypatch, account=10, source=20, captcha=2)
    sessions = _session_factory()
    started = datetime(2026, 8, 29, tzinfo=timezone.utc)

    with sessions() as db:
        for offset in range(2):
            context, _ = auth_security.begin_login_attempt(
                db, "gray_user", _request(), now=started + timedelta(seconds=offset)
            )
            auth_security.record_login_failure(db, context, now=started + timedelta(seconds=offset))

        assert auth_security.peek_source_failure_count(
            db, _request(), now=started + timedelta(seconds=2)
        ) == 2
        # LOGIN_WINDOW_SECONDS 为 300，窗口外的旧失败不应让该 IP 永远看到验证码。
        assert auth_security.peek_source_failure_count(
            db, _request(), now=started + timedelta(seconds=400)
        ) == 0
