"""每日安排的行级操作信息；复用现有审计表，不回填或推测历史人员。"""
from sqlalchemy import case, func

from business_time import business_iso
from models import AppUser
from resource_development_models import DevelopmentAudit as Audit
from resource_development_service import snapshot, user_name


FIELD_LABELS = {'owners': '负责人', 'targets': '语种／城市／开拓方向',
                'role_tags': '岗位目标', 'projects': '关联项目', 'remarks': '账号备注'}


def audit(db, user, row, action, before=None, carried_from=None):
    db.flush()
    after = snapshot(row)
    after['_operation'] = {'actor_name': user_name(db, user.id),
                           'carried_from': carried_from.isoformat() if carried_from else None}
    db.add(Audit(entity_id=row.id, entity_type=row.__tablename__.removeprefix('resource_development_'),
                 actor_id=user.id, action=action, before=before or {}, after=after))


def is_reset(entry):
    return entry.action == 'update' and entry.before.get('completed') is True and entry.after.get('completed') is False


def actor_names(db, entries):
    ids = {entry.actor_id for entry in entries}
    return {person.id: person.full_name or person.username
            for person in db.query(AppUser).filter(AppUser.id.in_(ids)).all()} if ids else {}


def operation(entry, names, include_changes=True):
    if not entry:
        return None
    metadata = entry.after.get('_operation') or {}
    reset = is_reset(entry)
    action = 'reset' if reset else entry.action
    label = {'create': '录入安排', 'update': '修改安排', 'complete': '确认完成',
             'reopen': '取消完成', 'reset': '安排变更，完成状态自动重置'}.get(action, action)
    if entry.action == 'create' and metadata.get('carried_from'):
        label = '沿用安排'
    changes = []
    for key, title in (FIELD_LABELS.items() if include_changes else []):
        if entry.before.get(key) != entry.after.get(key) and field_text(key, entry.before) != field_text(key, entry.after):
            changes.append({'field': key, 'label': title,
                            'before': field_text(key, entry.before), 'after': field_text(key, entry.after)})
    return {'id': str(entry.id), 'action': action, 'label': label,
            'actor_name': metadata.get('actor_name') or names.get(entry.actor_id) or '未记录',
            'operated_at': business_iso(entry.created_at), 'changes': changes,
            'carried_from': metadata.get('carried_from')}


def field_text(key, value):
    raw = value.get(key)
    if key == 'owners':
        owners = raw or ([{'name': value.get('owner_name')}] if value.get('owner_id') else [])
        return '、'.join(owner.get('name') or '未命名' for owner in owners) or '未分配'
    if key == 'targets':
        parts = []
        for target in raw or []:
            label = (target.get('project') or {}).get('project_name') or target.get('label') or '-'
            scope = '；'.join(item.get('label') or ' · '.join(filter(None, [item.get('language_label'), item.get('city')]))
                             for item in target.get('scope', []))
            if not scope and target.get('kind') != 'request_project' and target.get('label') != label:
                scope = target.get('label') or ''
            parts.append(' · '.join(filter(None, [label, scope, target.get('arrangement_note')])))
        return '；'.join(parts) or '-'
    if key == 'projects':
        return '；'.join(p.get('project_name') or p.get('order_no') or '-' for p in raw or []) or '-'
    if key == 'role_tags':
        return '、'.join(raw or []) or '-'
    return raw or '-'


def cell_operations(db, cells):
    """窗口查询每行每类的最近事件，避免列表加载全部历史或逐行查询。"""
    if not cells:
        return {}
    reset = (Audit.action == 'update') & Audit.before['completed'].as_boolean().is_(True) & Audit.after['completed'].as_boolean().is_(False)
    category = case((reset, 'reset'), else_=Audit.action)
    ranked = db.query(Audit.id.label('id'), func.row_number().over(
        partition_by=(Audit.entity_id, category), order_by=(Audit.created_at.desc(), Audit.id.desc())).label('position')
    ).filter(Audit.entity_type == 'arrangement_cell', Audit.entity_id.in_([cell.id for cell in cells])).subquery()
    entries = db.query(Audit).join(ranked, ranked.c.id == Audit.id).filter(ranked.c.position == 1).order_by(Audit.created_at, Audit.id).all()
    names = actor_names(db, entries)
    result = {}
    for entry in entries:
        values = result.setdefault(entry.entity_id, {'created': None, 'edited': None, 'status': None})
        event = operation(entry, names, include_changes=False)
        if entry.action == 'create':
            values['created'] = event
        if entry.action in {'create', 'update'}:
            values['edited'] = event
        if entry.action in {'complete', 'reopen'} or is_reset(entry):
            values['status'] = event
    return result


def cell_history(db, cell, skip=0, limit=20):
    query = db.query(Audit).filter_by(entity_type='arrangement_cell', entity_id=cell.id)
    total = query.count()
    entries = query.order_by(Audit.created_at.desc(), Audit.id.desc()).offset(skip).limit(limit).all()
    names = actor_names(db, entries)
    return {'items': [operation(entry, names) for entry in entries], 'total': total}
