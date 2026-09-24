"""仅在局域网调试机运行开放群聊迁移与回归。"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--migrate', action='store_true')
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--allow-cloud-db', action='store_true', help='仅在用户明确授权云端数据库测试时使用')
    args = parser.parse_args()
    if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('仅允许在已核验的局域网调试机执行')
    from database import engine
    print('Database host:', engine.url.host, 'Python:', sys.executable, flush=True)
    local = engine.url.host in {'localhost', '127.0.0.1', '192.168.31.144'}
    if not local and not (args.allow_cloud_db and engine.url.host == '43.132.156.72'):
        raise SystemExit('数据库不在局域网调试机，停止迁移与测试')
    if args.migrate:
        if not local:
            from datetime import datetime
            backup = ROOT / 'backups' / ('before_annotation_chat_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.dump')
            backup.parent.mkdir(exist_ok=True)
            result = subprocess.run([r'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe', '-Fc',
                '-h', engine.url.host, '-p', str(engine.url.port or 5432), '-U', engine.url.username,
                '-d', engine.url.database, '-f', str(backup)],
                env=dict(os.environ, PGPASSWORD=engine.url.password or ''))
            if result.returncode:
                raise SystemExit('数据库备份失败，未执行迁移')
            print('Database backup:', backup, flush=True)
        from sqlalchemy import text
        sql = (ROOT / 'data/migrations/20260924_annotation_open_group_chat.sql').read_text(encoding='utf-8')
        with engine.begin() as connection:
            connection.execute(text(sql))
        print('开放项目群迁移完成')
    if args.test:
        return subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_annotation_open_chat.py',
            'tests/test_annotation_project_chat.py', 'tests/test_chat_attachment_storage.py', '-q', '--tb=short'],
            cwd=ROOT, env=dict(os.environ, RUN_ANNOTATION_CHAT_DB_TESTS='1', PYTHONIOENCODING='utf-8')).returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
