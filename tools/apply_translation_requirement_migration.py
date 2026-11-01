"""仅创建简单需求、接收回复及下级订单安排的三张新表；不改既有表。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TABLES = ('translation_simple_requirement', 'translation_simple_requirement_recipient', 'translation_arrangement_order_target')


def verify_target(args):
    roots = {'william': Path(r'D:\xinshi_system'), 'pc': Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower()) != ROOT or Path.cwd().resolve() != ROOT or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('主机、目录或虚拟环境不匹配')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if commit != args.expected_commit:
        raise SystemExit('Git 提交不匹配')
    import main  # 只注册模型，不执行服务启动事件及自动迁移。
    from database import engine
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target != args.confirm_target or target != '43.132.156.72:15432/xinshi_system':
        raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    return engine


def apply_migration(connection):
    from translation_simple_requirements import TranslationSimpleRequirement, TranslationSimpleRequirementRecipient
    from project_arrangement_targets import ArrangementOrderTarget
    for model in (TranslationSimpleRequirement, TranslationSimpleRequirementRecipient, ArrangementOrderTarget):
        model.__table__.create(connection, checkfirst=True)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    engine = verify_target(args)
    from sqlalchemy import inspect, text
    with engine.begin() as connection:
        print('tables_before=' + repr({name: inspect(connection).has_table(name) for name in TABLES}))
        if args.check_only:
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    print('tables_ready=' + ','.join(TABLES))


if __name__ == '__main__':
    run()
