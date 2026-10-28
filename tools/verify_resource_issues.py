"""创建临时本机实例，验证开拓问题迁移、回归和真实浏览器；不访问业务库。"""
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]


def port():
    # 使用高位专用端口，避免系统分配到浏览器禁止访问的1720等协议端口。
    for _ in range(100):
        candidate = 40000 + secrets.randbelow(20000)
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', candidate))
            except OSError:
                continue
            return candidate
    raise RuntimeError('无法找到可用的隔离端口')


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    if socket.gethostname().upper()!='PC' or str(ROOT).lower()!=r'e:\xinshi_system' or Path(sys.executable).resolve()!=ROOT/'.venv/Scripts/python.exe':
        raise SystemExit('仅允许PC使用项目虚拟环境执行')
    binary=shutil.which('pg_ctl.exe')
    if not binary:raise SystemExit('缺少本机PostgreSQL，不得回退业务数据库')
    pg=Path(binary).parent;output=ROOT/('.tmp/chat-session-categories-qa' if '--categories-ui' in sys.argv else '.tmp/chat-topics-qa' if '--topics-ui' in sys.argv else '.tmp/chat-topics-regression-qa' if '--current-build' in sys.argv else '.tmp/resource-issues-qa');output.mkdir(parents=True,exist_ok=True)
    data=Path(tempfile.mkdtemp(prefix='postgres-',dir=output));pg_port,api_port,web_port=port(),port(),port()
    children=[];logs=[];flags=subprocess.CREATE_NO_WINDOW
    def command(*args,env=None,name='command.log',timeout=180):
        path=output/name
        with path.open('w',encoding='utf-8') as log:
            result=subprocess.run([str(x) for x in args],cwd=ROOT,env=env,creationflags=flags,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
        content=path.read_text(encoding='utf-8',errors='replace')
        if result.returncode:print(content,flush=True)
        result.check_returncode();return content
    def start(args,env,cwd,name):
        log=(output/name).open('w',encoding='utf-8');logs.append(log)
        child=subprocess.Popen([str(x) for x in args],cwd=cwd,env=env,creationflags=flags,stdout=log,stderr=subprocess.STDOUT);children.append(child)
    def ready(url):
        for _ in range(100):
            try:urlopen(url,timeout=1).close();return
            except Exception:time.sleep(.2)
        raise RuntimeError('隔离服务未就绪：'+url)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    print(f'主机=PC 项目={ROOT} 提交={commit} 数据库=127.0.0.1:{pg_port}/issues_test（临时独立实例）',flush=True)
    identity=subprocess.check_output(['whoami.exe']).decode().strip()
    command('icacls.exe',data,'/grant',f'{identity}:(OI)(CI)F',name='permissions.log')
    command(pg/'initdb.exe','-D',data,'-U','issue_test','--auth=trust','--encoding=UTF8','--locale=C',name='initdb.log')
    command(pg/'pg_ctl.exe','-D',data,'-l',data/'postgres.log','-o',f'-h 127.0.0.1 -p {pg_port}','-w','start',name='postgres-start.log')
    env=dict(os.environ,DATABASE_URL=f'postgresql+psycopg2://issue_test@127.0.0.1:{pg_port}/issues_test',SECRET_KEY=secrets.token_urlsafe(48),
             RESOURCE_ISSUES_QA='1',RUN_RESOURCE_DEVELOPMENT_DB_TESTS='1',PYTHONUTF8='1',LOCAL_SCHEMA_MIGRATIONS_ENABLED='false',
             VITE_API_PROXY_TARGET=f'http://127.0.0.1:{api_port}',ISSUE_UI_BASE=f'http://localhost:{web_port}')
    env['ISSUE_UI_OUTPUT']=str(output)
    if '--topics-ui' in sys.argv or '--categories-ui' in sys.argv: env['CHAT_TOPICS_UI']='1'
    try:
        command(pg/'createdb.exe','-h','127.0.0.1','-p',pg_port,'-U','issue_test','issues_test',name='createdb.log')
        setup='''
import main
from database import engine
from models import Base
from sqlalchemy import text
from pathlib import Path
assert engine.url.host=='127.0.0.1' and engine.url.username=='issue_test' and engine.url.database=='issues_test'
with engine.begin() as connection:
    connection.execute(text('CREATE EXTENSION IF NOT EXISTS pg_trgm'))
    connection.execute(text('CREATE SEQUENCE chat_message_sequence'))
# 迁移负责创建新表及其SQL默认值，不能先让ORM创建同名表。
Base.metadata.create_all(engine,tables=[table for table in Base.metadata.sorted_tables if table.name not in ('resource_development_issue','resource_development_issue_task','resource_issue_audience','chat_topic','chat_message_topic','chat_topic_audit','chat_session_category','chat_session_category_link','chat_session_category_folder','chat_discussion_message','chat_discussion_member','chat_discussion_mention')])
sql=Path('data/migrations/20261012_resource_development_issues.sql').read_text(encoding='utf-8')
with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
    connection.exec_driver_sql(sql)
    connection.exec_driver_sql(sql)
    topics=Path('data/migrations/20261012_chat_topics.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(topics)
    connection.exec_driver_sql(topics)
    categories=Path('data/migrations/20261019_chat_session_categories.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(categories)
    connection.exec_driver_sql(categories)
    folders=Path('data/migrations/20261020_chat_session_folders.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(folders)
    connection.exec_driver_sql(folders)
    discussions=Path('data/migrations/20261020_resource_discussion_rooms.sql').read_text(encoding='utf-8')
    connection.exec_driver_sql(discussions)
    connection.exec_driver_sql(discussions)
    connection.exec_driver_sql(Path('data/migrations/20261011_auto_talent_resource_code.sql').read_text(encoding='utf-8'))
Base.metadata.create_all(engine)
from tools.apply_chat_summary_migration import apply_migration
with engine.begin() as connection:
    apply_migration(connection)
    apply_migration(connection)
print('开拓问题迁移首次及重复执行通过')
'''
        print(command(sys.executable,'-c',setup,env=env,name='migration.log'),flush=True)
        if '--ui-only' not in sys.argv:
            tests=['tests/test_resource_issues.py','tests/test_resource_arrangements.py','tests/test_resource_development.py','tests/test_resource_follow_up.py','tests/test_resource_request_daily_notes.py']
            if (ROOT/'tests/test_chat_topics.py').is_file():
                tests.insert(0,'tests/test_chat_topics.py')
            if '--categories-ui' in sys.argv:
                tests=['tests/test_chat_topics.py','tests/test_chat_session_categories.py']
            if '--summary-migration-only' in sys.argv:
                tests=['tests/test_resource_issues.py', '-k', 'summary_migration or payload_rejects or (three_sources and direct)']
            print(command(sys.executable,'-m','pytest',*tests,'-q','--tb=short',env=env,name='pytest.log',timeout=300),flush=True)
        if '--backend-only' in sys.argv or '--summary-migration-only' in sys.argv:return
        seed='''
import os
import main
from database import engine
from sqlalchemy.orm import Session
from tools.resource_issues_fixture import seed
from resource_issue_schemas import IssueCreate,IssueTaskWrite
import resource_issue_service as service
from models import ChatProjectMessage
from uuid import uuid4
from pathlib import Path
with Session(engine) as db:
    data=seed(db);user=data['users']['collector']
    for index in range(24):
        kind=['translation','annotation','direct'][index%3]
        message=data['messages'][kind]
        if index>=3:
            message=ChatProjectMessage(id=uuid4(),sender_user_id=data['users']['proposer'].id,sender_name=data['users']['proposer'].full_name,content=f'验收资源问题{index:02d} 原文',message_type='user',project_id=message.project_id,annotation_project_id=message.annotation_project_id,direct_conversation_id=message.direct_conversation_id)
            db.add(message);db.flush()
        row=service.create_issue(db,user,IssueCreate(source_message_id=message.id,category=['arrangement','execution','problem','idea'][index%4],content=f'验收问题{index:02d} 内容'+('\\n长段落'*150 if index==0 else ''),remarks='备注\\n第二行'))
        service.write_task(db,user,row['id'],IssueTaskWrite(revision=row['revision'],content='跟进验收任务',executor_id=data['users']['executor'].id,planned_date='2026-10-12'))
    if os.getenv('CHAT_TOPICS_UI') == '1':
        from models import RolePermission, Role
        from annotation_chat_service import add_member
        from chat_topic_service import set_message_topic
        from uuid import UUID
        role=db.query(Role).filter_by(role_name='issue_qa_collector').one()
        db.add_all(RolePermission(role_id=role.id,permission_code=code) for code in ('chat_topics:manage','chat_topics:classify','workflow:operate'))
        add_member(db,data['annotation'].id,user.id,baseline=0)
        for index in range(44):
            db.add(ChatProjectMessage(id=uuid4(),annotation_project_id=data['annotation'].id,sender_user_id=data['users']['proposer'].id,sender_name=data['users']['proposer'].full_name,content=f'高校历史消息{index:02d}',message_type='user'))
        db.flush()
        for message in db.query(ChatProjectMessage).all():
            set_message_topic(db,data['users']['proposer'],message,UUID('00000000-0000-0000-0000-000000001015'))
    db.commit()
    sql=Path('data/migrations/20261012_resource_development_issues.sql').read_text(encoding='utf-8')
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.exec_driver_sql(sql)
        assert connection.exec_driver_sql('SELECT count(*) FROM resource_development_issue').scalar()==24
print('重复迁移保留24条记录及任务')
'''
        print(command(sys.executable,'-c',seed,env=env,name='seed.log'),flush=True)
        start([sys.executable,'-m','uvicorn','tools.issues_isolated_app:app','--host','127.0.0.1','--port',api_port],env,ROOT,'backend.log')
        ready(f'http://127.0.0.1:{api_port}/openapi.json')
        start(['node','node_modules/vite/bin/vite.js','preview','--outDir','dist' if '--topics-ui' in sys.argv or '--categories-ui' in sys.argv or '--current-build' in sys.argv else '../.tmp/resource-issues-dist','--host','127.0.0.1','--port',web_port,'--strictPort'],env,ROOT/'frontend','frontend.log')
        ready(env['ISSUE_UI_BASE'])
        script='tools/verify_chat_session_categories_ui.py' if '--categories-ui' in sys.argv else 'tools/verify_chat_topics_ui.py' if '--topics-ui' in sys.argv else 'tools/verify_resource_issues_ui.py'
        print(command(sys.executable,script,env=env,name='browser.log',timeout=300),flush=True)
        print(f'开拓问题隔离验收通过：{output}',flush=True)
    finally:
        for child in reversed(children):
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=10)
        for log in logs:log.close()
        command(pg/'pg_ctl.exe','-D',data,'-m','fast','-w','stop',name='postgres-stop.log')


if __name__=='__main__':run()
