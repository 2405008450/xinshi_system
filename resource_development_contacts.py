"""资源账号保存、审计与权限遮罩，以及原表联系方式分类。"""
import re
import unicodedata
from uuid import uuid4

from resource_development_models import DevelopmentResourceContact as Contact, DevelopmentAudit
from business_time import business_now


def contact_data(db, record_id, allowed=True):
    row = db.get(Contact, record_id)
    whatsapp = row.whatsapp if row else ""
    accounts = [dict(item) for item in (row.custom_accounts or [])] if row else []
    if not allowed:
        whatsapp = "******" if whatsapp else ""
        accounts = [{"name": item["name"], "value": "******"} for item in accounts]
    return {"whatsapp": whatsapp, "custom_accounts": accounts,
            "custom_accounts_text": "；".join(f'资源{item["name"]}号：{item["value"]}' for item in accounts)}


def save_contacts(db, user, record_id, payload):
    fields = payload.model_fields_set & {"whatsapp", "custom_accounts"}
    if not fields:
        return
    row = db.get(Contact, record_id)
    before = contact_data(db, record_id)
    values = {"whatsapp": before["whatsapp"], "custom_accounts": before["custom_accounts"]}
    if "whatsapp" in fields:
        values["whatsapp"] = payload.whatsapp
    if "custom_accounts" in fields:
        values["custom_accounts"] = [item.model_dump() for item in payload.custom_accounts]
    if all(values[key] == before[key] for key in values):
        return
    if row is None:
        row = Contact(record_id=record_id)
        db.add(row)
    row.whatsapp, row.custom_accounts = values["whatsapp"], values["custom_accounts"]
    db.add(DevelopmentAudit(id=uuid4(), entity_id=record_id, entity_type="record_contacts",
                            actor_id=user.id, action="update" if before["whatsapp"] or before["custom_accounts"] else "create",
                            before=before, after=values, created_at=business_now()))


MOBILE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{3,99}")
XHS_SUFFIX = re.compile(r"^(?P<value>.+?)\s*\((?:小红书(?:号|ID|id)?)\)$", re.IGNORECASE)
WECHAT_SUFFIX = re.compile(r"^(?P<value>.+?)\s*\((?:微信号|微信ID)\)$", re.IGNORECASE)
MISSING = {"未提供", "没提供", "未发", "未互换", "微信号未提供", "暂无", "无", "没有", "未留", "待提供", "-", "--"}


def normalize(raw):
    return unicodedata.normalize("NFKC", str(raw or "")).strip()


def clean_id(value):
    value = value.strip().strip('“”"\'').strip()
    return value if IDENTIFIER.fullmatch(value) else ""


def classify_contact(raw):
    """返回可确定的字段值和未结构化原文；原始单元格始终另行保留。"""
    original = str(raw or "").strip()
    value = normalize(raw)
    result = {"phone": "", "wechat": "", "xiaohongshu": "", "other": "", "kind": "empty"}
    if not value:
        return result
    if value in MISSING or re.fullmatch(r"微信(?:号|ID)?\s*未提供", value, re.IGNORECASE):
        result["kind"] = "missing_marker"
        result["other"] = original
        return result
    if re.search(r"他推的|朋友id|朋友ID|推荐人|转介绍", value):
        result["kind"] = "third_party"
        result["other"] = original
        return result
    if re.search(r"whats\s?app", value, re.IGNORECASE):
        # 系统没有个人 WhatsApp 字段；如还明确标出 WeChat，单独提取它。
        wechat = re.search(r"(?:WeChat|微信(?:号|ID)?)\s*[:：]?\s*([A-Za-z0-9_.-]{4,100})", value, re.IGNORECASE)
        if wechat:
            result["wechat"] = clean_id(wechat.group(1))
        else:
            wechat_number = re.search(r"(1[3-9]\d{9})\s*\(WeChat\)", value, re.IGNORECASE)
            if wechat_number:
                result["wechat"] = wechat_number.group(1)
        result["kind"] = "other_channel"
        result["other"] = original
        return result
    if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        result.update(kind="email_other", other=original)
        return result
    xhs = XHS_SUFFIX.fullmatch(value)
    if xhs:
        prefix = xhs.group("value").strip()
        if "/" in prefix:
            first, prefix = prefix.rsplit("/", 1)
            phone = re.search(r"\+\d[\d\s-]{6,20}(?=\s*\(电话号码\))", first)
            if phone:
                result["phone"] = phone.group().strip()
        result["xiaohongshu"] = clean_id(prefix)
        if result["xiaohongshu"]:
            result["kind"] = "xiaohongshu_labeled"
            return result
    if "小红书" in value:
        result["kind"] = "xiaohongshu_ambiguous"
        result["other"] = original
        return result
    phone_and_wechat = re.fullmatch(r"电话\s*[:：]\s*(1[3-9]\d{9})\s*微信\s*[:：]\s*([A-Za-z0-9_.-]{4,100})", value)
    if phone_and_wechat:
        result.update(phone=phone_and_wechat.group(1), wechat=phone_and_wechat.group(2), kind="phone_and_wechat_labeled")
        return result
    labeled_wechat = re.fullmatch(r"(?:微信(?:号|ID)?|WeChat)\s*[:：]?\s*([A-Za-z0-9_.-]{4,100})", value, re.IGNORECASE)
    if labeled_wechat:
        result.update(wechat=clean_id(labeled_wechat.group(1)), kind="wechat_labeled")
        return result
    suffix_wechat = WECHAT_SUFFIX.fullmatch(value)
    if suffix_wechat:
        result.update(wechat=clean_id(suffix_wechat.group("value")), kind="wechat_labeled")
        return result
    if "微信名" in value:
        result.update(kind="wechat_display_name", other=original)
        return result
    direct_phone = re.fullmatch(r"(?:电话\s*[:：]\s*)?(1[3-9]\d{9})(?:\s*[-—]\s*直接打电话(?:来|过来))?", value)
    if direct_phone:
        result.update(phone=direct_phone.group(1), kind="phone")
        return result
    if re.fullmatch(r"0086(1[3-9]\d{9})", value):
        result.update(phone="+86" + value[4:], kind="phone_international_prefix")
        return result
    if re.fullmatch(r"[A-Za-z0-9_.-]{4,100}\s*[-—]\s*直接加微信过来", value):
        result.update(wechat=value.split("-")[0].strip(), kind="wechat_context")
        return result
    spaced_phone = re.fullmatch(r"(1[3-9]\d[\d\s]{8,14})", value)
    if spaced_phone and re.sub(r"\D", "", value) and MOBILE.fullmatch(re.sub(r"\D", "", value)):
        result.update(phone=re.sub(r"\D", "", value), kind="phone_spaced")
        return result
    phone_with_note = re.fullmatch(r"(1[3-9]\d{9})\s*[,，]\s*留号码未互换", value)
    if phone_with_note:
        result.update(phone=phone_with_note.group(1), kind="phone_with_note", other=original)
        return result
    phone_note = re.fullmatch(r"(1[3-9]\d{9})(?:留号码未互换|有标注质检经验|直接打电话过来)", value)
    if phone_note:
        result.update(phone=phone_note.group(1), kind="phone_with_note", other=original)
        return result
    trailing_id = re.fullmatch(r"\([^)]*\)([A-Za-z][A-Za-z0-9_.-]{3,99})", value)
    if trailing_id:
        result.update(wechat=trailing_id.group(1), kind="wechat_with_note", other=original)
        return result
    annotated = re.fullmatch(r"([A-Za-z0-9_.-]{4,100})\s*\([^)]*\)", value)
    if annotated:
        result.update(wechat=annotated.group(1), kind="wechat_with_note", other=original)
        return result
    if re.fullmatch(r"[A-Za-z]+\s+[A-Za-z]+", value):
        result.update(kind="person_name", other=original)
        return result
    if re.fullmatch(r"[A-Za-z0-9_.-]{4,100}", value):
        if re.fullmatch(r"\d{12,}", value) or re.fullmatch(r"[-.0-9]+", value) and len(re.sub(r"\D", "", value)) < 7:
            result.update(kind="ambiguous_numeric", other=original)
            return result
        result.update(wechat=value, kind="wechat_unlabeled")
        return result
    result.update(kind="unclassified", other=original)
    return result
