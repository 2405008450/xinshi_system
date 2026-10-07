"""子订单复制母订单业务快照，所有明细重新归属子订单。"""
from copy import deepcopy

from annotation_models import AnnotationProjectAssignee
from annotation_ops_models import AnnotationAssigneeRate, AnnotationCustomFieldDefinition


def source_direction(parent, payload):
    items = list(parent.language_items)
    if payload.copy_source_language_item_id:
        source = next((item for item in items if item.id == payload.copy_source_language_item_id), None)
        if source is None:
            raise ValueError("复制来源语种不属于当前母订单")
        return source
    selected = payload.language_items[0] if payload.language_items else None
    return next((item for item in items if selected and item.source_language_id == selected.source_language_id
                 and item.target_language_id == selected.target_language_id), items[0] if items else None)


def copy_prices(parent, source, target):
    from annotation_schemas import AnnotationPriceItemInput
    result = []
    for row in parent.price_items:
        if row.source_language_id and (source is None or (row.source_language_id, row.target_language_id) != (source.source_language_id, source.target_language_id)):
            continue
        values = AnnotationPriceItemInput.model_validate(row, from_attributes=True).model_dump(exclude={'id'})
        if row.source_language_id:
            values.update(source_language_id=target.source_language_id, target_language_id=target.target_language_id)
        result.append(values)
    return result


def copy_scoped_fields(db, parent, child, actor_id):
    mapping = {}
    fields = db.query(AnnotationCustomFieldDefinition).filter_by(project_id=parent.id).all()
    excluded = {'id', 'project_id', 'created_by', 'created_at', 'updated_at'}
    for field in fields:
        values = {column.name: deepcopy(getattr(field, column.name)) for column in field.__table__.columns if column.name not in excluded}
        cloned = AnnotationCustomFieldDefinition(project_id=child.id, created_by=actor_id, **values)
        db.add(cloned)
        db.flush()
        mapping[str(field.id)] = str(cloned.id)
    return mapping


def copy_people(db, parent, child, source, field_mapping):
    target = child.language_items[0] if child.language_items else None
    excluded = {'id', 'project_id', 'sequence_no', 'created_at', 'updated_at', 'language_item_id', 'custom_values'}
    for original in parent.assignees:
        if original.language_item_id and (source is None or original.language_item_id != source.id):
            continue
        values = {column.name: deepcopy(getattr(original, column.name)) for column in original.__table__.columns if column.name not in excluded}
        values['custom_values'] = {field_mapping.get(key, key): deepcopy(value) for key, value in (original.custom_values or {}).items()}
        cloned = AnnotationProjectAssignee(project_id=child.id, sequence_no=len(child.assignees) + 1,
            language_item_id=target.id if original.language_item_id and target else None, **values)
        child.assignees.append(cloned)
        db.flush()
        if original.rate:
            rate_fields = {'amount', 'currency', 'unit', 'remarks'}
            cloned.rate = AnnotationAssigneeRate(**{key: getattr(original.rate, key) for key in rate_fields})


def copy_materials(db, parent_id, child_id):
    from annotation_material_models import AnnotationMaterialFile as Material, AnnotationMaterialVersion as Version, AnnotationMaterialUpload as Upload
    originals = db.query(Material).filter_by(project_id=parent_id).order_by(Material.id).all()
    for original in originals:
        versions = db.query(Version).filter_by(file_id=original.id).order_by(Version.version_no).all()
        # 锁住不可变上传对象，避免复制与最后一个引用的删除并发。
        db.query(Upload).filter(Upload.id.in_([version.upload_id for version in versions])).order_by(Upload.id).with_for_update().all()
        cloned = Material(project_id=child_id, category=original.category)
        db.add(cloned)
        db.flush()
        for version in versions:
            db.add(Version(file_id=cloned.id, upload_id=version.upload_id, version_no=version.version_no))
