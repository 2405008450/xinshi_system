"""多维字数统计查询与保存服务。"""
from __future__ import annotations

import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from manuscript_models import ManuscriptArrangement, ManuscriptDispatch
from models import AppUser, TranslationProject, TranslationSubOrder
from word_count_models import WordCountMetric
from word_count_schemas import WordCountCreateMatrix, WordCountMatrixPatch
import preliminary_word_count as preliminary
import translation_duration_metrics as duration


METRIC_TYPES = ("words", "characters_no_spaces", "cjk_chars_korean_words", "foreign_words", "documents", "pages", "minutes", "hours")
ENTITY_DIMENSIONS = ("company", "customer", "preliminary", "translator_estimate")
WORD_COUNT_REGIONS = (
    ("words", "characters_no_spaces", "cjk_chars_korean_words", "foreign_words"),
    ("documents",),
    ("pages",),
    ("minutes", "hours"),
)


def has_multiple_word_count_regions(values):
    return sum(any(values.get(key) is not None for key in region) for region in WORD_COUNT_REGIONS) > 1


def validate_word_count_region(dimension, values):
    if has_multiple_word_count_regions(values):
        label = '我司统计' if dimension == 'company' else '客户统计'
        raise HTTPException(422, f'{label}只能填写一个统计区域，请清空其他区域')
    if values.get('minutes') is not None and values.get('hours') is not None:
        raise HTTPException(422, '分钟和小时只能选择一种')


def _empty_values() -> dict[str, Optional[int]]:
    return {metric_type: None for metric_type in METRIC_TYPES}


def attach_order_sources(projects, sub_orders):
    """仅标记订单来源与下级数量，统计值始终保留本单独立填报值。"""
    from translation_direction_service import directions, preserves_order_statistics
    children = {}
    by_number = {(row.parent_project_id, row.sub_order_no): row for row in sub_orders}
    for row in sub_orders:
        parent = by_number.get((row.parent_project_id, row.sub_order_no.rsplit('.', 1)[0]))
        children.setdefault(parent.id if parent else row.parent_project_id, []).append(row)

    def add_direction_matrix(totals, pair, matrix):
        target = totals.get(pair)
        if target is None:
            target = {dimension: _empty_values() for dimension in ENTITY_DIMENSIONS}
            totals[pair] = target
        for dimension, values in matrix.items():
            for metric, value in values.items():
                if value is not None:
                    target[dimension][metric] = (target[dimension][metric] or 0) + value

    def visit(owner):
        direct = children.get(owner.id, [])
        by_direction = {}
        for child in direct:
            for pair, matrix in visit(child).items():
                add_direction_matrix(by_direction, pair, matrix)
        owner.word_count_sub_order_count = len(direct)
        direction_split = preserves_order_statistics(owner, direct)
        owner.word_count_matrix_source = 'suborder' if hasattr(owner, 'sub_order_no') else 'project'
        owner.word_count_parent_order_no = None
        owner.word_count_matches_parent = False
        if direction_split:
            for child in direct:
                child.word_count_parent_order_no = getattr(owner, 'sub_order_no', None) or owner.order_no
                child.word_count_matches_parent = child.word_count_matrix == owner.word_count_matrix
        if not direct:
            owner.word_count_by_direction = []
            return {pair: owner.word_count_matrix for pair in directions(owner.language_pair)}
        for matrix in by_direction.values():
            for values in matrix.values():
                if values['minutes'] is not None and values['hours'] is not None:
                    values['minutes'] = round(values['minutes'] + values['hours'] * 60, 4)
                    values['hours'] = None
        owner.word_count_by_direction = [
            {'language_pair': pair, 'word_count_matrix': matrix} for pair, matrix in by_direction.items()
        ]
        return by_direction

    for project in projects:
        visit(project)


def hierarchy_matrix(db, entity_type, entity):
    """一次读取整棵订单树的独立统计，弹窗和稿件安排复用相同结果。"""
    project_id = entity.id if entity_type == 'project' else entity.parent_project_id
    project = entity if entity_type == 'project' else db.get(TranslationProject, project_id)
    return attach_entity_matrices(db, [project])[entity.id]


def attach_entity_matrices(db: Session, projects) -> dict:
    """按母订单批量读取整棵树，各订单统计互不覆盖，供列表复用。"""
    projects = list({row.id: row for row in projects}.values())
    if not projects:
        return {}
    project_ids = [row.id for row in projects]
    sub_orders = db.query(TranslationSubOrder).filter(
        TranslationSubOrder.parent_project_id.in_(project_ids)
    ).all()
    owners = {row.id: row for row in [*projects, *sub_orders]}
    for owner in owners.values():
        owner.word_count_matrix = {dimension: _empty_values() for dimension in ENTITY_DIMENSIONS}
    from sqlalchemy import or_
    sub_order_ids = [row.id for row in sub_orders]
    metrics = db.query(WordCountMetric).filter(or_(
        WordCountMetric.project_id.in_(project_ids),
        WordCountMetric.sub_order_id.in_(sub_order_ids),
    )).all() + preliminary.rows(db, project_ids, sub_order_ids)
    metrics += duration.rows(db, project_ids, sub_order_ids)
    for metric in metrics:
        owner = owners.get(metric.project_id or metric.sub_order_id)
        if owner is not None and metric.dimension in ENTITY_DIMENSIONS and metric.metric_type in METRIC_TYPES:
            owner.word_count_matrix[metric.dimension][metric.metric_type] = float(metric.count_value) if metric.metric_type in {'minutes','hours'} else metric.count_value
    from translation_simple_requirement_counts import attach
    attach(db,projects)
    attach_order_sources(projects, sub_orders)
    return owners


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


def _entity_metric_rows(db,entity_type,entity_id):
    return _entity_metric_query(db,entity_type,entity_id).all()+preliminary.rows(db,
        project_ids=[entity_id] if entity_type=='project' else [],
        sub_order_ids=[entity_id] if entity_type=='suborder' else [])+duration.rows(db,project_ids=[entity_id] if entity_type=='project' else [],sub_order_ids=[entity_id] if entity_type=='suborder' else [])


def _metric_values(rows):
    return {(row.dimension,row.metric_type):float(row.count_value) if row.metric_type in {'minutes','hours'}
            else int(row.count_value) for row in rows}


def _record_word_count_changes(db, entity_type, entity, before, actor_id):
    from translation_finance_audit import append_snapshots

    after = _metric_values(_entity_metric_rows(db, entity_type, entity.id))
    changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    if not changed:
        return
    actor = db.get(AppUser, actor_id)
    if actor is None:
        raise HTTPException(403, '无法确认字数修改人')
    is_project = entity_type == 'project'
    project_id = entity.id if is_project else entity.parent_project_id
    order_key = str(entity.id)
    metadata = {'order_no': entity.order_no if is_project else entity.sub_order_no,
                'project_name': entity.project_name if is_project else entity.sub_project_name}

    def snapshot(values):
        return {order_key: {**metadata, 'word_count_cells': [
            {'dimension': dimension, 'metric_type': metric, 'value': values.get((dimension, metric))}
            for dimension, metric in changed
        ]}}

    append_snapshots(db, actor, project_id, snapshot(before), snapshot(after))


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
    owner = hierarchy_matrix(db, entity_type, entity)
    entity_values = owner.word_count_matrix
    source = owner.word_count_matrix_source
    sub_order_count = owner.word_count_sub_order_count

    arrangements = _arrangements_for_entity(db, entity_type, entity, dispatch_id)
    arrangement_ids = [row.id for row in arrangements]
    arrangement_values = {
        arrangement_id: {"planned": _empty_values(), "actual": _empty_values()}
        for arrangement_id in arrangement_ids
    }
    if arrangement_ids:
        metrics = db.query(WordCountMetric).filter(WordCountMetric.arrangement_id.in_(arrangement_ids)).all()+duration.rows(db,arrangement_ids=arrangement_ids)
        for metric in metrics:
            values = arrangement_values.get(metric.arrangement_id)
            if values and metric.dimension in values and metric.metric_type in METRIC_TYPES:
                values[metric.dimension][metric.metric_type] = float(metric.count_value) if metric.metric_type in {'minutes','hours'} else metric.count_value

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "source": source,
        "sub_order_count": sub_order_count,
        "word_count_by_direction": owner.word_count_by_direction,
        "word_count_parent_order_no": owner.word_count_parent_order_no,
        "word_count_matches_parent": owner.word_count_matches_parent,
        "simple_requirement_word_count_matrix":getattr(owner,"simple_requirement_word_count_matrix",{}),
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
    if metric_type in {'minutes','hours'}:
        return duration.apply_cell(db,owner_filters,dimension,metric_type,value,updated_by)
    if dimension == 'preliminary':
        return preliminary.apply_cell(db,owner_filters,metric_type,value,updated_by)
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
                id=uuid4(),
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
        from annotation_progress_time import business_now
        existing.updated_at = business_now().replace(tzinfo=None)


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
    # 合并同一请求中的清空和填写后再校验，允许从旧口径切换到新口径。
    entity_changes = [change for change in payload.changes if change.scope == 'entity']
    touched={change.dimension for change in entity_changes if change.dimension in {'company','customer'}}
    record_changes = bool(entity_changes and updated_by is not None)
    if touched or record_changes:
        project_id = entity.id if entity_type == 'project' else entity.parent_project_id
        db.query(TranslationProject).filter_by(id=project_id).with_for_update().first()
        if entity_type == 'suborder':
            db.query(TranslationSubOrder).filter_by(id=entity_id).with_for_update().first()
        before = _metric_values(_entity_metric_rows(db,entity_type,entity_id))
    if touched:
        values={dimension:{} for dimension in touched}
        for (dimension,metric),value in before.items():
            if dimension in touched:values[dimension][metric]=value
        for change in payload.changes:
            if change.scope=='entity' and change.dimension in touched:values[change.dimension][change.metric_type]=change.value
        for dimension, items in values.items():
            validate_word_count_region(dimension, items)
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
        if record_changes:
            db.flush()
            _record_word_count_changes(db, entity_type, entity, before, updated_by)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_word_count_matrix(db, entity_type, entity_id, dispatch_id)


def validate_matrix_regions(matrix):
    for dimension in ('company', 'customer'):
        validate_word_count_region(dimension, getattr(matrix, dimension).model_dump())


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
    validate_matrix_regions(matrix)
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


def replace_entity_matrix(
    db: Session,
    entity_type: str,
    entity_id: UUID,
    matrix: WordCountCreateMatrix,
    *,
    updated_by: Optional[UUID],
) -> None:
    """在调用方事务内用完整矩阵替换项目或子订单字数。"""
    _load_entity(db, entity_type, entity_id)
    validate_matrix_regions(matrix)
    for dimension in ENTITY_DIMENSIONS:
        values = getattr(matrix, dimension)
        for metric_type, value in values.model_dump().items():
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
    metrics = db.query(WordCountMetric).filter(WordCountMetric.arrangement_id.in_(by_id)).all()+duration.rows(db,arrangement_ids=by_id)
    for metric in metrics:
        row = by_id.get(metric.arrangement_id)
        if row is not None and metric.dimension in {"planned", "actual"}:
            getattr(row, metric.dimension)[metric.metric_type] = float(metric.count_value) if metric.metric_type in {'minutes','hours'} else metric.count_value


def entity_matrix_values(db: Session, entity_type: str, entity_id: UUID) -> dict:
    return hierarchy_matrix(db, entity_type, _load_entity(db, entity_type, entity_id)).word_count_matrix
