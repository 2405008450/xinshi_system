"""按用户明确指令将赵震锋加入行政部并设置总经理职务；保留其他部门和成员，不改动既有表或排班记录。"""
import argparse
import socket
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))




def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target',required=True);parser.add_argument('--expected-commit',required=True);parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    roots={'william':Path(r'D:\xinshi_system'),'pc':Path(r'E:\xinshi_system')}
    if roots.get(socket.gethostname().lower())!=ROOT or Path.cwd().resolve()!=ROOT or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':raise SystemExit('主机、目录或虚拟环境不匹配')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if commit!=args.expected_commit:raise SystemExit('Git 提交不匹配')
    from tools.local_startup_config import startup_config
    from dotenv import dotenv_values
    import os
    startup_config({**dotenv_values(ROOT/'.env'),**os.environ})
    from database import engine
    from sqlalchemy import inspect,text
    target=f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if target!=args.confirm_target or target!='43.132.156.72:15432/xinshi_system':raise SystemExit('数据库目标不匹配')
    print(f'host={socket.gethostname()} project={ROOT} commit={commit} target={target}')
    from sqlalchemy.orm import Session
    import main  # 注册现有 ORM 关联；不执行启动钩子或结构迁移
    from home_office_setup import inspect_target,configure
    with Session(engine) as db:
        person,department,link=inspect_target(db)
        print({'name':person.full_name,'department':department.name,'current_position':link.position if link else None})
        if args.check_only:return
        result=configure(db);db.commit()
        from organization_service import publish
        publish(db)
        print(result)


if __name__=='__main__':run()
