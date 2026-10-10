"""同名核重：确定性比对、事务内归档和有条件撤销。"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import re
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import MetaData, Table, func, inspect, or_, select, text
from sqlalchemy.exc import NoInspectionAvailable, UnboundExecutionError
from sqlalchemy.orm import load_only, undefer
from sqlalchemy.orm.attributes import set_committed_value

from business_time import BUSINESS_TIMEZONE, business_iso, business_now
from resource_models import ResourcePerson
from resource_schemas import ResourcePersonDetailResponse, ResourcePersonUpdate
from talent_duplicate_models import TalentDuplicateOperation
from talent_privacy import RESOURCE_CONTACT_FIELDS, serialize_with_contact_access

SYSTEM_FIELDS = {"id", "person_id", "resource_code", "idempotency_key", "name_duplicate",
                 "archived_into_id", "archived_at", "created_at", "updated_at", "operated_by",
                 "operator_name", "operated_at", "duplicate_review_required", "wechat_accounts_revision",
                 "wechat_contact_state", "source", "sort_order"}
COLLECTIONS = ("capabilities", "education_experiences", "language_skills", "certificates", "annotation_language_skills")
PROFILES = ("written_profile", "interpretation_profile", "annotation_profile", "career_profile")
CONCAT_FIELDS = {"remarks", "overall_rating", "cooperation_note", "punctuality_note", "annotation_experience",
                 "interpretation_experience", "translation_experience", "other_experience",
                 "audio_annotation_evaluation", "non_audio_annotation_evaluation", "collection_evaluation",
                 "wechat_groups", "registration_source"}
FIELD_LABELS = {
    "full_name": "原姓名", "chinese_name": "中文姓名", "english_name": "英文姓名", "nickname": "昵称",
    "other_names": "其他名字", "primary_phone": "手机", "secondary_phone": "备用电话", "primary_email": "邮箱",
    "secondary_email": "备用邮箱", "contact_info": "兼容联系方式", "other_contact": "其他联系方式",
    "wechat": "个人微信", "whatsapp": "WhatsApp", "skype": "Skype", "line": "Line", "gender": "性别",
    "birth_date": "出生日期", "birth_year_month": "出生年月", "reported_age": "登记年龄", "nationality": "国籍",
    "ethnicity": "民族", "ancestral_home": "籍贯", "native_place": "主要成长地", "residence_address": "现居地",
    "registration_source": "来源", "wechat_account": "所在微信（公司账号）", "wechat_accounts": "所在微信（公司账号）",
    "wechat_groups": "所在微信群", "highest_education": "最高学历", "employment_status": "职业状态",
    "employment_detail": "职业说明", "remarks": "备注", "resume_path": "简历路径", "status": "档案状态",
    "cooperation_type": "合作形式", "capabilities": "专业能力", "education_experiences": "学历经历",
    "language_skills": "语言情况（类型／熟悉程度）", "certificates": "证书", "annotation_language_skills": "标注语言方向",
    "annotation_experience": "标注经验", "interpretation_experience": "口译经验", "translation_experience": "笔译经验",
    "other_experience": "其他经验", "overall_score": "总体评分", "overall_rating": "总体评价",
    "annotation_willingness": "标注意愿", "dialects": "方言", "dialect_regions": "方言地区",
    "cooperation_level": "配合度", "cooperation_note": "配合评价", "punctuality_level": "准时程度",
    "punctuality_note": "准时评价", "height": "身高", "appearance": "容貌", "first_contact_date": "首次联系",
    "student_stage": "学习阶段", "enrollment_year": "入学年份", "program_duration_years": "学制",
    "student_grade_override": "登记年级", "audio_annotation_score": "音频标注评分",
    "non_audio_annotation_score": "非音频标注评分", "collection_score": "采集评分",
    "audio_annotation_evaluation": "音频标注评价", "non_audio_annotation_evaluation": "非音频标注评价",
    "collection_evaluation": "采集评价",
}
PROFILE_LABELS = {"written_profile": "笔译", "interpretation_profile": "口译", "annotation_profile": "标注", "career_profile": "职业"}
SUB_LABELS = {"languages": "语种", "direction": "方向", "domain_skills": "领域", "quality_score": "质量评价",
              "default_priority": "优先级", "daily_accept_count": "每日接单数", "hourly_speed": "每小时速度",
              "daily_word_capacity": "每日字数", "can_cloud_edit": "云端编辑", "can_revision": "修订能力",
              "available_time_slot": "可用时间", "schedule_remarks": "排期说明", "availability_updated_at": "可用时间更新",
              "interpretation_level": "级别", "interpretation_modes": "形式", "evaluation_summary": "评价",
              "task_types": "任务类型", "data_modalities": "数据类型", "tools": "工具", "daily_capacity": "每日产能",
              "remarks": "备注", "industries": "行业", "functions": "职能", "job_titles": "岗位",
              "years_experience": "经验年数", "preferred_locations": "意向地点", "expected_salary": "期望薪资", "summary": "职业说明"}
PLACEHOLDERS = {"-", "无", "暂无", "未知", "没说", "未提供", "none", "null", "n/a", "cv中没有提供", "******"}
PUBLIC_COMPARE_FIELDS = {
    "full_name", "chinese_name", "english_name", "nickname", "other_names", "gender", "birth_date",
    "birth_year_month", "reported_age", "nationality", "ethnicity", "ancestral_home", "native_place",
    "residence_address", "highest_education", "employment_status", "status", "cooperation_type",
    "language_skills", "annotation_language_skills", "capabilities", "education_experiences", "certificates",
}


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError(type(value).__name__)


def plain(value):
    return json.loads(json.dumps(value, default=json_value, ensure_ascii=False))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=json_value,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def name_key(value):
    normalized = re.sub(r"\s+", " ", str(value or "")).strip()
    stripped = re.sub(r"(?:\s*[(（][^()（）]*[)）]\s*)+$", "", normalized).strip()
    return (stripped or normalized).lower()


def review_ready(db):
    """仅检查结构；不在服务启动或请求中执行迁移。每个会话只检查一次。"""
    if not hasattr(db, "info") or not hasattr(db, "get_bind"):
        return False
    if "talent_duplicate_ready" not in db.info:
        try:
            inspector = inspect(db.get_bind())
            columns = {row["name"] for row in inspector.get_columns("resource_person")}
            db.info["talent_duplicate_ready"] = {"archived_into_id", "archived_at"} <= columns and inspector.has_table("talent_duplicate_operation")
        except (NoInspectionAvailable, UnboundExecutionError):
            return False
    return db.info["talent_duplicate_ready"]


def require_ready(db):
    if not review_ready(db):
        raise HTTPException(503, "同名核重尚未启用：需要显式执行人才核重数据库迁移；当前仅支持只读比对")


def active_query(db, query):
    return query.filter(ResourcePerson.archived_into_id.is_(None)) if review_ready(db) else query


def archive_options(db):
    return (undefer(ResourcePerson.archived_into_id), undefer(ResourcePerson.archived_at)) if review_ready(db) else ()


def prepare_person(db, person):
    if person is not None and not review_ready(db):
        set_committed_value(person, "archived_into_id", None)
        set_committed_value(person, "archived_at", None)
    return person


def assert_writable(db, person):
    if review_ready(db) and person is not None and person.archived_into_id:
        raise HTTPException(409, {"message": "此档案已归档，请打开保留档案进行修改", "target_id": str(person.archived_into_id)})


def canonical_id(db, person_id):
    if not review_ready(db):
        return person_id
    row = db.query(ResourcePerson.archived_into_id).filter(ResourcePerson.id == person_id).first()
    return row[0] or person_id if row else person_id


def family_ids(db, person_id):
    if not review_ready(db):
        return [person_id]
    root = canonical_id(db, person_id)
    if root != person_id:
        return [person_id]  # 原归档档案仍展示自己的原业务历史。
    return [root, *[row[0] for row in db.query(ResourcePerson.id).filter(ResourcePerson.archived_into_id == root).all()]]


def contact_identifiers(person):
    """全部主备用联系方式交叉核对；保留国际区号，不猜测本地号码所属国家。"""
    result = {"email": set(), "phone": set(), "wechat": set(), "whatsapp": set(), "skype": set(), "line": set()}
    for field in RESOURCE_CONTACT_FIELDS:
        value = str(getattr(person, field, None) or "").strip()
        if value.lower() in PLACEHOLDERS or not value:
            continue
        result["email"].update(item.lower() for item in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", value))
        if field in {"primary_phone", "secondary_phone", "contact_info", "other_contact", "whatsapp"}:
            for item in re.findall(r"\+?\d[\d ()-]{5,}\d", value):
                digits = re.sub(r"\D", "", item)
                if 7 <= len(digits) <= 15:
                    result["phone"].add(digits)
        if field in {"wechat", "whatsapp", "skype", "line"}:
            result[field].add(value.lower())
    return result


def _columns(row):
    return plain({column.key: getattr(row, column.key) for column in row.__table__.columns if column.key != "name_duplicate"})


def person_snapshot(person):
    return {"person": _columns(person), **{key: sorted([_columns(item) for item in getattr(person, key)], key=lambda item: str(item.get("id", ""))) for key in (*COLLECTIONS, "attachments")},
            **{key: _columns(getattr(person, key)) if getattr(person, key) else None for key in PROFILES}}


def comparison_fingerprint(person):
    snap = person_snapshot(person)
    # 系统更新时间和同名触发器标记不是人工区分结论的身份依据。
    def clean(value):
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items() if key not in SYSTEM_FIELDS}
        if isinstance(value, list):
            return sorted((clean(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
        return value
    return digest(clean(snap))


def _references(db, identifiers):
    """沿真实外键收集业务记录与下游明细，撤销时检测任何关联变化。"""
    from resource_service import _OWNED_PERSON_TABLES
    inspector = inspect(db.get_bind())
    graph = []
    for table_name in inspector.get_table_names():
        if table_name in {"resource_person", "talent_duplicate_operation"}:
            continue
        for fk in inspector.get_foreign_keys(table_name):
            if len(fk.get("constrained_columns", [])) == 1:
                graph.append((table_name, fk["constrained_columns"][0], fk["referred_table"], fk["referred_columns"][0]))
    values = {("resource_person", "id"): set(identifiers)}
    gathered, metadata, processed = {}, MetaData(), {}
    while True:
        changed = False
        for table_name, column, parent, parent_column in graph:
            known = values.get((parent, parent_column), set())
            todo = known - processed.get((table_name, column), set())
            if not todo:
                continue
            processed.setdefault((table_name, column), set()).update(todo)
            table = Table(table_name, metadata, autoload_with=db.get_bind(), extend_existing=True)
            rows = db.execute(select(table).where(table.c[column].in_(list(todo)))).mappings().all()
            for row in rows:
                encoded = plain(dict(row))
                if table_name not in _OWNED_PERSON_TABLES:
                    gathered.setdefault(table_name, {})[digest(encoded)] = encoded
                for col in table.primary_key.columns:
                    values.setdefault((table_name, col.name), set()).add(row[col.name])
            changed |= bool(rows)
        if not changed:
            break
    return {key: sorted(rows.values(), key=digest) for key, rows in sorted(gathered.items())}


def full_snapshot(db, ids):
    from resource_service import get_talent
    people = {str(identifier): person_snapshot(get_talent(db, identifier)) for identifier in sorted(ids, key=str)}
    return {"people": people, "references": _references(db, ids)}


def _business_values(person):
    data = ResourcePersonDetailResponse.model_validate(person).model_dump(mode="json")
    result = {key: data.get(key) for key in ResourcePersonUpdate.model_fields
              if key not in SYSTEM_FIELDS and key not in {*COLLECTIONS, *PROFILES, "allow_duplicate"}}
    result.pop("wechat_account", None)  # 旧兼容字符串由公司账号公共能力生成。
    for profile in PROFILES:
        value = data.get(profile)
        if value:
            for key, item in value.items():
                if key not in SYSTEM_FIELDS:
                    result[f"{profile}.{key}"] = item
    for key in COLLECTIONS:
        result[key] = [{k: v for k, v in row.items() if k not in SYSTEM_FIELDS} for row in data.get(key, [])]
    return result


def field_label(key):
    if "." in key:
        section, field = key.split(".", 1)
        return f"{PROFILE_LABELS[section]}：{SUB_LABELS.get(field, field)}"
    return FIELD_LABELS.get(key, key)


def field_state(values):
    nonempty = [value for value in values if value is not None and value != "" and value != []]
    if not nonempty:
        return "missing"
    if len({digest(value) for value in nonempty}) > 1:
        return "conflict"
    return "same" if len(nonempty) == len(values) else "complement"


def pair_evidence(left, right):
    a, b = contact_identifiers(left), contact_identifiers(right)
    matches = [key for key in a if a[key] & b[key]]
    identity_conflicts = []
    if left.gender and right.gender and left.gender != right.gender:
        identity_conflicts.append("性别不同")
    a_birth = str(left.birth_year_month or left.birth_date or "")[:7]
    b_birth = str(right.birth_year_month or right.birth_date or "")[:7]
    if a_birth and b_birth and a_birth != b_birth:
        identity_conflicts.append("出生年月不同")
    values_a, values_b = _business_values(left), _business_values(right)
    complements = sum(field_state([values_a.get(key), values_b.get(key)]) == "complement" for key in values_a.keys() | values_b.keys())
    return {"person_ids": [str(left.id), str(right.id)], "contact_matches": matches,
            "identity_conflicts": identity_conflicts, "complement_count": complements,
            "category": "identity_conflict" if identity_conflicts else "contact_match" if matches else "complement" if complements else "name_only"}


def _pair_decisions(people, operations):
    fingerprints = {str(person.id): comparison_fingerprint(person) for person in people}
    states = {}
    for op in operations:
        if op.undone_at or op.action not in {"different", "defer"}:
            continue
        for a, b in itertools.combinations(sorted(op.person_ids), 2):
            if a not in fingerprints or b not in fingerprints:
                continue
            old = op.decisions.get("fingerprints", {})
            if old.get(a) == fingerprints[a] and old.get(b) == fingerprints[b]:
                states[(a, b)] = op.action
    return states


def _decision_query(db):
    return db.query(TalentDuplicateOperation).options(load_only(
        TalentDuplicateOperation.id, TalentDuplicateOperation.action, TalentDuplicateOperation.name_key,
        TalentDuplicateOperation.person_ids, TalentDuplicateOperation.decisions, TalentDuplicateOperation.created_at,
        TalentDuplicateOperation.undone_at,
    ))


def groups(db, keyword="", status="pending", skip=0, limit=20, contacts_visible=False):
    from resource_service import _person_options
    ready = review_ready(db)
    query = active_query(db, db.query(ResourcePerson))
    if ready and db.get_bind().dialect.name == "postgresql":
        normalized = func.resource_person_duplicate_name_key(ResourcePerson.full_name)
        duplicate_keys = active_query(db, db.query(normalized)).group_by(normalized).having(func.count(ResourcePerson.id) > 1)
        query = query.filter(normalized.in_(duplicate_keys))
    people = query.options(*_person_options(), *archive_options(db)).populate_existing().all()
    grouped = {}
    for person in people:
        prepare_person(db, person)
        key = name_key(person.full_name)
        if key:
            grouped.setdefault(key, []).append(person)
    operations = _decision_query(db).filter(TalentDuplicateOperation.name_key.in_(grouped)).order_by(TalentDuplicateOperation.created_at, TalentDuplicateOperation.id).all() if ready and grouped else []
    by_key = {}
    for operation in operations:
        by_key.setdefault(operation.name_key, []).append(operation)
    items = []
    counts = {"pending": 0, "different": 0, "deferred": 0}
    for key, members in grouped.items():
        if len(members) < 2:
            continue
        decisions = _pair_decisions(members, by_key.get(key, []))
        pairs = [tuple(sorted((str(a.id), str(b.id)))) for a, b in itertools.combinations(members, 2)]
        state = "pending" if any(pair not in decisions for pair in pairs) else "deferred" if "defer" in decisions.values() else "different"
        if keyword.strip().lower() and not any(keyword.strip().lower() in str(value or "").lower()
                                             for person in members for value in (person.full_name, person.resource_code)):
            continue
        counts[state] += 1
        if status != "all" and state != status:
            continue
        # 普通用户不返回联系方式匹配类型或相关排序，避免侧信道泄露。
        contact_match = contacts_visible and any(any(contact_identifiers(a)[kind] & contact_identifiers(b)[kind]
                                                    for kind in contact_identifiers(a)) for a, b in itertools.combinations(members, 2))
        comparison_values = [_business_values(person) for person in members]
        complement = any(field_state([value.get(field) for value in comparison_values]) == "complement"
                         for field in comparison_values[0]
                         if contacts_visible or field in PUBLIC_COMPARE_FIELDS)
        items.append({"key": key, "name": members[0].full_name, "count": len(members), "status": state,
                      "summary": "存在联系方式匹配，需结合身份核对" if contact_match else "资料存在互补，请逐条核对" if complement else "仅姓名相同，请核对身份",
                      "priority": 0 if contact_match else 1 if complement else 2})
    items.sort(key=lambda item: (item["priority"], -item["count"], item["key"]))
    return {"items": items[skip:skip + limit], "total": len(items), "counts": counts, "ready": ready}


def group_detail(db, key, contacts_visible=False):
    from resource_service import _person_options, get_talent_project_situations
    query = active_query(db, db.query(ResourcePerson))
    if review_ready(db) and db.get_bind().dialect.name == "postgresql":
        query = query.filter(func.resource_person_duplicate_name_key(ResourcePerson.full_name) == key)
    people = query.options(*_person_options(), *archive_options(db)).populate_existing().all()
    members = [prepare_person(db, person) for person in people if name_key(person.full_name) == key]
    if not members:
        raise HTTPException(404, "同名组已变化或不存在")
    situations = get_talent_project_situations(db, [person.id for person in members])
    members.sort(key=lambda p: (-situations.get(p.id, {}).get("total", 0), p.created_at, str(p.id)))
    values = [_business_values(person) for person in members]
    sensitive_tokens = set()
    if not contacts_visible:
        for person in members:
            for tokens in contact_identifiers(person).values():
                sensitive_tokens.update(token for token in tokens if len(token) > 2)
        sensitive_pattern = re.compile("|".join(re.escape(token) for token in sorted(sensitive_tokens, key=len, reverse=True)), re.I) if sensitive_tokens else None
    keys = list(dict.fromkeys(key for value in values for key in value))
    rows = []
    for field in keys:
        if not contacts_visible and field not in PUBLIC_COMPARE_FIELDS:
            continue
        cells = [value.get(field) for value in values]
        if not contacts_visible:
            def redact(value):
                if isinstance(value, dict):
                    return {k: redact(v) for k, v in value.items() if k not in {"remarks", "certificate_no"}}
                if isinstance(value, list):
                    return [redact(v) for v in value]
                if isinstance(value, str):
                    if sensitive_pattern:
                        value = sensitive_pattern.sub("******", value)
                    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "******", value)
                    return re.sub(r"\+?\d[\d ()-]{5,}\d", "******", value)
                return value
            cells = [redact(cell) for cell in cells]
        if field_state(cells) != "missing":
            rows.append({"key": field, "label": field_label(field), "state": field_state(cells), "values": cells})
    serialized = []
    for person in members:
        row = serialize_with_contact_access(person, ResourcePersonDetailResponse, RESOURCE_CONTACT_FIELDS, contacts_visible=contacts_visible)
        if not contacts_visible:
            # 原始备注/自由文本可能夹带联系方式；核重页面只返回白名单矩阵。
            row = {field: row.get(field) for field in ("id", "resource_code", "full_name", "gender", "nationality", "created_at")}
        row["project_situation"] = situations.get(person.id, {"total": 0})
        serialized.append(plain(row))
    decisions = _pair_decisions(members, _decision_query(db).filter_by(name_key=key).order_by(TalentDuplicateOperation.created_at).all()) if review_ready(db) else {}
    pairs = []
    for a, b in itertools.combinations(members, 2):
        evidence = pair_evidence(a, b) if contacts_visible else {"person_ids": [str(a.id), str(b.id)]}
        evidence["decision"] = decisions.get(tuple(sorted((str(a.id), str(b.id)))))
        pairs.append(evidence)
    return {"key": key, "members": serialized, "fields": rows, "pairs": pairs, "recommended_target_id": str(members[0].id),
            "ready": review_ready(db), "can_commit": contacts_visible and review_ready(db)}


def _collection_key(field, row):
    if field == "capabilities":
        return row["capability_type"]
    if field == "language_skills":
        return row["language_id"]  # 同语种不同母外语角色必须人工确认。
    if field == "annotation_language_skills":
        return digest([row["source_language_id"], row.get("target_language_id")])
    if field == "certificates":
        return digest([row["name"], row.get("issuer"), row.get("certificate_no")])
    return digest([row["education_level"], row.get("institution"), row.get("major"), row.get("graduation_year")])


def _merge_values(people, target, decisions):
    all_values = {str(person.id): _business_values(person) for person in people}
    target_values = all_values[str(target.id)]
    keys = list(dict.fromkeys(key for values in all_values.values() for key in values))
    result, fields, conflicts, used = copy.deepcopy(target_values), [], [], set()
    for key in keys:
        options = [{"person_id": identifier, "value": values.get(key)} for identifier, values in all_values.items()]
        nonempty = [row for row in options if row["value"] is not None and row["value"] != "" and row["value"] != []]
        decision = decisions.get(key)
        if key in COLLECTIONS:
            variants = {}
            for option in options:
                for value in option["value"] or []:
                    variants.setdefault(_collection_key(key, value), {})[digest(value)] = {"person_id": option["person_id"], "value": value}
            merged = []
            for identity, variants_by_hash in variants.items():
                choice_key = f"{key}:{identity}"
                variants_list = list(variants_by_hash.values())
                selected = decisions.get(choice_key)
                if selected:
                    used.add(choice_key)
                    choices = [item for item in variants_list if item["person_id"] == selected.get("person_id") and (not selected.get("value_hash") or digest(item["value"]) == selected["value_hash"])]
                    if len(choices) != 1:
                        raise HTTPException(422, "明细冲突的取值已变化，请重新选择")
                    chosen = choices[0]["value"]
                else:
                    chosen = variants_list[0]["value"]
                    if len(variants_list) > 1:
                        conflicts.append({"key": choice_key, "label": field_label(key), "options": [dict(item, value_hash=digest(item["value"])) for item in variants_list]})
                merged.append(chosen)
            result[key] = merged
        elif decision is not None:
            used.add(key)
            if not isinstance(decision, dict):
                raise HTTPException(422, "字段决策格式无效")
            if "person_id" in decision:
                if decision["person_id"] not in all_values:
                    raise HTTPException(422, "字段取值来源不在本次选中档案中")
                result[key] = all_values[decision["person_id"]].get(key)
            elif "value" in decision:
                result[key] = decision["value"]
            else:
                raise HTTPException(422, "请选择字段来源或填写修正值")
        elif key in CONCAT_FIELDS or key.endswith((".remarks", ".evaluation_summary", ".summary")):
            unique = {}
            for option in nonempty:
                unique.setdefault(str(option["value"]), []).append(option["person_id"])
            result[key] = "\n\n".join(f"【来源：{'、'.join(str(next(p.resource_code or p.full_name for p in people if str(p.id) == identifier)) for identifier in origins)}】\n{value}"
                                       for value, origins in unique.items()) if len(unique) > 1 else (nonempty[0]["value"] if nonempty else None)
        elif nonempty and all(isinstance(row["value"], list) for row in nonempty):
            union = []
            for option in nonempty:
                for value in option["value"]:
                    if value not in union:
                        union.append(value)
            result[key] = union
        else:
            if field_state([row["value"] for row in options]) == "conflict":
                conflicts.append({"key": key, "label": field_label(key), "options": options})
            result[key] = target_values.get(key) if target_values.get(key) is not None and target_values.get(key) != "" else (nonempty[0]["value"] if nonempty else None)
        fields.append({"key": key, "label": field_label(key), "options": options, "value": result.get(key),
                       "state": field_state([option["value"] for option in options]), "decision": decision})
    if set(decisions) - used:
        raise HTTPException(422, "提交了未知或无需处理的字段决策")
    return result, fields, conflicts


def _validated_payload(values, target):
    data = {key: value for key, value in values.items() if "." not in key}
    for profile in PROFILES:
        nested = {key.split(".", 1)[1]: value for key, value in values.items() if key.startswith(profile + ".")}
        if nested:
            data[profile] = nested
    data["resource_code"] = target.resource_code
    data["wechat_accounts_revision"] = target.wechat_accounts_revision
    try:
        payload = ResourcePersonUpdate.model_validate(data)
    except ValueError as exc:
        raise HTTPException(422, "合并字段未通过业务校验，请检查字段类型和取值") from exc
    from resource_service import _sync_display_name
    _sync_display_name(payload)
    # schema 部分历史字符串未声明长度，按实际数据库列再校验，绝不截断。
    for column in ResourcePerson.__table__.columns:
        value = getattr(payload, column.key, None)
        if isinstance(value, str) and getattr(column.type, "length", None) and len(value) > column.type.length:
            raise HTTPException(422, f"{field_label(column.key)}超过字段长度，请人工选择；原文仍在来源档案中保留")
    for profile in PROFILES:
        model = getattr(target.__class__, profile).property.mapper.class_
        nested = getattr(payload, profile)
        if nested:
            for column in model.__table__.columns:
                value = getattr(nested, column.key, None)
                if isinstance(value, str) and getattr(column.type, "length", None) and len(value) > column.type.length:
                    raise HTTPException(422, f"{field_label(profile + '.' + column.key)}超过字段长度")
    return payload


def preview(db, request):
    require_ready(db)
    from resource_service import get_talent
    people = [get_talent(db, identifier) for identifier in request.person_ids]
    if any(person is None or person.archived_into_id for person in people):
        raise HTTPException(409, "选中档案不存在或已归档，请刷新同名组")
    keys = {name_key(person.full_name) for person in people}
    if len(keys) != 1:
        raise HTTPException(409, "姓名分组已变化，请重新选择同名档案")
    target = next((person for person in people if person.id == request.target_id), None)
    affected = set(request.person_ids)
    if target:
        affected.update(row[0] for row in db.query(ResourcePerson.id).filter(ResourcePerson.archived_into_id.in_(request.person_ids)).all())
    snapshot = full_snapshot(db, affected)
    conflicts, fields, values = [], [], None
    if request.action == "merge":
        values, fields, conflicts = _merge_values(people, target, request.decisions)
        if not conflicts:
            normalized = _validated_payload(values, target)
            # 普通表单会清理文本、邮箱并按结构化姓名生成显示名，预览必须展示相同结果。
            for field in fields:
                key = field["key"]
                if key in COLLECTIONS:
                    continue
                if "." in key:
                    profile, attribute = key.split(".", 1)
                    value = getattr(getattr(normalized, profile), attribute)
                else:
                    value = getattr(normalized, key)
                field["value"] = values[key] = plain(value)
    elif request.decisions:
        raise HTTPException(422, "只有合并资料可以提交字段取值决策")
    elif request.action == "keep":
        values = _business_values(target)
        fields = [{"key": key, "label": field_label(key), "value": value,
                   "options": [{"person_id": str(target.id), "value": value}], "state": "same"}
                  for key, value in values.items() if value is not None and value != "" and value != []]
    token = digest({"snapshot": snapshot, "request": request.model_dump(exclude={"preview_token", "idempotency_key"}, mode="json")})
    return {"preview_token": token, "name_key": next(iter(keys)), "action": request.action,
            "target_id": str(request.target_id) if target else None, "affected_ids": [str(i) for i in sorted(affected, key=str)],
            "archive_ids": [str(person.id) for person in people if target and person.id != target.id], "fields": fields,
            "conflicts": conflicts, "final_values": values,
            "omitted_fields": [{"person_id": str(person.id), "fields": [{"label": field_label(key), "value": value}
                                 for key, value in _business_values(person).items() if value is not None and value != "" and value != []]}
                                for person in people if target and person.id != target.id] if request.action == "keep" else [],
            "reference_counts": {key: len(value) for key, value in snapshot["references"].items()},
            "history_policy": "原业务关联保留；保留档案汇总来源档案的项目与附件，来源附件只读。",
            "before_snapshot": snapshot}


def _apply_merge(db, target, payload, actor):
    from resource_service import PROFILE_FIELDS, _sync_legacy_translator, _sync_display_name
    from talent_wechat_accounts import write_talent_accounts
    for key, value in payload.model_dump(exclude={*COLLECTIONS, *PROFILES, "allow_duplicate", "resource_code", "wechat_account", "wechat_accounts", "wechat_accounts_revision"}).items():
        if key not in SYSTEM_FIELDS:
            setattr(target, key, value)
    # 合并公司账号仅并集账号，不调用删友状态转换，以免凭档案归档改写历史渠道状态。
    from talent_wechat_accounts import store_accounts
    store_accounts(db, target, payload.wechat_accounts or [], actor=actor, source="duplicate_review")
    for key, model in PROFILE_FIELDS.items():
        nested = getattr(payload, key)
        if nested is None:
            continue
        row = getattr(target, key)
        if row is None:
            row = model(person_id=target.id)
            setattr(target, key, row)
        for field, value in nested.model_dump().items():
            setattr(row, field, value)
    for key in COLLECTIONS:
        relationship = getattr(ResourcePerson, key).property
        model = relationship.mapper.class_
        existing = list(getattr(target, key))
        # 保留原主档明细 ID，来源明细创建独立副本，避免移动原始资料。
        by_identity = {_collection_key(key, plain({k: v for k, v in _columns(row).items() if k not in SYSTEM_FIELDS})): row for row in existing}
        selected = []
        for index, incoming in enumerate(getattr(payload, key)):
            data = incoming.model_dump(exclude={"id"})
            identity = _collection_key(key, plain({k: v for k, v in data.items() if k not in SYSTEM_FIELDS}))
            row = by_identity.get(identity)
            if row is None:
                row = model(id=uuid4(), person_id=target.id)
                getattr(target, key).append(row)
            for field, value in data.items():
                setattr(row, field, value)
            if hasattr(row, "sort_order"):
                row.sort_order = index
            if hasattr(row, "source") and not row.source:
                row.source = "duplicate_review"
            if hasattr(row, "created_at") and not row.created_at:
                row.created_at = business_now()
            if hasattr(row, "updated_at"):
                row.updated_at = business_now()
            selected.append(row)
        for row in existing:
            if row not in selected:
                if key == "certificates" and any(attachment.certificate_id == row.id for attachment in target.attachments):
                    # 已有证书附件依附明细，保留重复证书的原明细，不能级联删除材料。
                    continue
                getattr(target, key).remove(row)
    _sync_display_name(target)
    target.updated_at = business_now()
    target.operated_at = business_now()
    target.operated_by = actor.id
    target.operator_name = actor.full_name or actor.username
    db.flush()
    _sync_legacy_translator(db, target)


def commit(db, request, actor):
    require_ready(db)
    from talent_wechat_accounts import lock_account_writes
    lock_account_writes(db)
    request_hash = digest(request.model_dump(mode="json"))
    previous = db.query(TalentDuplicateOperation).filter_by(idempotency_key=request.idempotency_key).first()
    if previous:
        if previous.request_hash != request_hash or previous.actor_id != actor.id:
            raise HTTPException(409, "幂等键已用于另一项处理")
        return operation_result(previous)
    ids = set(request.person_ids)
    ids.update(row[0] for row in db.query(ResourcePerson.id).filter(ResourcePerson.archived_into_id.in_(ids)).all())
    db.query(ResourcePerson).filter(ResourcePerson.id.in_(ids)).order_by(ResourcePerson.id).with_for_update().all()
    db.expire_all()
    current = preview(db, request)
    if current["preview_token"] != request.preview_token:
        raise HTTPException(409, "资料或业务关联已变化，请重新预览后确认")
    if current["conflicts"]:
        raise HTTPException(422, "请先解决所有字段冲突")
    from resource_service import get_talent
    fingerprints = {str(identifier): comparison_fingerprint(get_talent(db, identifier)) for identifier in request.person_ids}
    if request.action in {"keep", "merge"}:
        target = get_talent(db, request.target_id)
        if request.action == "merge":
            _apply_merge(db, target, _validated_payload(current["final_values"], target), actor)
        now = datetime.now(BUSINESS_TIMEZONE)
        for identifier in ids - {request.target_id}:
            source = get_talent(db, identifier)
            source.archived_into_id = request.target_id
            source.archived_at = source.archived_at or now
        db.flush()
    after = full_snapshot(db, ids)
    op = TalentDuplicateOperation(id=uuid4(), idempotency_key=request.idempotency_key, request_hash=request_hash,
                                 action=request.action, name_key=current["name_key"], person_ids=[str(i) for i in request.person_ids],
                                 target_id=request.target_id, actor_id=actor.id, actor_name=actor.full_name or actor.username,
                                 decisions={"fields": request.decisions, "note": request.note, "fingerprints": fingerprints},
                                 before_snapshot=current["before_snapshot"], after_snapshot=after,
                                 comparison_fingerprint=digest(fingerprints), created_at=datetime.now(BUSINESS_TIMEZONE))
    db.add(op)
    db.commit()
    return operation_result(op)


def operation_result(op):
    return {"id": str(op.id), "action": op.action, "name_key": op.name_key, "person_ids": op.person_ids,
            "target_id": str(op.target_id) if op.target_id else None, "actor_name": op.actor_name,
            "created_at": business_iso(op.created_at), "undone_at": business_iso(op.undone_at)}


def history(db, skip=0, limit=20, contacts_visible=False, person_id=None):
    if not review_ready(db):
        return {"items": [], "total": 0}
    query = db.query(TalentDuplicateOperation).options(load_only(
        TalentDuplicateOperation.id, TalentDuplicateOperation.action, TalentDuplicateOperation.name_key,
        TalentDuplicateOperation.person_ids, TalentDuplicateOperation.target_id, TalentDuplicateOperation.actor_name,
        TalentDuplicateOperation.created_at, TalentDuplicateOperation.undone_at,
    )).order_by(TalentDuplicateOperation.created_at.desc(), TalentDuplicateOperation.id.desc())
    if not person_id:
        return {"items": [operation_result(op) for op in query.offset(skip).limit(limit).all()], "total": query.count()}
    operations = query.all()
    if person_id:
        operations = [op for op in operations if str(person_id) in op.before_snapshot["people"]]
    # 历史只返回操作摘要；原始敏感快照不出接口。
    return {"items": [operation_result(op) for op in operations[skip:skip + limit]], "total": len(operations)}


def annotate_review_states(db, people):
    """按当前页姓名批量取核对结论，不在列表中逐条加载全库。"""
    if not review_ready(db):
        return
    from resource_service import _person_options
    from sqlalchemy import func
    keys = {name_key(person.full_name) for person in people if person.name_duplicate}
    if not keys:
        return
    query = active_query(db, db.query(ResourcePerson)).options(*_person_options(), *archive_options(db))
    if db.get_bind().dialect.name == "postgresql":
        query = query.filter(func.resource_person_duplicate_name_key(ResourcePerson.full_name).in_(keys))
    members = [p for p in query.all() if name_key(p.full_name) in keys]
    operations = _decision_query(db).filter(TalentDuplicateOperation.name_key.in_(keys)).order_by(TalentDuplicateOperation.created_at).all()
    for key in keys:
        grouped = [p for p in members if name_key(p.full_name) == key]
        decisions = _pair_decisions(grouped, [op for op in operations if op.name_key == key])
        for person in grouped:
            others = [tuple(sorted((str(person.id), str(other.id)))) for other in grouped if other.id != person.id]
            person.__dict__["name_review_state"] = "different" if others and all(decisions.get(pair) == "different" for pair in others) else "pending"


def _typed(column, value):
    if value is None:
        return None
    try:
        kind = column.type.python_type
    except NotImplementedError:
        return value
    if kind is UUID:
        return UUID(value)
    if kind is datetime:
        return datetime.fromisoformat(value)
    if kind is date:
        return date.fromisoformat(value)
    if kind is Decimal:
        return Decimal(value)
    return value


def undo(db, operation_id, actor):
    require_ready(db)
    from talent_wechat_accounts import lock_account_writes
    lock_account_writes(db)
    op = db.query(TalentDuplicateOperation).filter_by(id=operation_id).with_for_update().first()
    if not op:
        raise HTTPException(404, "核重操作不存在")
    if op.undone_at:
        return operation_result(op)
    ids = [UUID(identifier) for identifier in op.after_snapshot["people"]]
    db.query(ResourcePerson).filter(ResourcePerson.id.in_(ids)).order_by(ResourcePerson.id).with_for_update().all()
    later = db.query(TalentDuplicateOperation).filter(TalentDuplicateOperation.created_at > op.created_at,
                                                     TalentDuplicateOperation.undone_at.is_(None)).all()
    if any(set(other.before_snapshot["people"]) & set(op.after_snapshot["people"]) for other in later):
        raise HTTPException(409, "这些档案已有后续核重操作，不能自动撤销")
    db.expire_all()
    current = full_snapshot(db, ids)
    if digest(current) != digest(op.after_snapshot):
        changed = [identifier for identifier in op.after_snapshot["people"]
                   if digest(current["people"].get(identifier)) != digest(op.after_snapshot["people"][identifier])]
        raise HTTPException(409, {"message": "档案、明细或业务关联已变化，不能自动撤销", "changed_person_ids": changed,
                                  "references_changed": current["references"] != op.after_snapshot["references"]})
    if op.action in {"keep", "merge"}:
        from resource_service import get_talent, _sync_legacy_translator
        # 先解除归档，再恢复明细；不触碰原业务外键。
        restore_rows = sorted(op.before_snapshot["people"].items(), key=lambda item: bool(item[1]["person"]["archived_into_id"]))
        for identifier, snapshot in restore_rows:
            row = get_talent(db, UUID(identifier))
            for column in ResourcePerson.__table__.columns:
                if column.key != "name_duplicate":
                    setattr(row, column.key, _typed(column, snapshot["person"][column.key]))
            if snapshot["person"]["archived_into_id"] is None:
                db.flush()
        db.flush()
        for identifier, snapshot in op.before_snapshot["people"].items():
            row = get_talent(db, UUID(identifier))
            for key in (*COLLECTIONS, *PROFILES):
                before = snapshot[key]
                after = op.after_snapshot["people"][identifier][key]
                if before == after:
                    continue
                model = getattr(ResourcePerson, key).property.mapper.class_
                if key in PROFILES:
                    nested = getattr(row, key)
                    if before is None:
                        setattr(row, key, None)
                    else:
                        if nested is None:
                            nested = model(person_id=row.id)
                            setattr(row, key, nested)
                        for column in model.__table__.columns:
                            setattr(nested, column.key, _typed(column, before[column.key]))
                else:
                    existing = {str(item.id): item for item in getattr(row, key)}
                    before_ids = {item["id"] for item in before}
                    for identifier_key, child in existing.items():
                        if identifier_key not in before_ids:
                            getattr(row, key).remove(child)
                    for item in before:
                        child = existing.get(item["id"])
                        if child is None:
                            child = model()
                            getattr(row, key).append(child)
                        for column in model.__table__.columns:
                            setattr(child, column.key, _typed(column, item[column.key]))
        db.flush()
        # 精确恢复兼容译员记录（包括合并时新建的兼容行），防止撤销留下新增能力。
        if op.target_id:
            from models import Translator
            before_translators = {item["id"]: item for item in op.before_snapshot["references"].get("translator", [])}
            for item in op.after_snapshot["references"].get("translator", []):
                translator = db.get(Translator, UUID(item["id"]))
                if item["id"] not in before_translators:
                    db.delete(translator)
                else:
                    original = before_translators[item["id"]]
                    for column in Translator.__table__.columns:
                        setattr(translator, column.key, _typed(column, original[column.key]))
    op.undone_at = datetime.now(BUSINESS_TIMEZONE)
    op.undone_by = actor.id
    db.commit()
    return operation_result(op)


def detail_inheritance(db, person_id, contacts_visible):
    if not review_ready(db):
        return {"archived_into_id": None, "archived_at": None, "inherited_contacts": [], "inherited_attachments": []}
    from resource_service import get_talent
    row = get_talent(db, person_id)
    sources = db.query(ResourcePerson).filter(ResourcePerson.archived_into_id == person_id).all()
    contacts, attachments = [], []
    for source in sources:
        if contacts_visible:
            for field in RESOURCE_CONTACT_FIELDS:
                if getattr(source, field):
                    contacts.append({"source_id": str(source.id), "source_code": source.resource_code,
                                     "field": field, "label": field_label(field), "value": getattr(source, field)})
        for attachment in source.attachments:
            attachments.append({"id": str(attachment.id), "source_id": str(source.id), "source_code": source.resource_code,
                                "category": attachment.category, "original_name": attachment.original_name, "readonly": True})
    return {"archived_into_id": str(row.archived_into_id) if row.archived_into_id else None,
            "archived_at": business_iso(row.archived_at), "inherited_contacts": contacts,
            "inherited_attachments": attachments}
