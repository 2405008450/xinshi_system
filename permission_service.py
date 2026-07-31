from uuid import UUID

from sqlalchemy.orm import Session

from models import Role, RolePermission, UserRole
from permission_registry import ALL_PERMISSION, SUPER_ROLE_NAMES, validate_permission_codes


def get_role_permission_codes(db: Session, role_id: UUID) -> list[str]:
    return [
        row.permission_code
        for row in (
            db.query(RolePermission.permission_code)
            .filter(RolePermission.role_id == role_id)
            .order_by(RolePermission.permission_code)
            .all()
        )
    ]


def set_role_permission_codes(db: Session, role_id: UUID, codes: list[str]) -> list[str]:
    normalized = validate_permission_codes(codes)
    role = db.query(Role).filter(Role.id == role_id).first()
    if role is None:
        raise LookupError("角色不存在")
    if role.role_name in SUPER_ROLE_NAMES:
        raise ValueError("超级管理员固定拥有全部权限，无需单独配置")

    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete(
        synchronize_session=False
    )
    db.add_all(
        RolePermission(role_id=role_id, permission_code=code)
        for code in normalized
    )
    db.commit()
    return normalized


def get_user_permission_codes(db: Session, user_id: UUID) -> list[str]:
    role_names = {
        row.role_name
        for row in (
            db.query(Role.role_name)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user_id)
            .all()
        )
    }
    if not SUPER_ROLE_NAMES.isdisjoint(role_names):
        return [ALL_PERMISSION]

    rows = (
        db.query(RolePermission.permission_code)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .filter(UserRole.user_id == user_id)
        .distinct()
        .order_by(RolePermission.permission_code)
        .all()
    )
    return [row.permission_code for row in rows]


def user_has_permission(db: Session, user_id: UUID, permission_code: str) -> bool:
    permissions = get_user_permission_codes(db, user_id)
    return ALL_PERMISSION in permissions or permission_code in permissions
