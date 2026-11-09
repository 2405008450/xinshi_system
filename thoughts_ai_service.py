"""个人思考 AI：本机持久化任务队列，正文不进入日志，不修改业务数据库结构。"""
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import threading
import time
from contextlib import contextmanager
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from business_time import business_iso, business_now

ROOT = Path(__file__).resolve().parent
_start_lock = threading.Lock()
_thread = None


class ThoughtRequest(BaseModel):
    action: Literal['organize', 'explore', 'todos']
    content: str = Field(min_length=1, max_length=6000)

    @field_validator('content')
    @classmethod
    def clean_content(cls, value):
        value = re.sub(r'!\[截图\]\(screenshot://[^)]*\)', '', value).strip()
        if not value:
            raise ValueError('请先输入需要分析的文字，当前 AI 暂不读取截图')
        return value


def enabled():
    return os.getenv('THOUGHTS_AI_ENABLED', 'false').lower() == 'true'


@contextmanager
def connect():
    path = Path(os.getenv('THOUGHTS_AI_QUEUE_PATH', str(ROOT / 'data/thoughts_ai/jobs.sqlite3')))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, action TEXT NOT NULL,
        content TEXT NOT NULL, state TEXT NOT NULL, result TEXT NOT NULL DEFAULT '',
        message TEXT NOT NULL DEFAULT '', truncated INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL, deadline REAL NOT NULL, finished REAL)''')
    try:
        with db:
            yield db
    finally:
        db.close()


def transport(payload):
    key = os.path.expandvars(os.getenv('THOUGHTS_AI_SSH_KEY', str(Path.home() / '.ssh/id_ed25519')))
    command = [
        'ssh', '-T', '-p', '23', '-i', key,
        '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes',
        '-o', f'UserKnownHostsFile={ROOT / "deploy/compute_known_hosts"}',
        '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2',
        'root@106.75.1.149', 'thoughts-ai',
    ]
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    response = subprocess.run(command, input=json.dumps(payload, ensure_ascii=False) + '\n',
                              capture_output=True, encoding='utf-8', timeout=110, creationflags=flags)
    if response.returncode:
        raise RuntimeError('compute_connection_failed')
    result = json.loads(response.stdout)
    if not isinstance(result, dict) or 'state' not in result:
        raise ValueError('invalid_compute_response')
    return result


def public(row):
    if row is None:
        return None
    return {key: row[key] for key in ['id', 'action', 'state', 'result', 'message', 'truncated', 'created_at']}


def maintain(db):
    now = time.time()
    # 重启后不自动重发已开始的推理，避免重复占用算力；过期正文一并清除。
    db.execute("UPDATE jobs SET state='failed', message='等待或生成超时，请重新提交', content='', finished=? WHERE state IN ('queued','running','cancelling') AND deadline<?", (now, now))
    db.execute('DELETE FROM jobs WHERE finished IS NOT NULL AND finished<?', (now - 86400,))


def create(user_id, payload):
    if not enabled():
        raise HTTPException(503, 'AI 服务尚未启用')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        maintain(db)
        existing = db.execute("SELECT id FROM jobs WHERE user_id=? AND state IN ('queued','running','cancelling')", (str(user_id),)).fetchone()
        if existing:
            raise HTTPException(409, '已有 AI 任务正在处理，请等待或取消后再提交')
        count = db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running','cancelling')").fetchone()[0]
        if count >= 20:
            raise HTTPException(429, 'AI 等待人数较多，请稍后再试')
        recent = db.execute('SELECT COUNT(*) FROM jobs WHERE user_id=? AND deadline>?', (str(user_id), time.time() + 240)).fetchone()[0]
        if recent >= 6:
            raise HTTPException(429, '提交较频繁，请一分钟后再试')
        job_id = str(uuid4())
        db.execute('INSERT INTO jobs(id,user_id,action,content,state,created_at,deadline) VALUES(?,?,?,?,?,?,?)',
                   (job_id, str(user_id), payload.action, payload.content, 'queued', business_iso(business_now()), time.time() + 300))
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    ensure_worker()
    return public(row)


def latest(user_id):
    with connect() as db:
        maintain(db)
        row = db.execute('SELECT * FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 1', (str(user_id),)).fetchone()
    if enabled():
        ensure_worker()
    return {'enabled': enabled(), 'job': public(row), 'max_chars': 6000}


def cancel(user_id, job_id):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM jobs WHERE id=? AND user_id=?', (job_id, str(user_id))).fetchone()
        if row is None:
            raise HTTPException(404, 'AI 任务不存在')
        if row['state'] == 'queued':
            db.execute("UPDATE jobs SET state='cancelled',content='',message='已取消',finished=? WHERE id=?", (time.time(), job_id))
        elif row['state'] == 'running':
            db.execute("UPDATE jobs SET state='cancelling',message='正在取消，当前短请求结束后释放资源' WHERE id=?", (job_id,))
        return public(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())


def claim():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        maintain(db)
        # SQLite 保证多进程只领取一条交互任务，远端 flock 再保障跨实例单并发。
        if db.execute("SELECT 1 FROM jobs WHERE state IN ('running','cancelling')").fetchone():
            return None
        row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1").fetchone()
        if row:
            db.execute("UPDATE jobs SET state='running',message='正在等待算力或生成' WHERE id=?", (row['id'],))
        return row


def complete(job_id, response):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT state FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row or row['state'] not in ('running', 'cancelling'):
            return
        if row['state'] == 'cancelling':
            response = {'state': 'cancelled', 'message': '已取消'}
        state = response.get('state')
        if state not in ('succeeded', 'cancelled'):
            state = 'failed'
        db.execute('UPDATE jobs SET state=?,result=?,message=?,truncated=?,content=?,finished=? WHERE id=?',
                   (state, str(response.get('result', ''))[:12000] if state == 'succeeded' else '',
                    response.get('message', ''), bool(response.get('truncated')), '', time.time(), job_id))


def process(row):
    while time.time() < row['deadline'] - 110:
        with connect() as db:
            current = db.execute('SELECT state FROM jobs WHERE id=?', (row['id'],)).fetchone()
        if not current or current['state'] != 'running':
            complete(row['id'], {'state': 'cancelled'})
            return
        try:
            result = transport({'operation': 'generate', 'action': row['action'], 'content': row['content']})
        except Exception:
            complete(row['id'], {'state': 'failed', 'message': '算力连接失败或响应超时，请稍后重试'})
            return
        if result['state'] != 'busy':
            complete(row['id'], result)
            return
        with connect() as db:
            db.execute("UPDATE jobs SET message=? WHERE id=? AND state='running'", (result.get('message', '算力繁忙，正在等待'), row['id']))
        time.sleep(2)
    complete(row['id'], {'state': 'failed', 'message': '算力持续繁忙，请稍后重试'})


def worker():
    while enabled():
        try:
            row = claim()
            if row:
                process(row)
            else:
                time.sleep(1)
        except Exception:
            # 不记录个人正文及外部进程输出；存储暂时不可用时有界退避。
            time.sleep(3)


def ensure_worker():
    global _thread
    with _start_lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=worker, name='thoughts-ai', daemon=True)
            _thread.start()
