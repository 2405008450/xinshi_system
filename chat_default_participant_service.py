from fastapi import HTTPException
from sqlalchemy import inspect
from models import AppUser
from chat_default_participant_models import AnnotationChatDefaultParticipant as DefaultParticipant


def require_ready(db):
    if not inspect(db.connection()).has_table(DefaultParticipant.__tablename__):
        raise HTTPException(503, '默认参与人配置尚未完成数据库迁移，请联系管理员')


def default_user_ids(db):
    require_ready(db)
    return [uid for uid, in db.query(DefaultParticipant.user_id).join(AppUser, AppUser.id == DefaultParticipant.user_id).filter(AppUser.is_active.is_(True))]


def catalog(db, user):
    import annotation_chat_service as annotation
    from chat_session_category_service import can_manage_folders
    selected = default_user_ids(db)
    eligible = {row.id for row in annotation.eligible_users(db)}
    users = db.query(AppUser).filter(AppUser.is_active.is_(True)).order_by(AppUser.full_name, AppUser.username).all()
    return dict(user_ids=selected, can_manage=can_manage_folders(db, user), users=[dict(
        id=row.id, name=row.full_name or row.username, username=row.username, department=row.department or '',
        can_participate=row.id in eligible) for row in users])


def save(db, user, ids):
    from chat_session_category_service import require_manager
    import annotation_chat_service as annotation
    require_manager(db, user)
    require_ready(db)
    ids = set(ids)
    if db.get_bind().dialect.name == 'postgresql':
        from sqlalchemy import text
        db.execute(text('SELECT pg_advisory_xact_lock(646227451908631)'))
    eligible = {row.id for row in annotation.eligible_users(db, ids)}
    if ids != eligible:
        raise HTTPException(422, '部分所选人员已停用或没有项目沟通权限，请重新选择')
    db.query(DefaultParticipant).delete(synchronize_session=False)
    db.add_all(DefaultParticipant(user_id=uid, updated_by=user.id) for uid in ids)
    db.commit()
    return catalog(db, user)
