"""稿件安排模块的业务逻辑。"""
from __future__ import annotations

import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from mail_service import send_plain_text_email
from manuscript_models import (
    ManuscriptArrangement,
    ManuscriptDeliveryMilestone,
    ManuscriptDispatch,
)
from manuscript_schemas import (
    ManuscriptArrangementCreate,
    ManuscriptArrangementUpdate,
    ManuscriptAssignmentInput,
    ManuscriptDispatchCreate,
    ManuscriptDispatchUpdate,
    ManuscriptSettlementUpdate,
)
from models import AppUser, TranslationProject, TranslationSubOrder, Translator
from workflow_crud import get_active_projects


ORDER_STATUS_TRANSLATOR_ASSIGNED = "translator_assigned"
ORDER_STATUS_SENT_TO_TRANSLATOR = "sent_to_translator"
ORDER_STATUS_CONFIRMED = "confirmed"
MANUSCRIPT_MANAGED_ORDER_STATUSES = {
    ORDER_STATUS_TRANSLATOR_ASSIGNED,
    ORDER_STATUS_SENT_TO_TRANSLATOR,
}


def _preferred_email(translator: Translator) -> Optional[str]:
    """优先使用邮箱 1，邮箱 1 为空时使用邮箱 2。"""
    for value in (translator.email1, translator.email2):
        normalized = (value or "").strip()
        if normalized:
            return normalized
    return None


def _default_subject(order_no: str, project_name: str) -> str:
    return f"稿件安排｜{order_no}｜{project_name}"


def _default_body(
    translator_name: str,
    order_no: str,
    project_name: str,
    planned_delivery_at: Optional[datetime.datetime],
    *,
    translation_scope: Optional[str] = None,
    planned_word_count: Optional[int] = None,
) -> str:
    delivery_text = (
        planned_delivery_at.strftime("%Y-%m-%d %H:%M")
        if planned_delivery_at
        else "待确认"
    )
    scope_text = (translation_scope or "").strip() or "以项目经理提供的稿件为准"
    word_text = str(planned_word_count) if planned_word_count is not None else "待确认"
    return (
        f"{translator_name}您好：\n\n"
        f"现安排您处理以下稿件：\n"
        f"订单号：{order_no}\n"
        f"项目名称：{project_name}\n"
        f"需翻译部分：{scope_text}\n"
        f"预定字数：{word_text}\n"
        f"全稿预定时间：{delivery_text}\n\n"
        "请以项目经理提供的稿件文件和最终要求为准。"
    )


def _load_dispatch(
    db: Session,
    dispatch_id: UUID,
) -> Optional[ManuscriptDispatch]:
    return (
        db.query(ManuscriptDispatch)
        .options(
            joinedload(ManuscriptDispatch.arrangements).joinedload(
                ManuscriptArrangement.milestones
            )
        )
        .filter(ManuscriptDispatch.id == dispatch_id)
        .first()
    )


def _load_entity(
    db: Session,
    entity_type: str,
    translation_project_id: UUID,
    sub_order_id: Optional[UUID],
) -> tuple[TranslationProject, Optional[TranslationSubOrder]]:
    project = (
        db.query(TranslationProject)
        .filter(TranslationProject.id == translation_project_id)
        .first()
    )
    if not project:
        raise LookupError("项目不存在")

    sub_order = None
    if entity_type == "suborder":
        sub_order = (
            db.query(TranslationSubOrder)
            .filter(
                TranslationSubOrder.id == sub_order_id,
                TranslationSubOrder.parent_project_id == project.id,
            )
            .first()
        )
        if not sub_order:
            raise LookupError("子订单不存在或不属于所选项目")
    elif sub_order_id is not None:
        raise ValueError("母订单稿件安排不能提供子订单 ID")
    return project, sub_order


def _entity_values(
    project: TranslationProject,
    sub_order: Optional[TranslationSubOrder],
) -> dict:
    if sub_order:
        return {
            "order_no": sub_order.sub_order_no,
            "project_name": sub_order.sub_project_name or project.project_name,
            "network_file_path": (
                sub_order.network_file_path or project.network_file_path
            ),
            "customer_deadline_time": (
                sub_order.customer_deadline_time or project.customer_deadline_time
            ),
        }
    return {
        "order_no": project.order_no,
        "project_name": project.project_name,
        "network_file_path": project.network_file_path,
        "customer_deadline_time": project.customer_deadline_time,
    }


def _final_delivery_at(
    milestones: list,
) -> Optional[datetime.datetime]:
    final = next(
        (item for item in milestones if item.milestone_type == "final"),
        None,
    )
    return final.planned_at if final else None


def _validate_deadline_warning(
    assignment: ManuscriptAssignmentInput,
    customer_deadline_time: Optional[datetime.datetime],
) -> bool:
    """返回是否超过客户交稿时间；该规则只用于提示，不阻止保存。"""
    if not customer_deadline_time:
        return False
    final_at = _final_delivery_at(assignment.milestones)
    return bool(final_at and final_at > customer_deadline_time)


def _apply_milestones(
    arrangement: ManuscriptArrangement,
    assignment: ManuscriptAssignmentInput,
) -> None:
    arrangement.milestones.clear()
    for item in sorted(assignment.milestones, key=lambda row: row.sequence_no):
        arrangement.milestones.append(
            ManuscriptDeliveryMilestone(
                milestone_type=item.milestone_type,
                name=item.name.strip(),
                sequence_no=item.sequence_no,
                planned_at=item.planned_at,
            )
        )
    arrangement.planned_delivery_at = _final_delivery_at(assignment.milestones)


def _create_arrangement_line(
    db: Session,
    dispatch: ManuscriptDispatch,
    assignment: ManuscriptAssignmentInput,
    current_user: AppUser,
    entity_values: dict,
) -> ManuscriptArrangement:
    translator = (
        db.query(Translator)
        .filter(Translator.id == assignment.translator_id)
        .first()
    )
    if not translator:
        raise LookupError("译员不存在")

    final_delivery_at = _final_delivery_at(assignment.milestones)
    email_subject = (assignment.email_subject or "").strip() or _default_subject(
        entity_values["order_no"],
        entity_values["project_name"],
    )
    email_body = (assignment.email_body or "").strip() or _default_body(
        translator.translator_name,
        entity_values["order_no"],
        entity_values["project_name"],
        final_delivery_at,
        translation_scope=assignment.translation_scope,
        planned_word_count=assignment.planned_word_count,
    )
    arrangement = ManuscriptArrangement(
        entity_type=dispatch.entity_type,
        translation_project_id=dispatch.translation_project_id,
        sub_order_id=dispatch.sub_order_id,
        translator_id=translator.id,
        order_no_snapshot=entity_values["order_no"],
        project_name_snapshot=entity_values["project_name"],
        translator_name_snapshot=translator.translator_name,
        cooperation_type_snapshot=translator.cooperation_type,
        recipient_email=_preferred_email(translator),
        planned_word_count=assignment.planned_word_count,
        actual_word_count=assignment.actual_word_count,
        word_count_type=assignment.word_count_type,
        translation_scope=(assignment.translation_scope or "").strip() or None,
        settlement_method=assignment.settlement_method,
        custom_settlement_method=(
            (assignment.custom_settlement_method or "").strip() or None
        ),
        translator_unit_price=assignment.translator_unit_price,
        translator_total_price=assignment.translator_total_price,
        manuscript_source_path=entity_values["network_file_path"],
        email_subject=email_subject,
        email_body=email_body,
        remarks=assignment.remarks,
        status="draft",
        created_by=current_user.id,
        created_by_name=current_user.full_name or current_user.username,
    )
    _apply_milestones(arrangement, assignment)
    return arrangement


def get_arrangement_context(
    db: Session,
    *,
    keyword: Optional[str] = None,
    project_limit: int = 100,
) -> dict:
    active_projects = get_active_projects(
        db,
        skip=0,
        limit=project_limit,
        keyword=keyword,
    )
    project_ids = {
        item["translation_project_id"]
        for item in active_projects["items"]
    }
    sub_order_ids = {
        item["sub_order_id"]
        for item in active_projects["items"]
        if item["entity_type"] == "suborder" and item["sub_order_id"]
    }
    project_status_map = {
        row.id: row.project_status
        for row in (
            db.query(TranslationProject.id, TranslationProject.project_status)
            .filter(TranslationProject.id.in_(project_ids))
            .all()
            if project_ids
            else []
        )
    }
    sub_order_status_map = {
        row.id: row.status
        for row in (
            db.query(TranslationSubOrder.id, TranslationSubOrder.status)
            .filter(TranslationSubOrder.id.in_(sub_order_ids))
            .all()
            if sub_order_ids
            else []
        )
    }
    for item in active_projects["items"]:
        item["project_status"] = (
            sub_order_status_map.get(item["sub_order_id"])
            if item["entity_type"] == "suborder"
            else project_status_map.get(item["translation_project_id"])
        )

    translators = (
        db.query(Translator)
        .filter(or_(Translator.status != "inactive", Translator.status.is_(None)))
        .order_by(
            Translator.default_priority.asc().nullslast(),
            Translator.translator_name.asc(),
        )
        .all()
    )
    return {
        "active_projects": active_projects,
        "translators": [
            {
                "id": row.id,
                "translator_code": row.translator_code,
                "translator_name": row.translator_name,
                "cooperation_type": row.cooperation_type,
                "status": row.status,
                "languages": row.languages,
                "translation_type": row.translation_type,
                "direction": row.direction,
                "quality_score": row.quality_score,
                "email1": row.email1,
                "email2": row.email2,
                "available_time_slot": row.available_time_slot,
                "daily_word_capacity": row.daily_word_capacity,
                "can_cloud_edit": row.can_cloud_edit,
                "can_revision": row.can_revision,
                "domain_skills": row.domain_skills or [],
                "remarks": row.remarks,
            }
            for row in translators
        ],
    }


def list_dispatches(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 200,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
) -> list[ManuscriptDispatch]:
    query = db.query(ManuscriptDispatch).options(
        joinedload(ManuscriptDispatch.arrangements).joinedload(
            ManuscriptArrangement.milestones
        )
    )
    if status:
        query = query.filter(ManuscriptDispatch.status == status)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        matching_dispatch_ids = (
            db.query(ManuscriptArrangement.dispatch_id)
            .filter(
                or_(
                    ManuscriptArrangement.translator_name_snapshot.ilike(pattern),
                    ManuscriptArrangement.recipient_email.ilike(pattern),
                )
            )
        )
        query = query.filter(
            or_(
                ManuscriptDispatch.order_no_snapshot.ilike(pattern),
                ManuscriptDispatch.project_name_snapshot.ilike(pattern),
                ManuscriptDispatch.id.in_(matching_dispatch_ids),
            )
        )
    return (
        query.order_by(ManuscriptDispatch.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_arrangements(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 200,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
) -> list[ManuscriptArrangement]:
    query = db.query(ManuscriptArrangement).options(
        joinedload(ManuscriptArrangement.milestones)
    )
    if status:
        query = query.filter(ManuscriptArrangement.status == status)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                ManuscriptArrangement.order_no_snapshot.ilike(pattern),
                ManuscriptArrangement.project_name_snapshot.ilike(pattern),
                ManuscriptArrangement.translator_name_snapshot.ilike(pattern),
                ManuscriptArrangement.recipient_email.ilike(pattern),
            )
        )
    return (
        query.order_by(ManuscriptArrangement.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_arrangement(
    db: Session,
    arrangement_id: UUID,
) -> Optional[ManuscriptArrangement]:
    return (
        db.query(ManuscriptArrangement)
        .options(joinedload(ManuscriptArrangement.milestones))
        .filter(ManuscriptArrangement.id == arrangement_id)
        .first()
    )


def create_dispatch(
    db: Session,
    payload: ManuscriptDispatchCreate,
    current_user: AppUser,
) -> ManuscriptDispatch:
    project, sub_order = _load_entity(
        db,
        payload.entity_type,
        payload.translation_project_id,
        payload.sub_order_id,
    )
    values = _entity_values(project, sub_order)
    dispatch = ManuscriptDispatch(
        entity_type=payload.entity_type,
        translation_project_id=project.id,
        sub_order_id=sub_order.id if sub_order else None,
        order_no_snapshot=values["order_no"],
        project_name_snapshot=values["project_name"],
        status="draft",
        remarks=payload.remarks,
        created_by=current_user.id,
        created_by_name=current_user.full_name or current_user.username,
    )
    db.add(dispatch)
    for assignment in payload.arrangements:
        _validate_deadline_warning(
            assignment,
            values["customer_deadline_time"],
        )
        dispatch.arrangements.append(
            _create_arrangement_line(
                db,
                dispatch,
                assignment,
                current_user,
                values,
            )
        )
    db.commit()
    return _load_dispatch(db, dispatch.id)


def update_dispatch(
    db: Session,
    dispatch_id: UUID,
    payload: ManuscriptDispatchUpdate,
    current_user: AppUser,
) -> Optional[ManuscriptDispatch]:
    dispatch = _load_dispatch(db, dispatch_id)
    if not dispatch:
        return None
    if dispatch.status != "draft":
        raise ValueError("只有草稿批次可以整体编辑")

    project, sub_order = _load_entity(
        db,
        payload.entity_type,
        payload.translation_project_id,
        payload.sub_order_id,
    )
    values = _entity_values(project, sub_order)
    dispatch.entity_type = payload.entity_type
    dispatch.translation_project_id = project.id
    dispatch.sub_order_id = sub_order.id if sub_order else None
    dispatch.order_no_snapshot = values["order_no"]
    dispatch.project_name_snapshot = values["project_name"]
    dispatch.remarks = payload.remarks
    dispatch.updated_at = datetime.datetime.now()
    dispatch.arrangements.clear()
    db.flush()
    for assignment in payload.arrangements:
        dispatch.arrangements.append(
            _create_arrangement_line(
                db,
                dispatch,
                assignment,
                current_user,
                values,
            )
        )
    db.commit()
    return _load_dispatch(db, dispatch.id)


def _sync_dispatch_status(dispatch: ManuscriptDispatch) -> None:
    if dispatch.status == "cancelled":
        return
    active = [item for item in dispatch.arrangements if item.status != "cancelled"]
    if not active:
        dispatch.status = "cancelled"
    elif all(item.status == "sent" for item in active):
        dispatch.status = "sent"
    elif any(item.status == "sent" for item in active):
        dispatch.status = "partially_sent"
    elif dispatch.confirmed_at:
        dispatch.status = "ready"
    else:
        dispatch.status = "draft"
    dispatch.updated_at = datetime.datetime.now()


def _set_order_status(
    project: TranslationProject,
    sub_order: Optional[TranslationSubOrder],
    target_status: str,
) -> None:
    """在当前事务内直接更新母项目或对应子订单的业务状态。"""
    now = datetime.datetime.now()
    if sub_order:
        sub_order.status = target_status
        sub_order.updated_at = now
    else:
        project.project_status = target_status
        project.updated_at = now


def _get_order_status(
    project: TranslationProject,
    sub_order: Optional[TranslationSubOrder],
) -> Optional[str]:
    return sub_order.status if sub_order else project.project_status


def _get_previous_order_status(
    db: Session,
    dispatch: ManuscriptDispatch,
    project: TranslationProject,
    sub_order: Optional[TranslationSubOrder],
) -> str:
    """保存确认安排前的状态；多批次沿用首次派稿前的状态。"""
    current_status = _get_order_status(project, sub_order)
    if current_status not in MANUSCRIPT_MANAGED_ORDER_STATUSES:
        return current_status or ORDER_STATUS_CONFIRMED

    query = db.query(ManuscriptDispatch).filter(
        ManuscriptDispatch.id != dispatch.id,
        ManuscriptDispatch.translation_project_id == project.id,
        ManuscriptDispatch.status != "cancelled",
        ManuscriptDispatch.confirmed_at.is_not(None),
    )
    if sub_order:
        query = query.filter(ManuscriptDispatch.sub_order_id == sub_order.id)
    else:
        query = query.filter(ManuscriptDispatch.sub_order_id.is_(None))
    previous_dispatch = query.order_by(
        ManuscriptDispatch.confirmed_at.desc()
    ).first()
    previous_status = (
        previous_dispatch.previous_order_status if previous_dispatch else None
    )
    if previous_status in MANUSCRIPT_MANAGED_ORDER_STATUSES:
        return ORDER_STATUS_CONFIRMED
    return previous_status or ORDER_STATUS_CONFIRMED


def _sync_order_status(
    db: Session,
    project: TranslationProject,
    sub_order: Optional[TranslationSubOrder],
) -> Optional[str]:
    query = (
        db.query(ManuscriptArrangement)
        .join(
            ManuscriptDispatch,
            ManuscriptDispatch.id == ManuscriptArrangement.dispatch_id,
        )
        .filter(
            ManuscriptArrangement.translation_project_id == project.id,
            ManuscriptArrangement.status != "cancelled",
            ManuscriptDispatch.status != "cancelled",
            ManuscriptDispatch.confirmed_at.is_not(None),
        )
    )
    if sub_order:
        query = query.filter(ManuscriptArrangement.sub_order_id == sub_order.id)
    else:
        query = query.filter(ManuscriptArrangement.sub_order_id.is_(None))
    lines = query.all()
    if not lines:
        return None
    target_status = (
        ORDER_STATUS_SENT_TO_TRANSLATOR
        if all(item.status == "sent" for item in lines)
        else ORDER_STATUS_TRANSLATOR_ASSIGNED
    )
    _set_order_status(project, sub_order, target_status)
    return target_status


def confirm_dispatch(
    db: Session,
    dispatch_id: UUID,
    current_user: AppUser,
) -> Optional[ManuscriptDispatch]:
    dispatch = _load_dispatch(db, dispatch_id)
    if not dispatch:
        return None
    if dispatch.status != "draft":
        raise ValueError("只有草稿批次可以确认")
    if not dispatch.arrangements:
        raise ValueError("派稿批次至少需要一位译员")

    project, sub_order = _load_entity(
        db,
        dispatch.entity_type,
        dispatch.translation_project_id,
        dispatch.sub_order_id,
    )
    now = datetime.datetime.now()
    for arrangement in dispatch.arrangements:
        translator = (
            db.query(Translator)
            .filter(Translator.id == arrangement.translator_id)
            .first()
        )
        if not translator:
            raise LookupError(f"译员 {arrangement.translator_name_snapshot} 不存在")
        if translator.status == "inactive":
            raise ValueError(
                f"已停用的译员 {translator.translator_name} 不能确认派稿"
            )
        arrangement.translator_name_snapshot = translator.translator_name
        arrangement.cooperation_type_snapshot = translator.cooperation_type
        arrangement.recipient_email = _preferred_email(translator)
        arrangement.status = "ready"
        arrangement.updated_at = now

    dispatch.status = "ready"
    dispatch.confirmed_at = now
    dispatch.updated_at = now
    project.major_project_manager_confirmation = current_user.username
    dispatch.previous_order_status = _get_previous_order_status(
        db,
        dispatch,
        project,
        sub_order,
    )
    # “确认安排”是明确的业务动作，直接写入“已排译员”，不依赖回查时的自动刷新。
    _set_order_status(project, sub_order, ORDER_STATUS_TRANSLATOR_ASSIGNED)
    db.commit()
    return _load_dispatch(db, dispatch.id)


def cancel_dispatch(
    db: Session,
    dispatch_id: UUID,
) -> Optional[ManuscriptDispatch]:
    dispatch = _load_dispatch(db, dispatch_id)
    if not dispatch:
        return None
    if any(item.status == "sent" for item in dispatch.arrangements):
        raise ValueError("包含已发送明细的批次不能整体取消")
    was_confirmed = dispatch.confirmed_at is not None
    now = datetime.datetime.now()
    for arrangement in dispatch.arrangements:
        arrangement.status = "cancelled"
        arrangement.updated_at = now
    dispatch.status = "cancelled"
    dispatch.cancelled_at = now
    dispatch.updated_at = now
    project, sub_order = _load_entity(
        db,
        dispatch.entity_type,
        dispatch.translation_project_id,
        dispatch.sub_order_id,
    )
    # Session 关闭了 autoflush，必须先落盘取消状态，后续回查才不会把本批次误算为有效安排。
    db.flush()
    remaining_status = _sync_order_status(db, project, sub_order)
    current_status = _get_order_status(project, sub_order)
    if (
        was_confirmed
        and remaining_status is None
        and current_status in MANUSCRIPT_MANAGED_ORDER_STATUSES
    ):
        rollback_status = dispatch.previous_order_status or ORDER_STATUS_CONFIRMED
        if rollback_status in MANUSCRIPT_MANAGED_ORDER_STATUSES:
            rollback_status = ORDER_STATUS_CONFIRMED
        _set_order_status(project, sub_order, rollback_status)
    db.commit()
    return _load_dispatch(db, dispatch.id)


def create_arrangement(
    db: Session,
    payload: ManuscriptArrangementCreate,
    current_user: AppUser,
) -> ManuscriptArrangement:
    milestones = []
    if payload.planned_delivery_at:
        from manuscript_schemas import ManuscriptMilestoneInput

        milestones = [
            ManuscriptMilestoneInput(
                milestone_type="final",
                name="全稿",
                sequence_no=1,
                planned_at=payload.planned_delivery_at,
            )
        ]
    dispatch_payload = ManuscriptDispatchCreate(
        entity_type=payload.entity_type,
        translation_project_id=payload.translation_project_id,
        sub_order_id=payload.sub_order_id,
        remarks=None,
        arrangements=[
            ManuscriptAssignmentInput(
                translator_id=payload.translator_id,
                planned_word_count=payload.planned_word_count,
                actual_word_count=payload.actual_word_count,
                word_count_type=payload.word_count_type,
                translation_scope=payload.translation_scope,
                settlement_method=payload.settlement_method,
                custom_settlement_method=payload.custom_settlement_method,
                translator_unit_price=payload.translator_unit_price,
                translator_total_price=payload.translator_total_price,
                email_subject=payload.email_subject,
                email_body=payload.email_body,
                remarks=payload.remarks,
                milestones=milestones,
            )
        ],
    )
    dispatch = create_dispatch(db, dispatch_payload, current_user)
    confirmed = confirm_dispatch(db, dispatch.id, current_user)
    return confirmed.arrangements[0]


def send_arrangement(
    db: Session,
    arrangement_id: UUID,
) -> Optional[ManuscriptArrangement]:
    arrangement = get_arrangement(db, arrangement_id)
    if not arrangement:
        return None
    if arrangement.status == "sent":
        return arrangement
    if arrangement.status not in {"ready", "failed"}:
        raise ValueError("只有已确认安排或发送失败的稿件才能执行发送")

    translator = (
        db.query(Translator)
        .filter(Translator.id == arrangement.translator_id)
        .first()
    )
    if not translator:
        raise LookupError("译员不存在")
    if translator.status == "inactive":
        raise ValueError("已停用的译员不能发送稿件")
    if not arrangement.recipient_email:
        raise ValueError("译员资料中缺少收件邮箱")

    project, sub_order = _load_entity(
        db,
        arrangement.entity_type,
        arrangement.translation_project_id,
        arrangement.sub_order_id,
    )
    now = datetime.datetime.now()
    arrangement.send_attempted_at = now
    arrangement.send_error = None
    arrangement.updated_at = now
    message_id = f"<manuscript-{arrangement.id}@xinshi-system.local>"
    try:
        send_result = send_plain_text_email(
            recipient_email=arrangement.recipient_email,
            subject=arrangement.email_subject,
            body=arrangement.email_body,
            message_id=message_id,
        )
    except Exception as exc:
        arrangement.status = "failed"
        arrangement.send_error = str(exc)[:5000]
        if arrangement.dispatch:
            _sync_dispatch_status(arrangement.dispatch)
        _sync_order_status(db, project, sub_order)
        db.commit()
        raise

    arrangement.delivery_recipient = send_result.delivery_recipient
    arrangement.delivery_mode = send_result.delivery_mode
    arrangement.smtp_message_id = send_result.message_id
    arrangement.status = "sent"
    arrangement.sent_at = now
    arrangement.updated_at = now
    if arrangement.dispatch:
        _sync_dispatch_status(arrangement.dispatch)
    _sync_order_status(db, project, sub_order)
    db.commit()
    return get_arrangement(db, arrangement.id)


def send_dispatch(
    db: Session,
    dispatch_id: UUID,
) -> tuple[ManuscriptDispatch, int, int, int]:
    dispatch = _load_dispatch(db, dispatch_id)
    if not dispatch:
        raise LookupError("派稿批次不存在")
    if dispatch.status not in {"ready", "partially_sent"}:
        raise ValueError("只有已确认或部分发送的批次可以批量发送")

    sent_count = 0
    failed_count = 0
    skipped_count = 0
    for arrangement in list(dispatch.arrangements):
        if arrangement.status == "sent" or arrangement.status == "cancelled":
            skipped_count += 1
            continue
        try:
            send_arrangement(db, arrangement.id)
            sent_count += 1
        except Exception:
            failed_count += 1
    refreshed = _load_dispatch(db, dispatch_id)
    return refreshed, sent_count, failed_count, skipped_count


def update_settlement(
    db: Session,
    arrangement_id: UUID,
    payload: ManuscriptSettlementUpdate,
) -> Optional[ManuscriptArrangement]:
    arrangement = get_arrangement(db, arrangement_id)
    if not arrangement:
        return None
    if arrangement.status == "cancelled":
        raise ValueError("已取消的译员明细不能更新结算信息")
    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("settlement_method") != "other":
        update_data["custom_settlement_method"] = None
    for field, value in update_data.items():
        setattr(arrangement, field, value)
    arrangement.updated_at = datetime.datetime.now()
    db.commit()
    return get_arrangement(db, arrangement.id)


def update_arrangement(
    db: Session,
    arrangement_id: UUID,
    payload: ManuscriptArrangementUpdate,
) -> Optional[ManuscriptArrangement]:
    arrangement = get_arrangement(db, arrangement_id)
    if not arrangement:
        return None
    if arrangement.status not in {"draft", "failed", "sent", "ready"}:
        raise ValueError("当前状态的稿件安排不能修改")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(arrangement, field, value)
    if "planned_delivery_at" in update_data:
        final = next(
            (
                item
                for item in arrangement.milestones
                if item.milestone_type == "final"
            ),
            None,
        )
        if final:
            final.planned_at = update_data["planned_delivery_at"]
            final.updated_at = datetime.datetime.now()
    arrangement.updated_at = datetime.datetime.now()
    db.commit()
    return get_arrangement(db, arrangement.id)


def delete_arrangement(db: Session, arrangement_id: UUID) -> bool:
    arrangement = get_arrangement(db, arrangement_id)
    if not arrangement:
        return False
    if arrangement.status not in {"draft", "failed", "cancelled"}:
        raise ValueError("只有未发送的稿件安排可以删除")
    dispatch = arrangement.dispatch
    db.delete(arrangement)
    db.flush()
    if dispatch and not dispatch.arrangements:
        db.delete(dispatch)
    elif dispatch:
        _sync_dispatch_status(dispatch)
    db.commit()
    return True
