"""笔译订单按直接上级继承；显式差异存新表，已有订单表不改结构。"""
from datetime import datetime
from uuid import UUID
from sqlalchemy import ForeignKey, JSON, Uuid, inspect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm.attributes import set_committed_value
from models import Base, TranslationProject, TranslationSubOrder
from annotation_progress_time import business_datetime


class TranslationOrderInheritance(Base):
    __tablename__ = 'translation_order_inheritance'
    sub_order_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey('translation_sub_order.id', ondelete='CASCADE'), primary_key=True)
    overrides: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


FIELDS = ('service_content', 'language_pair', 'customer_deadline_time',
          'customer_requirement_professional', 'customer_requirement_special',
          'remarks', 'file_type_secondary', 'status')
EXTRA = {'service_content', 'customer_requirement_professional', 'customer_requirement_special'}
LABELS = dict(zip(FIELDS, ('服务内容', '翻译方向', '客户交稿时间', '客户专业要求', '客户特殊要求', '补充说明', '文本类型', '项目状态')))


def ready(db):
    if db.info.get('_translation_inheritance_ready'):
        return True
    found = inspect(db.connection()).has_table(TranslationOrderInheritance.__tablename__)
    if found:
        db.info['_translation_inheritance_ready'] = True
    return found


def serial(value):
    if isinstance(value, datetime):
        return business_datetime(value).isoformat()
    return value.strip() or None if isinstance(value, str) else value


def native(field, value):
    if field == 'customer_deadline_time' and isinstance(value, str):
        return business_datetime(datetime.fromisoformat(value)).replace(tzinfo=None)
    return value


def values(root):
    return {field: serial(getattr(root, 'project_status' if field == 'status' else field, None)) for field in FIELDS}


def tree(db, root_id, *, lock=False):
    query = db.query(TranslationProject).filter_by(id=root_id)
    root = query.with_for_update().one() if lock else query.one()
    rows = db.query(TranslationSubOrder).filter_by(parent_project_id=root_id).order_by(TranslationSubOrder.sub_order_no).all()
    records = {row.sub_order_id: row for row in db.query(TranslationOrderInheritance).filter(TranslationOrderInheritance.sub_order_id.in_([r.id for r in rows])).all()}
    return root, rows, records


def effective_tree(root, rows, records, *, reconcile_native=False):
    result = {root.order_no: values(root)}
    overrides = {}
    for row in sorted(rows, key=lambda r: r.sub_order_no.count('.')):
        parent = result.get(row.sub_order_no.rsplit('.', 1)[0], result[root.order_no])
        record = records.get(row.id)
        # 历史手工差异保留；未填写的旧字段按直接上级补齐。
        own = dict(record.overrides or {}) if record else {
            field: serial(getattr(row, field, None)) for field in FIELDS if field not in EXTRA
            and serial(getattr(row, field, None)) is not None
            and serial(getattr(row, field, None)) != parent[field]
        }
        if record and reconcile_native:
            for field in FIELDS:
                current = serial(getattr(row, field, None))
                if field not in EXTRA and current is not None and current != own.get(field, parent[field]):
                    own[field] = current
        overrides[row.id] = own
        result[row.sub_order_no] = {**parent, **own}
    return result, overrides


def prepare(db, root_id):
    """在上级改值前固定历史覆盖项，防止把原继承值误判成手工覆盖。"""
    if not ready(db):
        raise ValueError('笔译订单继承表尚未初始化，请联系管理员')
    root, rows, records = tree(db, root_id, lock=True)
    _, overrides = effective_tree(root, rows, records, reconcile_native=True)
    for row in rows:
        if row.id not in records:
            record = TranslationOrderInheritance(sub_order_id=row.id, overrides=overrides[row.id])
            db.add(record)
            records[row.id] = record
        else:
            records[row.id].overrides = overrides[row.id]
    db.flush()
    return root, rows, records


def synchronize(db, context):
    root, rows, records = context
    effective, _ = effective_tree(root, rows, records)
    from annotation_progress_time import business_now
    for row in rows:
        changed = False
        for field, value in effective[row.sub_order_no].items():
            if field in EXTRA:
                setattr(row, field, value)
            elif serial(getattr(row, field, None)) != value:
                setattr(row, field, native(field, value))
                changed = True
        if changed:
            row.updated_at = business_now().replace(tzinfo=None)
    db.flush()


def create_state(db, row, parent, payload):
    if not ready(db):
        raise ValueError('笔译订单继承表尚未初始化，请联系管理员')
    parent_values = values(parent) if isinstance(parent, TranslationProject) else {
        field: serial(getattr(parent, field, None)) for field in FIELDS
    }
    supplied = payload.model_dump(exclude_unset=True)
    own = {field: serial(supplied[field]) for field in FIELDS if field in supplied and serial(supplied[field]) != parent_values[field]}
    db.add(TranslationOrderInheritance(sub_order_id=row.id, overrides=own))
    for field, value in {**parent_values, **own}.items():
        setattr(row, field, native(field, value))
    db.flush()


def update_state(context, row, supplied, inherit_fields=()):
    root, rows, records = context
    effective, _ = effective_tree(root, rows, records)
    parent = effective.get(row.sub_order_no.rsplit('.', 1)[0], effective[root.order_no])
    own = dict(records[row.id].overrides or {})
    for field in inherit_fields:
        if field not in FIELDS:
            raise ValueError('无效的继承字段')
        own.pop(field, None)
    for field in FIELDS:
        if field not in supplied or field in inherit_fields:
            continue
        value = serial(supplied[field])
        if value == parent[field]:
            own.pop(field, None)
        else:
            own[field] = value
    records[row.id].overrides = own


def descendants_index(effective):
    result = {}
    for number in effective:
        ancestor = number
        while '.' in ancestor:
            ancestor = ancestor.rsplit('.', 1)[0]
            result.setdefault(ancestor, []).append(number)
    return result


def differences(owner_no, effective, index=None):
    """相同差异的整棵分支仅列该分支的最高订单号。"""
    base = effective[owner_no]
    index = index if index is not None else descendants_index(effective)
    descendants = index.get(owner_no, [])
    output = {}
    for field in FIELDS:
        changed = [number for number in descendants if effective[number][field] != base[field]]
        covered = set()
        items = []
        for number in sorted(changed, key=lambda no: (no.count('.'), no)):
            if number in covered:
                continue
            branch = index.get(number, [])
            same = all(effective[child][field] == effective[number][field] for child in branch)
            items.append({'order_no': number, 'value': effective[number][field], 'includes_descendants': bool(branch) and same})
            if same:
                covered.update(branch)
        if items:
            output[field] = {'label': LABELS[field], 'count': len(changed), 'items': items}
    return output


def attach(db, projects=(), sub_orders=()):
    if not ready(db):
        return
    targets = {row.id: row for row in projects}
    root_ids = set(targets) | {row.parent_project_id for row in sub_orders}
    if not root_ids:
        return
    roots = db.query(TranslationProject).filter(TranslationProject.id.in_(root_ids)).all()
    rows = db.query(TranslationSubOrder).filter(TranslationSubOrder.parent_project_id.in_(root_ids)).all()
    records = {r.sub_order_id:r for r in db.query(TranslationOrderInheritance).filter(TranslationOrderInheritance.sub_order_id.in_([r.id for r in rows])).all()}
    for root in roots:
        children = [r for r in rows if r.parent_project_id == root.id]
        effective, overrides = effective_tree(root, children, records, reconcile_native=True)
        index = descendants_index(effective)
        root.child_field_differences = differences(root.order_no, effective, index)
        for row in children:
            for field, value in effective[row.sub_order_no].items():
                if field in EXTRA:
                    setattr(row, field, value)
                else:
                    set_committed_value(row, field, native(field, value))
            row.inherited_fields = [field for field in FIELDS if field not in overrides[row.id]]
            row.child_field_differences = differences(row.sub_order_no, effective, index)


def attach_creation_parent(db, parent):
    """同一批导入只加载一次既有继承树，新节点在 create_state 中即时赋值。"""
    if not isinstance(parent, TranslationSubOrder):
        return
    transaction = db.get_transaction()
    cached = db.info.get('_translation_inheritance_create_tree')
    if cached is None or cached[0] is not transaction:
        cached = (transaction, set())
        db.info['_translation_inheritance_create_tree'] = cached
    if parent.parent_project_id not in cached[1]:
        attach(db, sub_orders=[parent])
        cached[1].add(parent.parent_project_id)


def hierarchy_summary(rows):
    rows = list(rows)
    parents = {row.sub_order_no.rsplit('.', 1)[0] for row in rows}
    def is_file(row):
        if getattr(row, 'folder_info', None):
            return False
        name = getattr(row, 'sub_project_name', None)
        if name is None:
            return row.sub_order_no not in parents
        from translation_file_name_rules import normalize_single_file_name
        try:
            normalize_single_file_name(name)
            return True
        except ValueError:
            return False
    return [{'level': level, 'orders': len(items), 'files': sum(is_file(row) for row in items)}
            for level in range(1, 5) if (items := [row for row in rows if row.sub_order_no.count('.') == level])]
