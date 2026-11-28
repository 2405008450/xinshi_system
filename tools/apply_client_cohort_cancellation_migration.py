"""创建取消原因分类及客户新老手动设置表；可按明确授权分类历史取消记录，原说明不改动。"""
import argparse,socket,subprocess,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def apply_migration(connection):
    from interpretation_partial_cancellation import InterpretationCancellationClassification
    from client_cohort import ClientCohortOverride
    for model in [InterpretationCancellationClassification,ClientCohortOverride]:model.__table__.create(connection,checkfirst=True)



def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True)
    parser.add_argument('--expected-commit',required=True)
    parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--classify-existing',action='store_true')
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
        for name in ['interpretation_cancellation_classification','client_cohort_override']:print(name+'_exists='+str(inspect(connection).has_table(name)),flush=True)
    if args.classify_existing:
        from sqlalchemy.orm import Session
        from interpretation_partial_cancellation import classify_existing
        with Session(engine) as db:
            counts=classify_existing(db,check_only=args.check_only)
            if not args.check_only:db.commit()
            print('classification='+str(counts),flush=True)
    print('check only' if args.check_only else 'table ready; existing data unchanged',flush=True)


if __name__=='__main__':run()
