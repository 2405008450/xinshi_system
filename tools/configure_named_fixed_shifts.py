"""按用户明确指定名单调整固定班次；核对目标、提交、账号和版本后调用业务保存。"""
import argparse,json,socket,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TARGET='43.132.156.72:15432/xinshi_system'
REQUESTED=[
 ('jinglin','靖琳','fixed_early_early','project'),
 ('shaofei','少妃','management','project'),
 ('zhongyu','钟毓','management','project'),
 ('thomas','Thomas','flexible','project'),
 ('ethan','Ethan','flexible','project'),
 ('williamzhao','赵震锋','flexible','administration'),
 ('lulu','lulu','flexible','administration'),
 ('lixian','李娴','home_rotation','project'),
]


def requested_assignments(db,current):
 from models import AppUser
 result={row['user_id']:dict(row) for row in current}
 changes=[]
 for username,name,shift,department in REQUESTED:
  matches=db.query(AppUser).filter(AppUser.username==username,AppUser.is_active.is_(True),AppUser.is_deleted.is_(False)).all()
  if len(matches)!=1 or name.casefold() not in (matches[0].full_name or '').casefold():raise RuntimeError('人员身份不唯一或姓名不匹配：'+username)
  person=matches[0];uid=str(person.id)
  after={'user_id':uid,'department':result.get(uid,{}).get('department',department),'shift':shift}
  changes.append({'username':username,'name':person.full_name,'before':result.get(uid),'after':after})
  result[uid]=after
 return list(result.values()),changes


def run():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--expected-revision',required=True,type=int);parser.add_argument('--apply',action='store_true')
 args=parser.parse_args()
 roots={'william':Path(r'D:\xinshi_system'),'pc':Path(r'E:\xinshi_system')}
 if roots.get(socket.gethostname().lower())!=ROOT or Path.cwd().resolve()!=ROOT or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':raise SystemExit('主机、工作目录或Python不匹配')
 commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip()
 if commit!=args.expected_commit:raise SystemExit('Git提交已变化')
 from tools.local_startup_config import startup_config
 from dotenv import dotenv_values
 import os
 startup_config({**dotenv_values(ROOT/'.env'),**os.environ})
 import main  # Register all existing ORM relationships; no startup hooks/migrations.
 from database import engine,SessionLocal
 from models import AppUser
 import fixed_shift as fixed
 target=f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
 if target!=TARGET or args.confirm_target!=TARGET:raise SystemExit('数据库目标不匹配')
 with SessionLocal() as db:
  config=db.query(fixed.FixedShiftConfig).filter_by(id=1).with_for_update().one()
  if config.revision!=args.expected_revision:raise SystemExit('固定班次版本已变化，请重新核对')
  values,changes=requested_assignments(db,config.assignments.get('current',[]))
  print(json.dumps({'host':socket.gethostname(),'project':str(ROOT),'commit':commit,'target':target,'revision':config.revision,'changes':changes},ensure_ascii=True))
  if not args.apply:db.rollback();print('read-only preview; no writes');return
  if all(item['before']==item['after'] for item in changes):print('already applied; unchanged');return
  actor=db.query(AppUser).filter_by(username='williamzhao',is_active=True,is_deleted=False).one()
  result=fixed.save_config(db,actor,fixed.FixedWrite(revision=config.revision,assignments=values))
  print(json.dumps({'result':'saved','revision':result['revision'],'changed_accounts':len(changes),'preserved_other_assignments':True,'schema_changes':False},ensure_ascii=True))


if __name__=='__main__':run()
