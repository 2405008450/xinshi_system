"""只读生成已有账号归属清单，不合并记录，不修改业务数据库。"""
import json
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPING = {'BOSS直聘': ['BOSS 1', 'BOSS 2', 'BOSS 3'], '智联招聘': ['智联招聘1', '智联招聘2', '智联招聘3'], '前程无忧': ['前程无忧主号', '前程无忧小号']}


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system' or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('仅允许在 PC 使用项目虚拟环境执行')
    sys.path.insert(0, str(ROOT))
    from database import engine
    from sqlalchemy import inspect, text
    if (engine.url.host, engine.url.port, engine.url.database) != ('43.132.156.72', 15432, 'xinshi_system'):
        raise SystemExit('当前数据库不是已核对的业务目标，停止生成清单')
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        names = list(MAPPING) + [name for accounts in MAPPING.values() for name in accounts]
        rows = connection.execute(text("SELECT id,name,code,revision FROM resource_development_option WHERE kind='platform' AND name = ANY(:names)"), {'names': names}).mappings().all()
        by_name = {row['name']: dict(row) for row in rows}
        missing = sorted(set(names) - set(by_name))
        if missing:
            raise ValueError('明确名称未找到，停止：' + '、'.join(missing))
        plan = []
        for parent_name, accounts in MAPPING.items():
            parent = by_name[parent_name]
            plan.append(dict(parent_name=parent_name, parent_id=str(parent['id']), parent_revision=parent['revision'],
                             accounts=[dict(name=name, id=str(by_name[name]['id']), revision=by_name[name]['revision'], code=by_name[name]['code']) for name in accounts]))
        ids = [row['id'] for row in rows]
        history_counts = {}
        for table in ['resource_development_record', 'resource_development_counter', 'resource_development_arrangement_cell']:
            history_counts[table] = connection.execute(text(f'SELECT count(*) FROM {table} WHERE platform_id = ANY(:ids)'), {'ids': ids}).scalar()
        available = inspect(connection).has_table('resource_channel_account_link')
    output = ROOT / '.tmp/resource-channels-pc/account-plan.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    content = dict(database='43.132.156.72:15432/xinshi_system', git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   read_only=True, hierarchy_available=available, groups=plan, history_counts=history_counts)
    output.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(plan_file=str(output), hierarchy_available=available, groups=MAPPING, history_counts=history_counts), ensure_ascii=False))


if __name__ == '__main__':
    run()
