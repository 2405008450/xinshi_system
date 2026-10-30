"""按用户指定配置广州办公室四个分区；默认只读预览。"""
import argparse,json,socket,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
AREAS=[{'name':'总经理室','seats':1},{'name':'财务室','seats':2},{'name':'管理区','seats':6},{'name':'大办公区','seats':26}]


def configure(db,expected_revision,apply=False):
    import office_management as office
    row=db.query(office.OfficeSite).filter_by(city_key='广州').with_for_update().one()
    current=office.office_areas(db,[row.id]).get(row.id,[])
    if row.revision!=expected_revision:raise RuntimeError('广州办公室版本已变化，请重新核对')
    print(json.dumps({'office':row.name,'before_seats':row.seats,'before_areas':current,'areas':AREAS,'total_seats':35,'revision':row.revision},ensure_ascii=True))
    if not apply:return {'result':'preview','revision':row.revision}
    if current==AREAS and row.seats==35:return {'result':'unchanged','revision':row.revision}
    office.save(db,office.OfficeUpdate(city=row.city,name=row.name,seats=35,areas=AREAS,revision=row.revision),row.id)
    return {'result':'saved','revision':row.revision,'seats':row.seats}


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--expected-revision',type=int,required=True);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    roots={'william':Path(r'D:\xinshi_system'),'pc':Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower())!=ROOT or Path.cwd().resolve()!=ROOT or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':raise SystemExit('主机、目录或Python不匹配')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if commit!=args.expected_commit:raise SystemExit('Git提交不匹配')
    from tools.local_startup_config import startup_config
    from dotenv import dotenv_values
    import os
    startup_config({**dotenv_values(ROOT/'.env'),**os.environ})
    import main
    from database import engine,SessionLocal
    target=f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if args.confirm_target!=target or target!='43.132.156.72:15432/xinshi_system':raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    with SessionLocal() as db:
        print(json.dumps(configure(db,args.expected_revision,args.apply),ensure_ascii=True))
        if not args.apply:db.rollback()


if __name__=='__main__':run()
