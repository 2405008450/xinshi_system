"""总结字段、人员/部门范围与业务通知；权限继续由开拓事项逐条控制。"""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import or_
from models import AppUser
from department_models import Department
from resource_issue_models import DevelopmentIssueAudience as Audience

CATEGORY_LABELS={'arrangement':'信息同步','request':'提出需求','idea':'想法讨论','decision':'决策批复','execution':'任务执行','problem':'问题/异常','risk':'风险隐患','standard':'规则标准'}


def write_summary(db,row,value):
    if value is None:return
    if row.category!='execution' and (value.follower_user_ids or value.planned_completion_at or value.actual_progress):
        raise HTTPException(422,'仅任务执行类型可以设置完成时间、跟进人和实际进度')
    followers=set(value.follower_user_ids);explicit=set(value.notify_user_ids);department_ids=set(value.notify_department_ids)
    users={person.id:person for person in db.query(AppUser).filter(AppUser.is_active.is_(True)).all()}
    if not (followers|explicit)<=users.keys():raise HTTPException(422,'部分人员不存在或已停用，请重新选择')
    departments={item.id:item for item in db.query(Department).filter(Department.id.in_(department_ids))} if department_ids else {}
    if len(departments)!=len(department_ids):raise HTTPException(422,'部分部门已不存在，请重新选择')
    department_names={name for item in departments.values() for name in [item.name,*(item.aliases or [])]}
    from organization_service import department_condition
    recipients=explicit|({uid for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True), department_condition(db, department_names))} if department_names else set())
    row.summary_data=value.model_dump(mode='json')
    db.query(Audience).filter(Audience.issue_id==row.id).delete(synchronize_session=False)
    entries={('follower',uid) for uid in followers}|{('notify_user',uid) for uid in recipients}|{('notify_department',uid) for uid in department_ids}
    db.add_all([Audience(issue_id=row.id,kind=kind,target_id=uid) for kind,uid in entries])
    if recipients:
        from crud import create_notifications_for_users
        notifications=create_notifications_for_users(db,list(recipients),f'总结同步 · {CATEGORY_LABELS[row.category]}',
            row.content[:1000],notification_type='chat_summary',related_project_type='chat_summary',related_entity_id=row.id,commit=False)
        from resource_issue_models import business_now
        for notification in notifications:notification.created_at=business_now().replace(tzinfo=None)
        db.info.setdefault('summary_notifications',[]).extend(notifications)


def commit_notifications(db):
    notifications=db.info.pop('summary_notifications',[])
    db.commit()
    if notifications:
        from notification_ws import dispatch_personal_message
        from schemas import NotificationResponse
        for notification in notifications:
            dispatch_personal_message(notification.recipient_user_id,{'type':'notification','notification':NotificationResponse.model_validate(notification).model_dump(mode='json')})


def display_data(db,rows):
    user_ids=set();dept_ids=set()
    for row in rows:
        data=row.summary_data or {}
        user_ids.update(UUID(uid) for key in ['follower_user_ids','notify_user_ids'] for uid in data.get(key,[]))
        dept_ids.update(UUID(uid) for uid in data.get('notify_department_ids',[]))
    people={str(person.id):person.full_name or person.username for person in db.query(AppUser).filter(AppUser.id.in_(user_ids))} if user_ids else {}
    departments={str(item.id):item.name for item in db.query(Department).filter(Department.id.in_(dept_ids))} if dept_ids else {}
    result={}
    for row in rows:
        data=row.summary_data or {}
        result[row.id]=dict(summary=data,specific_classification=data.get('specific_classification',row.topic_path or ''),
            planned_completion_at=data.get('planned_completion_at'),actual_progress=data.get('actual_progress',''),
            follower_names=[people.get(uid,'已删除人员') for uid in data.get('follower_user_ids',[])],
            notify_user_names=[people.get(uid,'已删除人员') for uid in data.get('notify_user_ids',[])],
            notify_department_names=[departments.get(uid,'已删除部门') for uid in data.get('notify_department_ids',[])])
    return result


def progress_allowed(user,row):
    return row.category=='execution' and str(user.id) in (row.summary_data or {}).get('follower_user_ids',[])
