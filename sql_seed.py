import sys
sys.path.append('e:/xinshi_system')

from database import SessionLocal
from sqlalchemy import text
import random

def generate_sql_projects():
    db = SessionLocal()
    try:
        # 获取现有的 client_id 和 user_id 以外键
        clients = db.execute(text('SELECT id, client_short_name FROM client')).fetchall()
        users = db.execute(text('SELECT id FROM app_user')).fetchall()

        if not clients:
            print("❌ 错误：未找到 Client 数据。无法满足外键要求。")
            return
        if not users:
            print("❌ 错误：未找到 AppUser 数据。无法满足外键要求。")
            return

        print(f"找到 {len(clients)} 个客户，{len(users)} 个用户。开始执行纯 SQL 生成...")

        for i in range(1, 11):
            c = random.choice(clients)
            u = random.choice(users)
            
            # 使用更安全的文本替换拼接，避免 PostgreSQL 处理单引号报错
            order_no = f"PRJ-20260228-SQL{i:03d}"
            project_name = f"[{c[1]}] SQL直插测试项目批次 {random.randint(100, 999)}"
            
            # 1. 插入 translation_project 并返回 id
            proj_res = db.execute(
                text("INSERT INTO translation_project (order_no, project_name, client_id, created_by, pm_confirmed_by, project_status) "
                     "VALUES (:order_no, :project_name, :client_id, :created_by, :pm_confirmed_by, 'pending') RETURNING id"),
                {"order_no": order_no, "project_name": project_name, "client_id": c[0], "created_by": u[0], "pm_confirmed_by": u[0]}
            )
            proj_id = proj_res.scalar()
            
            # 2. 必须随之初始化工作流实例
            wf_res = db.execute(
                text("INSERT INTO workflow_instance (translation_project_id, current_stage_key, project_status) "
                     "VALUES (:proj_id, 'reception', 'pending') RETURNING id"),
                {"proj_id": proj_id}
            )
            wf_id = wf_res.scalar()
            
            # 3. 产生第一条操作记录日志
            db.execute(
                text("INSERT INTO workflow_log (workflow_instance_id, from_stage, to_stage, direction, description, note) "
                     "VALUES (:wf_id, '', 'reception', 'forward', '进入接稿（客户专员）', '纯SQL自动初始化插入')"),
                {"wf_id": wf_id}
            )
            
            print(f"✅ SQL 插入成功: {order_no} | 项目名: {project_name}")

        db.commit()
        print("\\n🎉 10 条纯 SQL 组装的测试数据（含工作流）生成完毕！")
    finally:
        db.close()

if __name__ == "__main__":
    generate_sql_projects()
