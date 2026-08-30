"""登录图形验证码：按需触发、后端生成 SVG、状态落库。

日常登录不展示验证码；只有当账号或来源 IP 在限流窗口内已经失败若干次时，
才要求输入。验证码答案只以 HMAC 摘要落库，且一次性消费。
"""

from __future__ import annotations

import base64
import hmac
import logging
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from auth_security import hmac_fingerprint, source_fingerprint, utc_now
from auth_security_models import LoginCaptchaChallenge


logger = logging.getLogger(__name__)


def _positive_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


CAPTCHA_THRESHOLD = _positive_int("AUTH_LOGIN_CAPTCHA_THRESHOLD", 2, 1)
CAPTCHA_TTL_SECONDS = _positive_int("AUTH_LOGIN_CAPTCHA_TTL_SECONDS", 120, 30)
CAPTCHA_ISSUE_LIMIT_PER_MINUTE = _positive_int("AUTH_LOGIN_CAPTCHA_ISSUE_LIMIT_PER_MINUTE", 10, 1)

CAPTCHA_LENGTH = 4
# 去掉 0/O、1/I/L、2/Z 等易混字符，减少用户反复输错。
CAPTCHA_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXY3456789"
CAPTCHA_ISSUE_WINDOW_SECONDS = 60

CAPTCHA_REQUIRED_HEADER = "X-Login-Captcha-Required"
CAPTCHA_ERROR = "验证码错误，请重新输入"
CAPTCHA_ISSUE_THROTTLE_ERROR = "验证码获取过于频繁，请稍后再试"

_rng = secrets.SystemRandom()

_SVG_WIDTH = 120
_SVG_HEIGHT = 40
_TEXT_COLORS = ("#1d4ed8", "#b91c1c", "#047857", "#7c3aed", "#b45309", "#0f766e")
_NOISE_COLORS = ("#94a3b8", "#cbd5e1", "#a5b4fc", "#fca5a5", "#86efac")


@dataclass(frozen=True)
class IssuedCaptcha:
    captcha_id: str
    image: str
    expires_in: int


def captcha_required(account_failure_count: int, source_failure_count: int) -> bool:
    return max(account_failure_count, source_failure_count) >= CAPTCHA_THRESHOLD


def normalize_code(code: str | None) -> str:
    return (code or "").strip().upper()


def _answer_hash(code: str) -> str:
    return hmac_fingerprint("captcha", normalize_code(code))


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def render_svg(code: str) -> str:
    """用纯字符串拼出带干扰的 SVG，避免为验证码引入图像处理依赖。"""

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_SVG_WIDTH}" height="{_SVG_HEIGHT}" '
        f'viewBox="0 0 {_SVG_WIDTH} {_SVG_HEIGHT}" role="img" aria-label="图形验证码">',
        f'<rect width="{_SVG_WIDTH}" height="{_SVG_HEIGHT}" fill="#f1f5f9"/>',
    ]
    for _ in range(3):
        start_y = _rng.randint(0, _SVG_HEIGHT)
        end_y = _rng.randint(0, _SVG_HEIGHT)
        control_x = _rng.randint(30, _SVG_WIDTH - 30)
        control_y = _rng.randint(-10, _SVG_HEIGHT + 10)
        parts.append(
            f'<path d="M0 {start_y} Q{control_x} {control_y} {_SVG_WIDTH} {end_y}" '
            f'stroke="{_rng.choice(_NOISE_COLORS)}" stroke-width="{_rng.choice(("1", "1.5"))}" fill="none"/>'
        )
    for _ in range(24):
        parts.append(
            f'<circle cx="{_rng.randint(0, _SVG_WIDTH)}" cy="{_rng.randint(0, _SVG_HEIGHT)}" '
            f'r="{_rng.choice(("0.8", "1", "1.2"))}" fill="{_rng.choice(_NOISE_COLORS)}"/>'
        )
    step = _SVG_WIDTH / (len(code) + 1)
    for index, char in enumerate(code):
        x = step * (index + 1) + _rng.randint(-3, 3)
        y = _SVG_HEIGHT / 2 + _rng.randint(7, 10)
        parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" fill="{_rng.choice(_TEXT_COLORS)}" '
            f'font-family="DejaVu Sans, Verdana, sans-serif" font-size="{_rng.randint(22, 26)}" '
            f'font-weight="700" text-anchor="middle" '
            f'transform="rotate({_rng.randint(-24, 24)} {x:.1f} {y:.1f})">{char}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _generate_code() -> str:
    return "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(CAPTCHA_LENGTH))


def _to_data_uri(svg: str) -> str:
    return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode('utf-8')).decode('ascii')}"


def issue_throttle_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=CAPTCHA_ISSUE_THROTTLE_ERROR,
        headers={"Retry-After": str(CAPTCHA_ISSUE_WINDOW_SECONDS), "Cache-Control": "no-store"},
    )


def captcha_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=CAPTCHA_ERROR,
        headers={CAPTCHA_REQUIRED_HEADER: "1", "Cache-Control": "no-store"},
    )


def issue_captcha(db: Session, request: Request, *, now: datetime | None = None) -> IssuedCaptcha:
    current_time = now or utc_now()
    source_hash = source_fingerprint(request)

    recent_issues = db.execute(
        select(func.count())
        .select_from(LoginCaptchaChallenge)
        .where(
            LoginCaptchaChallenge.source_hash == source_hash,
            LoginCaptchaChallenge.created_at
            >= current_time - timedelta(seconds=CAPTCHA_ISSUE_WINDOW_SECONDS),
        )
    ).scalar_one()
    if recent_issues >= CAPTCHA_ISSUE_LIMIT_PER_MINUTE:
        logger.warning("login_captcha event=issue_throttled source=%s", source_hash[:12])
        raise issue_throttle_exception()

    # 同一来源同时只保留一个有效挑战；旧挑战标记为已消费而非删除，
    # 这样签发频率统计仍能看到完整历史。
    db.execute(
        update(LoginCaptchaChallenge)
        .where(
            LoginCaptchaChallenge.source_hash == source_hash,
            LoginCaptchaChallenge.consumed_at.is_(None),
        )
        .values(consumed_at=current_time)
    )

    code = _generate_code()
    challenge = LoginCaptchaChallenge(
        id=uuid.uuid4(),
        answer_hash=_answer_hash(code),
        source_hash=source_hash,
        expires_at=current_time + timedelta(seconds=CAPTCHA_TTL_SECONDS),
        created_at=current_time,
    )
    db.add(challenge)
    db.commit()
    return IssuedCaptcha(
        captcha_id=str(challenge.id),
        image=_to_data_uri(render_svg(code)),
        expires_in=CAPTCHA_TTL_SECONDS,
    )


def verify_captcha(
    db: Session,
    request: Request,
    captcha_id: str | None,
    code: str | None,
    *,
    now: datetime | None = None,
) -> bool:
    current_time = now or utc_now()
    if not captcha_id or not normalize_code(code):
        return False
    try:
        challenge_id = uuid.UUID(str(captcha_id))
    except (AttributeError, TypeError, ValueError):
        return False

    challenge = db.execute(
        select(LoginCaptchaChallenge)
        .where(LoginCaptchaChallenge.id == challenge_id)
        .with_for_update()
    ).scalar_one_or_none()
    if challenge is None:
        return False

    already_consumed = challenge.consumed_at is not None
    expires_at = _as_utc(challenge.expires_at)
    answer_hash = challenge.answer_hash
    challenge_source = challenge.source_hash

    # 无论校验结果如何都一次性作废，杜绝重放和对同一张图逐次碰撞。
    challenge.consumed_at = current_time
    db.commit()

    if already_consumed or expires_at is None or expires_at < current_time:
        return False
    if not hmac.compare_digest(challenge_source, source_fingerprint(request)):
        return False
    return hmac.compare_digest(answer_hash, _answer_hash(code))
