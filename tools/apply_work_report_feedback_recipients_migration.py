"""仅创建报告沟通接收记录表，不修改或回填现有业务表。"""
import argparse,socket,subprocess,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def apply_migration(connection):
    from work_report_feedback_recipients import ReportFeedbackRecipient
    ReportFeedbackRecipient.__table__.create(connection,checkfirst=True)


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True)
    parser.add_argument('--expected-commit',required=True)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    roots={'william':Path(r'D:\xinshi_system'),'pc':Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower())!=ROOT or Path.cwd().resolve()!=ROOT or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':raise SystemExit('主机、目录或虚拟环境不匹配')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if commit!=args.expected_commit:raise SystemExit('Git 提交不匹配')
    import main  # noqa: F401 只注册模型
    from database import engine
    from sqlalchemy import inspect,text
    if os.getenv('LOCAL_SCHEMA_MIGRATIONS_ENABLED','').lower() in ('1','true','yes','on'):raise SystemExit('必须关闭启动自动迁移')
    target=f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target!=args.confirm_target or target!='43.132.156.72:15432/xinshi_system':raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}',flush=True)
    with engine.begin() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY') if args.check_only else text("SET LOCAL lock_timeout='5s'"))
        if not args.check_only:apply_migration(connection)
        ready=inspect(connection).has_table('work_report_feedback_recipient')
        print('work_report_feedback_recipient_exists='+str(ready),flush=True)
        if ready:print('indexes='+str(inspect(connection).get_indexes('work_report_feedback_recipient')),flush=True)
    print('check only' if args.check_only else 'table ready; existing data unchanged',flush=True)


if __name__=='__main__':run()
