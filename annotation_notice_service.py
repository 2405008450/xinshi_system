"""标注须知主题初始化、查询与保存。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from annotation_notice_models import AnnotationNoticeSection
from annotation_notice_schemas import AnnotationNoticeSectionUpdate
from concurrency import StaleUpdateError, parse_expected_updated_at


ANNOTATION_NOTICE_SECTIONS = (
    ("customer_quote", "A. 客户报价"),
    ("annotator_quote", "B. 标注员报价"),
    ("trial_collection", "C. 试标/试采流程"),
    ("audio_annotation", "D. 音频标注流程"),
    ("audio_evaluation", "E. 音频评测流程"),
    ("text_evaluation", "F. 文本评测流程"),
    ("quality_inspection", "G. 质检流程"),
    ("listening_test", "H. 测听流程"),
    ("slot_deduction", "I. 扣槽流程"),
    ("generalization", "J. 泛化流程"),
    ("translation", "K. 翻译流程"),
)


def ensure_annotation_notice_sections(db: Session) -> None:
    existing = {
        row.section_key: row
        for row in db.query(AnnotationNoticeSection).all()
    }
    changed = False
    for sort_order, (section_key, title) in enumerate(ANNOTATION_NOTICE_SECTIONS, start=1):
        row = existing.get(section_key)
        if row is None:
            db.add(AnnotationNoticeSection(
                section_key=section_key,
                title=title,
                sort_order=sort_order,
            ))
            changed = True
        elif row.title != title or row.sort_order != sort_order:
            row.title = title
            row.sort_order = sort_order
            changed = True
    if changed:
        db.commit()


def _serialize(row: AnnotationNoticeSection) -> dict:
    editor = row.editor
    return {
        "id": row.id,
        "section_key": row.section_key,
        "title": row.title,
        "sort_order": row.sort_order,
        "content_json": row.content_json,
        "updated_by": row.updated_by,
        "updated_by_name": (editor.full_name or editor.username) if editor else None,
        "updated_at": row.updated_at,
    }


def list_annotation_notice_sections(db: Session) -> list[dict]:
    ensure_annotation_notice_sections(db)
    rows = db.query(AnnotationNoticeSection).options(
        joinedload(AnnotationNoticeSection.editor)
    ).order_by(AnnotationNoticeSection.sort_order).all()
    return [_serialize(row) for row in rows]


def update_annotation_notice_section(
    db: Session,
    section_key: str,
    payload: AnnotationNoticeSectionUpdate,
    user_id: UUID,
) -> dict | None:
    allowed_keys = {key for key, _title in ANNOTATION_NOTICE_SECTIONS}
    if section_key not in allowed_keys:
        return None
    ensure_annotation_notice_sections(db)
    row = db.query(AnnotationNoticeSection).filter(
        AnnotationNoticeSection.section_key == section_key
    ).with_for_update().first()
    if row is None:
        return None

    expected = parse_expected_updated_at(payload.expected_updated_at)
    if (row.updated_at is None) != (expected is None):
        raise StaleUpdateError()
    if row.updated_at is not None and expected is not None:
        current = row.updated_at.replace(tzinfo=None) if row.updated_at.tzinfo else row.updated_at
        if abs((current - expected).total_seconds()) > 0.001:
            raise StaleUpdateError()

    row.content_json = payload.content_json
    row.updated_by = user_id
    row.updated_at = datetime.now()
    db.commit()
    return _serialize(
        db.query(AnnotationNoticeSection).options(
            joinedload(AnnotationNoticeSection.editor)
        ).filter(AnnotationNoticeSection.id == row.id).one()
    )
