"""多维字数统计查询与保存服务。"""
from __future__ import annotations

import datetime
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from manuscript_models import ManuscriptArrangement, ManuscriptDispatch
from models import TranslationProject, TranslationSubOrder
from word_count_models import WordCountMetric
from word_count_schemas import WordCountCreateMatrix, WordCountMatrixPatch


METRIC_TYPES = ("words", "characters_no_spaces", "cjk_chars_korean_words", "foreign_words")
ENTITY_DIMENSIONS = ("company", "customer", "translator_estimate")


def _empty_values() -> dict[str, Optional[int]]:
    return {metric_type: None for metric_type in METRIC_TYPES}


def _load_entity(db: Session, entity_type: str, entity_id: UUID):
    if entity_type == "project":
        entity = db.query(TranslationProject).filter(TranslationProject.id == entity_id).first()
    elif entity_type == "suborder":
        entity = db.query(TranslationSubOrder).filter(TranslationSubOrder.id == entity_id).first()
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="不支持的字数统计对象")
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="字数统计对象不存在")
    return entity


def _entity_metric_query(db: Session, entity_type: str, entity_id: UUID):
    query = db.query(WordCountMetric)
    if entity_type == "project":
        return query.filter(WordCountMetric.project_id == entity_id)
    return query.filter(WordCountMetric.sub_order_id == entity_id)


def _arrangements_for_entity(
    db: Session,
    entity_type: str,
    entity,
    dispatch_id: Optional[UUID] = None,
) -> list[ManuscriptArrangement]:
    project_id = entity.id if entity_type == "project" else entity.parent_project_id
    sub_order_id = None if entity_type == "project" else entity.id
    query = db.query(ManuscriptArrangement).filter(
        ManuscriptArrangement.translation_project_id == project_id,
        ManuscriptArrangement.sub_order_id.is_(sub_order_id) if sub_order_id is None else ManuscriptArrangement.sub_order_id == sub_order_id,
    )
    if dispatch_id is not None:
        dispatch = db.query(ManuscriptDispatch).filter(ManuscriptDispatch.id == dispatch_id).first()
        if (
            dispatch is None
            or dispatch.translation_project_id != project_id
            or dispatch.sub_order_id != sub_order_id
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="稿件安排批次不属于当前项目")
        return query.filter(ManuscriptArrangement.dispatch_id == dispatch_id).order_by(ManuscriptArrangement.created_at.asc()).all()

    rows = (
        query.join(ManuscriptDispatch, ManuscriptDispatch.id == ManuscriptArrangement.dispatch_id)
        .filter(
            ManuscriptArrangement.status != "cancelled",
            ManuscriptDispatch.status != "cancelled",
            ManuscriptDispatch.confirmed_at.is_not(None),
        )
        .order_by(ManuscriptArrangement.created_at.asc())
        .all()
    )
    # 与项目详情现有语义一致：同一译员只展示最后一条有效安排。
    latest_by_translator = {row.translator_id: row for row in rows}
    return list(latest_by_translator.values())


def get_word_count_matrix(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    dispatch_id: Optional[UUID] = None,
) -> dict:
    entity = _load_entity(db, entity_type, entity_id)
    entity_values = {dimension: _empty_values() for dimension in ENTITY_DIMENSIONS}
    for metric in _entity_metric_query(db, entity_type, entity_id).all():
        if metric.dimension in entity_values and metric.metric_type in METRIC_TYPES:
            entity_values[metric.dimension][metric.metric_type] = metric.count_value

    arrangements = _arrangements_for_entity(db, entity_type, entity, dispatch_id)
    arrangement_ids = [row.id for row in arrangements]
    arrangement_values = {
        arrangement_id: {"planned": _empty_values(), "actual": _empty_values()}
        for arrangement_id in arrangement_ids
    }
    if arrangement_ids:
        metrics = db.query(WordCountMetric).filter(WordCountMetric.arrangement_id.in_(arrangement_ids)).all()
        for metric in metrics:
            values = arrangement_values.get(metric.arrangement_id)
            if values and metric.dimension in values and metric.metric_type in METRIC_TYPES:
                values[metric.dimension][metric.metric_type] = metric.count_value

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        **entity_values,
        "translators": [
            {
                "arrangement_id": row.id,
                "dispatch_id": row.dispatch_id,
                "translator_id": row.translator_id,
                "translator_name": row.translator_name_snapshot,
                "status": row.status,
                **arrangement_values[row.id],
            }
            for row in arrangements
        ],
    }


def _owner_filters(entity_type: str, entity_id: UUID, arrangement_id: Optional[UUID] = None):
    if arrangement_id is not None:
        return {"arrangement_id": arrangement_id, "project_id": None, "sub_order_id": None}
    if entity_type == "project":
        return {"project_id": entity_id, "sub_order_id": None, "arrangement_id": None}
    return {"project_id": None, "sub_order_id": entity_id, "arrangement_id": None}


def _apply_cell(
    db: Session,
    *,
    owner_filters: dict,
    dimension: str,
    metric_type: str,
    value: Optional[int],
    updated_by: Optional[UUID],
) -> None:
    query = db.query(WordCountMetric).filter(
        WordCountMetric.dimension == dimension,
        WordCountMetric.metric_type == metric_type,
    )
    for field, owner_id in owner_filters.items():
        column = getattr(WordCountMetric, field)
        query = query.filter(column.is_(None) if owner_id is None else column == owner_id)
    existing = query.first()
    if value is None:
        if existing is not None:
            db.delete(existing)
        return
    if existing is None:
        db.add(
            WordCountMetric(
                **owner_filters,
                dimension=dimension,
                metric_type=metric_type,
                count_value=value,
                updated_by=updated_by,
            )
        )
    else:
        existing.count_value = value
        existing.updated_by = updated_by
        existing.updated_at = datetime.datetime.now()


def patch_word_count_matrix(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    payload: WordCountMatrixPatch,
    *,
    updated_by: Optional[UUID],
    dispatch_id: Optional[UUID] = None,
) -> dict:
    entity = _load_entity(db, entity_type, entity_id)
    allowed_arrangements = {
        row.id for row in _arrangements_for_entity(db, entity_type, entity, dispatch_id)
    }
    try:
        for change in payload.changes:
            if change.scope == "translator" and change.arrangement_id not in allowed_arrangements:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="译员安排不属于当前项目或批次")
            owner_filters = _owner_filters(
                entity_type,
                entity_id,
                change.arrangement_id if change.scope == "translator" else None,
            )
            _apply_cell(
                db,
                owner_filters=owner_filters,
                dimension=change.dimension,
                metric_type=change.metric_type,
                value=change.value,
                updated_by=updated_by,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_word_count_matrix(db, entity_type, entity_id, dispatch_id)


def save_created_entity_matrix(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    matrix: Optional[WordCountCreateMatrix],
    *,
    updated_by: Optional[UUID],
) -> None:
    if matrix is None:
        return
    for dimension in ENTITY_DIMENSIONS:
        values = getattr(matrix, dimension)
        for metric_type, value in values.model_dump().items():
            if value is None:
                continue
            _apply_cell(
                db,
                owner_filters=_owner_filters(entity_type, entity_id),
                dimension=dimension,
                metric_type=metric_type,
                value=value,
                updated_by=updated_by,
            )


def replace_arrangement_values(
    db: Session,
    arrangement_id: UUID,
    dimension: str,
    values,
    *,
    updated_by: Optional[UUID] = None,
) -> None:
    """用完整的四口径对象替换某位译员的预定或实际矩阵。"""
    if dimension not in {"planned", "actual"}:
        raise ValueError("译员字数维度无效")
    value_map = values.model_dump() if hasattr(values, "model_dump") else dict(values or {})
    for metric_type in METRIC_TYPES:
        _apply_cell(
            db,
            owner_filters={
                "project_id": None,
                "sub_order_id": None,
                "arrangement_id": arrangement_id,
            },
            dimension=dimension,
            metric_type=metric_type,
            value=value_map.get(metric_type),
            updated_by=updated_by,
        )


def attach_arrangement_matrices(db: Session, arrangements: list[ManuscriptArrangement]) -> None:
    """批量把预定/实际矩阵挂载到 ORM 对象，供响应 Schema 序列化。"""
    if not arrangements:
        return
    by_id = {row.id: row for row in arrangements}
    for row in arrangements:
        row.planned = _empty_values()
        row.actual = _empty_values()
    metrics = db.query(WordCountMetric).filter(WordCountMetric.arrangement_id.in_(by_id)).all()
    for metric in metrics:
        row = by_id.get(metric.arrangement_id)
        if row is not None and metric.dimension in {"planned", "actual"}:
            getattr(row, metric.dimension)[metric.metric_type] = metric.count_value


def entity_matrix_values(db: Session, entity_type: str, entity_id: UUID) -> dict:
    values = {dimension: _empty_values() for dimension in ENTITY_DIMENSIONS}
    for metric in _entity_metric_query(db, entity_type, entity_id).all():
        if metric.dimension in values:
            values[metric.dimension][metric.metric_type] = metric.count_value
    return values
