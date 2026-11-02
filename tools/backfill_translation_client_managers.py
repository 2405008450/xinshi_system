"""按创建者姓名补齐笔译项目缺失的客户经理，默认只读预览。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from database import engine

ZONE = timezone(timedelta(hours=8))
TARGET = "43.132.156.72:15432/xinshi_system"
REASON = "按用户指令补齐历史笔译项目客户经理，采用项目创建者姓名；未改动客户档案"
MISSING = """
SELECT p.id, p.order_no, p.created_by, p.updated_at, u.username, u.full_name,
       c.client_manager AS client_fallback, m.id AS history_id,
       m.revision, m.new_manager_id, m.new_manager_name,
       (SELECT json_agg(json_build_object(
           'id', a.id, 'actor_id', a.actor_user_id,
           'username', a.actor_username_snapshot, 'source', a.operation_source))
        FROM project_operation_audit a
        WHERE a.project_type='translation' AND a.operation_type='create'
          AND a.project_id=p.id) AS creation_logs
FROM translation_project p
LEFT JOIN client c ON c.id=p.client_id
LEFT JOIN app_user u ON u.id=p.created_by
LEFT JOIN LATERAL (
    SELECT * FROM project_client_manager_change h
    WHERE h.project_type='translation' AND h.project_id=p.id
    ORDER BY revision DESC LIMIT 1
) m ON true
WHERE NULLIF(trim(CASE WHEN m.id IS NOT NULL
                      THEN m.new_manager_name ELSE c.client_manager END),'') IS NULL
ORDER BY p.id
"""


def validate_rows(rows):
    """任何缺失身份、日志冲突或既有调整记录都中止，避免推测或覆盖。"""
    for row in rows:
        if not row['created_by'] or not (row['username'] or '').strip():
            raise ValueError(f"创建者账号无法确认：{row['order_no']}")
        if not (row['full_name'] or '').strip():
            raise ValueError(f"创建者未设置姓名：{row['order_no']}")
        if row['history_id']:
            raise ValueError(f"存在客户经理调整记录，需单独核查：{row['order_no']}")
        for audit in row['creation_logs'] or []:
            if str(audit['actor_id']) != str(row['created_by']):
                raise ValueError(f"创建日志与创建者冲突：{row['order_no']}")


def save_json(path, value):
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-count', type=int)
    args = parser.parse_args()
    if (socket.gethostname().lower() != 'pc' or Path.cwd().resolve() != ROOT
            or ROOT != Path(r'E:\xinshi_system')
            or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe'):
        raise SystemExit('主机、项目目录或 Python 解释器不匹配')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if commit != args.expected_commit or target != args.confirm_target or target != TARGET:
        raise SystemExit('Git 提交或数据库目标不匹配')
    if args.apply and args.expected_count is None:
        raise SystemExit('写入必须指定预期数量')
    context = dict(host=socket.gethostname(), project_directory=str(ROOT), commit=commit, database=target)
    print(json.dumps(context, ensure_ascii=False))
    now = datetime.now(ZONE)
    with engine.begin() as connection:
        if args.apply:
            # 阻止并发修改客户档案和经理历史；按正常业务顺序锁定母项目。
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            connection.execute(text('LOCK TABLE client IN SHARE MODE'))
            connection.execute(text('LOCK TABLE project_client_manager_change IN SHARE ROW EXCLUSIVE MODE'))
        else:
            connection.execute(text('SET TRANSACTION READ ONLY'))
        rows = [dict(row) for row in connection.execute(text(
            MISSING + (' FOR UPDATE OF p' if args.apply else '')
        )).mappings()]
        validate_rows(rows)
        summary = dict(missing=len(rows), with_creation_logs=sum(bool(r['creation_logs']) for r in rows),
                       by_username=dict(Counter(r['username'] for r in rows)))
        print(json.dumps(summary, ensure_ascii=False))
        if not args.apply:
            return
        if len(rows) != args.expected_count:
            raise ValueError('缺失数量发生变化，重新只读核查后再执行')
        entries = [dict(row, inserted_history_id=str(uuid4())) for row in rows]
        backup = ROOT / 'backups' / f'translation_client_manager_backfill_{now:%Y%m%d-%H%M%S%z}.json'
        backup.parent.mkdir(exist_ok=True)
        save_json(backup, dict(**context, started_at=now.isoformat(), summary=summary, entries=entries,
                              rollback='按 inserted_history_id 删除本批历史；仅在项目 updated_at 仍等于 applied_updated_at 时恢复原 updated_at',
                              applied_updated_at=now.replace(tzinfo=None).isoformat()))
        if entries:
            connection.execute(text('''
                INSERT INTO project_client_manager_change
                    (id, project_type, project_id, revision, previous_manager_id,
                     previous_manager_name, new_manager_id, new_manager_name,
                     actor_user_id, actor_name, reason, changed_at)
                VALUES (:history_id, 'translation', :project_id, 1, NULL,
                        :previous_name, :creator_id, :username,
                        NULL, :actor_name, :reason, :changed_at)
            '''), [dict(history_id=e['inserted_history_id'], project_id=e['id'],
                        previous_name=e['client_fallback'], creator_id=e['created_by'],
                        username=e['full_name'], actor_name='数据维护（用户指令）',
                        reason=REASON + ('；已核对创建日志' if e['creation_logs'] else '；依据项目 created_by'),
                        changed_at=now) for e in entries])
            connection.execute(text('UPDATE translation_project SET updated_at=:changed_at WHERE id=:id'),
                               [dict(id=e['id'], changed_at=now.replace(tzinfo=None)) for e in entries])
        remaining = connection.execute(text(MISSING)).mappings().all()
        if remaining:
            raise ValueError('写入后仍有缺失，整批回滚')
        # 正常提交完成后才输出成功；异常时数据库事务自动回滚。
    save_json(backup.with_suffix('.result.json'), dict(committed_at=datetime.now(ZONE).isoformat(),
              inserted=len(entries), remaining_missing=0, backup=str(backup)))
    print(f'committed={len(entries)} remaining_missing=0 backup={backup}')


if __name__ == '__main__':
    run()
