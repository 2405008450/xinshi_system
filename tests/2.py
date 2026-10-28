import main
from database import SessionLocal
from models import AppUser, Role, UserRole
from passlib.context import CryptContext
import uuid

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

db = SessionLocal()
try:
    # 1. 找到"系统管理员"角色
    admin_role = db.query(Role).filter(Role.role_name == "系统管理员").first()
    if not admin_role:
        print("❌ 找不到系统管理员角色，请确保之前赋权成功了")
        exit()

    # 2. 准备你要创建的测试账号列表
    test_users = [
        {"username": "test1", "password": "123456", "full_name": "测试员A"},
        {"username": "test2", "password": "123456", "full_name": "测试员B"},
        {"username": "test3", "password": "123456", "full_name": "测试员C"},
    ]

    for u in test_users:
        # 检查账号是否已存在
        existing = db.query(AppUser).filter(AppUser.username == u["username"]).first()
        if existing:
            print(f"ℹ️ 账号 {u['username']} 已存在，跳过")
            continue

        # 创建用户
        new_user = AppUser(
            id=uuid.uuid4(),
            username=u["username"],
            password_hash=pwd_context.hash(u["password"]),
            full_name=u["full_name"],
            email=f"{u['username']}@local",
            is_active=True,
            is_deleted=False
        )
        db.add(new_user)
        db.flush()  # 刷新以获取 user.id

        # 绑定角色（写入 user_role 关联表）
        db.add(UserRole(user_id=new_user.id, role_id=admin_role.id))
        print(f"✅ 成功创建账号: {u['username']} / 密码: {u['password']}")

    db.commit()
    print("🎉 所有测试账号处理完毕！")
finally:
    db.close()