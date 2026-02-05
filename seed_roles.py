"""
初始化角色与默认管理员权限
- 创建角色：超级管理员、客户专员、项目专员、项目经理
- 若存在用户名为 admin 的用户，为其绑定「超级管理员」角色（便于测试分权）
运行：python seed_roles.py
"""
from database import SessionLocal
from models import Role, AppUser, UserRole
from crud import get_role_by_name, get_user_by_username, get_user_roles_by_user

ROLES = [
    ("超级管理员", "系统超级管理员，可访问所有功能"),
    ("客户专员", "仅可访问笔译项目管理"),
    ("项目专员", "仅可访问笔译项目管理"),
    ("项目经理", "仅可访问笔译项目管理"),
]


def seed_roles():
    db = SessionLocal()
    try:
        for role_name, description in ROLES:
            if get_role_by_name(db, role_name) is None:
                r = Role(role_name=role_name, description=description)
                db.add(r)
                db.commit()
                db.refresh(r)
                print(f"已创建角色: {role_name}")
            else:
                print(f"角色已存在: {role_name}")

        # 为 admin 用户绑定「超级管理员」（若存在且尚未绑定）
        admin_user = get_user_by_username(db, "admin")
        if admin_user:
            existing = get_user_roles_by_user(db, admin_user.id)
            super_role = get_role_by_name(db, "超级管理员")
            if super_role and not any(
                ur.role_id == super_role.id for ur in existing
            ):
                ur = UserRole(user_id=admin_user.id, role_id=super_role.id)
                db.add(ur)
                db.commit()
                print("已为用户 admin 绑定角色: 超级管理员")
            else:
                print("用户 admin 已拥有超级管理员或角色不存在，跳过")
        else:
            print("未找到用户 admin，请先在用户管理中创建并为其在「用户角色关联」中绑定角色")
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles()
