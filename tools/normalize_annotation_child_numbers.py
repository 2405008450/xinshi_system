"""将标注子订单编号改为母订单号.序号；默认只读预览，保留旧号占用与审计。"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-host')
    parser.add_argument('--expected-commit')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if args.apply and (args.expected_host != socket.gethostname() or args.expected_commit != commit):
        parser.error('应用必须提供匹配的主机名和完整提交')
    import main  # noqa: F401 注册 ORM 关系，不启动应用
    from database import SessionLocal
    from annotation_models import AnnotationProject
    from annotation_service import _lock_annotation_order_numbers, _lock_parent, reserve_annotation_order_no
    from project_order_no_models import ProjectOrderNoReservation
    from project_audit_service import record_project_operation
    from sqlalchemy import func
    with SessionLocal() as db:
        if args.apply:
            _lock_annotation_order_numbers(db)
        children = db.query(AnnotationProject).filter(
            AnnotationProject.parent_project_id.is_not(None)
        ).order_by(AnnotationProject.parent_project_id, AnnotationProject.child_sequence_no).all()
        parent_ids = sorted({child.parent_project_id for child in children}, key=str)
        parents = {pid: (_lock_parent(db, pid) if args.apply else db.get(AnnotationProject, pid)) for pid in parent_ids}
        changes = []
        for child in children:
            parent = parents[child.parent_project_id]
            if parent is None or not child.child_sequence_no or child.child_sequence_no < 1:
                raise ValueError(f'子订单 {child.order_no} 的母订单或序号异常')
            target = f'{parent.order_no}.{child.child_sequence_no:03d}'
            if child.order_no == target:
                continue
            if child.order_no != f'{parent.order_no}-S{child.child_sequence_no:03d}' or len(target) > 50:
                raise ValueError(f'子订单 {child.order_no} 不是预期的历史格式，请人工处理')
            occupied = db.query(AnnotationProject.id).filter(func.upper(AnnotationProject.order_no) == target.upper()).first()
            reserved = db.query(ProjectOrderNoReservation).filter_by(project_type='annotation', order_no_key=target.upper()).first()
            if occupied or (reserved and reserved.project_id != child.id):
                raise ValueError(f'目标编号 {target} 已被占用，整批不执行')
            changes.append({'id': str(child.id), 'old': child.order_no, 'new': target})
        if len({row['new'].upper() for row in changes}) != len(changes):
            raise ValueError('目标编号重复，整批不执行')
        report = {'host': socket.gethostname(), 'commit': commit, 'apply': args.apply, 'changes': changes}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({**report, 'committed': False}, ensure_ascii=False, indent=2), encoding='utf-8')
        if args.apply:
            by_id = {str(child.id): child for child in children}
            for row in changes:
                child = by_id[row['id']]
                # 保留旧号占用，新格式单独预留；既有外部引用和审计保持可追溯。
                for number in (row['old'], row['new']):
                    if not db.query(ProjectOrderNoReservation.id).filter_by(project_type='annotation', order_no_key=number.upper()).first():
                        reserve_annotation_order_no(db, project_id=child.id, order_no=number,
                            assignment_source='child_number_format', assigned_by=None)
                child.order_no = row['new']
                record_project_operation(db, project_type='annotation', operation_type='order_no_change',
                    project=child, actor_user_id=None, operation_source='child_number_format',
                    previous_order_no=row['old'], change_reason='统一为母订单号.三位子订单序号')
            db.commit()
        else:
            db.rollback()
        args.report.write_text(json.dumps({**report, 'committed': args.apply}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'apply': args.apply, 'changed': len(changes), 'report': str(args.report)}))
    return 0


if __name__ == '__main__':
    sys.exit(run())
