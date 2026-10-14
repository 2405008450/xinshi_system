"""三级订单字段继承；NULL 元数据表示历史订单，禁止推测其继承关系。"""
from copy import deepcopy
from sqlalchemy.exc import IntegrityError

from annotation_models import AnnotationProject
from annotation_schemas import AnnotationProjectDetailResponse, AnnotationProjectUpdate, AnnotationProjectWrite
from annotation_progress_time import business_now

EXCLUDED = {'area_id', 'language_items', 'custom_values', 'material_changes',
            'client_name', 'client_short_name', 'client_code', 'manager_contact'}
FIELDS = set(AnnotationProjectWrite.model_fields) - EXCLUDED
LABELS = {
    'project_name': '项目名称', 'project_types': '项目类型', 'task_description': '具体任务',
    'client_id': '客户', 'sub_client_id': '子客户', 'contact_name': '联系人',
    'customer_order_no': '客户单号', 'email_subject_preview': '邮件主题',
    'project_status': '项目进度', 'status_effective_on': '状态生效时间', 'priority': '优先次序',
    'language_region': '语言地区', 'potential_demand': '需求量', 'project_path': '项目路径',
    'quotation_path': '报价单路径', 'contract_path': '合同路径', 'task_dispatched_at': '任务派发时间',
    'task_submitted_at': '任务提交时间', 'client_manager_id': '客户经理',
    'customer_consultation_time': '客户咨询时间', 'customer_confirmation_time': '客户确认时间',
    'price_items': '客户报价', 'assignees': '人员安排', 'role_assignments': '内部负责人',
}


def write_values(project):
    values = AnnotationProjectDetailResponse.model_validate(project).model_dump()
    return AnnotationProjectWrite.model_validate({key: deepcopy(value) for key, value in values.items()
                                                if key in AnnotationProjectWrite.model_fields}).model_dump()


def _comparable(value):
    if isinstance(value, list):
        return [_comparable(item) for item in value]
    if isinstance(value, dict):
        return {key: bool(item) if key == 'language_item_id' else _comparable(item) for key, item in value.items()
                if key not in {'id', 'sequence_no', 'person_name', 'resource_code', 'display'}}
    return value


def snapshot(project):
    values = write_values(project)
    result = {key: _comparable(values.get(key)) for key in FIELDS}
    result.update({f'custom:{key}': deepcopy(value) for key, value in project.custom_values.items()})
    return result


def all_fields(db):
    from annotation_custom_field_service import list_custom_fields
    # 停用字段仅保留各级订单自己的历史值，不再同步或恢复继承。
    # 即使双方均无历史值，也不能补写 None，否则会触发停用字段修改校验。
    return FIELDS | {f'custom:{field.id}' for field in list_custom_fields(db, 'project', None)}


def independent_fields(db, project):
    metadata = project.inheritance_overrides
    if metadata is None:
        return all_fields(db)
    if '*' in metadata:
        return all_fields(db) - {key.removeprefix('inherit:') for key in metadata if key.startswith('inherit:')}
    return set(metadata)


def mark_changes(db, project, before):
    if not project.parent_project_id:
        return
    if project.inheritance_overrides is None:
        return
    overrides = set(project.inheritance_overrides)
    after = snapshot(project)
    changes = {key for key in set(before) | set(after) if before.get(key) != after.get(key)}
    if changes & {'project_status', 'status_effective_on'}:
        changes.update({'project_status', 'status_effective_on'})
    if '*' in overrides:
        overrides -= {f'inherit:{key}' for key in changes}
    else:
        overrides.update(changes)
    # 状态和生效时间是一个不可拆分的业务变更。
    if overrides & {'project_status', 'status_effective_on'}:
        overrides.update({'project_status', 'status_effective_on'})
    project.inheritance_overrides = sorted(overrides)


def _assignment_field_mapping(db, parent, child):
    from annotation_ops_models import AnnotationCustomFieldDefinition as Field
    parent_fields = db.query(Field).filter_by(project_id=parent.id).all()
    child_fields = {(field.table_code, field.field_key): field for field in db.query(Field).filter_by(project_id=child.id)}
    mapping = {}
    for original in parent_fields:
        key = (original.table_code, original.field_key)
        target = child_fields.get(key)
        if target is None:
            values = {column.name: deepcopy(getattr(original, column.name)) for column in Field.__table__.columns
                      if column.name not in {'id', 'project_id', 'created_by', 'created_at', 'updated_at'}}
            target = Field(project_id=child.id, created_by=original.created_by, **values)
            db.add(target)
            db.flush()
            child_fields[key] = target
        mapping[str(original.id)] = str(target.id)
    return mapping


def projected_values(db, parent, child, *, copy_assignments=True):
    """将上级业务值投影为下级自己的关联 ID，保留已存在的执行明细身份。"""
    from annotation_child_copy_service import copy_prices
    from annotation_schemas import AnnotationAssigneeInput
    from utils import normalize_email_subject_order_no
    values = write_values(parent)
    target = child.language_items[0]
    source = next((item for item in parent.language_items
                   if (item.source_language_id, item.target_language_id) ==
                   (target.source_language_id, target.target_language_id)), parent.language_items[0] if parent.language_items else None)
    values['email_subject_preview'] = normalize_email_subject_order_no(parent.email_subject_preview, child.order_no)
    prices = copy_prices(parent, source, target)
    for index, row in enumerate(prices):
        if index < len(child.price_items):
            row['id'] = child.price_items[index].id
    values['price_items'] = prices
    if copy_assignments:
        mapping = _assignment_field_mapping(db, parent, child)
        rows = []
        existing = {(row.person_id, bool(row.language_item_id), row.assignment_role): row for row in child.assignees}
        for original in parent.assignees:
            if original.language_item_id and (source is None or original.language_item_id != source.id):
                continue
            row = AnnotationAssigneeInput.model_validate(original, from_attributes=True).model_dump(exclude={'id'})
            row['language_item_id'] = target.id if original.language_item_id else None
            row['custom_values'] = {mapping.get(key, key): deepcopy(value) for key, value in original.custom_values.items()}
            match = existing.get((original.person_id, bool(original.language_item_id), original.assignment_role))
            if match:
                row['id'] = match.id
            rows.append(row)
        values['assignees'] = rows
    return values


def initialize_inheritance(db, parent, child):
    expected = projected_values(db, parent, child)
    actual = snapshot(child)
    inherited = {key: _comparable(expected.get(key)) for key in FIELDS}
    inherited.update({f'custom:{key}': value for key, value in expected['custom_values'].items()})
    child.inheritance_overrides = sorted(key for key in set(actual) | set(inherited)
                                         if actual.get(key) != inherited.get(key))
    if set(child.inheritance_overrides) & {'project_status', 'status_effective_on'}:
        child.inheritance_overrides = sorted(set(child.inheritance_overrides) | {'project_status', 'status_effective_on'})


def apply_restore(db, parent, project, payload):
    requested = set(payload.restore_inheritance)
    if not requested:
        return payload
    if parent is None or requested - all_fields(db):
        raise ValueError('恢复继承包含无效字段，或当前订单没有上级')
    if requested & {'project_status', 'status_effective_on'}:
        requested.update({'project_status', 'status_effective_on'})
    restore_metadata(project, requested)
    values = payload.model_dump()
    inherited = projected_values(db, parent, project, copy_assignments='assignees' in requested)
    for key in requested:
        if key.startswith('custom:'):
            field = key.split(':', 1)[1]
            values['custom_values'][field] = inherited['custom_values'].get(field)
        else:
            values[key] = inherited[key]
    return AnnotationProjectUpdate.model_validate(values)


def restore_metadata(project, requested):
    requested = set(requested)
    if requested & {'project_status', 'status_effective_on'}:
        requested.update({'project_status', 'status_effective_on'})
    metadata = set(project.inheritance_overrides) if project.inheritance_overrides is not None else {'*'}
    if '*' in metadata:
        metadata.update(f'inherit:{key}' for key in requested)
    else:
        metadata -= requested
    project.inheritance_overrides = sorted(metadata)


def propagate(db, parent, actor_id=None):
    from annotation_service import get_annotation_project, update_annotation_project
    # 运行会话关闭 autoflush；先写入本事务，再锁定并刷新下级，防止父级关联刷新丢失修改。
    # flush 不提交，任一下级同步失败时仍由调用方整笔回滚。
    db.flush()
    ids = [row.id for row in db.query(AnnotationProject).filter_by(parent_project_id=parent.id).order_by(AnnotationProject.id)]
    for child_id in ids:
        db.query(AnnotationProject).filter_by(id=child_id).with_for_update().populate_existing().first()
        child = get_annotation_project(db, child_id)
        fields = all_fields(db) - independent_fields(db, child)
        values = write_values(child)
        before = snapshot(child)
        if fields:
            inherited = projected_values(db, parent, child, copy_assignments='assignees' in fields)
            for key in fields:
                if key.startswith('custom:'):
                    field = key.split(':', 1)[1]
                    values['custom_values'][field] = inherited['custom_values'].get(field)
                else:
                    values[key] = inherited[key]
        language_changed = False
        if parent.parent_project_id:
            direction = parent.language_items[0]
            target = child.language_items[0]
            language_changed = (direction.source_language_id, direction.target_language_id) != (target.source_language_id, target.target_language_id)
            if language_changed:
                if ('price_items' not in fields and any(row.source_language_id for row in child.price_items)) or (
                    'assignees' not in fields and any(row.language_item_id for row in child.assignees)):
                    raise ValueError(f'三级订单 {child.order_no} 已独立维护语种关联的报价或人员，请先恢复继承或清理后再更换子订单语种')
                values['language_items'] = [{'id': target.id, 'source_language_id': direction.source_language_id,
                                            'target_language_id': direction.target_language_id}]
                for row in values['price_items']:
                    if row['source_language_id']:
                        row.update(source_language_id=direction.source_language_id, target_language_id=direction.target_language_id)
        after = {key: _comparable(values.get(key)) for key in FIELDS}
        after.update({f'custom:{key}': value for key, value in values['custom_values'].items()})
        if before == after and not language_changed:
            continue
        try:
            payload = AnnotationProjectUpdate.model_validate({**values, 'expected_updated_at': child.updated_at})
            update_annotation_project(db, child.id, payload, actor_id, commit=False, inherited=True)
        except ValueError as exc:
            raise ValueError(f'下级订单 {child.order_no} 同步失败：{exc}') from exc
        except IntegrityError as exc:
            raise ValueError(f'下级订单 {child_id} 存在关联执行记录，无法同步人员或报价；请先处理关联或将该组字段独立维护') from exc


def finish_inline_change(db, project, before, actor_id=None):
    mark_changes(db, project, before)
    project.updated_at = business_now().replace(tzinfo=None)
    propagate(db, project, actor_id)
