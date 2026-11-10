"""按用户指令将现有空安排人补为执行人；备份、加锁并逐条核对。"""
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
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert socket.gethostname().upper() == 'PC' and Path.cwd().resolve() == ROOT == Path(r'E:\xinshi_system')
    assert Path(sys.executable).resolve() == ROOT / '.venv/Scripts/python.exe'
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert commit == args.expected_commit
    from database import engine
    from sqlalchemy import text
    from chat_time import now
    assert (engine.url.host, engine.url.port, engine.url.database) == ('43.132.156.72', 15432, 'xinshi_system')
    instant = now()
    report = dict(time=instant.isoformat(), host=socket.gethostname(), commit=commit, target='43.132.156.72:15432/xinshi_system', apply=args.apply, rule='安排人为空时改为执行人本人')
    with engine.begin() as connection:
        assert connection.execute(text('select current_database()')).scalar_one() == 'xinshi_system'
        connection.execute(text('SELECT pg_advisory_xact_lock(74260301)'))
        before = [dict(row) for row in connection.execute(text('''
            SELECT t.*, u.full_name AS executor_name, u.username AS executor_username
            FROM technical_development_task t JOIN app_user u ON u.id=t.executor_id
            WHERE t.arranger_id IS NULL
              AND NOT EXISTS (SELECT 1 FROM technical_task_deletion d WHERE d.task_id=t.id)
            ORDER BY t.created_at,t.id FOR UPDATE OF t
        ''')).mappings()]
        report['count'] = len(before)
        report['changes'] = [dict(id=str(r['id']), name=r['name'], arranger_before=None, arranger_after=str(r['executor_id']), arranger_name=r['executor_name']) for r in before]
        if args.apply:
            args.output.mkdir(parents=True, exist_ok=True)
            backup = args.output / ('arrangers-before-' + instant.strftime('%Y%m%d-%H%M%S+0800') + '.json')
            with backup.open('x', encoding='utf-8') as stream:
                json.dump(dict(**report, rows=before), stream, ensure_ascii=False, default=str, indent=2)
            report['backup'] = str(backup)
            actor = connection.execute(text("SELECT id FROM app_user WHERE username='williamzhao' AND is_active AND NOT is_deleted")).scalar_one()
            for row in before:
                result = connection.execute(text('''
                    UPDATE technical_development_task
                    SET arranger_id=executor_id, revision=revision+1,
                        updated_by=:actor, updated_at=:instant,
                        notes=COALESCE(notes,'') || :note
                    WHERE id=:id AND arranger_id IS NULL AND revision=:revision
                '''), dict(actor=actor, instant=instant, id=row['id'], revision=row['revision'], note='\n' + instant.isoformat() + ' 用户确认：原安排人为空，统一改为执行人本人；由历史导入批处理账户登记。'))
                assert result.rowcount == 1
            for row in before:
                after = connection.execute(text('SELECT arranger_id,executor_id,revision,progress,parent_id FROM technical_development_task WHERE id=:id'), dict(id=row['id'])).mappings().one()
                assert after['arranger_id'] == after['executor_id'] == row['executor_id']
                assert after['revision'] == row['revision'] + 1
                assert after['progress'] == row['progress'] and after['parent_id'] == row['parent_id']
        print(json.dumps({k:v for k,v in report.items() if k != 'changes'}, ensure_ascii=False, default=str))
    if args.apply:
        (args.output / 'arrangers-filled.json').write_text(json.dumps(report, ensure_ascii=False, default=str, indent=2), encoding='utf-8')


if __name__ == '__main__':
    run()
