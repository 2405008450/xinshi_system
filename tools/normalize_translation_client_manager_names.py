"""将笔译或口译项目客户经理统一为用户姓名；默认只读，追加历史并保留回滚备份。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from tools.backfill_translation_client_managers import ROOT, TARGET, ZONE, save_json
from database import engine

QUERY = """
SELECT p.id, p.order_no, p.created_by, p.updated_at,
       c.client_manager AS fallback, m.id AS history_id, m.revision,
       m.new_manager_id, m.new_manager_name,
       (SELECT json_agg(json_build_object('id', a.id, 'actor_id', a.actor_user_id))
        FROM project_operation_audit a WHERE a.project_type='translation'
          AND a.operation_type='create' AND a.project_id=p.id) AS creation_logs
FROM translation_project p LEFT JOIN client c ON c.id=p.client_id
LEFT JOIN LATERAL (SELECT * FROM project_client_manager_change h
    WHERE h.project_type='translation' AND h.project_id=p.id
    ORDER BY revision DESC LIMIT 1) m ON true
ORDER BY p.id
"""


def project_query(project_type):
    if project_type not in ('translation', 'interpretation'):
        raise ValueError('不支持的项目类型')
    if project_type == 'translation':
        return QUERY
    # 口译优先取子客户档案；子客户经理为空时也不回退母客户，与业务属性一致。
    return QUERY.replace("'translation'", "'interpretation'").replace(
        'FROM translation_project p LEFT JOIN client c ON c.id=p.client_id',
        'FROM interpretation_project p LEFT JOIN client c ON c.id=p.client_id '
        'LEFT JOIN sub_client s ON s.id=p.sub_client_id',
    ).replace('c.client_manager AS fallback',
              'CASE WHEN s.id IS NOT NULL THEN s.client_manager ELSE c.client_manager END AS fallback')


def build_plan(rows, users):
    by_id = {str(u['id']): u for u in users}
    plan = []
    for row in rows:
        old = row['new_manager_name'] if row['history_id'] else row['fallback']
        if row['history_id'] and row['new_manager_id']:
            manager = by_id.get(str(row['new_manager_id']))
            source = '保留项目已分配人员，统一姓名'
        else:
            matches = [u for u in users if old and old in (u['full_name'], u['username'])]
            if len(matches) > 1:
                raise ValueError(f"人员匹配不唯一：{row['order_no']}")
            manager = matches[0] if matches else by_id.get(str(row['created_by']))
            source = '按历史人员值匹配姓名' if matches else '无效客户经理值，按项目创建者纠正'
            if not matches and any(str(a['actor_id']) != str(row['created_by'])
                                   for a in row['creation_logs'] or []):
                raise ValueError(f"创建日志冲突：{row['order_no']}")
        if not manager or not (manager['full_name'] or '').strip():
            raise ValueError(f"无法确认用户姓名：{row['order_no']}")
        if old == manager['full_name']:
            continue
        plan.append(dict(row, previous_name=old, manager_id=str(manager['id']),
                         manager_name=manager['full_name'], source=source,
                         inserted_history_id=str(uuid4())))
    return plan


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-count', type=int)
    parser.add_argument('--project-type', choices=['translation', 'interpretation'], default='translation')
    args = parser.parse_args()
    query = project_query(args.project_type)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    target = f'{engine.url.host}:{engine.url.port}/{engine.url.database}'
    if (socket.gethostname().lower() != 'pc' or ROOT != Path(r'E:\xinshi_system')
            or Path.cwd().resolve() != ROOT
            or Path(sys.executable).resolve() != ROOT / '.venv/Scripts/python.exe'
            or commit != args.expected_commit or target != args.confirm_target or target != TARGET):
        raise SystemExit('主机、目录、解释器、Git 提交或数据库目标不匹配')
    now = datetime.now(ZONE)
    context = dict(host=socket.gethostname(), directory=str(ROOT), commit=commit, target=target,
                   project_type=args.project_type)
    print(json.dumps(context, ensure_ascii=False))
    with engine.begin() as c:
        if args.apply:
            c.execute(text("SET LOCAL lock_timeout='5s'"))
            c.execute(text('LOCK TABLE client IN SHARE MODE'))
            if args.project_type == 'interpretation':
                c.execute(text('LOCK TABLE sub_client IN SHARE MODE'))
            c.execute(text('LOCK TABLE project_client_manager_change IN SHARE ROW EXCLUSIVE MODE'))
            c.execute(text('LOCK TABLE app_user IN SHARE MODE'))
        else:
            c.execute(text('SET TRANSACTION READ ONLY'))
        rows = [dict(r) for r in c.execute(text(query + (' FOR UPDATE OF p' if args.apply else ''))).mappings()]
        users = [dict(u) for u in c.execute(text('SELECT id, username, full_name FROM app_user')).mappings()]
        plan = build_plan(rows, users)
        print(json.dumps(dict(total=len(rows), changes=len(plan),
                              reasons=dict(Counter(e['source'] for e in plan))), ensure_ascii=False))
        if not args.apply:
            return
        if args.expected_count is None or len(plan) != args.expected_count:
            raise ValueError('预期数量不匹配')
        backup = ROOT / 'backups' / f'{args.project_type}_manager_names_{now:%Y%m%d-%H%M%S%z}.json'
        save_json(backup, dict(**context, started_at=now.isoformat(), entries=plan,
                              applied_updated_at=now.replace(tzinfo=None).isoformat(),
                              rollback='按 inserted_history_id 撤销新增历史；仅当 updated_at 仍为本批时间时恢复原更新时间'))
        payload = json.dumps(plan, default=str, ensure_ascii=False)
        if plan:
            # 单次集合写入，缩短共享数据库锁定时间；旧历史快照保持原样。
            c.execute(text('''INSERT INTO project_client_manager_change
                (id, project_type, project_id, revision, previous_manager_id,
                 previous_manager_name, new_manager_id, new_manager_name,
                 actor_user_id, actor_name, reason, changed_at)
                SELECT x.inserted_history_id, :project_type, x.id, coalesce(x.revision,0)+1,
                       x.new_manager_id, x.previous_name, x.manager_id, x.manager_name,
                       NULL, :actor, :reason || '；' || x.source, :now
                FROM json_to_recordset(CAST(:payload AS json)) AS x(
                    inserted_history_id uuid, id uuid, revision integer,
                    new_manager_id uuid, previous_name text, manager_id uuid,
                    manager_name text, source text)'''), dict(payload=payload,
                    project_type=args.project_type,
                    actor='数据维护（用户指令）', reason='客户经理统一为用户姓名', now=now))
            c.execute(text(f'''UPDATE {args.project_type}_project SET updated_at=:now
                WHERE id IN (SELECT x.id FROM json_to_recordset(CAST(:payload AS json)) AS x(id uuid))'''),
                dict(now=now.replace(tzinfo=None), payload=payload))
        after = [dict(r) for r in c.execute(text(query)).mappings()]
        if build_plan(after, users):
            raise ValueError('仍有姓名不一致，整批回滚')
    save_json(backup.with_suffix('.result.json'), dict(committed_at=datetime.now(ZONE).isoformat(),
              changed=len(plan), remaining=0, backup=str(backup)))
    print(f'committed={len(plan)} remaining=0 backup={backup}')


if __name__ == '__main__':
    run()
