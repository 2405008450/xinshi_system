"""按语言方向补齐子订单；调用者负责事务提交。"""
from sqlalchemy.orm import selectinload

from annotation_models import AnnotationProject, AnnotationProjectLanguageItem


def direction_key(item):
    return item.source_language_id, item.target_language_id


def direction_state(db, parent):
    children = db.query(AnnotationProject).filter_by(parent_project_id=parent.id).options(
        selectinload(AnnotationProject.language_items).joinedload(AnnotationProjectLanguageItem.source_language),
        selectinload(AnnotationProject.language_items).joinedload(AnnotationProjectLanguageItem.target_language),
    ).order_by(AnnotationProject.child_sequence_no).all()
    directions = {direction_key(item): item for item in parent.language_items}
    covered = {direction_key(child.language_items[0]) for child in children if len(child.language_items) == 1}
    extra = {direction_key(item): item for child in children for item in child.language_items
             if direction_key(item) not in directions}
    missing = [item for key, item in directions.items() if key not in covered]
    summary = {
        'automatic_enabled': len(directions) >= 2,
        'direction_count': len(directions),
        'missing_directions': [item.display for item in missing],
        'extra_directions': [item.display for item in extra.values()],
        'invalid_child_order_nos': [child.order_no for child in children if len(child.language_items) != 1],
    }
    return missing, summary


def ensure_direction_children(db, parent, actor_id=None, operation_source='automatic_direction_create'):
    from annotation_service import _lock_annotation_order_numbers, _lock_parent, create_annotation_project
    from annotation_schemas import AnnotationProjectCreate
    if parent.parent_project_id:
        return []
    # 保存、补建、手动创建均按编号锁→母订单锁的顺序，避免相互等待。
    _lock_annotation_order_numbers(db)
    db.flush()
    parent = _lock_parent(db, parent.id)
    missing, summary = direction_state(db, parent)
    if not summary['automatic_enabled']:
        return []
    created = []
    for direction in missing:
        payload = AnnotationProjectCreate(
            parent_project_id=parent.id,
            copy_source_language_item_id=direction.id,
            language_items=[{'source_language_id': direction.source_language_id,
                             'target_language_id': direction.target_language_id}],
        )
        created.append(create_annotation_project(db, payload, actor_id,
            operation_source=operation_source, commit=False))
    return created
