"""邮件组只使用启用且有有效邮箱的用户，历史发送快照不受影响。"""

from datetime import datetime

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import joinedload

from business_mail_models import MailRecipientGroupMember


def is_available_mail_user(user) -> bool:
    if not user or not user.is_active or not user.email:
        return False
    try:
        validate_email(user.email, check_deliverability=False)
    except EmailNotValidError:
        return False
    return True


def available_group_members(group):
    return [member for member in group.members if is_available_mail_user(member.user)]


def remove_unavailable_user_memberships(db, user):
    """随用户更新在同一事务内清理关联，不独立提交。"""
    if is_available_mail_user(user):
        return
    members = db.query(MailRecipientGroupMember).options(
        joinedload(MailRecipientGroupMember.group)
    ).filter(MailRecipientGroupMember.user_id == user.id).all()
    for member in members:
        member.group.updated_at = datetime.now()
        member.group.members.remove(member)
