"""历史人才备注解析规则。纯函数，无数据库连接，不发送个人资料。"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import re
import unicodedata
from uuid import NAMESPACE_URL, uuid5

VERSION = "talent-remarks-v1"
EMPTY = {"", "-", "无", "暂无", "未提供", "没说", "不详", "未知", "n/a", "none", "null", "(空)", "（空）", "cv中没有提供"}
CONTACT_FIELDS = ("contact_info", "primary_phone", "secondary_phone", "primary_email", "secondary_email", "other_contact", "wechat", "whatsapp", "skype", "line")
EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
PHONE = re.compile(r"(?<!\w)\+?\d[\d ()-]{5,24}\d(?!\w)")

TEXT_MAP = {
    "中文姓名": "chinese_name", "英文姓名": "english_name", "昵称": "nickname",
    "国籍": "nationality", "民族": "ethnicity", "性别": "gender",
    "所在地": "residence_address", "目前所在地": "residence_address", "现居地": "residence_address",
    "目前居住地": "residence_address", "居住地址": "residence_address",
    "主要成长地": "native_place", "成长地": "native_place", "祖籍": "ancestral_home",
    "来源": "registration_source", "简历路径": "resume_path", "简历链接": "resume_path",
    "所在微信": "wechat_account", "所在微信群": "wechat_groups",
    "身高": "height", "外貌": "appearance", "出生日期": "birth_date", "出生年月": "birth_year_month",
    "年龄": "reported_age", "最高学历": "highest_education", "最后学历": "highest_education",
    "职业状态": "employment_status", "职业情况": "employment_detail",
    "标注项目经验": "annotation_experience", "具体标注项目经验": "annotation_experience",
    "笔译经验": "translation_experience", "笔译项目经验": "translation_experience",
    "口译经验": "interpretation_experience", "口译项目经验": "interpretation_experience",
    "其他经验": "other_experience", "入学年份": "enrollment_year", "学制": "program_duration_years",
}
CONTACT_MAP = {"邮箱": "email", "电子邮箱": "email", "备用邮箱": "email", "手机": "phone", "手机号": "phone", "电话": "phone", "手机号码": "phone", "微信": "wechat", "微信号": "wechat", "WhatsApp": "whatsapp", "Skype": "skype", "Line": "line"}
LANGUAGE_MAP = {"母语": ("native", 0), "第一外语": ("foreign", 1), "其他外语": ("foreign", 0), "其它外语": ("foreign", 0), "所学外语": ("foreign", 0), "外语": ("foreign", 0), "方言/少数民族语": ("dialect_ethnic", 0), "中国方言/民族语言": ("dialect_ethnic", 0)}
EDUCATION_MAP = {"毕业院校": "institution", "院校": "institution", "所学专业": "major", "专业": "major", "毕业年份": "graduation_year", "辅修专业": "minor_major", "学位名称": "degree_name"}
CERT_KEYS = {"证书及等级", "具体证书&级别", "具体证书及级别", "证书名称"}
IDENTITY_KEYS = {"姓名", "译员名字", "人才姓名"}
LEVELS = {"高中及以下": "high_school_or_below", "高中": "high_school_or_below", "中专": "secondary_vocational", "中专/职高": "secondary_vocational", "专科": "associate", "大专": "associate", "本科": "bachelor", "学士": "bachelor", "硕士": "master", "硕士研究生": "master", "博士": "doctor", "博士研究生": "doctor", "bachelor": "bachelor", "bachelor's degree": "bachelor", "master": "master", "master's degree": "master", "phd": "doctor", "doctor": "doctor"}
EMPLOYMENT = {"学生": "student", "在校学生": "student", "在职": "employed", "有全职工作": "employed", "自由职业": "freelance", "待业": "seeking", "退休": "retired"}
ALIASES = {"阿语": "阿拉伯语", "西语": "西班牙语", "葡语": "葡萄牙语", "意语": "意大利语", "英文": "英语", "法文": "法语", "德文": "德语", "日文": "日语", "缅语": "缅甸语", "印尼语": "印度尼西亚语", "粤语": "粤语", "国语": "普通话"}
ALIASES.update({
    "English": "英语", "French": "法语", "German": "德语", "Spanish": "西班牙语",
    "Portuguese": "葡萄牙语", "Arabic": "阿拉伯语", "Japanese": "日语", "Korean": "韩语",
    "Chinese": "中文", "汉语": "中文", "Mandarin": "普通话", "Cantonese": "粤语",
    "Hokkien": "闽南语", "Hakka": "客家话", "Russian": "俄语", "Thai": "泰语",
    "Burmese": "缅甸语", "Indonesian": "印度尼西亚语", "Malay": "马来语",
    "Persian": "波斯语", "Farsi": "波斯语", "Bengali": "孟加拉语", "Hindi": "印地语",
    "Urdu": "乌尔都语", "Swahili": "斯瓦希里语", "斯瓦西里语": "斯瓦希里语",
    "库尔迪什语": "库尔德语", "信德": "信德语", "旁遮普": "旁遮普语",
    "卢旺达语": "基尼阿万达语（卢旺达语）", "Tagalog": "菲律宾语", "他加禄语": "菲律宾语",
    "朝鲜语": "韩语", "白话": "粤语", "广东话": "粤语",
})
PROFICIENCY = {"非常熟悉": "very_familiar", "熟悉": "familiar", "基本掌握": "basic", "主要能听": "listening_mainly", "只能听": "listening_only"}
PRESERVE_KEYS = {"单价", "预期价格", "项目评价", "备注", "联系进度（原表状态）", "是否已做测试", "合作情况", "年龄段", "语言对", "语种", "标注经验", "有无标注项目经验", "证书水平", "有无对应语种证书", "有无外语证书", "方言熟练程度", "方言熟悉程度", "身份", "户籍省份", "户籍市"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def norm(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).casefold()


def empty(value):
    return value is None or isinstance(value, str) and value.strip().casefold() in EMPTY


def vacant(value):
    """目标字段只有 NULL 和空白视为空；已有占位文字也不静默覆盖。"""
    return value is None or isinstance(value, str) and not value.strip()


def key_label(value):
    value = value.strip().strip("* ")
    return value[2:] if value.startswith("原表") else value


def split_values(value):
    """仅在括号外分隔，避免拆开地区变体及英语复合名称。"""
    out, buffer, depth = [], [], 0
    for char in value:
        if char in "(（[【": depth += 1
        if char in ")）]】": depth = max(0, depth - 1)
        if depth == 0 and char in "、,，/＋+;；\n":
            if "".join(buffer).strip(): out.append("".join(buffer).strip())
            buffer = []
        else: buffer.append(char)
    if "".join(buffer).strip(): out.append("".join(buffer).strip())
    return out


class Languages:
    def __init__(self, catalog, aliases):
        self.ids = {str(x["id"]): x for x in catalog if x.get("is_active", True)}
        self.names = defaultdict(set)
        self.labels = {}
        for identifier, row in self.ids.items():
            self.labels[norm(row["label"])] = identifier
            for field in ("label", "name_zh", "name_en", "short_name_zh", "short_name_en"):
                if row.get(field): self.names[norm(row[field])].add(identifier)
        for row in aliases:
            if row.get("is_active", True) and str(row["language_id"]) in self.ids:
                self.names[norm(row["alias"])].add(str(row["language_id"]))
        for alias, label in ALIASES.items():
            if norm(label) in self.labels:
                self.names[norm(alias)] = {self.labels[norm(label)]}

    def resolve(self, value):
        if re.search(r"[?？]|不确定|没说|团队|所有|待核|瑞士语|海地语|皮钦语", value):
            return None
        # 目录中的通用正式名称优先，防止同义别名误选地区变体。
        if norm(value) in self.labels: return self.labels[norm(value)]
        found = self.names.get(norm(value), set())
        if len(found) == 1: return next(iter(found))
        # 中国方言旧表使用“方言-地区”格式，地区仍完整留在原备注中。
        if "-" in value:
            prefix, region = value.split("-", 1)
            identifier = self.labels.get(norm(prefix))
            if identifier and region.strip() and self.ids[identifier].get("language_type") in {"dialect", "ethnic"}:
                return identifier
        match = re.fullmatch(r"(.+?)\s*[（(]([^()（）]+)[)）]", value)
        if match:
            a, b = self.names.get(norm(match[1]), set()), self.names.get(norm(match[2]), set())
            if len(a) == 1 and a == b: return next(iter(a))
        return None


def source_identity_matches(value, known_names, languages=None, original=None):
    candidate = norm(value)
    if candidate in known_names: return True
    if not languages or norm(original) != candidate: return False
    # 老通讯录名称格式为“任务标签 + 姓名 + 任务标签（地区）”。
    # 只接受已有完整姓名及目录/固定任务词组成的剩余文本，不做姓名模糊匹配。
    bare = re.sub(r"\([^()]*\)$", "", candidate)
    words = set(languages.names) | {norm(k) for k in ALIASES} | {"质检", "专检", "标注", "采集", "转写", "比对", "排版", "实习生", "笔译", "口译", "译员", "翻译", "兼职", "港繁", "台繁", "中英"}
    words = {w for w in words if len(w) >= 2}
    def segments(text):
        reachable = {0}
        for i in range(len(text)+1):
            if i in reachable:
                for word in words:
                    if text.startswith(word, i): reachable.add(i+len(word))
                if i < len(text) and text[i] in "-_/·、": reachable.add(i+1)
        return len(text) in reachable
    for name in sorted(known_names, key=len, reverse=True):
        start = bare.find(name)
        if name and start >= 0 and segments(bare[:start]) and segments(bare[start+len(name):]): return True
    return False


def extract(person, languages=None):
    """返回带来源的候选；历史 previous_values 与操作人账号从不作为当前值。"""
    note = person.get("remarks") or ""
    entries, pending, spans = [], [], []
    known_names = {norm(person.get(k)) for k in ("full_name", "chinese_name", "english_name", "nickname") if person.get(k)} | {norm(x) for x in person.get("other_names") or []}
    decoder = json.JSONDecoder()
    cursor = 0
    while cursor < len(note):
        start = note.find("{", cursor)
        if start < 0: break
        try: obj, size = decoder.raw_decode(note[start:])
        except ValueError:
            cursor = start + 1
            continue
        end = start + size
        spans.append((start, end, obj))
        cursor = end
        if not isinstance(obj, dict): continue
        if "sources" in obj:
            # JSON 客户通讯录必须有明确姓名对应，不能依靠批次归属推断人员。
            for i, source in enumerate(obj.get("sources") or []):
                if not isinstance(source, dict): continue
                source_name = source.get("客户名称") or source.get("姓名")
                if not source_name or not source_identity_matches(source_name, known_names, languages, obj.get("original_names")):
                    pending.append({"key": "sources", "reason": "来源姓名无法对应当前人才", "source": f"json@{start}.sources[{i}]"})
                    continue
                for label in ("来源", "手机", "电话", "邮箱", "地址", "职务"):
                    if not empty(source.get(label)):
                        historical = []
                        for update in obj.get("incremental_updates") or []:
                            if not isinstance(update, dict): continue
                            for change in update.get("source_changes") or []:
                                if not isinstance(change, dict): continue
                                historical.extend((change.get(k) or {}).get(label) for k in ("previous_values", "values") if isinstance(change.get(k), dict))
                            for newer in update.get("sources") or []:
                                if isinstance(newer, dict): historical.append(newer.get(label))
                        if any(not empty(v) and norm(v) != norm(source[label]) for v in historical):
                            pending.append({"key": label, "value": str(source[label]), "reason": "该来源字段存在历史差异，不能采用旧快照", "source": f"json@{start}.sources[{i}].{label}"})
                            continue
                        target = {"地址": "原通讯录地址（用途待核）", "职务": "职业情况"}.get(label, label)
                        entries.append({"key": target, "value": str(source[label]), "source": f"json@{start}.sources[{i}].{label}", "json_span": [start, end], "json_path": ["sources", i, label]})
            # 增量包含旧值和来源差异，仅供人工审核，不覆盖 sources 已确认值。
            if obj.get("incremental_updates"):
                pending.append({"key": "incremental_updates", "reason": "历史增量需核对时间与当前归属", "source": f"json@{start}"})
        elif any(key_label(k) in TEXT_MAP or key_label(k) in CONTACT_MAP for k in obj):
            # 外部表原始行 JSON 只有明确姓名匹配才承接，操作人字段不映射。
            name = obj.get("姓名") or obj.get("译员名字")
            if name and norm(name) in known_names:
                for k, v in obj.items():
                    if not empty(v) and isinstance(v, (str, int)):
                        entries.append({"key": key_label(k), "value": str(v), "source": f"json@{start}.{k}", "json_span": [start, end], "json_path": [k]})
            else: pending.append({"key": "原始行JSON", "reason": "身份归属待核", "source": f"json@{start}"})
    # JSON 原始范围用等长空格屏蔽，使文本位置仍对应原备注。
    plain = list(note)
    for start, end, _ in spans:
        for i in range(start, end):
            if plain[i] not in "\r\n": plain[i] = " "
    plain = "".join(plain)
    matches = list(re.finditer(r"(?m)^[ \t]*(?:\*\*)?([^\n:：{}]{1,40}?)(?:\*\*)?[：:][ \t]*", plain))
    source, section = "备注", []
    def flush():
        names = [e["value"].strip() for e in section if e["key"] in IDENTITY_KEYS and not empty(e["value"])]
        conflicting = any(norm(name) not in known_names for name in names)
        for e in section:
            if conflicting:
                pending.append({**e, "reason": "当前来源段姓名与档案不一致"})
            else: entries.append(e)
        section.clear()
    for i, match in enumerate(matches):
        key = key_label(match[1])
        stop = matches[i+1].start() if i+1 < len(matches) else len(note)
        raw_value = plain[match.end():stop].rstrip()
        value = raw_value
        # 来源说明、批次边界不进入上一个字段值。
        boundary = re.search(r"(?m)^\s*(?:【|\[|原始资料[：:]|外部表[：:])", value)
        if boundary: value = value[:boundary.start()].rstrip()
        provenance = re.search(r"\s*【(?:原表|本表)?第[\d\s,，、]+行】\s*$", value)
        row_source = provenance[0].strip() if provenance else None
        if provenance: value = value[:provenance.start()].rstrip()
        if key in {"外部表", "原表", "原始资料", "本地批量导入", "合并来源"}:
            flush(); source = value
            continue
        section.append({"key": key, "value": value, "raw_value": raw_value, "row_source": row_source, "source": source, "start": match.end(), "end": match.end()+len(value)})
    flush()
    return entries, pending, spans


def normalize_field(field, value):
    value = value.strip()
    if field == "gender":
        return {"男": "男", "女": "女", "male": "男", "female": "女"}.get(value.casefold())
    if field == "highest_education": return LEVELS.get(value.casefold().replace("’", "'"))
    if field == "employment_status": return EMPLOYMENT.get(value)
    if field == "wechat_account" and re.search(r"找不到|未找到|不确定|不知道|未确定|待核|未提供|暂无", value): return None
    if field in {"reported_age", "enrollment_year", "program_duration_years"}:
        m = re.fullmatch(r"(\d{1,4})\s*(?:岁|年)?", value)
        if not m: return None
        n = int(m[1]); bounds = {"reported_age": (0, 120), "enrollment_year": (1900, 2200), "program_duration_years": (1, 15)}[field]
        return n if bounds[0] <= n <= bounds[1] else None
    if field in {"birth_date", "birth_year_month"}:
        from datetime import date
        m = re.fullmatch(r"(\d{4})[-/年](\d{1,2})(?:[-/月](\d{1,2})日?)?月?", value)
        if not m: return None
        try: d = date(int(m[1]), int(m[2]), int(m[3] or 1))
        except ValueError: return None
        if field == "birth_date" and not m[3]: return None
        if field == "birth_year_month" and m[3]: return None
        return d.isoformat() if field == "birth_date" else d.strftime("%Y-%m")
    if field == "resume_path" and not (value.startswith(("\\\\", "http://", "https://")) or re.match(r"^[A-Za-z]:[\\/]", value)):
        return None
    if field in {"nationality", "ethnicity", "residence_address", "native_place", "ancestral_home"} and re.search(r"[?？]|不确定|待核|可能|现居.*原籍", value): return None
    return value


def certificate_key(value):
    key = norm(value).replace("-", "")
    for pattern, label in [(r"(?:cet6|(?:大学)?英语六级)", "cet6"), (r"(?:cet4|(?:大学)?英语四级)", "cet4"), (r"(?:tem8|英语专业八级|专八)", "tem8"), (r"(?:tem4|英语专业四级|专四)", "tem4"), (r"(?:jlpt|日语能力考试|日语)?n([1-5])", "jlpt")]:
        match = re.search(pattern, key)
        if match: return label + (match[1] if label == "jlpt" else "")
    return key


def proficiency_value(value):
    if value in PROFICIENCY: return PROFICIENCY[value]
    compact = norm(value).replace("，", ",").replace(",", "")
    # 沿用已确认问卷的四类原始选项，不从“从小使用”推断母语角色。
    for prefix, result in [("非常熟练", "very_familiar"), ("一般(基本沟通无问题)", "familiar"), ("能听只能讲些很普通的", "listening_mainly"), ("只会听不会讲", "listening_only")]:
        if compact.startswith(prefix): return result
    return None


def same_source(a, b):
    if a.get("source") != b.get("source"): return False
    ar, br = a.get("row_source"), b.get("row_source")
    if not ar and not br: return True
    if not ar or not br: return False
    return bool(set(re.findall(r"\d+", ar)) & set(re.findall(r"\d+", br)))


def replace_contacts(note, tokens, spans):
    """只替换已被保护字段承接的值；JSON 字符串重新编码，结构不变。"""
    tokens = sorted(set(tokens), key=len, reverse=True)
    if not tokens: return note
    def redact(value, parent_key=None):
        if isinstance(value, str):
            for token in tokens:
                # 不误替换较长账号中的短片段，也不更改 JSON 键名。
                value = re.sub(r"(?<![A-Za-z0-9_@.+-])" + re.escape(token) + r"(?![A-Za-z0-9_@.+-])", "（已转入联系字段）", value)
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            phone_key = CONTACT_MAP.get(key_label(str(parent_key))) == "phone" or parent_key in {"excess_phones", "primary_phone", "secondary_phone", "phone"}
            integer = str(int(value)) if isinstance(value, int) or value.is_integer() else str(value)
            if phone_key and (str(value) in tokens or integer in tokens): return "（已转入联系字段）"
        if isinstance(value, list): return [redact(v, parent_key) for v in value]
        if isinstance(value, dict): return {k: redact(v, k) for k, v in value.items()}
        return value
    result, cursor = [], 0
    for start, end, obj in spans:
        result.append(redact(note[cursor:start]))
        redacted = redact(obj)
        result.append(json.dumps(redacted, ensure_ascii=False) if redacted != obj else note[start:end])
        cursor = end
    result.append(redact(note[cursor:]))
    return "".join(result)


def plan_person(person, relations, languages, limits):
    entries, pending, spans = extract(person, languages)
    changes, adds, updates, decisions = {}, [], [], []
    candidates = defaultdict(list)
    contacts = defaultdict(list)
    def decision(entry, status, reason, field=None, value=None):
        decisions.append({**entry, "status": status, "reason": reason, "field": field, "normalized": value})
    for e in pending: decision(e, "pending", e["reason"])
    for e in entries:
        k, value = e["key"], e["value"]
        if empty(value): decision(e, "satisfied", "原值为空或缺失占位符"); continue
        if k in TEXT_MAP:
            field = TEXT_MAP[k]; normalized = normalize_field(field, value)
            if normalized is None: decision(e, "pending", "格式或语义不能明确标准化", field); continue
            if field in limits and len(str(normalized)) > limits[field]:
                decision(e, "pending", "超出字段长度，不截断", field); continue
            candidates[field].append((e, normalized))
        elif k in CONTACT_MAP:
            kind = CONTACT_MAP[k]
            if value.strip() == "（已转入联系字段）":
                decision(e, "satisfied", "此前批次已转存联系方式", kind)
                continue
            if kind == "email": values = EMAIL.findall(value)
            elif kind == "phone": values = [x.strip() for x in PHONE.findall(value) if 7 <= len(re.sub(r"\D", "", x)) <= 15]
            else: values = [value.strip()] if re.fullmatch(r"[A-Za-z0-9_.+@-]{3,100}", value.strip()) else []
            if not values: decision(e, "pending", "无有效联系方式", kind)
            for token in values: contacts[kind].append((e, token))
        elif k in LANGUAGE_MAP or k in EDUCATION_MAP or k in CERT_KEYS:
            continue
        elif k in IDENTITY_KEYS: decision(e, "satisfied", "身份核对信息，不改主姓名")
        elif k in PRESERVE_KEYS: decision(e, "preserved", "按导入规范保留原始语义")
        else: decision(e, "unmapped", "无明确承接规则，保留原文")
    for field, rows in candidates.items():
        values = {canonical(v): v for _, v in rows}
        if len(values) != 1:
            for e, v in rows: decision(e, "pending", "同字段多来源值冲突", field, v)
            continue
        value = next(iter(values.values()))
        current = person.get(field)
        if vacant(current):
            # 不用出生或年龄覆盖另一已有出生依据；不制造不完整学生资料。
            if field in {"birth_date", "birth_year_month"} and (person.get("birth_date") or person.get("birth_year_month")):
                status, reason = "pending", "已有出生依据需核对"
            elif field == "enrollment_year" and not (person.get("program_duration_years") or "program_duration_years" in candidates):
                status, reason = "pending", "缺少学制"
            else: changes[field] = value; status, reason = "filled", "补充空值"
        elif norm(current) == norm(value): status, reason = "satisfied", "已有相同值"
        else: status, reason = "pending", "已有非空值，保留现值"
        for e, v in rows: decision(e, status, reason, field, v)
    # 所有账号在受保护字段中统一查重，不能覆盖现有主/备用字段。
    contact_text = "\n".join(str(person.get(f) or "") for f in CONTACT_FIELDS)
    redaction_tokens = []
    for kind, rows in contacts.items():
        values = {}
        for e, token in rows: values.setdefault(norm(token), []).append((e, token))
        for normalized, group in values.items():
            token = group[0][1]
            known = EMAIL.findall(contact_text) if kind == "email" else PHONE.findall(contact_text) if kind == "phone" else [person.get(kind)]
            known_keys = {norm(v) if kind != "phone" else re.sub(r"\D", "", str(v)) for v in known if v}
            lookup = normalized if kind != "phone" else re.sub(r"\D", "", token)
            if lookup in known_keys: status, reason, field = "satisfied", "联系字段已承接", kind
            else:
                fields = {"email": ["primary_email", "secondary_email"], "phone": ["primary_phone", "secondary_phone"]}.get(kind, [kind])
                field = next((f for f in fields if vacant(person.get(f)) and f not in changes), None)
                if field is None and kind in {"email", "phone"}:
                    # 溢出联系方式仅补空的其他联系方式字段，不追加到非空字段。
                    field = "other_contact" if vacant(person.get("other_contact")) else None
                    if field:
                        merged = (changes.get(field, "") + ("\n" if changes.get(field) else "") + token)
                        if len(merged) <= limits.get(field, 255): changes[field] = merged
                        else: field = None
                elif field and len(token) <= limits.get(field, 255): changes[field] = token.lower() if kind == "email" else token
                else: field = None
                if field: status, reason = "filled", "补充空联系字段"
                else: status, reason = "pending", "联系字段已占用或容量不足"
            if status in {"filled", "satisfied"}: redaction_tokens.extend(v for _, v in group)
            for e, token in group: decision(e, status, reason, field, token)
    current_skills = relations.get("resource_language_skill", [])
    requested = defaultdict(list)
    for e in entries:
        if e["key"] not in LANGUAGE_MAP or empty(e["value"]): continue
        role, priority = LANGUAGE_MAP[e["key"]]
        for token in split_values(e["value"]):
            identifier = languages.resolve(token)
            if identifier: requested[identifier].append((e, token, role, priority))
            else: decision(e, "pending", "语种目录匹配不唯一或语义含糊", "language_skills", token)
    for identifier, rows in requested.items():
        roles = {r[2] for r in rows}
        existing = [x for x in current_skills if str(x["language_id"]) == identifier]
        effective = roles - {"dialect_ethnic"} or {"dialect_ethnic"}
        if len(effective) > 1 or (effective != {"dialect_ethnic"} and any(x["role"] not in effective for x in existing)):
            for e, token, _, _ in rows: decision(e, "pending", "同语种语言角色冲突", "language_skills", token)
            continue
        role = next(iter(effective))
        priority = next((r[3] for r in rows if r[2] == role), rows[0][3])
        proficiency_entries = [p for p in entries if p["key"] in {"方言熟悉程度", "方言熟练程度"} and not empty(p["value"]) and any(r[2] == "dialect_ethnic" and same_source(r[0], p) for r in rows)]
        proficiency = None
        if proficiency_entries:
            choices = {proficiency_value(p["value"]) for p in proficiency_entries}
            if len(choices) == 1 and None not in choices: proficiency = next(iter(choices))
            else:
                for p in proficiency_entries: decision(p, "pending", "熟悉程度不明确或多来源冲突", "language_proficiency")
        if existing: status, reason = "satisfied", "已有语种与角色关联"
        else:
            values = {"language_id": identifier, "role": role, "priority": priority, "sort_order": len(current_skills)+len([a for a in adds if a["table"] == "resource_language_skill"]), "proficiency": proficiency, "remarks": "历史备注规范化；原文继续留存在人才备注"}
            adds.append({"table": "resource_language_skill", "values": values})
            status, reason = "filled", "补充明确语言关联"
        for e, token, _, _ in rows: decision(e, status, reason, "language_skills", token)
        if proficiency:
            if not existing: proficiency_status, proficiency_reason = "filled", "随新增语言承接明确熟悉程度"
            elif len(existing) == 1 and vacant(existing[0].get("proficiency")):
                updates.append({"table": "resource_language_skill", "id": str(existing[0]["id"]), "changes": {"proficiency": proficiency}})
                proficiency_status, proficiency_reason = "filled", "补充已有语言的空熟悉程度"
            elif len(existing) == 1 and existing[0].get("proficiency") == proficiency:
                proficiency_status, proficiency_reason = "satisfied", "已有相同熟悉程度"
            else: proficiency_status, proficiency_reason = "pending", "已有熟悉程度或语言记录不能唯一对应"
            for p in proficiency_entries: decision(p, proficiency_status, proficiency_reason, "language_proficiency", proficiency)
    # 教育只在最高学历明确且属于教育经历支持范围时创建，不把学校名推断为学历。
    education_values = defaultdict(list)
    for e in entries:
        if e["key"] in EDUCATION_MAP and not empty(e["value"]): education_values[EDUCATION_MAP[e["key"]]].append(e)
    level = changes.get("highest_education", person.get("highest_education"))
    wanted = {"education_level": level}
    education_entries = []
    ambiguous = False
    # 新来源学历与已存最高学历冲突时，不能把该来源学校归到已存学历层次。
    if any(normalize_field("highest_education", e["value"]) != level for e in entries if TEXT_MAP.get(e["key"]) == "highest_education" and not empty(e["value"])):
        ambiguous = True
    for field, es in education_values.items():
        education_entries.extend(es)
        if len({norm(e["value"]) for e in es}) != 1: ambiguous = True; continue
        value = es[0]["value"].strip()
        if field == "graduation_year":
            if not re.fullmatch(r"(?:19|20|21)\d{2}", value): ambiguous = True; continue
            value = int(value)
        elif len(value) > 255: ambiguous = True; continue
        wanted[field] = value
    if education_entries:
        existing = relations.get("resource_education_experience", [])
        matched = [x for x in existing if x["education_level"] == level and wanted.get("institution") and norm(x.get("institution")) == norm(wanted["institution"])]
        if not ambiguous and level in {"associate", "bachelor", "master", "doctor"} and (not existing or len(matched) == 1):
            if matched:
                row = matched[0]; patch = {}
                for field, value in wanted.items():
                    if vacant(row.get(field)): patch[field] = value
                    elif norm(row[field]) != norm(value): ambiguous = True
                if not ambiguous and patch: updates.append({"table": "resource_education_experience", "id": str(row["id"]), "changes": patch})
                status = "pending" if ambiguous else "filled" if patch else "satisfied"
            else:
                wanted["sort_order"] = 0
                adds.append({"table": "resource_education_experience", "values": wanted})
                status = "filled"
        else: status = "pending"
        for e in education_entries: decision(e, status, "教育信息明确承接" if status != "pending" else "学历、学校、来源或已有经历不能唯一对应", "education_experiences")
    for e in entries:
        if e["key"] not in CERT_KEYS or empty(e["value"]): continue
        for name in split_values(e["value"]):
            if name.casefold() in EMPTY: continue
            if len(name) > 255 or re.search(r"[?？]|没考|未考|没过|未过|未通过|没通过|不通过|无证|没有|待考|备考|计划|准备|不会", name):
                decision(e, "pending", "证书内容不能明确登记", "certificates", name); continue
            # 不把单独语言名、成绩数字或有/是当成取得证书。
            if not re.search(r"证|CET|TEM|CATTI|IELTS|TOEFL|雅思|托福|JLPT|TOPIK|HSK|DELE|DALF|N[1-5]|英语[四六]级", name, re.I):
                decision(e, "pending", "缺少明确证书名称", "certificates", name); continue
            existing = relations.get("resource_certificate", [])
            if any(certificate_key(x["name"]) == certificate_key(name) for x in existing) or any(a["table"] == "resource_certificate" and certificate_key(a["values"]["name"]) == certificate_key(name) for a in adds):
                decision(e, "satisfied", "已有相同证书", "certificates", name); continue
            certificate_type = "language" if re.search(r"英语|日语|外语|CET|TEM|CATTI|IELTS|TOEFL|雅思|托福|JLPT|TOPIK|HSK|DELE|DALF|N[1-5]", name, re.I) else "other"
            adds.append({"table": "resource_certificate", "values": {"certificate_type": certificate_type, "name": name, "material_received": False, "sort_order": len(existing)+len([a for a in adds if a["table"] == "resource_certificate"]), "remarks": "历史备注自报证书；未核验材料"}})
            decision(e, "filled", "补充明确自报证书", "certificates", name)
    note = replace_contacts(person.get("remarks") or "", redaction_tokens, spans)
    if note != (person.get("remarks") or ""): changes["remarks"] = note
    for item in adds:
        item["values"]["id"] = str(uuid5(NAMESPACE_URL, VERSION+":"+str(person["id"])+":"+item["table"]+":"+canonical(item["values"])))
        item["values"]["person_id"] = str(person["id"])
    return {"id": str(person["id"]), "resource_code": person.get("resource_code"), "before": {"person": person, "relations": relations}, "changes": changes, "adds": adds, "updates": updates, "decisions": decisions}
