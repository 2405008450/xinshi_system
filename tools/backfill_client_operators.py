"""客户首次录入人回溯：默认只读预览；显式 apply 创建独立表并留存可回滚清单。"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text
from database import engine
from client_operator import ClientOperator
from annotation_progress_time import business_now

TARGET = '43.132.156.72:15432/xinshi_system'
EVIDENCE_SQL = """
SELECT c.id AS client_id, c.client_code, c.client_name, c.created_at AS client_created_at,
       c.updated_at AS client_updated_at, q.id AS consultation_id, q.consultation_code,
       q.editor_id, u.username, u.full_name,
       q.project_intake->'_work_report_capture'->>'owner_id' AS capture_owner_id
FROM client c JOIN consultation q ON q.client_id=c.id AND q.created_at=c.created_at
LEFT JOIN app_user u ON u.id=q.editor_id
ORDER BY c.id, q.id
"""


def classify(rows, existing_ids=()):
    """时间必须精确相等、唯一咨询、身份完整；登录留痕存在时必须与录入人一致。"""
    groups = defaultdict(list)
    for row in rows:
        groups[str(row['client_id'])].append(row)
    accepted, skipped = [], []
    existing_ids = {str(value) for value in existing_ids}
    for client_id, group in groups.items():
        row = dict(group[0])
        reason = None
        if client_id in existing_ids:
            reason = '已记录操作人，不覆盖'
        elif len(group) != 1:
            reason = '同一创建时刻关联多个咨询'
        elif not row['editor_id'] or not row['username']:
            reason = '咨询录入人账号无法确认'
        elif row['capture_owner_id'] and row['capture_owner_id'] != str(row['editor_id']):
            reason = '咨询录入人与登录账号留痕冲突'
        if reason:
            skipped.append(dict(row, reason=reason))
        else:
            row['operator_name'] = row['full_name'] or row['username']
            row['source'] = 'consultation_capture_backfill' if row['capture_owner_id'] else 'consultation_editor_backfill'
            accepted.append(row)
    return accepted, skipped


def save_json(path, value):
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-count', type=int)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if (socket.gethostname().lower() != 'pc' or Path.cwd().resolve() != ROOT
            or ROOT != Path(r'E:\xinshi_system')
            or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe'):
        raise SystemExit('主机、项目路径或解释器不匹配')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if commit != args.expected_commit or target != TARGET or args.confirm_target != target:
        raise SystemExit('提交或数据库目标不匹配')
    if args.apply and args.expected_count is None:
        raise SystemExit('写入必须指定预期数量')
    context = dict(host=socket.gethostname(), directory=str(ROOT), commit=commit, database=target)
    print(json.dumps(context, ensure_ascii=False))
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL statement_timeout='30s'"))
        connection.execute(text("SET LOCAL lock_timeout='5s'"))
        if not args.apply:
            connection.execute(text('SET TRANSACTION READ ONLY'))
        else:
            connection.execute(text('LOCK TABLE client, consultation, app_user IN SHARE MODE'))
        existed = inspect(connection).has_table('client_operator')
        if existed and args.apply:
            connection.execute(text('LOCK TABLE client_operator IN SHARE ROW EXCLUSIVE MODE'))
        existing_ids = connection.execute(text('SELECT client_id FROM client_operator')).scalars().all() if existed else []
        rows = [dict(row) for row in connection.execute(text(EVIDENCE_SQL)).mappings()]
        accepted, skipped = classify(rows, existing_ids)
        summary = dict(candidates=len({r['client_id'] for r in rows}), accepted=len(accepted),
                       skipped=dict(Counter(row['reason'] for row in skipped)),
                       by_source=dict(Counter(row['source'] for row in accepted)),
                       by_username=dict(Counter(row['username'] for row in accepted)))
        print(json.dumps(summary, ensure_ascii=False))
        if not args.apply:
            return
        if len(accepted) != args.expected_count:
            raise ValueError('预期数量已变化，停止回填')
        stamp = business_now()
        backup = ROOT / 'backups' / f'client_operator_backfill_{stamp:%Y%m%d-%H%M%S%z}.json'
        backup.parent.mkdir(exist_ok=True)
        save_json(backup, dict(**context, recorded_at=stamp.isoformat(), table_existed=existed,
                              summary=summary, entries=accepted, skipped=skipped,
                              rollback='仅删除本清单 client_id 且 recorded_at 等于本批 recorded_at 的 client_operator 行；原客户与咨询记录未修改，勿删除后续新增行或整表'))
        ClientOperator.__table__.create(connection, checkfirst=True)
        if accepted:
            connection.execute(ClientOperator.__table__.insert(), [dict(
                client_id=row['client_id'], operator_user_id=row['editor_id'],
                operator_name=row['operator_name'], source=row['source'],
                consultation_id=row['consultation_id'], consultation_code=row['consultation_code'],
                recorded_at=stamp,
            ) for row in accepted])
        actual = connection.execute(text('SELECT count(*) FROM client_operator WHERE recorded_at=:stamp'), {'stamp':stamp}).scalar_one()
        if actual != len(accepted):
            raise ValueError('回填验证不一致，事务回滚')
    save_json(backup.with_suffix('.result.json'), dict(committed_at=business_now().isoformat(), inserted=actual, backup=str(backup)))
    print(f'committed={actual} backup={backup}')


if __name__ == '__main__':
    run()
