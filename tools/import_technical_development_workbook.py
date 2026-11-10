"""开发任务统计的一次性整理与导入；默认仅生成预览，明确 --apply 后入库。"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE = Path(r'E:\Documents\开发任务统计.xlsx')
ALIASES = {'裕林': '钟裕林', '运坚': '黄运坚', '晨旭': '习晨旭', '胜辉': '李胜辉'}


def clean(value):
    return str(value or '').replace('\u200b', '').replace('\ufeff', '').strip()


def prepare():
    import openpyxl
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    book = openpyxl.load_workbook(SOURCE, data_only=True)
    sheet = book['任务明细']
    assert [cell.value for cell in sheet[1]] == ['序号', '项目名称', '任务内容', '任务来源', '负责人', '开始时间', '完成时间', '当前状态', '补充说明', '父记录']
    groups = defaultdict(list)
    project = owner = ''
    excluded = []
    titles = []
    for number, cells in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
        raw = [str(v) if v is not None else '' for v in cells]
        values = [clean(v) for v in cells]
        if not any(values):
            continue
        if not any(values[:9]):
            excluded.append({'row': number, 'reason': '仅有父记录，没有业务字段', 'raw': raw})
            continue
        if values[1]:
            project = values[1]
        if values[4]:
            owner = ALIASES[values[4]]
        assert project and owner, f'第 {number} 行缺少项目或负责人'
        row = dict(row=number, project=project, owner=owner, content=values[2], source=values[3], start=values[5], finish=values[6], status=values[7], supplement=values[8], raw=raw, inherited_owner=not bool(values[4]))
        if not row['content']:
            titles.append(row)
            groups[(project, owner)]
        else:
            groups[(project, owner)].append(row)
    assert len({(r['project'], r['owner'], r['content']) for rows in groups.values() for r in rows}) == sum(map(len, groups.values()))
    batch = 'technical-workbook-' + digest[:16]
    tasks = []
    project_owners = defaultdict(set)
    for project, owner in groups:
        project_owners[project].add(owner)
    for (project, owner), rows in groups.items():
        assert rows
        parent = None
        if len(rows) > 1:
            key = f'group:{project}:{owner}'
            parent = str(uuid5(NAMESPACE_URL, batch + ':' + key))
            title_notes = '\n'.join(f'原项目标题行{r["row"]}：' + json.dumps(r['raw'], ensure_ascii=False) for r in titles if r['project'] == project and r['owner'] == owner)
            tasks.append(dict(id=parent, parent_id=None, name=project + (f'（{owner}）' if len(project_owners[project]) > 1 else ''), content='项目归类；具体工作与原始状态见下属任务。', owner=owner, source='', progress=0, group=True, rows=[r['row'] for r in rows], notes=f'来源：{SOURCE.name} / 任务明细\n按项目和负责人归类，不根据子任务推算总进度。\n{title_notes}\n导入批次：{batch}'))
        for row in rows:
            key = f'row:{row["row"]}'
            notes = [f'来源：{SOURCE.name} / 任务明细 / 第{row["row"]}行', f'原项目：{project}', f'原任务来源：{row["source"] or "未填写"}', f'原负责人：{row["raw"][4] or "留空，沿用本项目人员段"} → {owner}', f'原当前状态：{row["status"] or "未填写"}']
            if row['inherited_owner']:
                notes.append('负责人按当前项目人员段补齐；原单元格为空。')
            if row['start']:
                notes.append('原开始时间：' + row['start'])
            if row['finish']:
                notes.append('原完成时间：' + row['finish'] + '（原表字段，未作为预定截止时间或奖金评定依据）')
            if row['supplement']:
                notes.append('原补充说明：' + row['supplement'])
            if row['status'] not in ('已完成', '未开始'):
                notes.append('原表未给出可确定百分比，系统初始进度保留为0；不代表已核实为未开始。')
            notes.append('原始行：' + json.dumps(dict(zip([c.value for c in sheet[1]], row['raw'])), ensure_ascii=False))
            notes.append('导入批次：' + batch)
            tasks.append(dict(id=str(uuid5(NAMESPACE_URL, batch + ':' + key)), parent_id=parent, name=row['content'] if parent else project, content=row['content'], owner=owner, source=row['source'], progress=100 if row['status'] == '已完成' else 0, group=False, rows=[row['row']], notes='\n'.join(notes), original=row))
    return dict(batch=batch, source=str(SOURCE), source_sha256=digest, details=sum(map(len, groups.values())), group_count=sum(t['group'] for t in tasks), title_rows=titles, excluded=excluded, owner_counts=dict(Counter(r['owner'] for rows in groups.values() for r in rows)), status_counts=dict(Counter(r['status'] or '未填写' for rows in groups.values() for r in rows)), tasks=tasks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--arranger-policy', choices=['directory'])
    parser.add_argument('--arranger-map', type=Path, help='按原始来源及归类节点明确映射系统用户名；禁止默认归人')
    parser.add_argument('--actor', help='批处理登记账户，审计明确标记为历史表导入')
    parser.add_argument('--expected-commit')
    args = parser.parse_args()
    assert socket.gethostname().upper() == 'PC'
    report = prepare()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'preview.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('tasks', 'title_rows')}, ensure_ascii=False))
    if args.arranger_policy:
        assert args.actor, '必须明确导入操作账户，不能伪造历史操作者'
        assert args.arranger_map, '须先完成安排人对齐表'
        apply_report(report, args)
    else:
        assert not args.apply, '必须先确定安排人规则'


def apply_report(report, args):
    """复用人员校验、编号和层级逻辑；整批事务提交，失败全部回滚。"""
    import gzip
    from uuid import UUID
    import main as app_models  # noqa: F401 注册完整 ORM；不运行服务启动钩子
    from database import engine, SessionLocal
    from sqlalchemy import text
    from models import AppUser
    import technical_development as service
    import technical_task_management as management
    from chat_time import now

    assert Path(sys.executable).resolve() == (ROOT / r'.venv\Scripts\python.exe').resolve()
    assert ROOT == Path(r'E:\xinshi_system')
    assert (engine.url.host, engine.url.port, engine.url.database) == ('43.132.156.72', 15432, 'xinshi_system')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert args.expected_commit == commit, 'Git提交与核对值不一致'
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == report['source_sha256']
    with SessionLocal() as db:
        assert db.execute(text('select current_database()')).scalar_one() == 'xinshi_system'
        service.require_ready(db)
        management.require_ready(db)
        actor = db.query(AppUser).filter_by(username=args.actor, is_active=True, is_deleted=False).one()
        service.require_user(actor, db)
        users = {u.full_name: u for u in db.query(AppUser).filter_by(is_active=True, is_deleted=False)}
        by_username = {u.username: u for u in users.values()}
        arranger_map = json.loads(args.arranger_map.read_text(encoding='utf-8'))
        # 对齐表以任务ID为键，必须逐条覆盖；不存在无条件兜底安排人。
        assert all(t['id'] in arranger_map for t in report['tasks']), '安排人对齐表尚未覆盖全部任务'
        assert all(value is None or value in by_username for value in arranger_map.values()), '对齐表包含无效或停用人员'
        service.lock_tree(db)
        stamp = now()
        result = dict(batch=report['batch'], apply=args.apply, time=stamp.isoformat(), actor=actor.username, policy=args.arranger_policy, commit=commit, host=socket.gethostname(), target='43.132.156.72:15432/xinshi_system', created=[], existing=[])
        nullable_before = db.execute(text("select is_nullable from information_schema.columns where table_name='technical_development_task' and column_name='arranger_id'")).scalar_one()
        result['arranger_nullable_before'] = nullable_before
        if args.apply:
            # 写入前独立只读一致性快照，覆盖编号分配可能触及的全部表。
            backup_dir = args.output / ('backup-' + stamp.strftime('%Y%m%d-%H%M%S+0800'))
            backup_dir.mkdir(exist_ok=False)
            tables = ['technical_development_task', 'technical_development_progress', 'technical_development_task_number', 'technical_task_hierarchy_number', 'business_number_lease']
            manifest = dict(time=stamp.isoformat(), batch=report['batch'], arranger_nullable_before=nullable_before, tables={})
            raw = engine.raw_connection()
            try:
                cursor = raw.cursor()
                cursor.execute('BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                for table in tables:
                    target = backup_dir / (table + '.csv.gz')
                    with gzip.open(target, 'wt', encoding='utf-8', newline='') as stream:
                        cursor.copy_expert(f'COPY {table} TO STDOUT WITH (FORMAT CSV, HEADER TRUE)', stream)
                    manifest['tables'][table] = hashlib.sha256(target.read_bytes()).hexdigest()
                raw.rollback()
            finally:
                raw.close()
            (backup_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            result['backup'] = str(backup_dir)
            if nullable_before == 'NO':
                db.execute(text("SET LOCAL lock_timeout='5s'"))
                db.execute(text((ROOT / 'data/migrations/20261110_technical_development_optional_arranger.sql').read_text(encoding='utf-8')))
                result['schema_change'] = 'technical_development_task.arranger_id允许NULL；按用户明确要求安排人留空'
        for task in report['tasks']:
            task_id = UUID(task['id'])
            owner = users[task['owner']]
            arranger = by_username.get(arranger_map[task['id']])
            payload = service.TaskCreate(name=task['name'], content=task['content'], parent_id=UUID(task['parent_id']) if task['parent_id'] else None, executor_id=owner.id, arranger_id=arranger.id if arranger else None, notes=task['notes'] + f'\n安排人整理规则：按人员管理名册对齐；泉哥=ethan；周会/开会/空白来源留空。\n历史表批处理登记账户：{actor.username}（非原任务操作人或实际完成时间）')
            service.validate_people(db, payload)
            existing = db.get(service.DevelopmentTask, task_id)
            if existing:
                assert report['batch'] in existing.notes, '固定ID与其他任务冲突'
                result['existing'].append(str(task_id))
                continue
            # 同名称、同正文和同执行人的记录不自动合并，先阻止重复入库。
            duplicate = db.query(service.DevelopmentTask).filter_by(name=payload.name, content=payload.content, executor_id=owner.id).first()
            assert duplicate is None, f'已有同名同内容任务，请核实：{payload.name}'
            if not args.apply:
                result['created'].append(dict(id=str(task_id), name=payload.name, arranger=arranger.username if arranger else None, preview=True))
                continue
            service.validate_parent(management.active_tasks(db), task_id, payload.parent_id)
            row = service.DevelopmentTask(id=task_id, **payload.model_dump(exclude={'allocations'}), progress=task['progress'], progress_updated_at=stamp if task['progress'] else None, created_by=actor.id, updated_by=actor.id, created_at=stamp, updated_at=stamp)
            db.add(row)
            db.flush()
            number = service.allocate_number(db, task_id, stamp)
            if task['progress']:
                db.add(service.DevelopmentProgress(task_id=task_id, percentage=100, previous_percentage=0, content=f'历史表导入：原状态为已完成；来源第{task["rows"][0]}行。本记录时间为导入时间，不是原完成时间。', reason='导入历史状态', author_id=actor.id, author_name=f'历史表导入（{actor.full_name or actor.username}）', created_at=stamp))
            db.flush()
            result['created'].append(dict(id=str(task_id), number=number, name=row.name))
        assert len(result['created']) + len(result['existing']) == len(report['tasks'])
        if args.apply:
            db.commit()
        else:
            db.rollback()
        target = args.output / ('import-result.json' if args.apply else 'dry-run.json')
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(dict(apply=args.apply, created=len(result['created']), existing=len(result['existing']), report=str(target)), ensure_ascii=False))


if __name__ == '__main__':
    main()
