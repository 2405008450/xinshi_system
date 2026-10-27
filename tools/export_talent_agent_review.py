"""单线程短事务导出同名证据，供当前 Agent 离线识别；不调用模型或写业务库。"""
import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
import re
import socket
import sys
import time

from sqlalchemy import create_engine, func, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main  # 只注册模型，不运行 lifespan 或结构迁移。
from business_time import business_iso, business_now
from database import engine as application_engine
from resource_models import ResourcePerson
from resource_service import _person_options
from talent_duplicate_service import (active_query, review_options, comparison_fingerprint, contact_identifiers,
    contact_usage_index, _business_values, _pair_decisions, _decision_query, pair_evidence, field_state, review_ready)
from talent_privacy import RESOURCE_CONTACT_FIELDS


class ScanPaused(RuntimeError):
    def __init__(self, message, pressure=None):
        super().__init__(message)
        self.pressure = pressure


def assert_scan_capacity(db):
    pressure = dict(db.execute(text("""
        SELECT count(*) AS connections,
               count(*) FILTER (WHERE state='active') AS active,
               count(*) FILTER (WHERE state LIKE 'idle in transaction%') AS idle_transactions,
               count(*) FILTER (WHERE xact_start < clock_timestamp()-interval '15 seconds') AS old_transactions
        FROM pg_stat_activity
        WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'
    """)).mappings().one())
    if pressure['connections'] >= 40 or pressure['active'] >= 5 or pressure['idle_transactions'] >= 3 or pressure['old_transactions']:
        raise ScanPaused('数据库负载升高，已释放连接；稍后用同一输出目录继续',pressure)
    return pressure


def read_page(scan_engine, after_key, limit, on_pressure=None):
    """只在这里持有连接；返回完全加载的对象，分析和文件写入在事务之外。"""
    with Session(scan_engine, expire_on_commit=False) as db:
        db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        pressure = assert_scan_capacity(db)
        if on_pressure:
            on_pressure(pressure)
        if not review_ready(db):
            raise ScanPaused('核重结构未启用，停止扫描')
        normalized = func.resource_person_duplicate_name_key(ResourcePerson.full_name)
        keys = [row[0] for row in active_query(db, db.query(normalized)).filter(normalized > after_key)
                .group_by(normalized).having(func.count(ResourcePerson.id) > 1).order_by(normalized).limit(limit).all()]
        if not keys:
            db.rollback()
            return [], [], {}, {}
        people = active_query(db, db.query(ResourcePerson)).filter(normalized.in_(keys)).options(*_person_options(), *review_options(db)).all()
        from talent_duplicate_models import TalentDuplicateOperation
        operations = _decision_query(db).filter(TalentDuplicateOperation.name_key.in_(keys)).order_by(TalentDuplicateOperation.created_at, TalentDuplicateOperation.id).all()
        grouped = defaultdict(list)
        for person in people:
            from talent_duplicate_service import name_key
            grouped[name_key(person.full_name)].append(person)
        # 使用主档计数，含归档来源的联系方式；共用账号也纳入证据版本。
        usage = contact_usage_index(db)
        decisions = {key: _pair_decisions(grouped[key], [op for op in operations if op.name_key == key],usage) for key in keys}
        db.expunge_all()
        db.rollback()
    return keys, people, decisions, usage


def serialize_groups(keys, people, decisions, usage):
    from talent_duplicate_service import name_key
    grouped = defaultdict(list)
    for person in people:
        grouped[name_key(person.full_name)].append(person)
    exported = []
    for key in keys:
        members = sorted(grouped[key], key=lambda person: str(person.id))
        states = decisions.get(key, {})
        if len(members) < 2 or all(states.get(tuple(sorted((str(a.id), str(b.id))))) == 'different' for a,b in itertools.combinations(members,2)):
            continue
        tokens = {str(getattr(person, field, '') or '').strip() for person in members for field in RESOURCE_CONTACT_FIELDS}
        tokens.update(token for person in members for values in contact_identifiers(person).values() for token in values)
        tokens.update(token for person in members for values in getattr(usage,'by_person',{}).get(str(person.id),{}).values() for token in values)
        sensitive = re.compile('|'.join(re.escape(value) for value in sorted(tokens, key=len, reverse=True) if len(value) > 2), re.I) if any(len(value) > 2 for value in tokens) else None
        def scrub(value):
            if isinstance(value, dict):
                return {k: scrub(v) for k,v in value.items() if k not in {'certificate_no','language_id','source_language_id','target_language_id'}}
            if isinstance(value, list):
                return [scrub(item) for item in value]
            if isinstance(value, str):
                value = re.sub(r'https?://\S+', '[原附件链接]', value)
                value = sensitive.sub('[联系方式]', value) if sensitive else value
                value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[邮箱]', value)
                return re.sub(r'\+?\d[\d ()-]{5,}\d', '[电话]', value)[:1500]
            return value
        values = {str(person.id): _business_values(person) for person in members}
        pairs = []
        for a,b in itertools.combinations(members,2):
            ids = tuple(sorted((str(a.id),str(b.id))))
            if states.get(ids) == 'different':
                continue
            left, right = values[str(a.id)], values[str(b.id)]
            facts = pair_evidence(a,b,usage)
            meaningful = {field for field in left.keys() | right.keys() if field not in {*RESOURCE_CONTACT_FIELDS,
                'full_name','chinese_name','wechat_accounts','resume_path','status','cooperation_type','registration_source',
                'capabilities','remarks','overall_rating','annotation_willingness'}}
            groups = {state: {field: scrub(left[field]) if state == 'same' else [scrub(left.get(field)),scrub(right.get(field))]
                for field in sorted(meaningful) if field_state([left.get(field),right.get(field)]) == state}
                for state in ('same','conflict','complement')}
            pairs.append({'codes': [a.resource_code,b.resource_code], 'person_ids': list(ids),
                'contact_matches': facts['contact_matches'], 'shared_contact_counts': facts['shared_contact_counts'],
                'shared_contact_warning': facts['shared_contact_warning'], 'identity_conflicts': facts['identity_conflicts'],
                'evidence_version': facts['evidence_version'], 'equal': groups['same'], 'differences': groups['conflict'],
                'supplementary': groups['complement']})
        exported.append({'key': key, 'fingerprints': {str(p.id): comparison_fingerprint(p) for p in members},
            'members': [{'id': str(p.id), 'code': p.resource_code, 'name': p.full_name, 'source': scrub(p.registration_source),
                'remarks': scrub(p.remarks), 'created_at': business_iso(p.created_at)} for p in members], 'pairs': pairs})
    return exported


def atomic_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def write_snapshot(destination, state):
    """即使暂停也能分析已完成的批次，明确标记覆盖不完整。"""
    report = {**state, 'group_count':len(state['groups']), 'pair_count':sum(len(group['pairs']) for group in state['groups'])}
    atomic_json(destination / 'input.json',report)
    brief = [{'index':[i,j], 'name':group['key'], **{k:v for k,v in pair.items() if k != 'person_ids'}}
             for i,group in enumerate(report['groups']) for j,pair in enumerate(group['pairs'])]
    (destination / 'evidence.jsonl').write_text('\n'.join(json.dumps(row,ensure_ascii=False) for row in brief),encoding='utf-8')
    return report


def export(destination, page_size=5, interval=1.0, max_pages=0, scan_engine=None):
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('只允许在 PC 项目目录只读导出')
    url = application_engine.url
    owned = scan_engine is None
    if owned:
        if (url.host, url.port, url.database) != ('43.132.156.72',15432,'xinshi_system'):
            raise SystemExit('数据库目标与已确认目标不一致，停止导出')
        scan_engine = create_engine(url, poolclass=NullPool, connect_args={'connect_timeout':3,
            'options':'-c statement_timeout=3000 -c lock_timeout=200 -c idle_in_transaction_session_timeout=5000 -c timezone=Asia/Hong_Kong -c application_name=talent_identity_readonly_scan'})
    destination.mkdir(parents=True, exist_ok=True)
    checkpoint = destination / 'checkpoint.json'
    state = json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {
        'format_version':2, 'evidence_rule':'identity-pairs-v2', 'created_at':business_iso(business_now()), 'database':{'host':url.host,'port':url.port,'name':url.database},
        'after_key':'', 'groups':[], 'complete':False}
    if state.get('evidence_rule') != 'identity-pairs-v2' or state['database'] != {'host':url.host,'port':url.port,'name':url.database}:
        raise SystemExit('检查点的证据规则或数据库目标不一致，请使用新的输出目录')
    pages = 0
    try:
        while not state['complete']:
            keys, people, decisions, usage = read_page(scan_engine,state['after_key'],page_size,
                on_pressure=lambda pressure: state.update(pressure=pressure,pressure_checked_at=business_iso(business_now())))
            # read_page 已关闭 Session/连接，模型输入构造不持有数据库事务。
            state['groups'].extend(serialize_groups(keys,people,decisions,usage))
            state['complete'] = not keys
            if keys:
                state['after_key'] = keys[-1]
            state['updated_at'] = business_iso(business_now())
            atomic_json(checkpoint,state)
            pages += 1
            if max_pages and pages >= max_pages:
                break
            if keys:
                time.sleep(interval)
        report = write_snapshot(destination,state)
        (destination / 'paused.json').unlink(missing_ok=True)
        print(json.dumps({key:report[key] for key in ('created_at','complete','group_count','pair_count')},ensure_ascii=False),flush=True)
        return report
    except (ScanPaused,OperationalError) as exc:
        write_snapshot(destination,state)
        # 不输出 SQL、连接凭据或资料参数，不自动重试。
        atomic_json(destination / 'paused.json',{'at':business_iso(business_now()),'error_type':type(exc).__name__,
            'reason':str(exc) if isinstance(exc,ScanPaused) else '读取超时或连接异常；连接已释放，可从检查点继续',
            'pressure':getattr(exc,'pressure',None)})
        raise ScanPaused('已暂停只读扫描，可使用同一 --output 目录继续') from None
    finally:
        if owned:
            scan_engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT / f'outputs/talent-agent-review-{business_now():%Y%m%d-%H%M%S%z}')
    parser.add_argument('--page-size',type=int,default=5,choices=range(1,21))
    parser.add_argument('--interval',type=float,default=1.0)
    parser.add_argument('--max-pages',type=int,default=0)
    args = parser.parse_args()
    if args.interval < 0 or args.max_pages < 0:
        parser.error('间隔和页数不能为负数')
    try:
        export(args.output.resolve(),args.page_size,args.interval,args.max_pages)
    except ScanPaused as exc:
        raise SystemExit(str(exc))
