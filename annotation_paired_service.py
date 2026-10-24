"""双人采标事务服务。调用方提交事务；整个订单工作区写入串行化。"""
from datetime import date, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import or_, inspect
from sqlalchemy.orm import Session

from annotation_models import AnnotationProject
from annotation_paired_models import (
    PairedWorkspace, PairedContact, PairedGroup, PairedMembers, PairedTask,
    PairedRecord, PairedAudit, PairedParticipant, business_now,
)
from business_time import business_iso
from resource_models import ResourcePerson, ResourceLanguageSkill


def plain(row):
    if row is None:
        return None
    result = {}
    for column in inspect(row).mapper.column_attrs:
        if column.key == "request_hash":
            continue
        value = getattr(row, column.key)
        result[column.key] = business_iso(value) if isinstance(value, datetime) else str(value) if isinstance(value, UUID) else value
    return result


def audit(db, project_id, entity_id, action, before, after, actor):
    db.add(PairedAudit(project_id=project_id, entity_id=entity_id, action=action,
                       before=before or {}, after=after or {}, actor_id=actor.id,
                       actor_name=(actor.full_name or actor.username)))


def workspace(db, project_id, *, write=False, initialize=False):
    # 与订单编辑采用相同的行锁，避免同时取消项目类型与写入执行记录。
    query = db.query(AnnotationProject).filter(AnnotationProject.id == project_id)
    project = (query.with_for_update() if write else query).populate_existing().first()
    if not project:
        raise HTTPException(404, "订单不存在")
    row = db.get(PairedWorkspace, project_id)
    if not row:
        if "paired_collection_annotation" not in (project.project_types or []):
            raise HTTPException(400, "当前订单不是双人采标类型")
        if initialize:
            row = PairedWorkspace(project_id=project_id)
            db.add(row)
            db.flush()
    if write and row and row.archived and not initialize:
        raise HTTPException(409, "工作区已归档，请先恢复后再修改")
    if write and row is None and not initialize:
        raise HTTPException(409, "请先初始化双人采标工作区")
    return row


def fresh(row, expected_revision):
    if expected_revision is None or row.revision != expected_revision:
        raise HTTPException(409, "记录已更新，请保留草稿并重新加载后核对")


def request_hash(payload):
    import hashlib
    import json
    content = payload.model_dump(mode="json", exclude={"expected_revision"})
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def replay(row, payload):
    if row.request_hash != request_hash(payload):
        raise HTTPException(409, "本次请求标识已用于不同内容，请重新打开新增窗口")


def scoped(db, model, project_id, row_id):
    row = db.get(model, row_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "当前订单中不存在该记录")
    return row


def person(db, person_id):
    row = db.get(ResourcePerson, person_id)
    if not row:
        raise HTTPException(400, "人才不存在")
    return row


def person_summary(db, person_id):
    row = person(db, person_id)
    return {"id": str(row.id), "resource_code": row.resource_code, "full_name": row.full_name,
            "region": row.residence_address, "language_skills": [
                {"id": str(skill.id), "language_id": str(skill.language_id), "label": skill.language_label,
                 "accent": skill.accent or ""} for skill in row.language_skills]}


def sync_participants(db, task):
    active_ids = {UUID(value) for value in task.person_ids}
    existing = {row.person_id: row for row in db.query(PairedParticipant).filter_by(task_id=task.id)}
    for person_id, row in existing.items():
        row.active = person_id in active_ids
    for person_id in active_ids - existing.keys():
        db.add(PairedParticipant(task_id=task.id, person_id=person_id))


def save_workspace(db, project_id, payload, actor):
    row = workspace(db, project_id, write=True, initialize=True)
    fresh(row, payload.expected_revision)
    if not payload.allow_multiple_groups:
        occupied = set()
        for group in db.query(PairedGroup).filter_by(project_id=project_id, archived=False).all():
            members = current_members(db, group.id)
            for member in (members.person1_id, members.person2_id):
                if member in occupied:
                    raise HTTPException(400, "已有人员参与多个有效分组，不能关闭允许多组")
                occupied.add(member)
    before = plain(row)
    row.allow_multiple_groups = payload.allow_multiple_groups
    if not payload.archived and "paired_collection_annotation" not in (db.get(AnnotationProject, project_id).project_types or []):
        raise HTTPException(409, "恢复工作区前，请先恢复订单的双人采标类型")
    row.archived = payload.archived
    if set(payload.notes) - {"strategy", "moments", "posts", "handover"} or any(len(value) > 20000 for value in payload.notes.values()):
        raise HTTPException(400, "联系安排字段或内容长度不符合要求")
    row.notes = payload.notes
    row.revision += 1
    db.flush()
    audit(db, project_id, project_id, "workspace", before, plain(row), actor)
    return plain(row)


def save_contact(db, project_id, payload, actor, row_id=None):
    workspace(db, project_id, write=True)
    person(db, payload.person_id)
    row = scoped(db, PairedContact, project_id, row_id) if row_id else db.query(PairedContact).filter_by(project_id=project_id, person_id=payload.person_id).first()
    before = plain(row)
    if row:
        if row_id:
            fresh(row, payload.expected_revision)
            if row.person_id != payload.person_id:
                raise HTTPException(400, "联系人不能更换人才，请另行新增")
        else:
            # 重复引用只合并来源，不覆盖业务人员已经维护的联系意愿。
            merged = dict(row.data)
            merged["sources"] = list(dict.fromkeys([*merged.get("sources", []), *payload.data.get("sources", [])]))
            row.data = merged
            row.revision += 1
            db.flush()
            audit(db, project_id, row.id, "contact_source", before, plain(row), actor)
            return plain(row)
    else:
        row = PairedContact(project_id=project_id, person_id=payload.person_id, created_by=actor.id)
        db.add(row)
    allowed = {"sources", "quote", "reason", "availability", "remarks", "channel_states", "follow_ups", "attachments", "response_status"}
    if set(payload.data) - allowed:
        raise HTTPException(400, "联系资料包含不支持的字段")
    row.willingness = payload.willingness
    row.data = {**payload.data, "follow_ups": (row.data or {}).get("follow_ups", []), "attachments": (row.data or {}).get("attachments", [])}
    if row_id:
        row.revision += 1
    db.flush()
    audit(db, project_id, row.id, "contact", before, plain(row), actor)
    return plain(row)


def current_members(db, group_id):
    return db.query(PairedMembers).filter_by(group_id=group_id).order_by(PairedMembers.version.desc()).first()


def group_result(db, group):
    return {**plain(group), "members": plain(current_members(db, group.id))}


def save_group(db, project_id, payload, actor, row_id=None):
    ws = workspace(db, project_id, write=True)
    row = scoped(db, PairedGroup, project_id, row_id) if row_id else db.query(PairedGroup).filter_by(project_id=project_id, request_key=payload.request_key).first()
    if row and not row_id:
        replay(row, payload)
        return group_result(db, row)
    before = group_result(db, row) if row else None
    old = current_members(db, row.id) if row else None
    if row:
        fresh(row, payload.expected_revision)
        if row.request_key != payload.request_key:
            raise HTTPException(400, "分组请求标识不能修改")
    for member in (payload.person1_id, payload.person2_id):
        if not db.query(PairedContact.id).filter_by(project_id=project_id, person_id=member).first():
            raise HTTPException(400, "请先将两名组员加入本订单联系表")
        if not ws.allow_multiple_groups and not payload.archived:
            for other in db.query(PairedGroup).filter_by(project_id=project_id, archived=False).all():
                if row and other.id == row.id:
                    continue
                members = current_members(db, other.id)
                if member in (members.person1_id, members.person2_id):
                    raise HTTPException(400, "该人才已在当前订单其他有效分组中")
    changed = old and (old.person1_id, old.person2_id) != (payload.person1_id, payload.person2_id)
    if (changed or (row and row.archived != payload.archived)) and not payload.reason.strip():
        raise HTTPException(400, "更换成员、退出或恢复分组必须填写原因")
    if not row:
        row = PairedGroup(project_id=project_id, name=payload.name, request_key=payload.request_key, request_hash=request_hash(payload))
        db.add(row)
        db.flush()
    else:
        row.revision += 1
    row.name, row.archived = payload.name.strip(), payload.archived
    if old is None or changed:
        members = PairedMembers(group_id=row.id, version=(old.version + 1 if old else 1),
                                person1_id=payload.person1_id, person2_id=payload.person2_id,
                                reason=payload.reason, created_by=actor.id)
        db.add(members)
        db.flush()
        if old is None:
            initial = PairedTask(project_id=project_id, group_id=row.id, members_id=members.id,
                                 request_key=uuid4(), stage="collection", name=f"{row.name} · 首批采集",
                                 person_ids=[str(payload.person1_id), str(payload.person2_id)])
            db.add(initial)
            db.flush()
            sync_participants(db, initial)
    db.flush()
    audit(db, project_id, row.id, "group", before, group_result(db, row), actor)
    return group_result(db, row)


def save_task(db, project_id, payload, actor, row_id=None):
    workspace(db, project_id, write=True)
    row = scoped(db, PairedTask, project_id, row_id) if row_id else db.query(PairedTask).filter_by(project_id=project_id, request_key=payload.request_key).first()
    if row and not row_id:
        replay(row, payload)
        return plain(row)
    before = plain(row)
    group = scoped(db, PairedGroup, project_id, payload.group_id)
    if group.archived:
        raise HTTPException(400, "已归档分组不能新增或修改任务")
    if row:
        fresh(row, payload.expected_revision)
        if row.group_id != group.id or row.request_key != payload.request_key:
            raise HTTPException(400, "任务来源及请求标识不能修改")
        row.revision += 1
    else:
        members = current_members(db, group.id)
        row = PairedTask(project_id=project_id, group_id=group.id, members_id=members.id,
                         request_key=payload.request_key, request_hash=request_hash(payload), stage="collection")
        db.add(row)
    members = db.get(PairedMembers, row.members_id)
    ids = list(dict.fromkeys(str(value) for value in payload.person_ids))
    if row.stage == "collection":
        ids = [str(members.person1_id), str(members.person2_id)]
    elif not ids:
        raise HTTPException(400, "标注任务至少安排一名人员")
    for value in ids:
        person(db, UUID(value))
    row.person_ids, row.name, row.status = ids, payload.name.strip(), payload.status
    if set(payload.data) - {"content", "workload", "price", "personal_prices", "method", "remarks", "exit_reason"}:
        raise HTTPException(400, "任务资料包含不支持的字段")
    if payload.status == "withdrawn" and not payload.data.get("exit_reason", "").strip():
        raise HTTPException(400, "退出任务必须填写原因")
    row.data = payload.data
    db.flush()
    sync_participants(db, row)
    if row_id and (before.get("data") or {}).get("price", "") != payload.data.get("price", ""):
        from annotation_paired_schemas import RecordWrite
        save_record(db, project_id, row.id, RecordWrite(request_key=uuid4(), kind="price", title="任务价格更新",
                                                      data={"price": payload.data.get("price", "")}), actor)
    audit(db, project_id, row.id, "task", before, plain(row), actor)
    return plain(row)


def transfer(db, project_id, payload, actor):
    workspace(db, project_id, write=True)
    people = list(dict.fromkeys(str(value) for value in payload.person_ids))
    for value in payload.person_ids:
        person(db, value)
    result = []
    for task_id in dict.fromkeys(payload.task_ids):
        source = scoped(db, PairedTask, project_id, task_id)
        if source.stage != "collection":
            raise HTTPException(400, "只能将采集批次转入标注")
        existing = db.query(PairedTask).filter_by(source_task_id=source.id).first()
        if existing:
            result.append(plain(existing))
            continue
        if source.status in {"withdrawn", "archived"} or db.get(PairedGroup, source.group_id).archived:
            raise HTTPException(400, "退出或归档的采集批次不能转入标注")
        target = PairedTask(project_id=project_id, group_id=source.group_id, members_id=source.members_id,
                            source_task_id=source.id, request_key=uuid4(), stage="annotation",
                            name=f"{source.name} · 标注", person_ids=people, data={"content": source.data.get("content", ""), "workload": source.data.get("workload", "")})
        db.add(target)
        db.flush()
        sync_participants(db, target)
        audit(db, project_id, target.id, "transfer", None, plain(target), actor)
        result.append(plain(target))
    return result


def save_record(db, project_id, task_id, payload, actor, row_id=None):
    workspace(db, project_id, write=True)
    task = scoped(db, PairedTask, project_id, task_id)
    row = db.get(PairedRecord, row_id) if row_id else db.query(PairedRecord).filter_by(task_id=task_id, request_key=payload.request_key).first()
    if row and row.task_id != task.id:
        raise HTTPException(404, "阶段记录不属于当前任务")
    if row_id and row is None:
        raise HTTPException(404, "阶段记录不存在")
    if row and not row_id:
        replay(row, payload)
        return plain(row)
    before = plain(row)
    data = payload.data.model_dump(mode="json")
    if payload.kind == "account":
        from annotation_ops_models import AnnotationAccountAssignment
        account_ids = list(dict.fromkeys(payload.account_ids))
        for account_id in account_ids:
            active = db.query(AnnotationAccountAssignment).filter_by(account_id=account_id, project_id=project_id, released_on=None).first()
            if not active or not active.person_id or str(active.person_id) not in task.person_ids:
                raise HTTPException(400, "账号必须已分配给当前订单的任务人员；请先在账号管理中释放或重新分配")
        data["account_ids"] = [str(value) for value in account_ids]
    people = list(dict.fromkeys(str(value) for value in payload.person_ids)) or list(task.person_ids)
    allowed_people = set(task.person_ids) | (set(row.person_ids) if row else set())
    if any(value not in allowed_people for value in people):
        raise HTTPException(400, "记录人员必须属于当前任务；历史记录保留原人员")
    if row:
        fresh(row, payload.expected_revision)
        if row.kind != payload.kind or row.request_key != payload.request_key:
            raise HTTPException(400, "阶段记录类型及请求标识不能修改")
        # 调整安排不改写既有评价和执行记录的人员归属。
        people = row.person_ids
        row.revision += 1
    else:
        siblings = db.query(PairedRecord).filter_by(task_id=task_id, kind=payload.kind).order_by(PairedRecord.position).all()
        position = len(siblings) + 1
        if payload.insert_after_id:
            previous = next((item for item in siblings if item.id == payload.insert_after_id), None)
            if not previous or payload.kind != "progress":
                raise HTTPException(400, "只能在本任务已有进度节点后插入")
            position = previous.position + 1
            data["inserted"] = True
            for sibling in siblings:
                if sibling.position >= position:
                    old = plain(sibling)
                    sibling.position += 1
                    sibling.data = {**sibling.data, "postponed": True}
                    sibling.revision += 1
                    sibling.updated_at = business_now()
                    audit(db, project_id, sibling.id, "postpone", old, plain(sibling), actor)
        row = PairedRecord(task_id=task_id, kind=payload.kind, position=position, request_key=payload.request_key, request_hash=request_hash(payload), created_by=actor.id)
        db.add(row)
    row.title, row.data, row.person_ids = payload.title.strip(), data, people
    row.updated_at = business_now()
    db.flush()
    audit(db, project_id, row.id, "record", before, plain(row), actor)
    return plain(row)


def delete_entity(db, project_id, kind, row_id, actor):
    workspace(db, project_id, write=True)
    model = {"contacts": PairedContact, "groups": PairedGroup, "tasks": PairedTask}.get(kind)
    if model is None:
        raise HTTPException(400, "不支持删除该类型")
    row = scoped(db, model, project_id, row_id)
    before = plain(row)
    if kind == "contacts":
        if db.query(PairedMembers.id).join(PairedGroup, PairedGroup.id == PairedMembers.group_id).filter(PairedGroup.project_id == project_id, or_(PairedMembers.person1_id == row.person_id, PairedMembers.person2_id == row.person_id)).first():
            raise HTTPException(409, "该联系人已有分组历史，请保留联系记录")
    if kind in {"groups", "tasks"}:
        tasks = db.query(PairedTask).filter_by(group_id=row.id).all() if kind == "groups" else [row]
        for task in tasks:
            if task.stage == "annotation" or task.revision > 1 or db.query(PairedRecord.id).filter_by(task_id=task.id).first() or db.query(PairedTask.id).filter_by(source_task_id=task.id).first():
                raise HTTPException(409, "已产生执行记录，请使用退出或归档并保留历史")
        for task in tasks:
            db.delete(task)
        db.flush()
        if kind == "groups":
            db.query(PairedMembers).filter_by(group_id=row.id).delete()
    if kind != "tasks":
        db.delete(row)
    audit(db, project_id, row_id, "delete", before, None, actor)
    db.flush()


def list_entities(db, project_id, kind, keyword="", statuses=None, skip=0, limit=20, group_id=None):
    workspace(db, project_id)
    if kind == "contacts":
        query = db.query(PairedContact).filter_by(project_id=project_id).join(ResourcePerson, ResourcePerson.id == PairedContact.person_id)
        if keyword:
            query = query.filter(or_(ResourcePerson.full_name.ilike(f"%{keyword}%"), ResourcePerson.resource_code.ilike(f"%{keyword}%")))
        if statuses:
            query = query.filter(PairedContact.willingness.in_(statuses))
        rows = query.order_by(ResourcePerson.resource_code, PairedContact.id)
        render = lambda item: {**plain(item), "person": person_summary(db, item.person_id)}
    elif kind == "groups":
        query = db.query(PairedGroup).filter_by(project_id=project_id)
        if keyword:
            query = query.filter(PairedGroup.name.ilike(f"%{keyword}%"))
        rows = query.order_by(PairedGroup.created_at, PairedGroup.id)
        render = lambda item: group_result(db, item)
    elif kind in {"collection", "annotation"}:
        query = db.query(PairedTask).filter_by(project_id=project_id, stage=kind)
        if keyword:
            query = query.filter(PairedTask.name.ilike(f"%{keyword}%"))
        if statuses:
            query = query.filter(PairedTask.status.in_(statuses))
        if group_id:
            query = query.filter(PairedTask.group_id == group_id)
        rows = query.order_by(PairedTask.created_at, PairedTask.id)
        def render(item):
            result = plain(item)
            members = db.get(PairedMembers, item.members_id)
            result["members_version"] = members.version
            source = db.get(PairedTask, item.source_task_id) if item.source_task_id else None
            result["source_task_name"] = source.name if source else None
            latest = {}
            for record in db.query(PairedRecord).filter_by(task_id=item.id).order_by(PairedRecord.updated_at, PairedRecord.id):
                latest[record.kind] = {"title": record.title, "data": record.data}
            result["latest_records"] = latest
            return result
    else:
        raise HTTPException(400, "不支持的列表类型")
    return {"items": [render(row) for row in rows.offset(skip).limit(limit)], "total": query.count()}


def paired_ready(db):
    from sqlalchemy import inspect as sa_inspect
    return sa_inspect(db.connection()).has_table("annotation_paired_task")


def talent_participations(db, person_ids):
    if not person_ids or not paired_ready(db):
        return []
    requested = {str(value): value for value in person_ids}
    result = []
    tasks = db.query(PairedParticipant, PairedTask, AnnotationProject).join(PairedTask, PairedTask.id == PairedParticipant.task_id).join(AnnotationProject, AnnotationProject.id == PairedTask.project_id).filter(
        PairedParticipant.person_id.in_(person_ids)).all()
    # 记录中的实际人员独立保留，后续任务换人不能使历史经历消失。
    records = db.query(PairedRecord, PairedTask, AnnotationProject).join(PairedTask, PairedTask.id == PairedRecord.task_id).join(AnnotationProject, AnnotationProject.id == PairedTask.project_id).filter(
        or_(*(PairedRecord.person_ids.contains([value]) for value in requested))).all()
    for participant, task, project in tasks:
        result.append((participant.person_id, project, task.stage, task.created_at))
    for record, task, project in records:
        for value in record.person_ids:
            if value in requested:
                result.append((requested[value], project, task.stage, record.created_at))
    return result


def talent_records(db, person_ids, project_id):
    if not person_ids or not paired_ready(db):
        return []
    requested = [str(value) for value in person_ids]
    rows = db.query(PairedRecord, PairedTask).join(PairedTask, PairedTask.id == PairedRecord.task_id).filter(
        PairedTask.project_id == project_id, PairedRecord.kind.in_(["performance", "trial", "inspection"]),
        or_(*(PairedRecord.person_ids.contains([value]) for value in requested))).order_by(PairedRecord.created_at).all()
    return [{**plain(record), "stage": task.stage, "task_name": task.name} for record, task in rows]
