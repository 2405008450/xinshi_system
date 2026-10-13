"""客户授权的姓名核重低速任务：独立连接、逐组事务、遇忙暂停。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import sys
import time
import threading
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from business_time import business_iso, business_now


class PauseTask(Exception):
    pass


def read_pressure(db):
    return dict(db.execute(text("""
        SELECT count(*) AS connections,
               count(*) FILTER (WHERE state='active') AS active,
               count(*) FILTER (WHERE state LIKE 'idle in transaction%') AS idle_transactions,
               count(*) FILTER (WHERE xact_start < clock_timestamp()-interval '15 seconds') AS old_transactions
        FROM pg_stat_activity
        WHERE datname=current_database() AND pid<>pg_backend_pid()
              AND backend_type='client backend'
    """)).mappings().one())


def assert_quiet(pressure):
    if (pressure['connections'] >= 40 or pressure['active'] >= 5
            or pressure['idle_transactions'] >= 3 or pressure['old_transactions']):
        raise PauseTask('数据库负载升高：' + json.dumps(pressure, ensure_ascii=False))


def actor_for(db, username):
    from models import AppUser
    from crud import get_user_roles_with_role_names
    from permission_registry import SUPER_ROLE_NAMES
    actor = db.query(AppUser).filter_by(username=username).one_or_none()
    if actor is None or not actor.is_active or SUPER_ROLE_NAMES.isdisjoint(
            get_user_roles_with_role_names(db, actor.id)):
        raise PauseTask('操作账号不是有效超级管理员')
    return actor


def candidate_keys(db):
    from talent_name_merge_service import name_kind
    rows = db.execute(text("""
        SELECT resource_person_duplicate_name_key(full_name) AS key
        FROM resource_person WHERE archived_into_id IS NULL
        GROUP BY resource_person_duplicate_name_key(full_name)
        HAVING count(*) BETWEEN 2 AND 100
        ORDER BY key
    """)).scalars().all()
    return [key for key in rows if name_kind(key) in {'chinese', 'english'}]


def propose(db, key):
    from talent_name_merge_service import _members, _version, preview_group
    from resource_service import get_talent_project_situations
    from talent_duplicate_schemas import NameMergePreviewRequest
    people = _members(db, key)
    if len(people) < 2:
        return None
    if len(people) > 100:
        raise PauseTask('同名组超过容量，需要人工处理')
    situations = get_talent_project_situations(db, [person.id for person in people])
    request = NameMergePreviewRequest(group_key=key, group_version=_version(people, situations))
    result = preview_group(db, request)
    return {**request.model_dump(), 'preview_token': result['preview_token'],
            'idempotency_key': str(uuid4())}


def execute_one(db, request, username):
    """不排队等待线上人才／开拓写入；所有修改复用原核重服务。"""
    from talent_duplicate_schemas import NameMergeCommitRequest
    from talent_name_merge_service import commit_group
    assert_quiet(read_pressure(db))
    actor = actor_for(db, username)
    if not db.execute(text('SELECT pg_try_advisory_xact_lock(724092401)')).scalar():
        raise PauseTask('线上人才或开拓正在写入，本任务让行')
    return commit_group(db, NameMergeCommitRequest(**request), actor)


def write_status(path, state):
    state['updated_at'] = business_iso(business_now())
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    progress = {key: state[key] for key in ('status', 'operator', 'started_at', 'updated_at',
                                            'interval_seconds', 'workers', 'reason', 'pressure', 'last_group_seconds') if key in state}
    progress.update({'total': len(state.get('keys', [])), 'success': len(state['results']),
                     'remaining': len(state.get('keys', []))-len(state.get('processed_keys', state.get('keys', [])[:state['index']])),
                     'archived_records': sum(len(row['person_ids'])-1 for row in state['results'])})
    progress_path = path.with_name('progress.json')
    progress_temporary = progress_path.with_suffix('.tmp')
    progress_temporary.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding='utf-8')
    progress_temporary.replace(progress_path)


def pause_reason(exc):
    from fastapi import HTTPException
    return (str(exc) if isinstance(exc, PauseTask) else
            f'核重拒绝提交（HTTP {exc.status_code}）' if isinstance(exc, HTTPException) else
            f'执行异常：{type(exc).__name__}；已停止，需检查后手动恢复')


def run_queue(engine, state, status_path, stop_path, username, workers, interval, max_groups=0):
    """两个线程独立预览，写入在进程内串行；等待写入时不打开连接。"""
    done = set(state.get('processed_keys', state['keys'][:state['index']]))
    pending = [key for key in state['keys'] if key not in done]
    limited = bool(max_groups and len(pending) > max_groups)
    if max_groups:
        pending = pending[:max_groups]
    state['processed_keys'] = [key for key in state['keys'] if key in done]
    state_lock, write_lock = threading.Lock(), threading.Lock()
    stopped = threading.Event()
    failures = []
    cursor = 0

    def check_stop():
        if stop_path.exists():
            raise PauseTask('用户停止')
        return stopped.is_set()

    def wait_idle(seconds):
        deadline = time.monotonic() + max(0, seconds)
        while time.monotonic() < deadline:
            if check_stop() or stopped.wait(min(0.5, max(0, deadline-time.monotonic()))):
                return True
        return check_stop()

    def worker(worker_id):
        nonlocal cursor
        try:
            # 错开两线程，避免同时产生查询高峰。
            if wait_idle((worker_id-1)*interval/workers):
                return
            while not check_stop():
                with state_lock:
                    if stopped.is_set() or cursor >= len(pending):
                        return
                    key = pending[cursor]; cursor += 1
                    request = state['requests'].get(key)
                started = time.monotonic()
                if request is None:
                    with Session(engine) as db:
                        db.execute(text('SET TRANSACTION READ ONLY'))
                        assert_quiet(read_pressure(db))
                        request = propose(db, key)
                        db.rollback()
                    if request is not None:
                        with state_lock:
                            state['requests'][key] = request
                            # 提交前持久化幂等键；中断或结果未知时可安全续跑。
                            write_status(status_path, state)
                result = None
                if request is not None:
                    while not write_lock.acquire(timeout=0.1):
                        if check_stop():
                            return
                    try:
                        if check_stop():
                            return
                        with Session(engine) as db:
                            try:
                                result = execute_one(db, request, username)
                            except Exception:
                                db.rollback()
                                raise
                    finally:
                        write_lock.release()
                elapsed = time.monotonic()-started
                with state_lock:
                    if result is not None:
                        state['results'].append({**result, 'worker_id': worker_id})
                    done.add(key)
                    state['processed_keys'] = [item for item in state['keys'] if item in done]
                    # 保留连续前缀，并单独记录乱序完成项，续跑不遗漏失败组。
                    while state['index'] < len(state['keys']) and state['keys'][state['index']] in done:
                        state['index'] += 1
                    state['last_group_seconds'] = round(elapsed, 3)
                    write_status(status_path, state)
                    print(json.dumps({'updated_at': state['updated_at'], 'worker_id': worker_id,
                                      'success': len(state['results']), 'remaining': len(state['keys'])-len(done),
                                      'last_group_seconds': state['last_group_seconds']}, ensure_ascii=False), flush=True)
                if elapsed > 8:
                    raise PauseTask('单组耗时超过 8 秒，停止后续组')
                with state_lock:
                    if cursor >= len(pending):
                        return
                if wait_idle(interval-elapsed):
                    return
        except Exception as exc:
            with state_lock:
                failures.append(pause_reason(exc))
                stopped.set()

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='talent-merge') as pool:
        futures = [pool.submit(worker, identifier+1) for identifier in range(workers)]
        for future in futures:
            future.result()
    if failures:
        raise PauseTask(failures[0])
    if limited:
        raise PauseTask(f'双线程试运行已完成 {len(pending)} 组')


@contextmanager
def single_worker():
    import msvcrt
    path = ROOT / '.tmp/talent-name-merge-worker.lock'
    path.parent.mkdir(exist_ok=True)
    with path.open('a+b') as handle:
        if path.stat().st_size == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise PauseTask('已有低速核重任务运行') from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def run(args):
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('只能在 PC 的项目目录执行')
    if args.interval < 30:
        raise SystemExit('处理间隔不能小于 30 秒')
    if args.workers not in (1, 2):
        raise SystemExit('只允许一个或两个工作线程')
    if args.max_groups < 0:
        raise SystemExit('试运行组数不能为负数')
    import main  # 注册 ORM；不执行应用启动、结构迁移或后台轮询。
    from database import engine as application_engine
    url = application_engine.url
    if (url.host, url.port, url.database) != ('43.132.156.72', 15432, 'xinshi_system'):
        raise SystemExit('数据库目标与已授权目标不符')
    engine = create_engine(url, poolclass=NullPool, connect_args={
        'connect_timeout': 3, 'application_name': 'talent_name_merge_slow',
        'options': '-c timezone=Asia/Hong_Kong -c statement_timeout=2000 '
                   '-c lock_timeout=200 -c idle_in_transaction_session_timeout=5000',
    })
    output_root = ROOT / 'outputs/talent-name-merge-slow'
    output_root.mkdir(parents=True, exist_ok=True)
    directory = (Path(args.run_dir).resolve() if args.run_dir else output_root / uuid4().hex)
    if not directory.is_relative_to(output_root.resolve()):
        raise SystemExit('任务目录必须位于 outputs/talent-name-merge-slow 内')
    directory.mkdir(exist_ok=True)
    status_path = directory / 'status.json'
    stop_path = directory / 'STOP'
    if stop_path.exists():
        raise SystemExit('任务目录存在 STOP 标记，保持暂停')
    state = (json.loads(status_path.read_text(encoding='utf-8')) if status_path.exists() else
             {'status': 'preparing', 'operator': args.actor, 'started_at': business_iso(business_now()),
              'interval_seconds': args.interval, 'results': [], 'requests': {}, 'index': 0})
    if state['operator'] != args.actor:
        raise SystemExit('续跑账号与原任务不符')
    state['interval_seconds'] = args.interval
    state['workers'] = args.workers
    state.pop('reason', None)
    try:
        with single_worker():
            with Session(engine) as db:
                db.execute(text('SET TRANSACTION READ ONLY'))
                actor_for(db, args.actor)
                pressure = read_pressure(db)
                assert_quiet(pressure)
                state['pressure'] = pressure
                if 'keys' not in state:
                    state['keys'] = candidate_keys(db)
                db.rollback()
            state['status'] = 'running' if args.execute else 'preview_only'
            write_status(status_path, state)
            print(json.dumps({'run_dir': str(directory), 'groups': len(state['keys']),
                              'execute': args.execute, 'pressure': pressure}, ensure_ascii=False), flush=True)
            if not args.execute:
                return 0
            run_queue(engine, state, status_path, stop_path, args.actor,
                      args.workers, args.interval, args.max_groups)
            state['status'] = 'completed'
            write_status(status_path, state)
            return 0
    except Exception as exc:
        state['status'] = 'paused'
        state['reason'] = pause_reason(exc)
        write_status(status_path, state)
        print(json.dumps({'status': state['status'], 'reason': state['reason'],
                          'run_dir': str(directory)}, ensure_ascii=False), flush=True)
        return 2
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor', required=True, help='本次授权的超级管理员账号')
    parser.add_argument('--execute', action='store_true', help='实际合并；默认仅扫描预览')
    parser.add_argument('--interval', type=float, default=45)
    parser.add_argument('--workers', type=int, choices=(1, 2), default=1)
    parser.add_argument('--max-groups', type=int, default=0, help='仅处理指定数量用于试运行；0 表示处理剩余组')
    parser.add_argument('--run-dir', help='原任务目录，用于人工续跑；不会自动恢复')
    raise SystemExit(run(parser.parse_args()))
