"""客户指定姓名规则的批量合并；先预览，逐组事务，原档案与字段差异完整留存。"""
import unicodedata

from fastapi import HTTPException
from sqlalchemy import func

from business_time import business_iso, business_now
from resource_models import ResourcePerson
from resource_service import _person_options, get_talent_project_situations
from talent_duplicate_models import TalentDuplicateOperation
from talent_duplicate_schemas import DuplicateReviewRequest, DuplicateReviewCommit
from talent_duplicate_service import (
    active_query, archive_options, name_key, require_ready,
    person_snapshot, digest, _merge_values, _decision_query,
    _pair_decisions, preview, commit, operation_result, merge_audit,
)

RULE = "name-length-v1"
POLICY = "中文姓名至少三个汉字；英文姓名至少两个以空白分隔的单词。主档按业务关联数量、创建时间及 ID 排序选择；冲突保留主档，缺失补充，明细合并去重，所有来源原值留档。"


def name_kind(value):
    key = name_key(value)
    compact = "".join(key.split())
    if compact and all("CJK UNIFIED IDEOGRAPH" in unicodedata.name(char, "") or
                       "CJK COMPATIBILITY IDEOGRAPH" in unicodedata.name(char, "") for char in compact):
        return "chinese" if len(compact) >= 3 else "short_chinese"
    words = key.split()
    def latin_word(word):
        # 支持拉丁重音、人名中的连字符／撇号及姓名首字母缩写；数字和混合文字不算英文单词。
        return (any("LATIN" in unicodedata.name(char, "") for char in word) and
                all("LATIN" in unicodedata.name(char, "") or unicodedata.category(char).startswith("M")
                    or char in "-'’." for char in word))
    if len(words) >= 2 and all(latin_word(word) for word in words):
        return "english"
    return "other"


def _members(db, key=None):
    require_ready(db)
    normalized = func.resource_person_duplicate_name_key(ResourcePerson.full_name)
    query = active_query(db, db.query(ResourcePerson))
    if key is not None:
        query = query.filter(normalized == key)
    else:
        keys = active_query(db, db.query(normalized)).group_by(normalized).having(func.count(ResourcePerson.id) > 1)
        query = query.filter(normalized.in_(keys))
    return query.options(*_person_options(), *archive_options(db)).populate_existing().all()


def _ordered(members, situations):
    return sorted(members, key=lambda person: (-situations.get(person.id, {}).get("total", 0),
                                               business_iso(person.created_at) or "", str(person.id)))


def _version(members, situations):
    return digest({"rule": RULE, "people": {str(p.id): person_snapshot(p) for p in members},
                   "projects": {str(p.id): situations.get(p.id, {}).get("total", 0) for p in members}})


def list_groups(db, skip=0, limit=20):
    people = _members(db)
    grouped = {}
    for person in people:
        grouped.setdefault(name_key(person.full_name), []).append(person)
    eligible = {key: members for key, members in grouped.items()
                if len(members) >= 2 and name_kind(key) in {"chinese", "english"}}
    counts = {"chinese": 0, "english": 0, "short_chinese": 0, "other": 0}
    for key, members in grouped.items():
        if len(members) >= 2:
            counts[name_kind(key)] += 1
    # 全库扫描不受列表当前页、Agent 分档或人工待核筛选影响。
    keys = sorted(eligible)
    page_keys = keys[skip:skip + limit]
    page_people = [p for key in page_keys for p in eligible[key]]
    situations = get_talent_project_situations(db, [p.id for p in page_people]) if page_people else {}
    items = []
    for key in page_keys:
        members = _ordered(eligible[key], situations)
        items.append({"key": key, "kind": name_kind(key), "count": len(members),
                      "group_version": _version(members, situations), "target_id": str(members[0].id),
                      "members": [{"id": str(p.id), "name": p.full_name, "code": p.resource_code,
                                   "project_count": situations.get(p.id, {}).get("total", 0)} for p in members],
                      "blocked_reason": "单组超过 100 条，请分批人工处理" if len(members) > 100 else None})
    return {"rule": RULE, "policy": POLICY, "items": items, "total": len(keys), "counts": counts,
            "archive_count": sum(len(members) - 1 for members in eligible.values()),
            "created_at": business_iso(business_now())}


def _automatic_request(members):
    target = members[0]
    _, _, conflicts = _merge_values(members, target, {})
    decisions = {}
    order = {str(person.id): index for index, person in enumerate(members)}
    for conflict in conflicts:
        options = [row for row in conflict["options"] if row["value"] is not None and row["value"] != "" and row["value"] != []]
        chosen = min(options, key=lambda row: order[row["person_id"]])
        decisions[conflict["key"]] = {"person_id": chosen["person_id"],
                                       **({"value_hash": chosen["value_hash"]} if "value_hash" in chosen else {})}
    values, _, conflicts = _merge_values(members, target, decisions)
    # 短字段不能装下拼接文本时保留优先来源原值，其余值继续在来源档案及日志中保留，绝不截断。
    for key, value in values.items():
        if "." in key:
            section, attribute = key.split(".", 1)
            model = getattr(ResourcePerson, section).property.mapper.class_
            column = model.__table__.columns.get(attribute)
        else:
            column = ResourcePerson.__table__.columns.get(key)
        length = getattr(column.type, "length", None) if column is not None else None
        if isinstance(value, str) and length and len(value) > length:
            from talent_duplicate_service import _business_values
            candidates = [(p, _business_values(p).get(key)) for p in members]
            chosen = next(((p, v) for p, v in candidates if isinstance(v, str) and v and len(v) <= length), None)
            if chosen is None:
                raise HTTPException(422, "来源资料超过字段容量，请先修正原档案")
            decisions[key] = {"person_id": str(chosen[0].id)}
    return DuplicateReviewRequest(action="merge", person_ids=[p.id for p in members], target_id=target.id,
                                  decisions=decisions, note=f"按客户姓名规则批量合并（{RULE}）；冲突及原值保留在来源档案与逐字段日志。")


def preview_group(db, request):
    if name_kind(request.group_key) not in {"chinese", "english"}:
        raise HTTPException(422, "仅处理至少三个汉字或至少两个英文单词的同名组")
    people = _members(db, request.group_key)
    if len(people) < 2 or len(people) > 100:
        raise HTTPException(409, "同名组已变化或超过单次容量，请重新加载")
    situations = get_talent_project_situations(db, [p.id for p in people])
    members = _ordered(people, situations)
    if _version(members, situations) != request.group_version:
        raise HTTPException(409, "资料、成员或项目数量已变化，请重新加载批量预览")
    payload = _automatic_request(members)
    result = preview(db, payload)
    audit = merge_audit(result, payload.decisions)
    audit.update({"rule": RULE, "policy": POLICY, "group_version": request.group_version})
    for field in audit["fields"]:
        if field.get("decision"):
            field["method"] = ("优先保留主档原值；其他冲突值留档" if field["decision"].get("person_id") == audit["target_id"]
                               else "按优先来源取值；其他原值留档（包含字段容量限制）")
        elif field.get("choices"):
            field["method"] = "明细取并集、相同项去重；同项冲突优先主档原值，其余冲突原值留档"
    decisions = _pair_decisions(members, _decision_query(db).filter_by(name_key=request.group_key).all())
    audit["warnings"] = ["此组已有人工区分或暂缓结论；按本次客户姓名规则将其同名成员合并。"] if decisions else []
    result.update({"audit": audit, "automatic_request": payload.model_dump(mode="json")})
    return result


def commit_group(db, request, actor):
    require_ready(db)
    # 重试必须直接返回同一项结果，不能因第一次提交已归档成员而重新计算一组。
    request_hash = digest(request.model_dump(mode="json"))
    previous = db.query(TalentDuplicateOperation).filter_by(idempotency_key=request.idempotency_key).first()
    if previous:
        if previous.actor_id != actor.id or previous.decisions.get("name_merge_request_hash") != request_hash:
            raise HTTPException(409, "幂等键已用于另一项处理")
        return operation_result(previous)
    # 与普通编辑／核重使用相同全局锁，锁内重读组成员，避免加入新成员后按旧组提交。
    from talent_wechat_accounts import lock_account_writes
    lock_account_writes(db)
    previous = db.query(TalentDuplicateOperation).filter_by(idempotency_key=request.idempotency_key).first()
    if previous:
        if previous.actor_id != actor.id or previous.decisions.get("name_merge_request_hash") != request_hash:
            raise HTTPException(409, "幂等键已用于另一项处理")
        return operation_result(previous)
    current = preview_group(db, request)
    if current["preview_token"] != request.preview_token:
        raise HTTPException(409, "资料或业务关联已变化，请重新预览")
    payload = DuplicateReviewCommit(**current["automatic_request"], preview_token=request.preview_token,
                                    idempotency_key=request.idempotency_key)
    return commit(db, payload, actor, audit_metadata={"merge_audit": current["audit"],
                                                     "name_merge_request_hash": request_hash})
