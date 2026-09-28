"""只读克隆结构到局域网独立 PostgreSQL 集群；不复制数据，不修改已有集群。"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-env', required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--pg-bin', required=True)
    parser.add_argument('--cluster-root', required=True)
    parser.add_argument('--port', type=int, default=15439)
    parser.add_argument('--allow-cloud-schema', action='store_true')
    args = parser.parse_args()
    if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5':
        parser.error('只能在局域网调试机执行')
    if not re.fullmatch(r'xinshi_form_regression_[a-z0-9_]{1,30}', args.database):
        parser.error('测试库名必须使用专项测试前缀')
    root = Path(args.cluster_root).resolve()
    if Path('E:/xinshi_runtime/validation').resolve() not in root.parents or root.exists():
        parser.error('必须使用验证目录下尚不存在的独立目录')
    if not 15000 <= args.port <= 15999:
        parser.error('测试端口必须在 15000～15999 范围')
    from dotenv import dotenv_values
    from sqlalchemy.engine import URL, make_url
    import psycopg2
    from psycopg2 import sql
    values = dotenv_values(args.source_env)
    source = make_url(values['DATABASE_URL']) if values.get('DATABASE_URL') else URL.create(
        'postgresql+psycopg2', username=values.get('DB_USER', 'postgres'), password=values.get('DB_PASSWORD'),
        host=values.get('DB_HOST', 'localhost'), port=int(values.get('DB_PORT', '5432')), database=values.get('DB_NAME', 'xinshi_system'))
    allowed = {'localhost', '127.0.0.1', '192.168.31.144'}
    if args.allow_cloud_schema:
        allowed.add('43.132.156.72')
    if source.host not in allowed:
        parser.error('源数据库未获授权')
    pg = Path(args.pg_bin)
    for name in ['pg_dump', 'initdb', 'pg_ctl']:
        if not (pg / f'{name}.exe').is_file():
            parser.error(f'缺少 {name}.exe')
    root.mkdir(parents=True)
    subprocess.run(['icacls', str(root), '/inheritance:r', '/grant:r',
                    f'{os.environ["USERNAME"]}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F',
                    '*S-1-5-32-544:(OI)(CI)F'], check=True, capture_output=True)
    env = {**os.environ, 'PGPASSWORD': source.password or '', 'PGCLIENTENCODING': 'UTF8',
           'PGOPTIONS': '-c default_transaction_read_only=on -c statement_timeout=60000'}
    dumped = subprocess.run([
        str(pg / 'pg_dump.exe'), '--schema-only', '--no-owner', '--no-privileges', '--lock-wait-timeout=10s',
        '--host', source.host, '--port', str(source.port or 5432), '--username', source.username,
        '--dbname', source.database,
    ], env=env, capture_output=True, timeout=180)
    if dumped.returncode:
        raise RuntimeError('读取源结构失败，未启动测试集群')
    schema = '\n'.join(line for line in dumped.stdout.decode('utf-8').splitlines() if not line.startswith('\\'))
    (root / 'schema.sql').write_text(schema, encoding='utf-8')
    password = secrets.token_urlsafe(32)
    pwfile = root / 'init-password'
    pwfile.write_text(password, encoding='utf-8')
    try:
        initialized = subprocess.run([
            str(pg / 'initdb.exe'), '-D', str(root / 'data'), '-U', 'form_test',
            '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C', f'--pwfile={pwfile}',
        ], capture_output=True, timeout=90)
        (root / 'initdb.log').write_bytes(initialized.stdout + initialized.stderr)
        if initialized.returncode:
            raise RuntimeError('独立集群初始化失败')
    finally:
        pwfile.unlink(missing_ok=True)
    target = URL.create('postgresql+psycopg2', username='form_test', password=password,
                        host='127.0.0.1', port=args.port, database=args.database)
    # 仅保存在访问受限的仓库外目录，配置不含源库凭据。
    (root / 'connection.json').write_text(json.dumps({'url': target.render_as_string(hide_password=False)}), encoding='utf-8')
    # Windows 后台进程会继承管道；使用文件接收日志，避免等待后台进程关闭管道。
    with (root / 'pg-ctl.log').open('wb') as log:
        started = subprocess.run([
            str(pg / 'pg_ctl.exe'), '-D', str(root / 'data'), '-l', str(root / 'postgres.log'),
            '-o', f'-h 127.0.0.1 -p {args.port}', '-w', 'start',
        ], stdout=log, stderr=subprocess.STDOUT, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
    if started.returncode:
        raise RuntimeError('独立集群启动失败')
    params = dict(host='127.0.0.1', port=args.port, user='form_test', password=password)
    admin = psycopg2.connect(dbname='postgres', **params)
    try:
        admin.autocommit = True
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(args.database)))
    finally:
        admin.close()
    with psycopg2.connect(dbname=args.database, **params) as db:
        with db.cursor() as cursor:
            cursor.execute(schema)
            cursor.execute('CREATE TABLE public.form_regression_marker (purpose text NOT NULL)')
            cursor.execute("INSERT INTO public.form_regression_marker VALUES ('isolated_form_regression')")
    print(f'独立测试库已就绪：127.0.0.1:{args.port}/{args.database}；仅复制结构')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'测试库准备失败（{type(exc).__name__}）；保留隔离目录现场，不回退到业务库。', file=sys.stderr)
        sys.exit(1)
