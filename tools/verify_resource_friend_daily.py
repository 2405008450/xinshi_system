"""仅在局域网执行群聊统计迁移；随后运行逐例回滚的集成测试。"""
import os
from pathlib import Path
import socket
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5' or ROOT != Path(r'E:\xinshi_system'):
    raise SystemExit('仅允许在局域网调试项目执行')
from database import engine
from sqlalchemy import text
sql = (ROOT / 'data/migrations/20260924_resource_development_friend_daily.sql').read_text(encoding='utf-8-sig')
with engine.begin() as conn:
    conn.execute(text(sql.replace('BEGIN;', '').replace('COMMIT;', '')))
print('friend daily migration OK', flush=True)
env = dict(os.environ, RUN_RESOURCE_DEVELOPMENT_DB_TESTS='1', PYTHONIOENCODING='utf-8')
raise SystemExit(subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_resource_friend_daily.py', 'tests/test_resource_development.py', 'tests/test_talent_overview.py', '-q', '--tb=short'], cwd=ROOT, env=env).returncode)
