"""只读核验核重队列：审计快照、留存附件、归档指向与全库剩余姓名组。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from fastapi import HTTPException
from business_time import business_iso, business_now
from talent_duplicate_service import digest
from talent_name_merge_service import name_kind
from talent_retention_service import _blob_path


def verify_operation(operation, checked_files):
    failures = []
    identifier = str(operation['id'])
    before, after = operation['before_snapshot'], operation['after_snapshot']
    decisions = operation['decisions'] or {}
    retention = decisions.get('retention') or {}
    for label, snapshot in [('before', before), ('after', after)]:
        if retention.get(label+'_sha256') != digest(snapshot):
            failures.append({'operation_id': identifier, 'check': label+'_snapshot_hash'})
    people = set(before.get('people', {}))
    if not set(operation['person_ids']) <= people or str(operation['target_id']) not in people:
        failures.append({'operation_id': identifier, 'check': 'original_participants'})
    audit = decisions.get('merge_audit') or {}
    if str(operation['target_id']) != audit.get('target_id') or not audit.get('fields'):
        failures.append({'operation_id': identifier, 'check': 'field_decision_audit'})
    for table, rows in before.get('references', {}).items():
        # 兼容译员字段可由主档同步；业务记录的原 ID 必须保留在提交后快照。
        original_ids = {row['id'] for row in rows if row.get('id')}
        final_ids = {row['id'] for row in after.get('references', {}).get(table, []) if row.get('id')}
        if not original_ids <= final_ids:
            failures.append({'operation_id': identifier, 'check': 'business_reference_ids', 'table': table})
    for attachment in retention.get('attachments', []):
        if attachment.get('state') != 'archived':
            continue
        checksum = attachment.get('sha256')
        if checksum not in checked_files:
            try:
                path = _blob_path(checksum)
                actual = hashlib.sha256()
                size = 0
                with path.open('rb') as source:
                    for chunk in iter(lambda: source.read(1024*1024), b''):
                        actual.update(chunk); size += len(chunk)
                checked_files[checksum] = (actual.hexdigest() == checksum, size)
            except (OSError, HTTPException):
                checked_files[checksum] = (False, None)
        valid, size = checked_files[checksum]
        if not valid or size != attachment.get('file_size'):
            failures.append({'operation_id': identifier, 'check': 'retained_attachment'})
    if operation['undone_at']:
        failures.append({'operation_id': identifier, 'check': 'operation_was_undone'})
    return failures


def run(directory):
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('只能在 PC 的项目目录只读核验')
    directory = Path(directory).resolve()
    if not directory.is_relative_to((ROOT/'outputs/talent-name-merge-slow').resolve()):
        raise SystemExit('任务目录不符合要求')
    state = json.loads((directory/'status.json').read_text(encoding='utf-8'))
    identifiers = [row['id'] for row in state['results']]
    from database import engine as application_engine
    url = application_engine.url
    if (url.host, url.port, url.database) != ('43.132.156.72', 15432, 'xinshi_system'):
        raise SystemExit('目标数据库与授权目标不符')
    engine = create_engine(url, poolclass=NullPool, connect_args={'connect_timeout': 3,
        'application_name': 'talent_review_readonly_verification',
        'options': '-c timezone=Asia/Hong_Kong -c statement_timeout=3000'})
    failures, checked_files, operations = [], {}, []
    try:
        with engine.connect() as connection:
            connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
            if identifiers:
                operations = connection.execute(text('''
                    SELECT id, target_id, person_ids, before_snapshot, after_snapshot, decisions, undone_at
                    FROM talent_duplicate_operation WHERE id=ANY(CAST(:ids AS uuid[]))
                '''), {'ids': identifiers}).mappings().all()
            keys = connection.execute(text('''
                SELECT resource_person_duplicate_name_key(full_name) AS key
                FROM resource_person WHERE archived_into_id IS NULL
                GROUP BY resource_person_duplicate_name_key(full_name) HAVING count(*)>1
            ''')).scalars().all()
            bad_redirects = connection.execute(text('''
                SELECT count(*) FROM resource_person source LEFT JOIN resource_person target
                ON target.id=source.archived_into_id WHERE source.archived_into_id IS NOT NULL
                AND (target.id IS NULL OR target.archived_into_id IS NOT NULL OR target.id=source.id)
            ''')).scalar_one()
            connection.rollback()
        # 附件读取和 JSON 校验在连接已关闭后执行，不占用数据库连接。
        for operation in operations:
            failures.extend(verify_operation(operation, checked_files))
        if len(operations) != len(identifiers):
            failures.append({'check': 'operation_count'})
        if bad_redirects:
            failures.append({'check': 'archive_redirects', 'count': bad_redirects})
        eligible = [key for key in keys if name_kind(key) in {'chinese', 'english'}]
        report = {'verified_at': business_iso(business_now()), 'database_read_only': True,
                  'verified_operations': len(operations), 'verified_retained_files': len(checked_files),
                  'archive_redirect_errors': bad_redirects, 'eligible_groups_remaining_in_database': len(eligible),
                  'queue_completed_at_snapshot': len(identifiers), 'queue_remaining_at_snapshot':
                      len(state['keys'])-len(state.get('processed_keys', state['keys'][:state['index']])),
                  'failures': failures, 'passed': not failures}
        temporary = directory/'verification-latest.tmp'
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(directory/'verification-latest.json')
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report['passed'] else 1
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir')
    raise SystemExit(run(parser.parse_args().run_dir))
