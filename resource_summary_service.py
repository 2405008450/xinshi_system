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
    if 'view_all' not in value.model_fields_set:
        from resource_issue_schemas import SummaryFields
        data=value.model_dump()
        data.update({key:(row.summary_data or {}).get(key,data[key]) for key in ('view_all','view_user_ids','view_department_ids')})
        value=SummaryFields.model_validate(data)
    if row.category!='execution' and (value.follower_user_ids or value.planned_completion_at or value.actual_progress):
        raise HTTPException(422,'仅任务执行类型可以设置完成时间、跟进人和实际进度')
    followers=set(value.follower_user_ids);explicit=set(value.notify_user_ids);department_ids=set(value.notify_department_ids)
    users={person.id:person for person in db.query(AppUser).filter(AppUser.is_active.is_(True)).all()}
    view_users=set(value.view_user_ids);view_departments=set(value.view_department_ids)
    if not (followers|explicit|view_users)<=users.keys():raise HTTPException(422,'部分人员不存在或已停用，请重新选择')
    all_departments=department_ids|view_departments
    departments={item.id:item for item in db.query(Department).filter(Department.id.in_(all_departments))} if all_departments else {}
    if len(departments)!=len(all_departments):raise HTTPException(422,'部分部门已不存在，请重新选择')
    department_names={name for uid,item in departments.items() if uid in department_ids for name in [item.name,*(item.aliases or [])]}
    from organization_service import department_condition
    recipients=explicit|({uid for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True), department_condition(db, department_names))} if department_names else set())
    metadata=value.model_dump(mode='json')
    if metadata['view_all'] is False:
        view_names={name for uid,item in departments.items() if uid in view_departments for name in [item.name,*(item.aliases or [])]}
        allowed=view_users|{row.collected_by}
        if view_names:
            allowed.update(uid for uid, in db.query(AppUser.id).filter(AppUser.is_active.is_(True),department_condition(db,view_names)))
        if not recipients<=allowed:
            raise HTTPException(422,'通知对象包含无查看权限的人员，请将他们加入查看权限后保存')
    row.summary_data=metadata
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
    notified={row.id:[] for row in rows}
    if notified:
        for issue_id, uid in db.query(Audience.issue_id, Audience.target_id).filter(
                Audience.issue_id.in_(notified), Audience.kind == 'notify_user'):
            notified[issue_id].append(str(uid));user_ids.add(uid)
    for row in rows:
        data=row.summary_data or {}
        user_ids.update(UUID(uid) for key in ['follower_user_ids','notify_user_ids','view_user_ids'] for uid in data.get(key,[]))
        dept_ids.update(UUID(uid) for key in ['notify_department_ids','view_department_ids'] for uid in data.get(key,[]))
    people={str(person.id):person.full_name or person.username for person in db.query(AppUser).filter(AppUser.id.in_(user_ids))} if user_ids else {}
    departments={str(item.id):item.name for item in db.query(Department).filter(Department.id.in_(dept_ids))} if dept_ids else {}
    result={}
    for row in rows:
        data=row.summary_data or {}
        result[row.id]=dict(summary=data,specific_classification=data.get('specific_classification',row.topic_path or ''),
            planned_completion_at=data.get('planned_completion_at'),actual_progress=data.get('actual_progress',''),
            follower_names=[people.get(uid,'已删除人员') for uid in data.get('follower_user_ids',[])],
            notify_user_names=[people.get(uid,'已删除人员') for uid in data.get('notify_user_ids',[])],
            notified_user_names=sorted([people.get(uid,'已删除人员') for uid in notified[row.id]],key=str.casefold),
            notify_department_names=[departments.get(uid,'已删除部门') for uid in data.get('notify_department_ids',[])],
            view_user_names=[people.get(uid,'已删除人员') for uid in data.get('view_user_ids',[])],
            view_department_names=[departments.get(uid,'已删除部门') for uid in data.get('view_department_ids',[])])
    return result


def progress_allowed(user,row):
    return row.category=='execution' and str(user.id) in (row.summary_data or {}).get('follower_user_ids',[])
