"""用户邮件显示名与轻量富文本签名。"""

from __future__ import annotations

import html
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from daily_report_mail_models import UserMailProfile
from mail_html_security import safe_css_color, safe_mail_href
from models import AppUser


class _SignatureHtmlParser(HTMLParser):
    allowed = {"p", "div", "br", "strong", "b", "em", "i", "u", "span", "a", "ul", "ol", "li"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag not in self.allowed:
            return
        values = dict(attrs)
        if tag == "br":
            self.output.append("<br>")
            self.text.append("\n")
            return
        attributes = ""
        if tag == "a":
            href = safe_mail_href(values.get("href", ""))
            if href:
                attributes = f' href="{html.escape(href, quote=True)}" rel="noopener noreferrer"'
        elif tag in {"span", "p", "div"}:
            style_values = {}
            for item in (values.get("style") or "").split(";"):
                key, separator, value = item.partition(":")
                if separator:
                    style_values[key.strip().lower()] = value.strip()
            color = safe_css_color(style_values.get("color", "") or values.get("color", ""))
            if color:
                attributes = f' style="color:{color};"'
        self.output.append(f"<{tag}{attributes}>")
        if tag == "li":
            self.text.append("• ")

    def handle_startendtag(self, tag: str, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag not in self.allowed or tag == "br":
            return
        self.output.append(f"</{tag}>")
        if tag in {"p", "div", "li"}:
            self.text.append("\n")

    def handle_data(self, data: str):
        self.output.append(html.escape(data))
        self.text.append(data)


def sanitize_signature_html(value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not value or not value.strip():
        return None, None
    parser = _SignatureHtmlParser()
    parser.feed(value)
    parser.close()
    safe_html = "".join(parser.output).strip()
    plain_text = re.sub(r"\n{3,}", "\n\n", "".join(parser.text)).strip()
    return (safe_html or None), (plain_text or None)


def get_user_mail_profile(db: Session, user_id: UUID) -> Optional[UserMailProfile]:
    return db.query(UserMailProfile).filter(UserMailProfile.user_id == user_id).first()


def get_user_mail_profiles(db: Session, user_ids: Iterable[UUID]) -> dict[UUID, UserMailProfile]:
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return {}
    rows = db.query(UserMailProfile).filter(UserMailProfile.user_id.in_(ids)).all()
    return {row.user_id: row for row in rows}


def recipient_display_name(user: AppUser, profile: Optional[UserMailProfile] = None) -> str:
    return (
        (profile.recipient_display_name.strip() if profile and profile.recipient_display_name else "")
        or (user.full_name or "").strip()
        or user.username.strip()
    )


def recipient_display_names(db: Session, users: Iterable[AppUser]) -> dict[UUID, str]:
    rows = list(users)
    profiles = get_user_mail_profiles(db, [item.id for item in rows])
    return {item.id: recipient_display_name(item, profiles.get(item.id)) for item in rows}


def serialize_user_mail_profile(user: AppUser, profile: Optional[UserMailProfile]) -> dict:
    return {
        "user_id": user.id,
        "recipient_display_name": profile.recipient_display_name if profile else None,
        "signature_html": profile.signature_html if profile else None,
        "signature_text": profile.signature_text if profile else None,
        "signature_enabled": bool(profile and profile.signature_enabled),
        "updated_at": profile.updated_at if profile else None,
    }


def save_user_mail_profile(db: Session, user: AppUser, payload, actor_id: UUID) -> dict:
    safe_html, plain_text = sanitize_signature_html(payload.signature_html)
    if payload.signature_enabled and not plain_text:
        raise ValueError("启用签名前请先填写有效的签名内容")
    profile = get_user_mail_profile(db, user.id)
    if not profile:
        profile = UserMailProfile(user_id=user.id)
        db.add(profile)
    profile.recipient_display_name = payload.recipient_display_name
    profile.signature_html = safe_html
    profile.signature_text = plain_text
    profile.signature_enabled = bool(payload.signature_enabled)
    profile.updated_by = actor_id
    profile.updated_at = datetime.now()
    db.commit()
    db.refresh(profile)
    return serialize_user_mail_profile(user, profile)


def active_signature(profile: Optional[UserMailProfile]) -> tuple[Optional[str], Optional[str]]:
    if not profile or not profile.signature_enabled or not profile.signature_html or not profile.signature_text:
        return None, None
    safe_html, plain_text = sanitize_signature_html(profile.signature_html)
    return safe_html, plain_text


def append_signature(
    body_html: str,
    body_text: str,
    profile: Optional[UserMailProfile],
) -> tuple[str, str]:
    signature_html, signature_text = active_signature(profile)
    if not signature_html or not signature_text:
        return body_html, body_text
    combined_html = (
        f'{body_html}<div data-mail-signature="true" '
        'style="margin-top:20px;padding-top:12px;border-top:1px solid #e5e7eb;">'
        f"{signature_html}</div>"
    )
    return combined_html, f"{body_text.rstrip()}\n\n{signature_text}"
