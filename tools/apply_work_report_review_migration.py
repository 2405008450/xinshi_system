"""显式创建工作报告分类、查看规则、逐项沟通与一次修订表，不回填历史、不预设授权规则。"""
import argparse
from pathlib import Path
import socket
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def migration_tables():
    from work_report_categories import WorkReportCategory
    from work_report_access import WorkReportAccessRule
    from work_report_collaboration import ReportFeedback, ReportRevision
    return [model.__table__ for model in [WorkReportCategory,WorkReportAccessRule,ReportFeedback,ReportRevision]]


def apply_migration(connection):
    for table in migration_tables():
        table.create(connection,checkfirst=True)


def seed_default_rule(db):
    from models import AppUser
    from work_report_access import WorkReportAccessRule, SUGGESTED_VIEWERS, CONFIGURATOR_USERNAME, AccessRuleWrite, save_rule
    name='默认工作报告查看范围'
    existing=db.query(WorkReportAccessRule).filter_by(name=name).first()
    if existing:return existing.id
    people=db.query(AppUser).filter(AppUser.username.in_(SUGGESTED_VIEWERS),AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).all()
    if {person.username for person in people}!=set(SUGGESTED_VIEWERS):raise RuntimeError('预设查看人账号不完整，停止初始化规则')
    actor=next(person for person in people if person.username==CONFIGURATOR_USERNAME)
    return save_rule(db,actor,AccessRuleWrite(name=name,viewer_ids=[person.id for person in people],senders_all=True))['id']


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--seed-default-rule',action='store_true',help='仅在用户明确授权默认名单查看全体成员时使用')
    args=parser.parse_args()
    roots={'william':Path(r'D:\xinshi_system'),'pc':Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower())!=ROOT or Path.cwd().resolve()!=ROOT or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':raise SystemExit('主机、目录或虚拟环境不匹配')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if commit!=args.expected_commit:raise SystemExit('Git 提交不匹配')
    import main  # noqa: F401 仅注册模型，不执行启动迁移。
    from database import engine
    from sqlalchemy import inspect,text
    target=f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target!=args.confirm_target or target!='43.132.156.72:15432/xinshi_system':raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with engine.begin() as connection:
        if args.check_only:

            for table in migration_tables():print(table.name+'_exists='+str(inspect(connection).has_table(table.name)))
            return
        connection.execute(text("SET LOCAL lock_timeout='5s'"));connection.execute(text("SET LOCAL statement_timeout='30s'"))
        apply_migration(connection)
    if args.seed_default_rule:
        from database import SessionLocal
        with SessionLocal() as db:print('default_rule_id='+str(seed_default_rule(db)))
    print('work report review tables ready; historical report rows unchanged')


if __name__=='__main__':run()
