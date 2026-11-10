"""跨进程、账号与窗口的业务编号租约；保存与占号确认处于同一事务。"""
import json
import re
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import DateTime, ForeignKey, String, Uuid, UniqueConstraint, JSON, inspect, select, text
from sqlalchemy.orm import mapped_column, Session
from models import Base
from chat_time import now


class BusinessNumberLease(Base):
    __tablename__ = 'business_number_lease'
    __table_args__ = (
        UniqueConstraint('scope', 'number', name='uq_business_number_lease_number'),
    )
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False, index=True)
    window_id = mapped_column(Uuid, nullable=False, index=True)
    scope = mapped_column(String(180), nullable=False, index=True)
    number = mapped_column(String(100), nullable=False)
    state = mapped_column(String(20), nullable=False, default='active')
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)


class BusinessNumberDeletionHistory(Base):
    """独立于业务主表，编号复用或主记录硬删除后仍保留每次删除快照。"""
    __tablename__ = 'business_number_deletion_history'
    id = mapped_column(Uuid, primary_key=True, default=uuid4)
    scope = mapped_column(String(180), nullable=False, index=True)
    number = mapped_column(String(100), nullable=False, index=True)
    entity_type = mapped_column(String(100), nullable=False)
    entity_id = mapped_column(String(80), nullable=False, index=True)
    entity_name = mapped_column(String(500))
    actor_id = mapped_column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    actor_name = mapped_column(String(255))
    deleted_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)
    snapshot = mapped_column(JSON, nullable=False)


def history_ready(db):
    if not isinstance(db, Session):
        return False
    if 'business_number_history_ready' not in db.info:
        db.info['business_number_history_ready'] = inspect(db.connection()).has_table(BusinessNumberDeletionHistory.__tablename__)
    return db.info['business_number_history_ready']


def archive_number(db, scope, number, row, *, actor=None, extra=None):
    """与删除同事务保存快照并释放占号；提交失败时两者一起回滚。"""
    if not number:
        return
    if not history_ready(db):
        raise HTTPException(503, '编号删除记录表尚未初始化，未执行删除')
    from fastapi.encoders import jsonable_encoder
    entity_id = str(getattr(row, 'id', None) or getattr(row, 'task_id', None))
    key = (scope, number, row.__tablename__, entity_id)
    if key in db.info.setdefault('number_archived', set()):
        return
    db.info['number_archived'].add(key)
    lock_scope(db, scope)
    values = {column.key:getattr(row,column.key) for column in inspect(row).mapper.column_attrs}
    values.update(extra or {})
    owner = getattr(actor, 'id', None) or db.info.get('number_actor')
    name = getattr(actor, 'full_name', None) or getattr(actor, 'username', None) or db.info.get('number_actor_name')
    label = next((str(values[field]) for field in ('project_name','sub_project_name','client_short_name','client_name','full_name','translator_name','name','position') if values.get(field)), '')
    db.add(BusinessNumberDeletionHistory(id=uuid4(),scope=scope,number=number,entity_type=row.__tablename__,entity_id=entity_id,entity_name=label[:500],actor_id=owner,actor_name=name,snapshot=jsonable_encoder(values)))
    if ready(db):
        lease = db.query(BusinessNumberLease).filter_by(scope=scope,number=number).with_for_update().first()
        if lease:
            lease.state='released'
            lease.expires_at=now()


def ready(db):
    if not isinstance(db, Session):
        return False
    if 'business_number_ready' not in db.info:
        db.info['business_number_ready'] = inspect(db.connection()).has_table('business_number_lease')
    return db.info['business_number_ready']


def lock_scope(db, scope):
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(hashtext(:scope))'), {'scope': 'business-number:' + scope})


def tokens(db):
    try:
        return [UUID(str(value)) for value in json.loads(db.info.get('number_tokens', '[]'))][:32]
    except (ValueError, TypeError):
        raise HTTPException(400, '编号占用凭证格式错误')


def live(row):
    # SQLite 隔离测试不保留时区；业务库使用 timestamptz。
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=now().tzinfo)
    return row.state == 'active' and expires > now()


def validate_tokens(db):
    supplied = set(tokens(db))
    if not supplied:
        return
    rows = db.query(BusinessNumberLease).filter(BusinessNumberLease.id.in_(supplied)).with_for_update().all()
    if len(rows) != len(supplied):
        raise HTTPException(409, '编号占用凭证已失效，请重新打开新增窗口取号；填写内容仍保留')
    consumed = db.info.get('number_consumed', set())
    for row in rows:
        if row.owner_id != db.info.get('number_actor') or (row.id not in consumed and not live(row)):
            raise HTTPException(409, '编号占用凭证已失效，请重新打开新增窗口取号；填写内容仍保留')


def allocate(db, scope, prefix, minimum=1, width=3):
    """先回收未落库的已释放/过期编号，再追加流水；每次占用使用新凭证。"""
    if not ready(db):
        if getattr(db, 'info', {}).get('number_reserve'):
            raise HTTPException(503, '业务编号占用表尚未初始化')
        return f'{prefix}{minimum:0{width}d}'
    lock_scope(db, scope)
    if not db.info.get('number_reserve'):
        validate_tokens(db)
    # 统一按整数比较流水，覆盖超过999、批量导入及无窗口的后台创建。
    kind = scope.split(':', 1)[0]
    source = SPECS.get(kind)
    if not source:
        source = {'translation_suborder':('translation_sub_order','sub_order_no',''),
                  'annotation_suborder':('annotation_project','order_no',''),
                  'subclient':('sub_client','sub_client_code',''),
                  'technical_subtask':('technical_task_hierarchy_number','task_no',''),
                  'greeting':('resource_development_record','greeting_no','')}.get(kind)
    pattern = re.compile(re.escape(prefix) + r'(\d+)$')
    stored_numbers = set()
    if source:
        table = Base.metadata.tables.get(source[0])
        if table is not None and inspect(db.connection()).has_table(source[0]):
            stored_numbers.update(db.execute(select(table.c[source[1]]).where(table.c[source[1]].startswith(prefix, autoescape=True))).scalars())
    # 标注历史订单号永久保留；人才编号还可能已存在于旧译员目录。
    extra_sources = []
    if kind in ('annotation', 'annotation_suborder'):
        extra_sources.append(('project_order_no_reservation', 'order_no'))
    if kind == 'talent':
        extra_sources.append(('translator', 'translator_code'))
    if kind in ('technical_task', 'technical_subtask'):
        extra_sources.append(('technical_task_hierarchy_number', 'task_no'))
    for name, column in extra_sources:
        table = Base.metadata.tables.get(name)
        if table is not None and inspect(db.connection()).has_table(name):
            stored_numbers.update(db.execute(select(table.c[column]).where(table.c[column].startswith(prefix, autoescape=True))).scalars())
    if kind != 'talent':
        minimum = max([minimum, *(int(match[1]) + 1 for value in stored_numbers if (match := pattern.fullmatch(value or '')))])
    supplied = tokens(db)
    if supplied and not db.info.get('number_reserve'):
        rows = db.query(BusinessNumberLease).filter(BusinessNumberLease.id.in_(supplied), BusinessNumberLease.scope == scope).with_for_update().all()
        for row in rows:
            if row.id in db.info.get('number_consumed', set()):
                continue
            if row.owner_id != db.info.get('number_actor') or not live(row):
                raise HTTPException(409, '编号占用已失效，请重新打开新增窗口取号；填写内容仍保留')
            if row.number.startswith(prefix):
                row.state = 'used'
                db.info.setdefault('number_consumed', set()).add(row.id)
                return row.number
    leases = db.query(BusinessNumberLease).filter(BusinessNumberLease.scope == scope, BusinessNumberLease.number.startswith(prefix, autoescape=True)).with_for_update().all()
    excluded = db.info.get('number_excluded', set())
    recycled = sorted((row for row in leases if (row.state in ('released', 'skipped') or row.state == 'active' and not live(row)) and row.number not in stored_numbers and row.number not in excluded and pattern.fullmatch(row.number)), key=lambda row:int(pattern.fullmatch(row.number)[1]))
    known = {row.number for row in leases}
    archived = set()
    if history_ready(db):
        archived = {number for number, in db.query(BusinessNumberDeletionHistory.number).filter(BusinessNumberDeletionHistory.scope == scope,BusinessNumberDeletionHistory.number.startswith(prefix,autoescape=True)).distinct() if number not in stored_numbers and number not in known and pattern.fullmatch(number)}
    available = [row.number for row in recycled] + list(archived)
    if available:
        number = min(available,key=lambda value:int(pattern.fullmatch(value)[1]))
        row = next((item for item in recycled if item.number == number),None)
        reserve = db.info.get('number_reserve')
        if row is None:
            actor = db.info.get('number_actor')
            if not actor:
                return number
            row = BusinessNumberLease(scope=scope,number=number,owner_id=actor)
            db.add(row)
        # 唯一约束仍覆盖(scope,number)；轮换主键凭证，旧窗口不能续期、释放或使用新占用。
        row.id = uuid4()
        row.owner_id = db.info.get('number_actor') or row.owner_id
        row.window_id = reserve or uuid4()
        row.state = 'active' if reserve else 'used'
        row.created_at = now()
        row.expires_at = now() + timedelta(minutes=15)
        if not db._flushing:
            db.flush()
        if reserve:
            db.info['number_reserved_row'] = row
        else:
            db.info.setdefault('number_consumed', set()).add(row.id)
        return row.number
    used = [int(match[1]) for row in leases if (match := pattern.fullmatch(row.number))]
    sequence = minimum if scope == 'talent' else max([minimum, *(value + 1 for value in used)])
    while scope == 'talent' and (sequence in used or f'{prefix}{sequence:0{width}d}' in stored_numbers):
        sequence = db.execute(text("SELECT nextval('resource_person_code_seq')")).scalar() if db.get_bind().dialect.name == 'postgresql' else sequence + 1
    number = f'{prefix}{sequence:0{width}d}'
    actor = db.info.get('number_actor')
    if actor:
        reserve = db.info.get('number_reserve')
        row = BusinessNumberLease(id=uuid4(), owner_id=actor, window_id=reserve or uuid4(), scope=scope, number=number,
                                  state='active' if reserve else 'used', expires_at=now() + timedelta(minutes=15))
        db.add(row)
        if not db._flushing:
            db.flush()
        if reserve:
            db.info['number_reserved_row'] = row
    return number


# 只有业务编号，不包含列表行号、版本号及外部系统编号。
SPECS = {
    'translation': ('translation_project', 'order_no', 'TP'),
    'interpretation': ('interpretation_project', 'order_no', 'IP'),
    'annotation': ('annotation_project', 'order_no', 'AP'),
    'recruitment': ('recruitment_project', 'order_no', 'HP'),
    'client': ('client', 'client_code', 'CL'),
    'consultation': ('consultation', 'consultation_code', 'EQ'),
    'resource_request': ('resource_request', 'request_no', 'RR'),
    'hr_requirement': ('hr_recruitment_requirement', 'demand_no', 'RT'),
    'technical_task': ('technical_development_task_number', 'task_no', 'DT'),
    'feedback': ('development_feedback', 'feedback_no', 'FB'),
    'talent': ('resource_person', 'resource_code', 'RC'),
}


def spec(db, kind, parent_id=None, business_date=None):
    scope = kind
    width = 3
    day = business_date or now().date()
    if kind in SPECS:
        table_name, column, code = SPECS[kind]
        prefix = f'{code}-{day:%y%m%d}-'
        if kind == 'talent':
            prefix, width = 'RC', 6
    elif kind == 'greeting':
        if not parent_id:
            raise HTTPException(422, '请先选择开拓平台')
        table = Base.metadata.tables['resource_development_option']
        code = db.execute(select(table.c.code).where(table.c.id == parent_id)).scalar()
        if not code:
            raise HTTPException(404, '开拓平台不存在或未设置代码')
        scope, prefix = f'greeting:{parent_id}', f'{code}-{day:%y%m%d}-'
        table_name, column = 'resource_development_record', 'greeting_no'
    elif kind in ('translation_suborder', 'annotation_suborder', 'subclient', 'technical_subtask'):
        if not parent_id:
            raise HTTPException(422, '请先选择上级记录')
        if kind == 'subclient':
            parent_table, parent_column, table_name, column = 'client', 'client_code', 'sub_client', 'sub_client_code'
        elif kind == 'annotation_suborder':
            parent_table, parent_column, table_name, column = 'annotation_project', 'order_no', 'annotation_project', 'order_no'
        elif kind == 'technical_subtask':
            parent_table, parent_column, table_name, column = 'technical_task_hierarchy_number', 'task_no', 'technical_task_hierarchy_number', 'task_no'
        else:
            parent_table, parent_column, table_name, column = 'translation_project', 'order_no', 'translation_sub_order', 'sub_order_no'
        table = Base.metadata.tables[parent_table]
        key = table.c.task_id if kind == 'technical_subtask' else table.c.id
        parent_no = db.execute(select(table.c[parent_column]).where(key == parent_id)).scalar()
        if not parent_no and kind == 'translation_suborder':
            table = Base.metadata.tables['translation_sub_order']
            parent_no = db.execute(select(table.c.sub_order_no).where(table.c.id == parent_id)).scalar()
        if not parent_no:
            raise HTTPException(404, '上级记录不存在')
        scope, prefix = f'{kind}:{parent_id}', parent_no + '.'
    else:
        raise HTTPException(422, '不支持的自动编号类型')
    table = Base.metadata.tables.get(table_name)
    if table is None or not inspect(db.connection()).has_table(table_name):
        raise HTTPException(503, '对应业务表尚未初始化')
    pattern = re.compile(re.escape(prefix) + r'(\d+)$')
    values = list(db.execute(select(table.c[column]).where(table.c[column].startswith(prefix, autoescape=True))).scalars())
    if kind in ('annotation','annotation_suborder') and inspect(db.connection()).has_table('project_order_no_reservation'):
        history = Base.metadata.tables['project_order_no_reservation']
        values += list(db.execute(select(history.c.order_no).where(history.c.project_type == 'annotation')).scalars())
    if kind == 'talent' and db.get_bind().dialect.name == 'postgresql':
        # 沿用现有序列，和人才导入/数据库触发器共用同一编号空间。
        minimum = db.execute(text("SELECT nextval('resource_person_code_seq')")).scalar()
        return scope, prefix, minimum, width
    else:
        minimum = 1
    minimum = max([minimum, *(int(match[1]) + 1 for value in values if (match := pattern.fullmatch(value or '')))])
    return scope, prefix, minimum, width


def consume_explicit(db, scope, number):
    """手填编号也不能绕过另一个窗口的有效占用。"""
    if not number or not ready(db):
        return
    lock_scope(db, scope)
    rows = db.query(BusinessNumberLease).filter_by(number=number).with_for_update().all()
    for row in rows:
        supplied = row.id in tokens(db)
        if row.id in db.info.get('number_consumed', set()):
            continue
        if supplied and (row.owner_id != db.info.get('number_actor') or not live(row)):
            raise HTTPException(409, '编号占用已失效，请重新打开新增窗口取号')
        if not live(row):
            continue
        if not supplied or row.owner_id != db.info.get('number_actor'):
            raise HTTPException(409, '该编号已被其他窗口占用，请重新取号')
        row.state = 'used'
        db.info.setdefault('number_consumed', set()).add(row.id)


def translation_suborder_parent(db, row):
    """点号层级的直接父单；二级子单的编号池独立于母订单。"""
    from models import TranslationSubOrder
    prefix = str(row.sub_order_no or '').rsplit('.', 1)[0]
    if '.' in prefix:
        parent = db.query(TranslationSubOrder.id).filter(
            TranslationSubOrder.parent_project_id == row.parent_project_id,
            TranslationSubOrder.sub_order_no == prefix,
        ).scalar()
        if parent:
            return parent
    return row.parent_project_id


def install_number_guards():
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    @event.listens_for(Session, 'before_flush')
    def guard(db, context, instances):
        if db.info.get('number_guard_running'):
            return
        db.info['number_guard_running'] = True
        try:
            targets = {table: (kind, field) for kind, (table, field, _) in SPECS.items()}
            targets['translation_sub_order'] = ('translation_suborder', 'sub_order_no')
            targets['sub_client'] = ('subclient', 'sub_client_code')
            targets['translator'] = ('talent', 'translator_code')
            targets['resource_development_record'] = ('greeting', 'greeting_no')
            # ORM 硬删除及 delete-orphan 级联删除共用同一历史/回池规则。
            for row in list(db.deleted):
                table = getattr(row,'__tablename__','')
                if table not in targets or table == 'technical_development_task_number':
                    continue
                kind, field = targets[table]
                value = getattr(row,field,None)
                scope = kind
                if kind in ('translation_suborder','subclient'):
                    parent = translation_suborder_parent(db, row) if kind == 'translation_suborder' else row.parent_client_id
                    scope = f'{kind}:{parent}'
                elif kind == 'annotation' and getattr(row,'parent_project_id',None):
                    scope = f'annotation_suborder:{row.parent_project_id}'
                elif kind == 'greeting':
                    scope = f'greeting:{row.platform_id}'
                archive_number(db,scope,value,row)
                if kind == 'annotation' and inspect(db.connection()).has_table('project_order_no_reservation'):
                    from project_order_no_models import ProjectOrderNoReservation
                    for reservation in db.query(ProjectOrderNoReservation).filter_by(project_type='annotation',project_id=row.id).all():
                        if reservation.order_no != value:
                            archive_number(db,scope,reservation.order_no,row,extra={'order_no':reservation.order_no,'last_project_order_no':value})
                        db.delete(reservation)
            for row in [*db.new, *db.dirty]:
                table = getattr(row, '__tablename__', '')
                if table not in targets:
                    continue
                kind, field = targets[table]
                if row not in db.new and not inspect(row).attrs[field].history.has_changes():
                    continue
                value = getattr(row, field, None)
                if kind == 'talent' and not value and ready(db):
                    _, prefix, minimum, width = spec(db, 'talent')
                    value = allocate(db, 'talent', prefix, minimum, width)
                    setattr(row,field,value)
                if not value:
                    continue
                if kind in ('translation_suborder', 'subclient'):
                    parent = translation_suborder_parent(db, row) if kind == 'translation_suborder' else row.parent_client_id
                    kind = f'{kind}:{parent}'
                elif kind == 'annotation' and getattr(row, 'parent_project_id', None):
                    kind = f'annotation_suborder:{row.parent_project_id}'
                consume_explicit(db, kind, value)
        finally:
            db.info['number_guard_running'] = False
    @event.listens_for(Session, 'after_transaction_end')
    def clear_transaction_state(db, transaction):
        if transaction.parent is None:
            db.info.pop('number_archived',None)
            db.info.pop('number_consumed',None)
