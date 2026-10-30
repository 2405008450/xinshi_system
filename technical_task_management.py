"""任务层级编号、位置互换和保留关联记录的删除管理。"""
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import DateTime, ForeignKey, String, Uuid, inspect
from sqlalchemy.orm import mapped_column
from models import Base
from chat_time import now
import technical_development as tasks


class TaskHierarchyNumber(Base):
    __tablename__ = 'technical_task_hierarchy_number'
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), primary_key=True)
    task_no = mapped_column(String(40), nullable=False, unique=True)


class TaskDeletion(Base):
    __tablename__ = 'technical_task_deletion'
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), primary_key=True)
    deleted_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    deleted_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)


TABLES = [TaskHierarchyNumber.__table__, TaskDeletion.__table__]

def ready(db):
    return all(inspect(db.connection()).has_table(table.name) for table in TABLES)

def require_ready(db):
    if not ready(db): raise HTTPException(503, '任务层级编号及删除管理表尚未初始化')

def deleted_ids(db):
    return {uid for uid, in db.query(TaskDeletion.task_id)} if ready(db) else set()

def is_deleted(db, task_id):
    return ready(db) and db.get(TaskDeletion, task_id) is not None

def active_tasks(db):
    query = db.query(tasks.DevelopmentTask)
    if ready(db): query = query.filter(~db.query(TaskDeletion.task_id).filter(TaskDeletion.task_id == tasks.DevelopmentTask.id).exists())
    return query.all()

def numbers(db):
    values = dict(db.query(tasks.DevelopmentTaskNumber.task_id, tasks.DevelopmentTaskNumber.task_no))
    if ready(db): values.update(dict(db.query(TaskHierarchyNumber.task_id, TaskHierarchyNumber.task_no)))
    return values

def next_child(db, parent_number):
    prefix = parent_number + '.'
    used = [int(value[len(prefix):]) for value, in db.query(TaskHierarchyNumber.task_no) if value.startswith(prefix) and value[len(prefix):].isdigit()]
    return prefix + f'{max(used, default=0)+1:03d}'

def assign_number(db, task_id):
    if not ready(db): return
    if db.get(TaskHierarchyNumber, task_id): return
    task = db.get(tasks.DevelopmentTask, task_id)
    if task.parent_id:
        assign_number(db, task.parent_id)
        value = next_child(db, db.get(TaskHierarchyNumber, task.parent_id).task_no)
    else:
        value = db.get(tasks.DevelopmentTaskNumber, task_id).task_no
    db.add(TaskHierarchyNumber(task_id=task_id, task_no=value)); db.flush()

def initialize_numbers(db):
    tasks.lock_tree(db)
    for row in db.query(tasks.DevelopmentTask).join(tasks.DevelopmentTaskNumber).order_by(tasks.DevelopmentTaskNumber.number_date, tasks.DevelopmentTaskNumber.sequence):
        assign_number(db, row.id)

def renumber_subtree(db, task_id):
    require_ready(db)
    rows = {row.id: row for row in db.query(tasks.DevelopmentTask)}
    mapping = {row.task_id: row for row in db.query(TaskHierarchyNumber)}
    row = rows[task_id]
    if row.parent_id:
        value = next_child(db, mapping[row.parent_id].task_no)
    else:
        day = now().strftime('%y%m%d')
        prefix = f'DT-{day}-'
        used = [int(item.task_no[len(prefix):]) for item in mapping.values() if item.task_no.startswith(prefix) and item.task_no[len(prefix):].isdigit()]
        value = prefix + f'{max(used,default=0)+1:03d}'
    old = mapping[task_id].task_no
    changes = {uid: value + item.task_no[len(old):] for uid,item in mapping.items() if uid==task_id or item.task_no.startswith(old+'.')}
    # 先释放唯一键，整个操作在同一树锁、事务内完成。
    for uid in changes: mapping[uid].task_no = 'tmp-' + uuid4().hex
    db.flush()
    for uid,number in changes.items(): mapping[uid].task_no = number
    db.flush()

def delete_task(db, user, task_id, revision):
    tasks.require_user(user, db); tasks.require_ready(db); require_ready(db); tasks.lock_tree(db)
    if db.get(TaskDeletion, task_id): return dict(deleted=True, task_id=task_id)
    row = tasks.get_task(db, task_id, revision)
    import technical_task_allocations as allocations
    if task_id in allocations.executions(db): raise HTTPException(422, '分工执行记录请随所属任务一起删除')
    removed = deleted_ids(db)
    if any(child.id not in removed for child in db.query(tasks.DevelopmentTask).filter_by(parent_id=task_id)):
        raise HTTPException(409, '任务下还有子任务，请先删除子任务，或同时选择下属任务')
    ids = {task_id} | {link.execution_task_id for link in db.query(allocations.TaskAllocation).filter_by(root_task_id=task_id)} if allocations.ready(db) else {task_id}
    stamp = now()
    for uid in ids - removed: db.add(TaskDeletion(task_id=uid,deleted_by=user.id,deleted_at=stamp))
    row.revision += 1; row.updated_by=user.id; row.updated_at=stamp
    db.commit()
    return dict(deleted=True, task_id=task_id)

def swap_tasks(db, user, task_id, data):
    tasks.require_user(user, db); tasks.require_ready(db); require_ready(db); tasks.lock_tree(db)
    if task_id == data.target_id: raise HTTPException(422,'请选择另一任务')
    first=tasks.get_task(db,task_id,data.revision)
    second=tasks.get_task(db,data.target_id,data.target_revision)
    import technical_task_allocations as allocations
    hidden=allocations.executions(db)
    if task_id in hidden or data.target_id in hidden: raise HTTPException(422,'分工执行记录不参与层级互换')
    replace={first.id:second.id,second.id:first.id}
    all_rows=db.query(tasks.DevelopmentTask).all()
    by_id={row.id:row for row in all_rows}
    original={row.id:row.parent_id for row in all_rows}
    stamp=now()
    for old_id,parent_id in original.items():
        row=by_id[replace.get(old_id,old_id)]
        target_parent=replace.get(parent_id,parent_id)
        if row.parent_id != target_parent or row.id in replace:
            row.parent_id=target_parent;row.revision+=1;row.updated_at=stamp;row.updated_by=user.id
    a=db.get(TaskHierarchyNumber,first.id);b=db.get(TaskHierarchyNumber,second.id)
    first_number,second_number=a.task_no,b.task_no
    a.task_no='tmp-'+uuid4().hex;b.task_no='tmp-'+uuid4().hex;db.flush()
    a.task_no=second_number;b.task_no=first_number
    db.commit()
    return dict(swapped=True)
