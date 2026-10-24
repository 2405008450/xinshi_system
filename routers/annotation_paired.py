"""双人采标 API；不在读取请求中创建工作区或执行迁移。"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import AppUser
from routers.auth import get_current_user, require_any_permission, require_module_access
from annotation_paired_models import PairedWorkspace, PairedTask, PairedRecord, PairedAudit, PairedContact
from annotation_paired_schemas import WorkspaceWrite, ContactWrite, GroupWrite, TaskWrite, TransferWrite, RecordWrite, FollowUpWrite
import annotation_paired_service as service

router = APIRouter(prefix="/annotation-ops/projects/{project_id}/paired-workspace", tags=["双人采标"],
                   dependencies=[Depends(require_module_access("projects:read", "projects:write"))])
write = [Depends(require_any_permission("projects:write"))]
talent_read = [Depends(require_any_permission("talents:read", "talents:write", "translators:read", "translators:write"))]


def run(db, action):
    try:
        result = action()
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(400, str(exc) if isinstance(exc, ValueError) else "记录存在关联或重复，请刷新后核对") from exc
    except ProgrammingError as exc:
        db.rollback()
        raise HTTPException(503, "双人采标数据库结构尚未就绪，请由管理员在获授权后执行增量迁移") from exc


@router.get("")
def get_workspace(project_id: UUID, db: Session = Depends(get_db)):
    try:
        row = service.workspace(db, project_id)
        return service.plain(row)
    except ProgrammingError as exc:
        db.rollback()
        raise HTTPException(503, "双人采标数据库结构尚未就绪，需先完成增量迁移") from exc


@router.post("/initialize", dependencies=write)
def initialize(project_id: UUID, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    def action():
        existing = db.get(PairedWorkspace, project_id)
        row = service.workspace(db, project_id, write=True, initialize=True)
        if existing is None:
            service.audit(db, project_id, project_id, "initialize", None, service.plain(row), actor)
        return service.plain(row)
    return run(db, action)


@router.put("", dependencies=write)
def update_workspace(project_id: UUID, payload: WorkspaceWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return run(db, lambda: service.save_workspace(db, project_id, payload, actor))


@router.get("/people")
def people(project_id: UUID, db: Session = Depends(get_db)):
    service.workspace(db, project_id)
    from annotation_paired_models import PairedMembers, PairedGroup, PairedParticipant
    ids = {row.person_id for row in db.query(PairedContact).filter_by(project_id=project_id)}
    for row in db.query(PairedMembers).join(PairedGroup, PairedGroup.id == PairedMembers.group_id).filter(PairedGroup.project_id == project_id):
        ids.update([row.person1_id, row.person2_id])
    for row in db.query(PairedTask).filter_by(project_id=project_id):
        ids.update(UUID(value) for value in row.person_ids)
    ids.update(row[0] for row in db.query(PairedParticipant.person_id).join(PairedTask, PairedTask.id == PairedParticipant.task_id).filter(PairedTask.project_id == project_id))
    return [service.person_summary(db, value) for value in ids]


@router.get("/staff")
def staff(project_id: UUID, db: Session = Depends(get_db)):
    service.workspace(db, project_id)
    return [{"value": f"{row.full_name or row.username}（{row.username}）", "label": f"{row.full_name or row.username}（{row.username}）"}
            for row in db.query(AppUser).filter(AppUser.is_active.is_(True)).order_by(AppUser.full_name, AppUser.username)]


@router.get("/candidates", dependencies=talent_read)
def candidates(project_id: UUID, keyword: str = "", language_id: UUID | None = None, channel: str = "", company_account: str = "",
               only_new: bool = False, added_date: date | None = None, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    from resource_models import ResourcePerson, ResourceLanguageSkill, ResourceAnnotationLanguageSkill
    from resource_development_models import DevelopmentAction, DevelopmentRecord
    ws = service.workspace(db, project_id)
    query = db.query(ResourcePerson)
    from talent_duplicate_service import active_query
    query = active_query(db, query)
    if keyword:
        query = query.filter(or_(ResourcePerson.full_name.ilike(f"%{keyword}%"), ResourcePerson.resource_code.ilike(f"%{keyword}%")))
    if language_id:
        query = query.filter(or_(ResourcePerson.language_skills.any(ResourceLanguageSkill.language_id == language_id),
                                ResourcePerson.annotation_language_skills.any(or_(ResourceAnnotationLanguageSkill.source_language_id == language_id, ResourceAnnotationLanguageSkill.target_language_id == language_id))))
    if channel == "small_group":
        query = query.filter(ResourcePerson.wechat_groups.is_not(None), ResourcePerson.wechat_groups != "")
    elif channel in {"wechat", "wecom"}:
        # 公司账号信息按登记值筛选，不推断未登记的群成员。
        from sqlalchemy import cast, Text
        query = query.filter(cast(ResourcePerson.wechat_accounts, Text).ilike("%企微%") if channel == "wecom" else ResourcePerson.wechat.is_not(None))
    if company_account:
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB
        query = query.filter(cast(ResourcePerson.wechat_accounts, JSONB).contains([company_account]))
    linked = {row.person_id for row in db.query(PairedContact).filter_by(project_id=project_id)}
    if only_new:
        query = query.filter(~ResourcePerson.id.in_(linked))
    actions = []
    if ws:
        from business_time import BUSINESS_TIMEZONE
        created_date = ws.created_at.replace(tzinfo=BUSINESS_TIMEZONE).date() if ws.created_at.tzinfo is None else ws.created_at.astimezone(BUSINESS_TIMEZONE).date()
        actions = db.query(DevelopmentAction, DevelopmentRecord.person_id).join(DevelopmentRecord, DevelopmentRecord.id == DevelopmentAction.record_id).filter(
            DevelopmentAction.status == "已添加", DevelopmentAction.action_date >= created_date, DevelopmentRecord.person_id.is_not(None)).all()
    by_person = {}
    daily = {}
    for action, person_id in actions:
        by_person.setdefault(person_id, []).append({"date": str(action.action_date), "channel": action.channel})
        daily.setdefault(str(action.action_date), set()).add(person_id)
    eligible = {row[0] for row in query.with_entities(ResourcePerson.id).all()}
    daily = {day: ids & eligible for day, ids in daily.items()}
    if added_date:
        query = query.filter(ResourcePerson.id.in_([key for key, values in by_person.items() if any(value["date"] == str(added_date) for value in values)]))
    total = query.count()
    items = []
    from talent_privacy import can_view_talent_contacts, CONTACT_MASK
    visible = can_view_talent_contacts(db, actor)
    # 远程业务库必须批量读取语言及口音，避免每位人才、每条语言分别请求数据库。
    query = query.options(
        selectinload(ResourcePerson.language_skills).undefer(ResourceLanguageSkill.accent),
        selectinload(ResourcePerson.language_skills).joinedload(ResourceLanguageSkill.language),
    )
    for row in query.order_by(ResourcePerson.resource_code.asc().nullslast(), ResourcePerson.id).offset(skip).limit(limit):
        item = service.person_summary(db, row.id)
        item.update(wechat=row.wechat if visible else CONTACT_MASK, phone=row.primary_phone if visible else CONTACT_MASK, email=row.primary_email if visible else CONTACT_MASK, contact_restricted=not visible,
                    company_accounts=row.wechat_accounts, small_groups=row.wechat_groups,
                    joined=row.id in linked, added_sources=by_person.get(row.id, []))
        items.append(item)
    # 大群登记人数是人次，不混入可识别人才人数，也不宣称已跨群去重。
    group_statistics = None
    if language_id:
        from interpretation_models import InterpretationLanguage
        from talent_overview_wecom_models import TalentOverviewWecomGroup
        from talent_overview_wecom_service import _latest, summarize_groups
        language = db.get(InterpretationLanguage, language_id)
        if language and language.talent_overview_key:
            registered = db.query(TalentOverviewWecomGroup).filter_by(overview_key=language.talent_overview_key, archived=False).all()
            group_statistics = summarize_groups(registered, _latest(db, [group.id for group in registered if group.is_built]))
    return {"items": items, "total": total, "daily_new": [{"date": day, "count": len(ids)} for day, ids in sorted(daily.items(), reverse=True) if ids], "group_statistics": group_statistics}


@router.get("/list/{kind}")
def list_rows(project_id: UUID, kind: str, keyword: str = "", statuses: list[str] = Query(default=[]), group_id: UUID | None = None,
              skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=500), db: Session = Depends(get_db)):
    return service.list_entities(db, project_id, kind, keyword, statuses, skip, limit, group_id)


@router.post("/contacts", dependencies=write)
def create_contact(project_id: UUID, payload: ContactWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return run(db, lambda: service.save_contact(db, project_id, payload, actor))


@router.put("/contacts/{row_id}", dependencies=write)
def update_contact(project_id: UUID, row_id: UUID, payload: ContactWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return run(db, lambda: service.save_contact(db, project_id, payload, actor, row_id))


@router.post("/contacts/{row_id}/follow-ups", dependencies=write)
def follow_up(project_id: UUID, row_id: UUID, payload: FollowUpWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    def action():
        service.workspace(db, project_id, write=True)
        row = service.scoped(db, PairedContact, project_id, row_id)
        service.fresh(row, payload.expected_revision)
        before = service.plain(row)
        from business_time import business_iso
        from annotation_paired_models import business_now
        entry = {"channel": payload.channel, "contact_date": payload.contact_date, "content": payload.content,
                 "actor_id": str(actor.id), "actor_name": actor.full_name or actor.username, "created_at": business_iso(business_now())}
        row.data = {**row.data, "response_status": payload.response_status, "follow_ups": [*row.data.get("follow_ups", []), entry]}
        row.revision += 1
        db.flush()
        service.audit(db, project_id, row.id, "follow_up", before, service.plain(row), actor)
        return service.plain(row)
    return run(db, action)


from pydantic import BaseModel, Field
from resource_schemas import ResourcePersonCreate


class TalentCreate(BaseModel):
    request_key: UUID
    talent: ResourcePersonCreate
    referral_person_id: UUID | None = None


@router.post("/talents", dependencies=[*write, Depends(require_any_permission("talents:write", "translators:write"))])
def create_talent(project_id: UUID, payload: TalentCreate, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    def action():
        service.workspace(db, project_id, write=True)
        from resource_models import ResourcePerson
        from resource_service import create_talent as create, TalentDuplicateError
        from talent_privacy import can_view_talent_contacts, has_contact_values, RESOURCE_CONTACT_FIELDS
        from routers.talents import _duplicate_error_detail
        if not can_view_talent_contacts(db, actor) and has_contact_values(payload.talent, RESOURCE_CONTACT_FIELDS):
            raise HTTPException(403, "当前账号无权填写人才联系方式")
        key = f"paired:{project_id}:{payload.request_key}"
        talent = db.query(ResourcePerson).filter_by(idempotency_key=key).first()
        source = "双人采标联系表新增"
        if payload.referral_person_id:
            referrer = service.person(db, payload.referral_person_id)
            source = f"{referrer.full_name}搭档"
        if talent is None:
            try:
                talent = create(db, payload.talent.model_copy(update={"registration_source": source}), idempotency_key=key, commit=False, actor=actor)
            except TalentDuplicateError as exc:
                raise HTTPException(409, _duplicate_error_detail(exc, contacts_visible=can_view_talent_contacts(db, actor))) from exc
        contact = service.save_contact(db, project_id, ContactWrite(person_id=talent.id, data={"sources": [source]}), actor)
        return {"person": service.person_summary(db, talent.id), "contact": contact}
    return run(db, action)


class AccentWrite(BaseModel):
    accent: str = Field(default="", max_length=255)
    expected_accent: str | None = None


@router.put("/people/{person_id}/languages/{skill_id}", dependencies=[*write, Depends(require_any_permission("talents:write", "translators:write"))])
def accent(project_id: UUID, person_id: UUID, skill_id: UUID, payload: AccentWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    def action():
        service.workspace(db, project_id, write=True)
        from resource_models import ResourceLanguageSkill
        skill = db.query(ResourceLanguageSkill).filter_by(id=skill_id, person_id=person_id).with_for_update().first()
        if skill is None:
            raise HTTPException(404, "人才语言记录不存在")
        if (skill.accent or "") != (payload.expected_accent or ""):
            raise HTTPException(409, "口音已被其他人修改，请重新加载")
        before = skill.accent
        skill.accent = payload.accent
        from resource_service import _record_talent_operation
        from business_time import business_now
        talent = service.person(db, person_id)
        _record_talent_operation(talent, actor)
        talent.updated_at = business_now()
        service.audit(db, project_id, person_id, "accent", {"skill_id": str(skill_id), "accent": before}, {"accent": payload.accent}, actor)
        return {"accent": skill.accent}
    return run(db, action)


@router.post("/contacts/{row_id}/attachments", dependencies=write)
async def upload_attachment(project_id: UUID, row_id: UUID, file: UploadFile = File(...), db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    from annotation_paired_models import PairedAttachment
    from pathlib import PureWindowsPath
    content = await file.read(10 * 1024 * 1024 + 1)
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "附件不能为空且不能超过10MB")
    def action():
        service.workspace(db, project_id, write=True)
        contact = service.scoped(db, PairedContact, project_id, row_id)
        row = PairedAttachment(contact_id=row_id, name=PureWindowsPath(file.filename or "附件").name[:255], content=content, created_by=actor.id)
        db.add(row)
        db.flush()
        entry = {"id": str(row.id), "name": row.name}
        contact.data = {**contact.data, "attachments": [*contact.data.get("attachments", []), entry]}
        contact.revision += 1
        service.audit(db, project_id, contact.id, "attachment", None, entry, actor)
        return entry
    return run(db, action)


@router.get("/contacts/{row_id}/attachments/{attachment_id}")
def download_attachment(project_id: UUID, row_id: UUID, attachment_id: UUID, db: Session = Depends(get_db)):
    from annotation_paired_models import PairedAttachment
    from fastapi.responses import Response
    from urllib.parse import quote
    service.scoped(db, PairedContact, project_id, row_id)
    row = db.get(PairedAttachment, attachment_id)
    if row is None or row.contact_id != row_id:
        raise HTTPException(404, "附件不存在")
    return Response(row.content, media_type="application/octet-stream", headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(row.name), "X-Content-Type-Options": "nosniff"})


@router.post("/groups", dependencies=write)
def create_group(project_id: UUID, payload: GroupWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return run(db, lambda: service.save_group(db, project_id, payload, actor))


@router.put("/groups/{row_id}", dependencies=write)
def update_group(project_id: UUID, row_id: UUID, payload: GroupWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return run(db, lambda: service.save_group(db, project_id, payload, actor, row_id))


@router.post("/tasks", dependencies=write)
def create_task(project_id: UUID, payload: TaskWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return run(db, lambda: service.save_task(db, project_id, payload, actor))


@router.put("/tasks/{row_id}", dependencies=write)
def update_task(project_id: UUID, row_id: UUID, payload: TaskWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return run(db, lambda: service.save_task(db, project_id, payload, actor, row_id))


@router.post("/transfer", dependencies=write)
def transfer(project_id: UUID, payload: TransferWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return run(db, lambda: service.transfer(db, project_id, payload, actor))


@router.get("/tasks/{task_id}/records")
def records(project_id: UUID, task_id: UUID, db: Session = Depends(get_db)):
    service.scoped(db, PairedTask, project_id, task_id)
    return [service.plain(row) for row in db.query(PairedRecord).filter_by(task_id=task_id).order_by(PairedRecord.kind, PairedRecord.position)]


def check_account_permission(db, actor, payload):
    from permission_service import user_has_permission
    if payload.kind == "account" and not any(user_has_permission(db, actor.id, code) for code in ("annotation_accounts:read", "annotation_accounts:write")):
        raise HTTPException(403, "引用平台账号需要标注账号查看权限")


@router.post("/tasks/{task_id}/records", dependencies=write)
def create_record(project_id: UUID, task_id: UUID, payload: RecordWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    check_account_permission(db, actor, payload)
    return run(db, lambda: service.save_record(db, project_id, task_id, payload, actor))


@router.put("/tasks/{task_id}/records/{row_id}", dependencies=write)
def update_record(project_id: UUID, task_id: UUID, row_id: UUID, payload: RecordWrite, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    check_account_permission(db, actor, payload)
    return run(db, lambda: service.save_record(db, project_id, task_id, payload, actor, row_id))


@router.delete("/entities/{kind}/{row_id}", dependencies=write)
def delete_row(project_id: UUID, kind: str, row_id: UUID, db: Session = Depends(get_db), actor: AppUser = Depends(get_current_user)):
    return run(db, lambda: service.delete_entity(db, project_id, kind, row_id, actor))


@router.get("/history")
def history(project_id: UUID, entity_id: UUID | None = None, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    service.workspace(db, project_id)
    query = db.query(PairedAudit).filter_by(project_id=project_id)
    if entity_id:
        query = query.filter_by(entity_id=entity_id)
    return {"items": [service.plain(row) for row in query.order_by(PairedAudit.created_at.desc(), PairedAudit.id).offset(skip).limit(limit)], "total": query.count()}
