"""历史多方向母订单补建：默认只读，应用时逐母订单事务并输出报告。"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def backfill(sessions, *, apply=False, parent_ids=None, on_result=None):
    from annotation_models import AnnotationProject
    from annotation_direction_service import direction_state, ensure_direction_children
    from annotation_service import get_annotation_project, _lock_annotation_order_numbers, _lock_parent
    with sessions() as db:
        query = db.query(AnnotationProject.id).filter(AnnotationProject.parent_project_id.is_(None))
        if parent_ids is not None:
            query = query.filter(AnnotationProject.id.in_(parent_ids))
        ids = [row.id for row in query.order_by(AnnotationProject.order_no).all()]
    results = []
    for project_id in ids:
        entry = {'parent_id': str(project_id), 'mode': 'apply' if apply else 'preview'}
        with sessions() as db:
            try:
                if apply:
                    _lock_annotation_order_numbers(db)
                    if not _lock_parent(db, project_id):
                        raise ValueError('母订单不存在')
                parent = get_annotation_project(db, project_id)
                if parent is None:
                    raise ValueError('母订单不存在')
                missing, summary = direction_state(db, parent)
                if summary['direction_count'] < 2:
                    continue
                entry.update(order_no=parent.order_no, project_status=parent.project_status,
                    directions=[item.display for item in parent.language_items],
                    existing_directions=[item.display for item in parent.language_items if item not in missing],
                    pending_directions=summary['missing_directions'],
                    extra_directions=summary['extra_directions'],
                    anomalies=[f'子订单 {number} 未绑定唯一方向，请人工处理' for number in summary['invalid_child_order_nos']])
                if apply:
                    created = ensure_direction_children(db, parent, operation_source='historical_direction_backfill')
                    entry['created_order_nos'] = [child.order_no for child in created]
                    db.commit()
                else:
                    db.rollback()
                entry['status'] = 'success'
            except Exception as exc:
                db.rollback()
                entry.update(status='failed', error=str(exc)[:2000])
        results.append(entry)
        if on_result:
            on_result(results)
    return results


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='显式应用；默认仅预览')
    parser.add_argument('--expected-host', help='应用前必须匹配的主机名')
    parser.add_argument('--expected-commit', help='应用前必须匹配的完整 Git 提交')
    parser.add_argument('--report', type=Path, default=ROOT / '.tmp' / f'annotation-direction-backfill-{datetime.now():%Y%m%d-%H%M%S}.json')
    args = parser.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if args.apply and (not args.expected_host or not args.expected_commit
            or socket.gethostname().casefold() != args.expected_host.casefold()
            or commit != args.expected_commit):
        parser.error('应用必须提供匹配的 --expected-host 和 --expected-commit')
    import main  # noqa: F401 注册已有 ORM 关系，不启动服务
    from database import SessionLocal
    args.report.parent.mkdir(parents=True, exist_ok=True)
    def write_report(rows):
        args.report.write_text(json.dumps({'host': socket.gethostname(), 'project_directory': str(ROOT),
            'commit': commit, 'apply': args.apply, 'results': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    write_report([])
    rows = backfill(SessionLocal, apply=args.apply, on_result=write_report)
    failures = sum(row['status'] == 'failed' for row in rows)
    print(f'已{"应用" if args.apply else "预览"} {len(rows)} 个多方向母订单，失败 {failures} 个；报告：{args.report}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(run())
