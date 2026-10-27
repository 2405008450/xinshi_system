"""资源开拓自定义字段的局部保存和受限展示。"""
from fastapi import HTTPException
from resource_development_models import DevelopmentCustomValue as Value, DevelopmentOption as Option, DevelopmentRecord as Record
from sqlalchemy import inspect, func, select


def values_ready(db):
    if 'development_custom_values_ready' not in db.info:
        db.info['development_custom_values_ready'] = inspect(db.connection()).has_table(Value.__tablename__)
    return db.info['development_custom_values_ready']


def serialize_custom_fields(db, record_id, allowed):
    if not values_ready(db):
        return {'custom_fields': {}, 'custom_field_items': []}
    rows = db.query(Value, Option.name).join(Option, Option.id == Value.field_id).filter(Value.record_id == record_id, Option.kind == 'custom_field').order_by(Option.name, Option.id).all()
    items = [{'id': str(row.field_id), 'name': name, 'value': row.value if allowed or not row.value else '受限内容'} for row, name in rows]
    return {'custom_fields': {item['id']: item['value'] for item in items}, 'custom_field_items': items}


def save_custom_fields(db, user, record_id, payload):
    if 'custom_fields' not in payload.model_fields_set or not payload.custom_fields:
        return
    if not values_ready(db):
        raise HTTPException(503, '自定义字段存储尚未初始化')
    definitions = db.query(Option).filter(Option.id.in_(payload.custom_fields), Option.kind == 'custom_field').all()
    if len(definitions) != len(payload.custom_fields):
        raise HTTPException(422, '自定义字段已不存在，请重新打开表单')
    current = {row.field_id: row for row in db.query(Value).filter(Value.record_id == record_id)}
    before, after = {}, {}
    for field_id, value in payload.custom_fields.items():
        row = current.get(field_id)
        old = row.value if row else ''
        if old == value:
            continue
        before[str(field_id)], after[str(field_id)] = old, value
        if row is None:
            db.add(Value(record_id=record_id, field_id=field_id, value=value))
        else:
            row.value = value
    if after:
        from resource_development_models import DevelopmentAudit
        db.add(DevelopmentAudit(entity_id=record_id, entity_type='record_custom_fields', actor_id=user.id,
                                action='update', before=before, after=after))


def account_columns(db):
    from resource_development_models import DevelopmentResourceContact as Contact
    from sqlalchemy import text
    if db.get_bind().dialect.name == 'postgresql':
        sql = "SELECT DISTINCT account->>'name' AS name FROM resource_development_resource_contact CROSS JOIN LATERAL json_array_elements(custom_accounts) AS account ORDER BY name"
    else:
        sql = "SELECT DISTINCT json_extract(account.value, '$.name') AS name FROM resource_development_resource_contact AS contact, json_each(contact.custom_accounts) AS account ORDER BY name"
    names = {}
    for name, in db.execute(text(sql)):
        if name and name.strip():
            names.setdefault(name.strip().lower(), name.strip())
    return [{'key': 'custom_account:' + key, 'name': value} for key, value in names.items()]


def account_value_match(db, name, pattern):
    from resource_development_models import DevelopmentResourceContact as Contact
    from search_matching import keyword_ilike
    if db.get_bind().dialect.name == 'postgresql':
        entries = func.json_array_elements(Contact.custom_accounts).table_valued('value').alias('account_value')
        label, value = entries.c.value.op('->>')('name'), entries.c.value.op('->>')('value')
    else:
        entries = func.json_each(Contact.custom_accounts).table_valued('key', 'value').alias('account_value')
        label, value = func.json_extract(entries.c.value, '$.name'), func.json_extract(entries.c.value, '$.value')
    return db.query(Contact).filter(Contact.record_id == Record.id,
        select(1).select_from(entries).where(func.lower(label) == name.lower(), keyword_ilike(value, pattern)).exists()).exists()
