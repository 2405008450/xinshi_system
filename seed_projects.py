import sys
import random
sys.path.append('e:/xinshi_system')

from database import SessionLocal
import models
import workflow_models  # 预先引入以自动注册 SQLAlchemy Mappers 关系
from crud import create_translation_project
from schemas import TranslationProjectCreate
from workflow_crud import init_workflow

def generate_mock_projects():
    db = SessionLocal()
    try:
        clients = db.query(models.Client).all()
        users = db.query(models.AppUser).all()
        translators = db.query(models.Translator).all()

        if not clients:
            print("❌ 没有找到 Client (客户) 数据，请先在系统中创建至少一个客户才能生成关联项目！")
            sys.exit(1)

        if not users:
            print("❌ 没有找到 User (用户) 数据，无法作为 PM (项目经理) 或 Creator (创建人)！")
            sys.exit(1)

        print(f"找到 {len(clients)} 个客户，{len(users)} 个用户，{len(translators)} 个译员。开始生成...")

        for i in range(1, 11):
            c = random.choice(clients)
            u = random.choice(users)
            t = random.choice(translators) if translators else None

            # 组装 Pydantic Data
            proj_in = TranslationProjectCreate(
                project_name=f"[{c.client_short_name}] 测试翻译项目批次 {random.randint(100, 999)}",
                client_id=c.id,
                created_by=u.id,
                pm_confirmed_by=u.id,
                translator_id=t.id if t else None,
                project_status="pending",
            )
            
            # 存入 translation_project，自动生成 order_no
            db_proj = create_translation_project(db, proj_in)
            
            # 同时调用我们的后端逻辑：初始化对应的 workflow_instance 和第一条 workflow_log
            init_workflow(db, db_proj.id)
            
            print(f"✅ 创建成功: {db_proj.order_no} | 项目名: {db_proj.project_name}")

        print("\n🎉 10 个笔译项目及对应的初始化工作流实例已成功生成完毕！")
    finally:
        db.close()

if __name__ == "__main__":
    generate_mock_projects()
