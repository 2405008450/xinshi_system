"""标注子订单名称补充语言方向；默认预览，已有独立名称保留正文。"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def normalize(connection, *, apply=False):
    from sqlalchemy import text
    from annotation_child_copy_service import child_project_name
    from annotation_progress_time import business_now

    rows = connection.execute(text('''
        SELECT child.id, child.order_no, child.project_name, child.updated_at,
               child.inheritance_overrides, parent.project_name AS parent_name,
               source.label AS source_label, target.label AS target_label,
               direction.id AS direction_id
        FROM annotation_project child
        JOIN annotation_project parent ON parent.id = child.parent_project_id
        LEFT JOIN annotation_project_language_item direction ON direction.project_id = child.id
        LEFT JOIN interpretation_language source ON source.id = direction.source_language_id
        LEFT JOIN interpretation_language target ON target.id = direction.target_language_id
        WHERE parent.parent_project_id IS NULL
        ORDER BY child.order_no, direction.sequence_no
    ''' + (' FOR UPDATE OF child, parent' if apply else ''))).mappings().all()
    grouped = {}
    for row in rows:
        grouped.setdefault(row['id'], []).append(row)
    changes, skipped = [], []
    for project_id, directions in grouped.items():
        row = directions[0]
        entry = {'id': str(project_id), 'order_no': row['order_no'], 'old': row['project_name']}
        if len(directions) != 1 or not row['source_label'] or not row['parent_name']:
            skipped.append({**entry, 'reason': '方向不唯一、语种缺失或订单名称为空'})
            continue
        direction = (f'{row["source_label"]}→{row["target_label"]}'
                     if row['target_label'] else row['source_label'])
        copied = (row['project_name'] or '').strip() == row['parent_name'].strip()
        if not copied and (row['project_name'] or '').startswith(f'{direction}-'):
            continue
        target = child_project_name(row['project_name'] or row['parent_name'], row['source_label'], row['target_label'])
        entry.update(new=target, previous_updated_at=row['updated_at'].isoformat(),
                     previous_inheritance_overrides=row['inheritance_overrides'])
        changes.append(entry)
        if apply:
            metadata = row['inheritance_overrides']
            if metadata is not None:
                metadata = set(metadata)
                metadata.discard('inherit:project_name')
                if '*' not in metadata:
                    metadata.add('project_name')
                metadata = sorted(metadata)
            connection.execute(text('''UPDATE annotation_project
                SET project_name=:name, updated_at=:updated_at,
                    inheritance_overrides=CAST(:metadata AS jsonb)
                WHERE id=:id'''), {
                'id': project_id, 'name': target,
                'updated_at': business_now().replace(tzinfo=None),
                'metadata': json.dumps(metadata) if metadata is not None else None,
            })
    return {'total': len(grouped), 'changes': changes, 'skipped': skipped}


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-host')
    parser.add_argument('--expected-commit')
    parser.add_argument('--expected-database', help='host:port/database，不含凭据')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    from database import engine
    from annotation_progress_time import business_now
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    target = f'{engine.url.host}:{engine.url.port or 5432}/{engine.url.database}'
    if args.apply and (args.expected_host != socket.gethostname() or args.expected_commit != commit
                       or args.expected_database != target):
        parser.error('应用必须提供匹配的主机名、完整 Git 提交和数据库目标')
    report = {'host': socket.gethostname(), 'project_directory': str(ROOT), 'commit': commit,
              'database': target, 'apply': args.apply, 'committed': False,
              'occurred_at': business_now().isoformat()}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    def save():
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with engine.connect() as connection:
        with connection.begin():
            if not args.apply:
                from sqlalchemy import text
                connection.execute(text('SET TRANSACTION READ ONLY'))
            report.update(normalize(connection, apply=args.apply))
            save()  # 提交前持久化旧值及恢复所需元数据。
        report['committed'] = args.apply
        save()
    print(json.dumps({key: report[key] for key in ('database', 'total', 'committed')}, ensure_ascii=False))
    print(f'调整 {len(report["changes"])} 条，跳过 {len(report["skipped"])} 条；报告：{args.report}')


if __name__ == '__main__':
    run()
