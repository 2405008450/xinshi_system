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
from sqlalchemy.pool import QueuePool
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
    target = str(operation['target_id'])
    final_target = after.get('people', {}).get(target)
    if final_target is None:
        failures.append({'operation_id': identifier, 'check': 'retained_target_snapshot'})
    else:
        original_person = before.get('people', {}).get(target, {}).get('person', {})
        final_person = final_target.get('person', {})
        if str(final_person.get('id', target)) != target:
            failures.append({'operation_id': identifier, 'check': 'retained_target_id'})
        if final_person.get('resource_code') != original_person.get('resource_code'):
            failures.append({'operation_id': identifier, 'check': 'retained_resource_code'})
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


def archive_people(connection, identifiers):
    if not identifiers:
        return {}
    rows = connection.execute(text('''
        SELECT id::text AS id, archived_into_id::text AS archived_into_id
        FROM resource_person WHERE id=ANY(CAST(:ids AS uuid[]))
    '''), {'ids': sorted(identifiers)}).mappings().all()
    return {row['id']: row for row in rows}


def verify_archive_targets(operations, people):
    """核对真实归档行，并兼容主档后续合并时统一改指向新主档。"""
    failures = []
    for operation in operations:
        identifier, target = str(operation['id']), str(operation['target_id'])
        missing = {str(person_id) for person_id in operation['person_ids']} | {target}
        missing -= people.keys()
        for person_id in sorted(missing):
            failures.append({'operation_id': identifier, 'person_id': person_id, 'check': 'archive_participant_missing'})
        if target not in people:
            continue
        effective_target = people[target]['archived_into_id'] or target
        for person_id in operation['person_ids']:
            person_id = str(person_id)
            if person_id != target and person_id in people and people[person_id]['archived_into_id'] != effective_target:
                failures.append({'operation_id': identifier, 'person_id': person_id, 'check': 'archive_target_mismatch'})
    return failures


def operation_batches(engine, identifiers, batch_size=20):
    """短事务分批读取；交给调用方校验前必须结束事务并归还连接。"""
    if batch_size < 1:
        raise ValueError('核验批次大小必须为正数')
    for offset in range(0, len(identifiers), batch_size):
        with engine.connect() as connection:
            connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
            rows = connection.execute(text('''
                SELECT id, target_id, person_ids, before_snapshot, after_snapshot, decisions, undone_at
                FROM talent_duplicate_operation WHERE id=ANY(CAST(:ids AS uuid[]))
            '''), {'ids': identifiers[offset:offset+batch_size]}).mappings().all()
            connection.rollback()
        yield rows


def verification_engine(url):
    """核验期间最多一个专用连接，逐批归还，run 最终统一 dispose。"""
    return create_engine(url, poolclass=QueuePool, pool_size=1, max_overflow=0,
        pool_timeout=1, pool_pre_ping=True, connect_args={'connect_timeout': 3,
        'application_name': 'talent_review_readonly_verification',
        'options': '-c timezone=Asia/Hong_Kong -c statement_timeout=3000 '
                   '-c idle_in_transaction_session_timeout=5000'})


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
    engine = verification_engine(url)
    failures, checked_files, operation_count, operation_links = [], {}, 0, []
    try:
        for batch in operation_batches(engine, identifiers):
            # JSON 哈希和附件读取在该批事务结束、连接归还后执行。
            for operation in batch:
                failures.extend(verify_operation(operation, checked_files))
                operation_count += 1
                operation_links.append({'id': str(operation['id']), 'target_id': str(operation['target_id']),
                                        'person_ids': [str(person_id) for person_id in operation['person_ids']]})
        participant_ids = {person_id for operation in operation_links for person_id in operation['person_ids']}
        participant_ids.update(operation['target_id'] for operation in operation_links)
        with engine.connect() as connection:
            connection.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
            # 分批快照读取完成后，重新核对全部操作的存在性和撤销状态。
            statuses = connection.execute(text('''
                SELECT id, undone_at FROM talent_duplicate_operation WHERE id=ANY(CAST(:ids AS uuid[]))
            '''), {'ids': identifiers}).mappings().all() if identifiers else []
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
            current_people = archive_people(connection, participant_ids)
            connection.rollback()
        archive_failures = verify_archive_targets(operation_links, current_people)
        failures.extend(archive_failures)
        if operation_count != len(identifiers) or {str(row['id']) for row in statuses} != set(identifiers):
            failures.append({'check': 'operation_count'})
        already_undone = {row.get('operation_id') for row in failures if row['check'] == 'operation_was_undone'}
        for row in statuses:
            if row['undone_at'] and str(row['id']) not in already_undone:
                failures.append({'operation_id': str(row['id']), 'check': 'operation_was_undone'})
        if bad_redirects:
            failures.append({'check': 'archive_redirects', 'count': bad_redirects})
        eligible = [key for key in keys if name_kind(key) in {'chinese', 'english'}]
        report = {'verified_at': business_iso(business_now()), 'database_read_only': True,
                  'verified_operations': operation_count, 'verified_retained_files': len(checked_files),
                  'archive_participants_checked': len(current_people), 'archive_participant_errors': len(archive_failures),
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
