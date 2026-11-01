"""技术任务会话复用讨论消息，部门权限覆盖目录、成员和历史检索。"""
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import DateTime, ForeignKey, Uuid, inspect
from sqlalchemy.orm import mapped_column
from models import Base, AppUser
from chat_time import now
import technical_development as tasks
from chat_session_category_models import ChatSessionCategory as Category, ChatSessionCategoryFolder as Folder
from discussion_chat_models import DiscussionMember

ROOT_ID = 'dcb1f917-6000-4000-8000-000000000012'
GENERAL_NAME = '技术/开发沟通'

class TaskConversation(Base):
    __tablename__ = 'technical_task_conversation'
    task_id = mapped_column(Uuid, ForeignKey('technical_development_task.id'), primary_key=True)
    room_id = mapped_column(Uuid, ForeignKey('chat_session_category.id'), nullable=False, unique=True)
    created_by = mapped_column(Uuid, ForeignKey('app_user.id'), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=now)

def ready(db): return inspect(db.connection()).has_table(TaskConversation.__tablename__)

def can_access(db,user): return isinstance(user,AppUser) and tasks.can_enter(db,user)

def require_category_access(db,user,category_id):
    if category_id is not None and UUID(str(category_id)) in restricted_ids(db) and not can_access(db,user):
        raise HTTPException(403,'技术/开发项目仅开发/IT部可访问')

def restricted_ids(db):
    ids={UUID(ROOT_ID)}
    if inspect(db.connection()).has_table(Folder.__tablename__):
        locations=db.query(Folder).all()
        for _ in range(3): ids.update(row.category_id for row in locations if row.parent_key in {str(uid) for uid in ids})
    if inspect(db.connection()).has_table(Category.__tablename__): ids.update(uid for uid, in db.query(Category.id).filter(Category.name==GENERAL_NAME))
    if ready(db): ids.update(uid for uid, in db.query(TaskConversation.room_id))
    return ids

def eligible(db):
    from organization_service import department_condition
    return db.query(AppUser).filter(AppUser.is_active.is_(True), AppUser.is_deleted.is_(False),department_condition(db,tasks.TECHNICAL_DEPARTMENTS))

def specs(db):
    if not ready(db): return {}
    from technical_task_management import numbers
    task_numbers=numbers(db)
    return {str(link.room_id):dict(id=str(link.room_id),name=f"{task_numbers.get(task.id,'')} · {task.name}"[:80],parent_key=ROOT_ID,technical_task_id=str(task.id)) for link,task in db.query(TaskConversation,tasks.DevelopmentTask).join(tasks.DevelopmentTask,tasks.DevelopmentTask.id==TaskConversation.task_id)}

def snapshots(db):
    if not ready(db): return {}
    return {row.task_id:dict(room_id=row.room_id,created=True) for row in db.query(TaskConversation)}

def add_members(db,room_id,pinned=False):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert=pg_insert if db.get_bind().dialect.name=='postgresql' else sqlite_insert
    for person in eligible(db):
        db.execute(insert(DiscussionMember).values(room_id=room_id,user_id=person.id,last_read_id=0,pinned=pinned,starred=False).on_conflict_do_nothing())

def open_conversation(db,user,task_id):
    tasks.require_user(user,db);tasks.require_ready(db);tasks.lock_tree(db)
    if not ready(db): raise HTTPException(503,'开发任务会话关联表尚未初始化')
    task=tasks.get_task(db,task_id)
    import technical_task_allocations as allocations
    if task_id in allocations.executions(db): raise HTTPException(422,'请从所属技术任务创建会话')
    row=db.get(TaskConversation,task_id)
    if row is None:
        room_id=uuid4()
        # 保存稳定唯一名称，展示名称由任务编号及名称实时生成。
        db.add(Category(id=room_id,name=f'开发 · {str(task.id)}',updated_by=user.id))
        db.flush()
        db.add(Folder(category_id=room_id,parent_key=ROOT_ID))
        row=TaskConversation(task_id=task_id,room_id=room_id,created_by=user.id)
        db.add(row);db.flush()
    else:
        category=db.get(Category,row.room_id)
        if not category.active: category.active=True;category.revision+=1;category.updated_by=user.id;category.updated_at=now()
        folder=db.get(Folder,row.room_id)
        if folder is None: db.add(Folder(category_id=row.room_id,parent_key=ROOT_ID))
        else: folder.parent_key=ROOT_ID
    add_members(db,row.room_id)
    db.commit()
    from discussion_chat_service import publish
    publish(db)
    return dict(room_id=row.room_id,title=specs(db)[str(row.room_id)]['name'],task_id=task_id)

def configure_general(db, actor=None, expected_revision=None):
    """显式执行用户要求的移动和置顶；不改原消息或移除成员。"""
    rows=db.query(Category).filter(Category.name==GENERAL_NAME,Category.active.is_(True)).with_for_update().all()
    if len(rows)!=1: raise RuntimeError('技术/开发沟通必须且只能匹配到一个在用会话')
    room=rows[0]
    if expected_revision is not None and room.revision != expected_revision: raise RuntimeError('技术/开发沟通版本已变化，请重新检查')
    if not db.query(DiscussionMember).filter_by(room_id=room.id).first(): raise RuntimeError('目标记录不是已有会话，停止操作')
    folder=db.get(Folder,room.id)
    if folder is None: db.add(Folder(category_id=room.id,parent_key=ROOT_ID))
    else: folder.parent_key=ROOT_ID
    if actor is not None:
        tasks.require_user(actor,db)
        room.revision+=1;room.updated_by=actor.id;room.updated_at=now()
    add_members(db,room.id,pinned=True)
    ids=[person.id for person in eligible(db)]
    db.query(DiscussionMember).filter(DiscussionMember.room_id==room.id,DiscussionMember.user_id.in_(ids)).update({DiscussionMember.pinned:True},synchronize_session=False)
    return dict(room_id=str(room.id),department_members=len(ids),moved=True,pinned=True)
