"""按用户授权低速执行个人联系方式相同的同名子组合并；独立连接、逐组留存、遇忙让行。"""
import argparse
import json
from pathlib import Path
import socket
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from fastapi import HTTPException
from business_time import business_iso,business_now
from tools.run_talent_name_merge_slow import (single_worker,read_pressure,assert_quiet,actor_for,
    BackendHealthMonitor,CapacityBusy,OnlineWriteBusy,prewrite_read_guard,failure_details)
from tools.run_talent_name_merge_slow import retry_wait_seconds


def save(path,state):
    state['updated_at']=business_iso(business_now())
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)


def verify_success(engine,result):
    from tools.verify_talent_name_merge_run import operation_batches,archive_people,verify_operation,verify_archive_targets
    operation=next(operation_batches(engine,[result['id']],batch_size=1))[0]
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        people=archive_people(connection,set(operation['person_ids'])|{str(operation['target_id'])})
        connection.rollback()
    failures=verify_operation(operation,{})+verify_archive_targets([operation],people)
    if failures:
        raise RuntimeError('合并后留存或归档核验未通过：'+json.dumps(failures,ensure_ascii=False))
    return dict(operation_id=result['id'],snapshot_hashes=True,field_audit=True,attachments=True,archive_targets=True)


def run(args):
    if socket.gethostname().upper()!='PC' or ROOT!=Path('E:/xinshi_system'):
        raise SystemExit('只允许在 PC 的项目目录执行')
    if args.interval<30:
        raise SystemExit('处理间隔不能小于30秒')
    import main
    from database import engine as configured
    from talent_contact_merge_service import RULE,discover,preview_candidate,commit_candidate
    u=configured.url
    if (u.host,u.port,u.database)!=('43.132.156.72',15432,'xinshi_system'):
        raise SystemExit('数据库目标与已授权目标不一致')
    directory=Path(args.run_dir).resolve()
    if not directory.is_relative_to((ROOT/'outputs').resolve()):
        raise SystemExit('执行记录必须保留在项目 outputs 目录内')
    directory.mkdir(parents=True,exist_ok=True)
    state_path=directory/'status.json'
    state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else dict(
        rule=RULE,operator=args.actor,started_at=business_iso(business_now()),results=[],skipped=[],requests={},index=0)
    if state['rule']!=RULE or state['operator']!=args.actor:
        raise SystemExit('检查点的规则或操作人不一致')
    engine=create_engine(u,poolclass=NullPool,connect_args={'connect_timeout':3,
        'application_name':'talent_contact_merge_slow','options':'-c timezone=Asia/Hong_Kong -c statement_timeout=3000 -c lock_timeout=200 -c idle_in_transaction_session_timeout=5000'})
    health=BackendHealthMonitor(lambda value:state.update(backend_health=value))
    waiting_since=None
    def check(db):
        pressure=read_pressure(db)
        state.update(pressure=pressure,pressure_checked_at=business_iso(business_now()))
        assert_quiet(pressure)
    def wait_idle(seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if (directory/'STOP').exists():
                raise InterruptedError('用户停止标记，已停止后续处理')
            time.sleep(min(1,max(0,deadline-time.monotonic())))
    try:
        with single_worker():
            for result in state['results']:
                if 'verification' not in result:
                    result['verification']=verify_success(engine,result)
                    save(state_path,state)
            while True:
                try:
                    if 'candidates' not in state:
                        with prewrite_read_guard('发现同名联系子组'),Session(engine) as db:
                            db.execute(text('SET TRANSACTION READ ONLY'))
                            check(db);actor_for(db,args.actor)
                            plan=discover(db);db.rollback()
                        # 用户截图对应子组优先执行，其余候选仍逐组独立核对。
                        plan['candidates'].sort(key=lambda row:(not {'RC000829','RC001010'}<=set(row['codes']),row['key'],row['person_ids']))
                        state.update(candidates=plan['candidates'],discovery_skipped=plan['skipped'],status='prepared')
                        save(state_path,state)
                        print(json.dumps(dict(status='prepared',candidates=len(plan['candidates']),archive_count=sum(len(c['person_ids'])-1 for c in plan['candidates'])),ensure_ascii=False),flush=True)
                    if not args.execute:
                        break
                    if state['index']>=len(state['candidates']):
                        state.pop('reason',None)
                        state.pop('failure',None)
                        state.update(status='completed',completed_at=business_iso(business_now()));save(state_path,state)
                        break
                    if (directory/'STOP').exists():
                        raise InterruptedError('用户停止标记，已停止后续处理')
                    candidate=state['candidates'][state['index']]
                    key='|'.join(candidate['person_ids'])
                    request=state['requests'].get(key)
                    health.check()
                    if request is None:
                        with prewrite_read_guard('合并前只读预览'),Session(engine) as db:
                            db.execute(text('SET TRANSACTION READ ONLY'));check(db)
                            proposed=preview_candidate(db,candidate);db.rollback()
                        request=dict(preview_token=proposed['preview_token'],idempotency_key=uuid4().hex,
                            target_id=proposed['target_id'],archive_ids=proposed['archive_ids'])
                        state['requests'][key]=request
                        state.update(status='previewed',current_codes=candidate['codes']);save(state_path,state)
                    with Session(engine) as db:
                        try:
                            with prewrite_read_guard('提交前检查'):
                                check(db);actor=actor_for(db,args.actor)
                                if not db.execute(text('SELECT pg_try_advisory_xact_lock(724092401)')).scalar():
                                    raise OnlineWriteBusy('线上人才正在写入，本次让行')
                            # 实际写入异常不自动重试，保留幂等键以核对未知提交结果。
                            started=time.monotonic()
                            result=commit_candidate(db,candidate,request['preview_token'],request['idempotency_key'],actor)
                            elapsed=time.monotonic()-started
                        except Exception:
                            db.rollback();raise
                    # 已提交结果先落盘，即使后续核验失败也不丢失成功记录。
                    state['results'].append(dict(result,codes=candidate['codes'],archive_count=len(request['archive_ids']),elapsed_seconds=round(elapsed,3)))
                    state['index']+=1;state.update(status='verifying');save(state_path,state)
                    verification=verify_success(engine,result)
                    state['results'][-1]['verification']=verification
                    state.pop('reason',None)
                    state.pop('failure',None)
                    state.update(status='running',verified_operations=sum('verification' in row for row in state['results']))
                    save(state_path,state)
                    print(json.dumps(dict(status='merged',codes=candidate['codes'],completed=len(state['results']),remaining=len(state['candidates'])-state['index'],archive_count=len(request['archive_ids']),elapsed_seconds=round(elapsed,3)),ensure_ascii=False),flush=True)
                    waiting_since=None
                    if elapsed>12:
                        state.update(status='paused',reason='单次提交超过12秒，已完成本组并停止后续处理');save(state_path,state);break
                    if state['index']<len(state['candidates']):
                        wait_idle(args.interval)
                except (CapacityBusy,OnlineWriteBusy) as exc:
                    state.update(status='waiting_capacity',reason=str(exc));save(state_path,state)
                    print(json.dumps(dict(status='waiting_capacity',pressure=state.get('pressure')),ensure_ascii=False),flush=True)
                    if waiting_since is None:waiting_since=time.monotonic()
                    if time.monotonic()-waiting_since>=args.capacity_wait:
                        state.update(status='paused',reason='等待负载恢复超过时限，已释放连接并暂停');save(state_path,state);break
                    wait_idle(retry_wait_seconds(args.retry_seconds))
                except HTTPException as exc:
                    if exc.status_code not in {409,422}:
                        raise
                    state['skipped'].append(dict(candidate=state['candidates'][state['index']],reason=str(exc.detail),http_status=exc.status_code))
                    state['index']+=1;state.update(status='running');save(state_path,state)
                    if state['index']<len(state['candidates']):wait_idle(args.interval)
                except InterruptedError as exc:
                    state.update(status='paused',reason=str(exc));save(state_path,state);break
    except InterruptedError as exc:
        state.update(status='paused',reason=str(exc));save(state_path,state)
    except Exception as exc:
        state.update(status='paused',reason='执行或提交后核验异常，请先核对保留的请求和操作记录',failure=failure_details(exc))
        save(state_path,state)
        raise
    finally:
        engine.dispose()
    print(json.dumps(dict(status=state.get('status'),merged=len(state['results']),archived=sum(row['archive_count'] for row in state['results']),skipped=len(state['skipped']),remaining=len(state.get('candidates',[]))-state['index']),ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-dir',required=True)
    parser.add_argument('--actor',default='Jimmy')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--interval',type=float,default=30)
    parser.add_argument('--capacity-wait',type=float,default=300)
    parser.add_argument('--retry-seconds',type=float,default=60)
    try:
        run(parser.parse_args())
    except Exception as exc:
        print(json.dumps(dict(status='paused',failure=failure_details(exc)),ensure_ascii=False),file=sys.stderr)
        raise SystemExit(1)
