from uuid import UUID, uuid4
import re
from fastapi import HTTPException
from sqlalchemy import inspect, func
from models import AppUser
from annotation_models import AnnotationProject
from discussion_chat_models import DiscussionMember, DiscussionMessage
from technical_requirement_models import TechnicalRoom, TechnicalAppend
from chat_time import now, api_time

DEFAULT_PEOPLE = [('黎涛',{'litao'}),('黄萌',{'huangmeng'}),('伟豪',{'weihao'}),('赵震锋',{'williamzhao'})]
IT_NAMES = {'it','it部','技术部','信息技术部'}


def ready(db):
    return inspect(db.connection()).has_table(TechnicalRoom.__tablename__)


def specs(db):
    if not ready(db): return []
    from discussion_chat_service import ANNOTATION_ROOT
    return [dict(id=str(room.room_id),name=f'技术需求 · {project.project_name or project.order_no}',parent_key=ANNOTATION_ROOT,
        technical_project_id=str(project.id),technical_order_no=project.order_no) for room,project in db.query(TechnicalRoom,AnnotationProject).join(AnnotationProject,AnnotationProject.id==TechnicalRoom.project_id)]


def default_members(db, project, user):
    from department_models import Department,DepartmentMember
    people=db.query(AppUser).filter(AppUser.is_active.is_(True)).all()
    ids={user.id}
    ids.update(row['assignee_id'] for row in project.role_assignments if row['role_code']=='project_manager' and row['assignee_id'])
    missing=[]
    for label, usernames in DEFAULT_PEOPLE:
        found=[p for p in people if (p.username or '').casefold() in usernames or (p.full_name or '') in ({label,'陈伟豪'} if label=='伟豪' else {label})]
        if not found: missing.append(label)
        ids.update(p.id for p in found)
    it_ids=set(uid for uid, in db.query(DepartmentMember.user_id).join(Department,Department.id==DepartmentMember.department_id).filter(func.lower(Department.name).in_(IT_NAMES)))
    it_ids.update(p.id for p in people if any(part.casefold() in IT_NAMES for part in re.split(r'[,，、;；|/\s]+',(p.department or ''))))
    if not it_ids: missing.append('IT部成员')
    if missing: raise HTTPException(422,'默认成员未匹配：'+'、'.join(missing))
    ids.update(it_ids)
    return [p for p in people if p.id in ids]


def serialize(db, row):
    project=db.get(AnnotationProject,row.project_id)
    return api_time(dict(room_id=row.room_id,project_id=row.project_id,title=f'技术需求 · {project.project_name or project.order_no}',
        order_no=project.order_no,requirements=row.requirements,revision=row.revision,updated_at=row.updated_at))


def open_room(db,user,project_id,extra_ids):
    from annotation_chat_service import require_project
    project=require_project(db,project_id,user,lock=True)
    if not ready(db): raise HTTPException(503,'技术需求尚未初始化')
    defaults=default_members(db,project,user)
    targets=db.query(AppUser).filter(AppUser.id.in_(set(extra_ids)),AppUser.is_active.is_(True)).all() if extra_ids else []
    if len(targets)!=len(set(extra_ids)): raise HTTPException(422,'选择的人员已停用或不存在')
    row=db.get(TechnicalRoom,project_id)
    from chat_session_category_models import ChatSessionCategory,ChatSessionCategoryFolder
    from discussion_chat_service import ANNOTATION_ROOT
    if row is None:
        room_id=uuid4()
        db.add(ChatSessionCategory(id=room_id,name=f'技术需求 · {project.project_name or project.order_no}'[:80],updated_by=user.id))
        db.flush()
        db.add(ChatSessionCategoryFolder(category_id=room_id,parent_key=ANNOTATION_ROOT))
        row=TechnicalRoom(project_id=project_id,room_id=room_id,requirements='',revision=1,created_by=user.id,updated_by=user.id)
        db.add(row);db.flush()
    else:
        category=db.get(ChatSessionCategory,row.room_id)
        if category is not None: category.active=True
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert=pg_insert if db.get_bind().dialect.name=='postgresql' else sqlite_insert
    for person in {p.id:p for p in [*defaults,*targets]}.values():
        db.execute(insert(DiscussionMember).values(room_id=row.room_id,user_id=person.id,last_read_id=0,pinned=False,starred=False).on_conflict_do_nothing())
    db.commit()
    from discussion_chat_service import publish
    publish(db)
    return serialize(db,row)


def get_room(db,user,room_id,lock=False):
    query=db.query(TechnicalRoom).filter_by(room_id=room_id)
    row=(query.with_for_update().populate_existing() if lock else query).first()
    if row is None: raise HTTPException(404,'技术需求会话不存在')
    from discussion_chat_service import require_room
    require_room(db,user,room_id)
    return row


def notify(db,row):
    from notification_ws import broadcast_to_users
    users=[uid for uid, in db.query(DiscussionMember.user_id).filter_by(room_id=row.room_id)]
    broadcast_to_users(users,{'type':'technical_requirements_changed','roomId':str(row.room_id)})


def save(db,user,room_id,content,revision):
    row=get_room(db,user,room_id,lock=True)
    if row.revision!=revision: raise HTTPException(409,'需求汇总已被他人更新，请重新加载后合并修改')
    row.requirements=content;row.revision+=1;row.updated_by=user.id;row.updated_at=now()
    db.commit()
    notify(db,row)
    return serialize(db,row)


def append(db,user,room_id,message_id,request_id):
    row=get_room(db,user,room_id,lock=True)
    if db.query(TechnicalAppend).filter_by(room_id=room_id,request_id=request_id).first(): return serialize(db,row)
    message=db.query(DiscussionMessage).filter_by(id=message_id,room_id=room_id).first()
    if message is None or message.recalled_at or not message.content.strip(): raise HTTPException(404,'原消息不存在、已撤回或没有文字')
    content='\n\n'.join(part for part in (row.requirements.rstrip(),message.content.strip()) if part)
    if len(content)>100000: raise HTTPException(422,'需求汇总超过十万字，请先整理内容')
    row.requirements=content;row.revision+=1;row.updated_by=user.id;row.updated_at=now()
    db.add(TechnicalAppend(room_id=room_id,request_id=request_id,message_id=message_id,created_by=user.id))
    db.commit()
    notify(db,row)
    return serialize(db,row)
