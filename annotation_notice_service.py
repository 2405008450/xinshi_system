"""标注须知树形栏目、正文与全文检索。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re
from uuid import UUID, uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from annotation_notice_models import AnnotationNoticeSection
from annotation_notice_schemas import (
    AnnotationNoticeReorder,
    AnnotationNoticeSectionCreate,
    AnnotationNoticeSectionEdit,
    AnnotationNoticeSectionUpdate,
)
from concurrency import StaleUpdateError, parse_expected_updated_at


# 保留该常量，兼容既有调用和固定栏目顺序测试；数据库初始化后不再覆盖用户调整。
ANNOTATION_NOTICE_SECTIONS = (
    ("customer_quote", "A. 客户报价"),
    ("annotator_quote", "B. 标注员报价"),
    ("trial_collection", "C. 试标/试采流程"),
    ("audio_collection", "D. 音频采集流程"),
    ("audio_annotation", "E. 音频标注流程"),
    ("audio_evaluation", "F. 音频评测流程"),
    ("text_evaluation", "G. 文本评测流程"),
    ("quality_inspection", "H. 质检流程"),
    ("listening_test", "I. 测听流程"),
    ("slot_deduction", "J. 扣槽流程"),
    ("generalization", "K. 泛化流程"),
    ("translation", "L. 翻译流程"),
    ("ai_evaluation", "M. AI评测流程"),
)

_DEFAULT_ROOTS = (
    ("customer_quote", "客户报价", 1, True),
    ("annotator_quote", "标注员报价", 2, True),
    ("trial_collection", "试标/试采流程", 3, True),
    ("project_flow", "项目流程", 4, False),
)
_DEFAULT_CHILDREN = (
    ("audio_collection", "音频采集流程"),
    ("audio_annotation", "音频标注流程"),
    ("audio_evaluation", "音频评测流程"),
    ("text_evaluation", "文本评测流程"),
    ("quality_inspection", "质检流程"),
    ("listening_test", "测听流程"),
    ("slot_deduction", "扣槽流程"),
    ("generalization", "泛化流程"),
    ("translation", "翻译流程"),
    ("ai_evaluation", "AI评测流程"),
)


def extract_notice_text(document: dict | None) -> str:
    """从受控 TipTap JSON 中提取可搜索纯文本。"""
    chunks: list[str] = []

    def visit(node) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            chunks.append(node["text"])
        elif node.get("type") in {"hardBreak", "paragraph", "heading", "listItem"} and chunks:
            chunks.append("\n")
        for child in node.get("content") or []:
            visit(child)

    visit(document)
    return re.sub(r"[ \t]+", " ", "".join(chunks)).strip()


def _alpha_label(index: int) -> str:
    value = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        value = chr(65 + remainder) + value
    return value


def _ordered_rows(rows: list[AnnotationNoticeSection]) -> list[AnnotationNoticeSection]:
    children: dict[UUID | None, list[AnnotationNoticeSection]] = defaultdict(list)
    for row in rows:
        children[row.parent_id].append(row)
    for siblings in children.values():
        siblings.sort(key=lambda item: (item.sort_order, str(item.id)))
    ordered: list[AnnotationNoticeSection] = []
    for root in children[None]:
        ordered.append(root)
        ordered.extend(children[root.id])
    return ordered


def _display_titles(rows: list[AnnotationNoticeSection]) -> dict[UUID, str]:
    labels: dict[UUID, str] = {}
    number = 0
    for row in _ordered_rows(rows):
        if row.has_content:
            number += 1
            labels[row.id] = f"{_alpha_label(number)}. {row.title}"
        else:
            labels[row.id] = row.title
    return labels


def _serialize(row: AnnotationNoticeSection, labels: dict[UUID, str], *, include_content: bool) -> dict:
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
        "updated_at": row.updated_at,
        "structure_updated_at": row.structure_updated_at,
    }


def _active_rows(db: Session) -> list[AnnotationNoticeSection]:
    return (
        db.query(AnnotationNoticeSection)
        .options(joinedload(AnnotationNoticeSection.editor))
        .filter(AnnotationNoticeSection.is_active.is_(True))
        .all()
    )


def ensure_annotation_notice_sections(db: Session) -> None:
    """仅为全新数据库补齐初始栏目，初始化完成后不覆盖用户配置。"""
    existing = {row.section_key: row for row in db.query(AnnotationNoticeSection).all()}
    changed = False
    now = datetime.now()
    for key, title, order, has_content in _DEFAULT_ROOTS:
        if key not in existing:
            row = AnnotationNoticeSection(
                section_key=key, title=title, sort_order=order,
                has_content=has_content, is_active=True, search_text="",
                structure_updated_at=now,
            )
            db.add(row)
            existing[key] = row
            changed = True
    if changed:
        db.flush()
    parent = existing["project_flow"]
    for order, (key, title) in enumerate(_DEFAULT_CHILDREN, start=1):
        if key not in existing:
            db.add(AnnotationNoticeSection(
                section_key=key, title=title, parent_id=parent.id,
                sort_order=order, has_content=True, is_active=True,
                search_text="", structure_updated_at=now,
            ))
            changed = True
    if changed:
        db.commit()


def list_annotation_notice_tree(db: Session) -> list[dict]:
    ensure_annotation_notice_sections(db)
    rows = _active_rows(db)
    labels = _display_titles(rows)
    children: dict[UUID | None, list[AnnotationNoticeSection]] = defaultdict(list)
    for row in rows:
        children[row.parent_id].append(row)
    for siblings in children.values():
        siblings.sort(key=lambda item: (item.sort_order, str(item.id)))

    def node(row: AnnotationNoticeSection) -> dict:
        payload = _serialize(row, labels, include_content=False)
        payload["children"] = [node(child) for child in children[row.id]]
        return payload

    return [node(row) for row in children[None]]


def list_annotation_notice_sections(db: Session) -> list[dict]:
    """旧平铺接口：只返回正文栏目，并让旧客户端继续读取带编号的 title。"""
    ensure_annotation_notice_sections(db)
    rows = _active_rows(db)
    labels = _display_titles(rows)
    payloads = []
    for row in _ordered_rows(rows):
        if not row.has_content:
            continue
        payload = _serialize(row, labels, include_content=True)
        payload["title"] = payload["display_title"]
        payloads.append(payload)
    return payloads


def get_annotation_notice_section(db: Session, section_id: UUID) -> dict | None:
    rows = _active_rows(db)
    row = next((item for item in rows if item.id == section_id), None)
    if row is None:
        return None
    return _serialize(row, _display_titles(rows), include_content=True)


def create_annotation_notice_section(
    db: Session, payload: AnnotationNoticeSectionCreate
) -> dict:
    parent = None
    if payload.parent_id:
        parent = db.get(AnnotationNoticeSection, payload.parent_id)
        if not parent or not parent.is_active:
            raise ValueError("父级栏目不存在")
        if parent.parent_id is not None:
            raise ValueError("标注须知最多支持两级栏目")
    siblings = db.query(AnnotationNoticeSection).filter(
        AnnotationNoticeSection.parent_id == payload.parent_id,
        AnnotationNoticeSection.is_active.is_(True),
    ).all()
    now = datetime.now()
    row = AnnotationNoticeSection(
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
    return get_annotation_notice_section(db, row.id)


def update_annotation_notice_structure(
    db: Session, section_id: UUID, payload: AnnotationNoticeSectionEdit
) -> dict | None:
    row = db.get(AnnotationNoticeSection, section_id)
    if not row or not row.is_active:
        return None
    _assert_version(row.structure_updated_at, payload.expected_structure_updated_at)
    row.title = payload.title
    row.has_content = payload.has_content
    row.structure_updated_at = datetime.now()
    db.commit()
    return get_annotation_notice_section(db, row.id)


def delete_annotation_notice_section(db: Session, section_id: UUID) -> bool:
    row = db.get(AnnotationNoticeSection, section_id)
    if not row or not row.is_active:
        return False
    has_children = db.query(AnnotationNoticeSection.id).filter(
        AnnotationNoticeSection.parent_id == row.id,
        AnnotationNoticeSection.is_active.is_(True),
    ).first()
    if has_children:
        raise ValueError("该一级栏目下仍有二级栏目，请先移动或删除二级栏目")
    row.is_active = False
    row.structure_updated_at = datetime.now()
    db.commit()
    return True


def reorder_annotation_notice_sections(db: Session, payload: AnnotationNoticeReorder) -> list[dict]:
    rows = db.query(AnnotationNoticeSection).filter(
        AnnotationNoticeSection.is_active.is_(True)
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
                raise ValueError("标注须知最多支持两级栏目")
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

    now = datetime.now()
    for item in payload.placements:
        row = by_id[item.id]
        row.parent_id = item.parent_id
        row.sort_order = item.sort_order
        row.structure_updated_at = now
    db.commit()
    return list_annotation_notice_tree(db)


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


def search_annotation_notice_sections(
    db: Session, keyword: str, skip: int = 0, limit: int = 20
) -> dict:
    ensure_annotation_notice_sections(db)
    normalized = keyword.strip()
    prefix_match = re.match(r"^([A-Za-z]+)\.\s*(.*)$", normalized)
    search_term = prefix_match.group(2).strip() if prefix_match else normalized
    query = db.query(AnnotationNoticeSection).filter(AnnotationNoticeSection.is_active.is_(True))
    if search_term:
        pattern = f"%{_escape_like_keyword(search_term)}%"
        query = query.filter(or_(
            AnnotationNoticeSection.title.ilike(pattern, escape="\\"),
            AnnotationNoticeSection.search_text.ilike(pattern, escape="\\"),
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
    row: AnnotationNoticeSection,
    payload: AnnotationNoticeSectionUpdate,
    user_id: UUID,
) -> dict:
    if not row.has_content:
        raise ValueError("该栏目仅用于分组，不能编辑正文")
    _assert_version(row.updated_at, payload.expected_updated_at)
    row.content_json = payload.content_json
    row.search_text = extract_notice_text(payload.content_json)
    row.updated_by = user_id
    row.updated_at = datetime.now()
    db.commit()
    return get_annotation_notice_section(db, row.id)


def update_annotation_notice_content(
    db: Session, section_id: UUID, payload: AnnotationNoticeSectionUpdate, user_id: UUID
) -> dict | None:
    row = db.query(AnnotationNoticeSection).filter(
        AnnotationNoticeSection.id == section_id,
        AnnotationNoticeSection.is_active.is_(True),
    ).with_for_update().first()
    return _update_content(db, row, payload, user_id) if row else None


def update_annotation_notice_section(
    db: Session, section_key: str, payload: AnnotationNoticeSectionUpdate, user_id: UUID
) -> dict | None:
    """兼容旧版按 section_key 保存正文。"""
    ensure_annotation_notice_sections(db)
    row = db.query(AnnotationNoticeSection).filter(
        AnnotationNoticeSection.section_key == section_key,
        AnnotationNoticeSection.is_active.is_(True),
    ).with_for_update().first()
    if not row:
        return None
    result = _update_content(db, row, payload, user_id)
    # 旧客户端只识别 title，保持原有“字母编号 + 栏目名称”的返回形态。
    result["title"] = result["display_title"]
    return result
