"""讨论 @ 的持久关系、候选人员和通知；从不解析正文伪造提醒。"""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import inspect
from models import AppUser
from discussion_chat_models import DiscussionMention as Mention, DiscussionMember as Member, DiscussionMessage as Message


def ready(db):
    return inspect(db.connection()).has_table(Mention.__tablename__)


def eligible_users(db, room, ids=None):
    from sqlalchemy import or_,func
    from models import Role,UserRole,RolePermission
    from permission_registry import SUPER_ROLE_NAMES
    import discussion_chat_service as service
    query=db.query(AppUser).filter(AppUser.is_active.is_(True))
    if ids is not None:query=query.filter(AppUser.id.in_(ids))
    if room.get('parent_key',service.RESOURCE_ROOT)==service.RESOURCE_ROOT:
        query=query.outerjoin(UserRole,UserRole.user_id==AppUser.id).outerjoin(Role,Role.id==UserRole.role_id).outerjoin(RolePermission,RolePermission.role_id==Role.id).filter(or_(func.lower(AppUser.username)=='jimmy',Role.role_name.in_(SUPER_ROLE_NAMES),RolePermission.permission_code.in_([*service.VIEW_PERMISSIONS,'*'])))
    return query.distinct().order_by(AppUser.username).all()


def group(db, user, room_id):
    import discussion_chat_service as service
    room = service.require_room(db,user,room_id)
    member_ids = {uid for uid, in db.query(Member.user_id).filter_by(room_id=room_id)}
    users = eligible_users(db,room)
    serialize = lambda person:dict(id=str(person.id),name=person.full_name or person.username)
    return dict(members=[serialize(person) for person in users if person.id in member_ids],eligible_users=[serialize(person) for person in users if person.id in member_ids],invitable_users=[serialize(person) for person in users if person.id not in member_ids])


def recipients(db,user,room_id,payload):
    import discussion_chat_service as service
    room=service.require_room(db,user,room_id)
    explicit=set(getattr(payload,'mentioned_user_ids',[]) or [])-{user.id}
    members={uid for uid, in db.query(Member.user_id).filter_by(room_id=room_id)}
    requested=explicit|(members-{user.id} if getattr(payload,'mention_all',False) else set())
    people=eligible_users(db,room,requested) if requested else []
    if not explicit.issubset({person.id for person in people}):raise HTTPException(422,'被提及的用户不存在、已停用或没有会话权限')
    return people,members


def create(db,user,message,payload,people,members):
    if not people:return []
    if not ready(db):raise HTTPException(503,'讨论提及表尚未初始化')
    from crud import create_notifications_for_users
    from chat_time import now
    notifications=create_notifications_for_users(db,[person.id for person in people],title='讨论提及提醒',content=f'{message.sender_name} 在讨论中 @了你，点击查看消息',notification_type='discussion_chat_mention',related_project_type='discussion',related_entity_id=message.room_id,commit=False)
    by_user={notice.recipient_user_id:notice for notice in notifications}
    for person in people:
        if person.id not in members:db.add(Member(room_id=message.room_id,user_id=person.id,last_read_id=max(0,message.id-1),pinned=False,starred=False))
        notice=by_user.get(person.id)
        if notice:notice.created_at=now().replace(tzinfo=None)
        db.add(Mention(message_id=message.id,user_id=person.id,user_name=person.full_name or person.username,is_all=getattr(payload,'mention_all',False),notification_id=notice.id if notice else None))
    return notifications


def serialize(db,message_id):
    if not ready(db):return []
    return [dict(mentioned_user_id=str(row.user_id),mentioned_user_name=row.user_name,is_all=row.is_all) for row in db.query(Mention).filter_by(message_id=message_id).order_by(Mention.user_name,Mention.user_id)]
