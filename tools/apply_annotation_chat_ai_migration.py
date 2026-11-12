"""显式初始化标注聊天 AI 分析任务表。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def apply_migration(connection):
    from annotation_models import AnnotationProject  # noqa: F401 注册外键目标
    from annotation_chat_ai_models import AnnotationChatAnalysis

    AnnotationChatAnalysis.__table__.create(connection, checkfirst=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    roots = {'william': Path(r'D:\xinshi_system'), 'pc': Path(r'E:\xinshi_system')}
    host = socket.gethostname()
    if roots.get(host.lower()) != ROOT or Path.cwd().resolve() != ROOT:
        raise SystemExit('主机或项目目录不匹配')
    if Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('须使用项目虚拟环境')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != args.expected_commit:
        raise SystemExit('Git 提交不匹配')

    from database import engine
    from sqlalchemy import inspect, text

    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标不匹配')
    print(f'host={host} project={ROOT} commit={commit} target={target}', flush=True)
    with engine.begin() as connection:
        if args.check_only:
            print(f'annotation_chat_analysis exists={inspect(connection).has_table("annotation_chat_analysis")}')
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        # 多次执行或其他维护进程同时初始化时，串行判断并创建。
        connection.execute(text('SELECT pg_advisory_xact_lock(2611111102)'))
        apply_migration(connection)
    print('annotation_chat_analysis ready')


if __name__ == '__main__':
    main()
