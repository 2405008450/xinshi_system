"""资源开拓统筹表只读预览。解析与比对不产生任何数据库写入。"""
from collections import Counter, defaultdict
from datetime import date, datetime
from io import BytesIO
import json
import re

from fastapi import HTTPException
from openpyxl import load_workbook

from resource_development_models import DevelopmentOption, DevelopmentRecord
from models import AppUser
from interpretation_models import InterpretationLanguage
from resource_development_contacts import classify_contact


HEADERS = ("日期", "开拓人/HR", "姓名", "语种", "来源", "对接账号", "备注：微信号/手机号", "已加微信", "已加企微", "已邀进群", "已沟通", "已入项", "后续跟进情况")
KEY_FIELDS = HEADERS[:7]
STATE_FIELDS = HEADERS[7:]
ACTION_CHANNELS = {"已加微信": "wechat", "已加企微": "enterprise", "已邀进群": "group", "已沟通": "communication", "已入项": "project"}
SOURCE_PATTERN = re.compile(r"【原表信息】(\{[^\n]*\})")
PLATFORM_ALIASES = {"boss": "BOSS直聘", "boss直聘": "BOSS直聘", "前程": "前程无忧", "51job": "前程无忧", "智联": "智联招聘", "鱼泡网": "鱼泡", "小红书": "小红书招聘号"}
OWNER_ALIASES = {"立溶": "郑立溶", "黎涛": "黎涛", "家俊": "冯家俊", "靖琳": "欧阳靖琳", "星宇": "刘星宇", "志荣": "仇志荣", "裕林": "钟裕林", "振中": "李振中", "依琳": "陈依琳", "政燃": "沈政燃", "翠珍": "梁翠珍", "静玲": "陈静玲", "舒婷": "彭舒婷", "景瀚": "肖景瀚", "宇琪": "李宇琪", "少洁": "蔡少洁", "菀筠": "黄菀筠", "楷翔": "林楷翔", "钟毓": "余钟毓", "绍娇": "杨绍娇", "浚轩": "邵浚轩", "胜辉": "李胜辉"}
LANGUAGE_ALIASES = {"西语": "西班牙语", "闽南话": "闽南语", "英语": "英语", "粤语": "粤语"}


def cell(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def key(values):
    return tuple(cell(values.get(field)).casefold() for field in KEY_FIELDS)


def parse_date(raw):
    value = cell(raw)
    try:
        if re.fullmatch(r"\d{8}", value):
            return date(int(value[:4]), int(value[4:6]), int(value[6:8])).isoformat()
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return ""


def match_languages(raw, catalog):
    parts = [part.strip() for part in re.split(r"[、，,/＋+;；\n]+", cell(raw)) if part.strip()]
    matched, unmatched = [], []
    for part in parts:
        base = re.sub(r"母语$", "", part)
        label = LANGUAGE_ALIASES.get(base, base)
        if label in catalog:
            if label not in matched:
                matched.append(label)
        else:
            unmatched.append(part)
    return matched, unmatched


def source_values(record):
    match = SOURCE_PATTERN.search(record.remarks or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def action_preview(raw, field, work_date, users):
    """只提出可核对的动作草案，不把原文视为已经验证的事实。"""
    value = cell(raw)
    match = re.match(r"^(\d{8}|\d{4})\s*[-－—]\s*(.+)$", value)
    result = {"field": field, "channel": ACTION_CHANNELS[field], "raw": value, "date": "", "operator": "", "status": "", "issues": []}
    if not match:
        result["issues"].append("状态标记缺少可识别的日期或操作人")
        return result
    digits, tail = match.groups()
    year = work_date[:4] if len(digits) == 4 and work_date else ""
    result["date"] = parse_date((year + digits) if year else digits)
    if not result["date"]:
        result["issues"].append("状态日期无效")
    names = sorted(users, key=len, reverse=True)
    name = next((name for name in names if tail.startswith(name)), "")
    result["operator"] = name
    if not name:
        result["issues"].append("状态操作人未匹配")
    elif not users[name].is_active:
        result["issues"].append("状态操作人已停用")
    if field in {"已加微信", "已加企微"}:
        result["status"] = "一次请求" if "请求" in tail and "已加" not in tail else "已添加"
    else:
        result["status"] = {"已邀进群": "已拉群", "已沟通": "已沟通", "已入项": "已入项"}[field]
    if name and tail[len(name):].strip() and not any(token in tail[len(name):] for token in ("请求", "已加", "已发")):
        result["issues"].append("状态标记还有未解析内容")
    return result


def preview_workbook(content: bytes, db):
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "文件超过 10 MB")
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise HTTPException(422, "无法读取 Excel 工作簿") from exc
    sheet = workbook.active
    iterator = sheet.values
    headings = tuple(cell(value) for value in next(iterator, ()))
    if headings[:13] != HEADERS:
        raise HTTPException(422, "表头与资源开拓统筹模板不一致，请检查前 13 列")

    options = list(db.query(DevelopmentOption).all())
    platforms = {item.name.casefold(): item.name for item in options if item.kind == "platform"}
    accounts = {item.name.casefold(): item.name for item in options if item.kind == "account"}
    users = list(db.query(AppUser).all())
    user_names = {item.full_name or item.username: item for item in users}
    user_names.update({short: user_names[full] for short, full in OWNER_ALIASES.items() if full in user_names})
    languages = {item.label for item in db.query(InterpretationLanguage).filter_by(is_active=True).all()}
    existing = list(db.query(DevelopmentRecord).all())
    historical = defaultdict(list)
    loose = defaultdict(list)
    for record in existing:
        loose[(record.work_date.isoformat(), record.full_name.strip().casefold(), str(record.owner_id))].append(record)
        values = source_values(record)
        if values:
            historical[key(values)].append(record)

    rows = []
    for number, raw in enumerate(iterator, 2):
        if not any(value is not None and cell(value) for value in raw[:13]):
            continue
        if len(rows) >= 10000:
            raise HTTPException(422, "最多预览 10000 条有效行")
        values = dict(zip(HEADERS, (cell(value) for value in raw[:13])))
        day = parse_date(values["日期"])
        owner_name = OWNER_ALIASES.get(values["开拓人/HR"], values["开拓人/HR"])
        owner = user_names.get(owner_name)
        platform_raw = values["来源"]
        platform_name = PLATFORM_ALIASES.get(platform_raw.casefold(), platform_raw)
        platform = platforms.get(platform_name.casefold())
        account_raw = values["对接账号"]
        account_name = re.sub(r"(?i)^hr([3456789])(?:微信|企微)?$", lambda match: "HR" + match.group(1) + ("企微" if "企微" in account_raw else "微信"), account_raw)
        account = accounts.get(account_name.casefold()) or accounts.get(re.sub(r"微信$", "", account_name).casefold())
        language = values["语种"]
        matched_languages, unmatched_languages = match_languages(language, languages)
        issues = []
        if not day:
            issues.append("日期无效")
        if not values["姓名"] or values["姓名"].casefold() in {"xx", "未知", "无"}:
            issues.append("姓名缺失或为占位值")
        if not owner:
            issues.append("开拓人未匹配")
        elif not owner.is_active:
            issues.append("开拓人已停用")
        if not platform:
            issues.append("来源平台未匹配")
        if account_raw and not account:
            issues.append("对接账号未匹配")
        if unmatched_languages:
            issues.append("语种需核对：" + "、".join(unmatched_languages))
        contacts = values["备注：微信号/手机号"]
        contact_mapping = classify_contact(contacts)
        if contacts and ("/" in contacts or "、" in contacts or "，" in contacts):
            issues.append("联系方式可能包含多个值")
        if contact_mapping["kind"] in {"third_party", "other_channel", "wechat_display_name", "email_other", "person_name", "ambiguous_numeric", "unclassified", "xiaohongshu_ambiguous"}:
            issues.append("联系方式仅保留原文或需核对")
        actions = [action_preview(values[name], name, day, user_names) for name in ACTION_CHANNELS if values[name]]
        for action in actions:
            issues.extend(f"{action['field']}：{issue}" for issue in action["issues"])
        state_count = len(actions)
        matches = historical.get(key(values), [])
        changed = []
        if len(matches) > 1:
            issues.append("历史记录匹配不唯一")
        elif matches:
            old = source_values(matches[0]) or {}
            changed = [name for name in STATE_FIELDS if cell(old.get(name)) != values[name]]
            if changed:
                issues.append("已导入记录的状态或跟进有变化：" + "、".join(changed))
        elif day and owner:
            candidates = loose.get((day, values["姓名"].casefold(), str(owner.id)), [])
            if candidates:
                issues.append("同日同开拓人同姓名已有记录，需核对是否同一条")
        rows.append({"row": number, "values": values, "work_date": day, "owner": owner_name, "platform": platform or platform_name,
                     "account": account or account_name, "languages": matched_languages, "unmatched_languages": unmatched_languages, "status_cells": state_count,
                     "contact_mapping": contact_mapping, "existing_ids": [str(item.id) for item in matches], "changed_fields": changed, "actions": actions, "issues": issues})
    workbook.close()

    counts = Counter(key(row["values"]) for row in rows)
    for row in rows:
        if counts[key(row["values"])] > 1:
            row["issues"].append("本文件内候选键重复")
        row["decision"] = ("已存在有变化" if row["changed_fields"] else "已存在") if len(row["existing_ids"]) == 1 and counts[key(row["values"])] == 1 else "待核对" if row["issues"] else "可追加候选"
    summary = Counter(row["decision"] for row in rows)
    issue_counts = Counter((issue.split("：", 1)[1] if issue.split("：", 1)[0] in ACTION_CHANNELS else issue.split("：", 1)[0])
                           for row in rows for issue in row["issues"])
    matched_ids = {item for row in rows for item in row["existing_ids"]}
    old_not_in_file = sum(str(record.id) not in matched_ids for record in existing if source_values(record))
    return {"sheet": sheet.title, "total": len(rows), "summary": dict(summary), "issues": dict(issue_counts), "old_not_in_file": old_not_in_file, "rows": rows,
            "note": "只读预览。联系方式按手机号、微信号、小红书号分类；无法确认属于本人联系方式的原文保留待核。候选键不能证明身份相同；状态列的日期和操作人需逐项核对。"}
