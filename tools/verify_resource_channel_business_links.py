"""业务账号关联前后只读核验，保存摘要而非人员历史明文。"""
import argparse
import hashlib
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['capture', 'verify'])
    parser.add_argument('--backup-file', type=Path, required=True)
    args = parser.parse_args()
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system' or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe':
        raise SystemExit('仅允许 PC 使用项目解释器')
    backup_file = args.backup_file.resolve()
    if Path(r'E:\xinshi_runtime\backups').resolve() not in backup_file.parents:
        raise SystemExit('核验只允许读取已批准迁移的仓库外备份')
    raw = backup_file.read_bytes()
    expected = backup_file.with_suffix('.sha256').read_text(encoding='utf-8').strip()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('原备份 SHA-256 不一致')
    backup = json.loads(raw)
    plan = json.loads((ROOT / '.tmp/resource-channels-pc/account-plan.json').read_text(encoding='utf-8'))
    names = [group['parent_name'] for group in plan['groups']] + [a['name'] for group in plan['groups'] for a in group['accounts']]
    ids = [row['id'] for row in backup['rows']['resource_development_option'] if row['name'] in names and row['kind'] == 'platform']
    if len(ids) != 11:
        raise ValueError('备份中的账号和平台与批准清单不一致')
    sys.path.insert(0, str(ROOT))
    from database import engine
    from sqlalchemy import text
    from uuid import UUID
    if (engine.url.host, engine.url.port, engine.url.database) != ('43.132.156.72', 15432, 'xinshi_system'):
        raise SystemExit('停止：不是已批准的业务目标')
    sql_ids = [UUID(value) for value in ids]
    baseline_file = backup_file.parent / 'history-baseline.json'
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        history, history_rows = {}, {}
        for table, order in [('resource_development_record', 'id'), ('resource_development_counter', 'platform_id,work_date'), ('resource_development_arrangement_cell', 'id')]:
            values = connection.execute(text(f'SELECT row_to_json(t) FROM {table} t WHERE platform_id = ANY(:ids) ORDER BY {order}'), {'ids': sql_ids}).scalars().all()
            history_rows[table] = values
            history[table] = dict(count=len(values), sha256=digest(values))
        audit_count = connection.execute(text("SELECT count(*) FROM resource_development_audit WHERE entity_type='option' AND entity_id = ANY(:ids)"), {'ids': sql_ids}).scalar()
        if args.mode == 'capture':
            baseline = dict(ids=ids, history=history, audit_count=audit_count)
            baseline_file.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(dict(captured=True, baseline_file=str(baseline_file), history=history), ensure_ascii=False))
            return
        baseline = json.loads(baseline_file.read_text(encoding='utf-8'))
        if baseline['ids'] != ids:
            raise ValueError('核验对象与原清单不一致')
        later_added = {}
        for table, original in baseline['history'].items():
            if original == history[table]:
                continue
            # 一条原安排可按整行摘要准确识别；并发新增业务安排不应被当成原记录变更或删除。
            if original['count'] == 1 and history[table]['count'] > 1 and sum(digest([row]) == original['sha256'] for row in history_rows[table]) == 1:
                later_added[table] = history[table]['count'] - 1
                continue
            raise ValueError('原历史资料与关联前不一致：' + json.dumps({'table': table, 'before': original, 'current': history[table]}, ensure_ascii=False))
        for table, order in [('resource_development_option', 'id'), ('resource_development_channel_member', 'platform_id,user_id,role')]:
            after = connection.execute(text(f'SELECT row_to_json(t) FROM {table} t ORDER BY {order}')).scalars().all()
            before = backup['rows'][table]
            if table.endswith('_option'):
                allowed = {'revision', 'updated_by', 'updated_at'}
                before = [{k: v for k, v in row.items() if row['id'] not in ids or k not in allowed} for row in before]
                after = [{k: v for k, v in row.items() if row['id'] not in ids or k not in allowed} for row in after]
            if before != after:
                raise ValueError('原账号 ID、编号、说明、用途、分类或人员分工发生变化')
        links = {str(row.account_id): str(row.parent_id) for row in connection.execute(text('SELECT account_id,parent_id FROM resource_channel_account_link'))}
        expected_links = {account['id']: group['parent_id'] for group in plan['groups'] for account in group['accounts']}
        old_links = {row['account_id']: row['parent_id'] for row in backup['rows'].get('resource_channel_account_link', [])}
        if links != (old_links | expected_links):
            raise ValueError('账号关系与已批准清单不一致')
        if audit_count - baseline['audit_count'] != 11:
            raise ValueError('关联操作审计数量不符合预期')
    result = dict(verified=True, account_ids_and_fields_preserved=True, members_preserved=True, history=baseline['history'], current_history=history, later_added_history=later_added,
                  linked_accounts=len(expected_links), grouped_platforms=len(plan['groups']), new_audits=audit_count - baseline['audit_count'])
    (backup_file.parent / 'links-verified.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / '.tmp/resource-channels-pc/business-verified.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    run()
