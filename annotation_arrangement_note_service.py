"""标注项目每日安排说明服务。"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from annotation_ops_models import AnnotationArrangementDailyNote
from concurrency import assert_fresh


def _note_dict(row: AnnotationArrangementDailyNote) -> dict:
    editor = row.editor
    return {
        "id": row.id,
        "note_date": row.note_date,
        "content_json": row.content_json,
        "updated_by": row.updated_by,
        "updated_by_name": editor.full_name or editor.username if editor else None,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def get_arrangement_daily_note(db: Session, note_date: date) -> Optional[dict]:
    row = (
        db.query(AnnotationArrangementDailyNote)
        .options(joinedload(AnnotationArrangementDailyNote.editor))
        .filter(AnnotationArrangementDailyNote.note_date == note_date)
        .first()
    )
    return _note_dict(row) if row else None


def save_arrangement_daily_note(db: Session, note_date: date, payload, user_id: UUID) -> dict:
    """同一天只保留一份安排；更新时使用时间戳防止多人互相覆盖。"""
    row = (
        db.query(AnnotationArrangementDailyNote)
        .filter(AnnotationArrangementDailyNote.note_date == note_date)
        .with_for_update()
        .first()
    )
    now = datetime.now()
    if row:
        assert_fresh(row, payload.expected_updated_at)
        row.content_json = payload.content_json
        row.updated_by = user_id
        row.updated_at = now
    else:
        row = AnnotationArrangementDailyNote(
            note_date=note_date,
            content_json=payload.content_json,
            updated_by=user_id,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    db.commit()
    return get_arrangement_daily_note(db, note_date)
