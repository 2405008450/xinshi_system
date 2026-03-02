"""检查数据库所有表的结构和数据行数"""
import sys
import io
sys.path.append('e:/xinshi_system')
sys.stdout = io.TextIOWrapper(open('e:/xinshi_system/db_inspect_output.txt', 'wb'), encoding='utf-8')

from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# 1. 列出所有表
tables = db.execute(text(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'public' ORDER BY table_name"
)).fetchall()

print("=" * 70)
print(f"数据库中共有 {len(tables)} 张表")
print("=" * 70)

for t in tables:
    tn = t[0]
    cols = db.execute(text(
        "SELECT column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns "
        f"WHERE table_schema = 'public' AND table_name = '{tn}' "
        "ORDER BY ordinal_position"
    )).fetchall()
    cnt = db.execute(text(f'SELECT COUNT(*) FROM "{tn}"')).scalar()
    print(f"\n{'─' * 70}")
    print(f"TABLE: {tn}  ({cnt} rows)")
    print(f"{'─' * 70}")
    print(f"  {'COLUMN':<40s} {'TYPE':<20s} {'NULL':>4s}  DEFAULT")
    print(f"  {'─'*38}  {'─'*18}  {'─'*4}  {'─'*30}")
    for c in cols:
        default_str = str(c[3])[:40] if c[3] else "-"
        print(f"  {c[0]:<40s} {c[1]:<20s} {c[2]:>4s}  {default_str}")

# 2. 对 translation_project 表抽样查看前3行
print(f"\n{'=' * 70}")
print("translation_project 表前 3 行:")
print(f"{'=' * 70}")
rows = db.execute(text(
    'SELECT id, order_no, project_name, client_id, project_status FROM translation_project LIMIT 3'
)).fetchall()
for r in rows:
    print(f"  id={r[0]}  order_no={r[1]}  name={r[2]}  client={r[3]}  status={r[4]}")

# 3. 对 workflow_instance 表抽样
print(f"\n{'=' * 70}")
print("workflow_instance 表前 3 行:")
print(f"{'=' * 70}")
rows = db.execute(text(
    'SELECT id, translation_project_id, current_stage_key, project_status FROM workflow_instance LIMIT 3'
)).fetchall()
for r in rows:
    print(f"  id={r[0]}  proj={r[1]}  stage={r[2]}  status={r[3]}")

# 4. 对 workflow_log 表抽样
print(f"\n{'=' * 70}")
print("workflow_log 表前 3 行:")
print(f"{'=' * 70}")
rows = db.execute(text(
    'SELECT id, workflow_instance_id, from_stage, to_stage, direction, description FROM workflow_log LIMIT 3'
)).fetchall()
for r in rows:
    print(f"  id={r[0]}  wf={r[1]}  from={r[2]}  to={r[3]}  dir={r[4]}  desc={r[5]}")

db.close()
print("\n✅ 检查完毕")
