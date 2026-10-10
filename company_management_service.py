"""公司管理树形栏目、正文与全文检索。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from company_management_models import CompanyManagementSection
from annotation_notice_schemas import (
    AnnotationNoticeReorder,
    AnnotationNoticeSectionCreate,
    AnnotationNoticeSectionEdit,
)
from concurrency import StaleUpdateError, parse_expected_updated_at
from annotation_notice_service import extract_notice_text
from company_management_schemas import CompanyManagementSectionUpdate
from company_management_image_service import commit_removed_images, validate_content_images


BUSINESS_TIMEZONE = timezone(timedelta(hours=8))


def _business_now() -> datetime:
    """无时区数据库字段统一保存 UTC+8，避免依赖服务器的系统时区。"""
    return datetime.now(BUSINESS_TIMEZONE).replace(tzinfo=None)


def _ordered_rows(rows: list[CompanyManagementSection]) -> list[CompanyManagementSection]:
    children: dict[UUID | None, list[CompanyManagementSection]] = defaultdict(list)
    for row in rows:
        children[row.parent_id].append(row)
    for siblings in children.values():
        siblings.sort(key=lambda item: (item.sort_order, str(item.id)))
    ordered: list[CompanyManagementSection] = []
    for root in children[None]:
        ordered.append(root)
        ordered.extend(children[root.id])
    return ordered


def _display_titles(rows: list[CompanyManagementSection]) -> dict[UUID, str]:
    """保留 display_title 响应字段，但不再附加与顺序绑定的字母编号。"""
    return {row.id: row.title for row in rows}


def _serialize(row: CompanyManagementSection, labels: dict[UUID, str], *, include_content: bool) -> dict:
    editor = row.editor
    return {
        "id": row.id,
        "section_key": row.section_key,
        "title": row.title,
        "display_title": labels.get(row.id, row.title),
        "parent_id": row.parent_id,
        "sort_order": row.sort_order,
        "has_content": row.has_content,
        "is_active": row.is_active,
        "content_json": row.content_json if include_content else None,
        "updated_by": row.updated_by,
        "updated_by_name": (editor.full_name or editor.username) if editor else None,
        "updated_at": (
            row.updated_at.replace(tzinfo=BUSINESS_TIMEZONE)
            if row.updated_at is not None and row.updated_at.tzinfo is None
            else row.updated_at
        ),
        "structure_updated_at": row.structure_updated_at,
    }


def _active_rows(db: Session) -> list[CompanyManagementSection]:
    return (
        db.query(CompanyManagementSection)
        .options(joinedload(CompanyManagementSection.editor))
        .filter(CompanyManagementSection.is_active.is_(True))
        .all()
    )


def ensure_company_management_sections(db: Session) -> None:
    """首次安装创建默认栏目；软删除及自定义配置不会被恢复或覆盖。"""
    defaults = (
        ("company_rules", "公司制度"),
        ("human_resources", "人事行政"),
        ("finance_rules", "财务规范"),
        ("templates", "常用模板"),
    )
    existing = {row.section_key for row in db.query(CompanyManagementSection).all()}
    for order, (key, title) in enumerate(defaults, 1):
        if key not in existing:
            db.add(CompanyManagementSection(
                id=uuid4(), section_key=key, title=title, sort_order=order,
                has_content=True, is_active=True, search_text="",
                structure_updated_at=_business_now(),
            ))
    db.commit()

def list_company_management_tree(db: Session) -> list[dict]:
    rows = _active_rows(db)
    labels = _display_titles(rows)
    children: dict[UUID | None, list[CompanyManagementSection]] = defaultdict(list)
    for row in rows:
        children[row.parent_id].append(row)
    for siblings in children.values():
        siblings.sort(key=lambda item: (item.sort_order, str(item.id)))

    def node(row: CompanyManagementSection) -> dict:
        payload = _serialize(row, labels, include_content=False)
        payload["children"] = [node(child) for child in children[row.id]]
        return payload

    return [node(row) for row in children[None]]


def get_company_management_section(db: Session, section_id: UUID) -> dict | None:
    rows = _active_rows(db)
    row = next((item for item in rows if item.id == section_id), None)
    if row is None:
        return None
    return _serialize(row, _display_titles(rows), include_content=True)


def create_company_management_section(
    db: Session, payload: AnnotationNoticeSectionCreate
) -> dict:
    parent = None
    if payload.parent_id:
        parent = db.query(CompanyManagementSection).filter(CompanyManagementSection.id == payload.parent_id).with_for_update().first()
        if not parent or not parent.is_active:
            raise ValueError("父级栏目不存在")
        if parent.parent_id is not None:
            raise ValueError("公司管理最多支持两级栏目")
    siblings = db.query(CompanyManagementSection).filter(
        CompanyManagementSection.parent_id == payload.parent_id,
        CompanyManagementSection.is_active.is_(True),
    ).all()
    now = _business_now()
    row = CompanyManagementSection(
        section_key=f"custom_{uuid4().hex}",
        title=payload.title,
        parent_id=payload.parent_id,
        sort_order=max((item.sort_order for item in siblings), default=0) + 1,
        has_content=payload.has_content,
        is_active=True,
        search_text="",
        structure_updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return get_company_management_section(db, row.id)


def update_company_management_structure(
    db: Session, section_id: UUID, payload: AnnotationNoticeSectionEdit
) -> dict | None:
    row = db.query(CompanyManagementSection).filter(CompanyManagementSection.id == section_id).with_for_update().first()
    if not row or not row.is_active:
        return None
    _assert_version(row.structure_updated_at, payload.expected_structure_updated_at)
    row.title = payload.title
    row.has_content = payload.has_content
    row.structure_updated_at = _business_now()
    db.commit()
    return get_company_management_section(db, row.id)


def delete_company_management_section(db: Session, section_id: UUID) -> bool:
    row = db.query(CompanyManagementSection).filter(CompanyManagementSection.id == section_id).with_for_update().first()
    if not row or not row.is_active:
        return False
    has_children = db.query(CompanyManagementSection.id).filter(
        CompanyManagementSection.parent_id == row.id,
        CompanyManagementSection.is_active.is_(True),
    ).first()
    if has_children:
        raise ValueError("该一级栏目下仍有二级栏目，请先移动或删除二级栏目")
    row.is_active = False
    row.structure_updated_at = _business_now()
    db.commit()
    return True


def reorder_company_management_sections(db: Session, payload: AnnotationNoticeReorder) -> list[dict]:
    rows = db.query(CompanyManagementSection).filter(
        CompanyManagementSection.is_active.is_(True)
    ).with_for_update().all()
    by_id = {row.id: row for row in rows}
    placements = {item.id: item for item in payload.placements}
    if set(placements) != set(by_id):
        raise ValueError("栏目结构已变化，请刷新后重新排序")

    sibling_orders: dict[UUID | None, set[int]] = defaultdict(set)
    for item in payload.placements:
        row = by_id[item.id]
        _assert_version(row.structure_updated_at, item.expected_structure_updated_at)
        if item.parent_id == item.id:
            raise ValueError("栏目不能作为自己的父级")
        if item.parent_id is not None:
            parent = by_id.get(item.parent_id)
            if parent is None or placements[parent.id].parent_id is not None:
                raise ValueError("公司管理最多支持两级栏目")
        if item.sort_order in sibling_orders[item.parent_id]:
            raise ValueError("同级栏目排序不能重复")
        sibling_orders[item.parent_id].add(item.sort_order)

    for parent_id, orders in sibling_orders.items():
        if orders != set(range(1, len(orders) + 1)):
            raise ValueError("同级栏目排序必须连续")

    # 同级排序使用唯一索引，先将全部活动栏目移到临时序号区间，避免交换位置时瞬时冲突。
    temporary_start = max((row.sort_order for row in rows), default=0) + len(rows) + 1000
    for offset, row in enumerate(rows):
        row.sort_order = temporary_start + offset
    db.flush()

    now = _business_now()
    for item in payload.placements:
        row = by_id[item.id]
        row.parent_id = item.parent_id
        row.sort_order = item.sort_order
        row.structure_updated_at = now
    db.commit()
    return list_company_management_tree(db)


def _assert_version(current: datetime | None, expected: datetime | None) -> None:
    parsed = parse_expected_updated_at(expected)
    if (current is None) != (parsed is None):
        raise StaleUpdateError()
    if current is not None and parsed is not None:
        normalized = current.replace(tzinfo=None) if current.tzinfo else current
        if abs((normalized - parsed).total_seconds()) > 0.001:
            raise StaleUpdateError()


def _escape_like_keyword(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _snippet(text: str, keyword: str, size: int = 160) -> str:
    normalized = text or ""
    position = normalized.casefold().find(keyword.casefold())
    if position < 0:
        return normalized[:size]
    start = max(0, position - size // 3)
    end = min(len(normalized), start + size)
    prefix = "…" if start else ""
    suffix = "…" if end < len(normalized) else ""
    return f"{prefix}{normalized[start:end]}{suffix}"


def search_company_management_sections(
    db: Session, keyword: str, skip: int = 0, limit: int = 20
) -> dict:
    normalized = keyword.strip()
    query = db.query(CompanyManagementSection).filter(CompanyManagementSection.is_active.is_(True))
    if normalized:
        pattern = f"%{_escape_like_keyword(normalized)}%"
        query = query.filter(or_(
            CompanyManagementSection.title.ilike(pattern, escape="\\"),
            CompanyManagementSection.search_text.ilike(pattern, escape="\\"),
        ))
    rows = query.all()
    all_rows = _active_rows(db)
    labels = _display_titles(all_rows)
    by_id = {row.id: row for row in all_rows}
    needle = normalized.casefold()
    matches = []
    order_index = {row.id: index for index, row in enumerate(_ordered_rows(all_rows))}
    for row in rows:
        display = labels[row.id]
        matched_title = needle in display.casefold() or needle in row.title.casefold()
        matched_content = row.has_content and needle in (row.search_text or "").casefold()
        if not matched_title and not matched_content:
            continue
        parent = by_id.get(row.parent_id)
        matches.append((not matched_title, order_index[row.id], {
            "id": row.id,
            "section_key": row.section_key,
            "display_title": display,
            "parent_title": parent.title if parent else None,
            "breadcrumb": f"{parent.title} / {display}" if parent else display,
            "snippet": _snippet(row.search_text, normalized) if matched_content else "栏目名称命中",
            "matched_title": matched_title,
            "matched_content": matched_content,
        }))
    matches.sort(key=lambda item: (item[0], item[1]))
    return {"items": [item[2] for item in matches[skip:skip + limit]], "total": len(matches)}


def _update_content(
    db: Session,
    row: CompanyManagementSection,
    payload: CompanyManagementSectionUpdate,
    user_id: UUID,
) -> dict:
    if not row.has_content:
        raise ValueError("该栏目仅用于分组，不能编辑正文")
    _assert_version(row.updated_at, payload.expected_updated_at)
    removed_images = validate_content_images(db, row, payload.content_json)
    row.content_json = payload.content_json
    row.search_text = extract_notice_text(payload.content_json)
    row.updated_by = user_id
    row.updated_at = _business_now()
    commit_removed_images(db, removed_images)
    return get_company_management_section(db, row.id)


def update_company_management_content(
    db: Session, section_id: UUID, payload: CompanyManagementSectionUpdate, user_id: UUID
) -> dict | None:
    row = db.query(CompanyManagementSection).filter(
        CompanyManagementSection.id == section_id,
        CompanyManagementSection.is_active.is_(True),
    ).with_for_update().first()
    return _update_content(db, row, payload, user_id) if row else None


