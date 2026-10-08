"""局域网账号迁移：默认只读预览；结构迁移、历史账号追加需显式选择。"""
import argparse
import json
import socket
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-schema', action='store_true')
    parser.add_argument('--backfill', action='store_true')
    parser.add_argument('--actor-id')
    parser.add_argument('--output', default='.tmp/talent-wechat-accounts-preview.json')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5' or str(root).lower() != r'e:\xinshi_system':
        raise SystemExit('只能在局域网调试机 E:\\xinshi_system 执行')
    sys.path.insert(0, str(root))
    from database import engine
    from sqlalchemy import inspect, text
    if args.apply_schema:
        sql = (root / 'data/migrations/20261008_talent_wechat_accounts.sql').read_text(encoding='utf-8')
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.exec_driver_sql(sql)
        print('账号结构迁移完成（可重复执行）')
        return
    person_columns = {c['name'] for c in inspect(engine).get_columns('resource_person')}
    record_columns = {c['name'] for c in inspect(engine).get_columns('resource_development_record')}
    from talent_wechat_accounts import normalize_accounts
    with engine.connect() as connection:
        people = connection.execute(text('SELECT id, resource_code, wechat_account' +
            (', wechat_accounts' if 'wechat_accounts' in person_columns else '') + ' FROM resource_person')).mappings().all()
        rows = connection.execute(text('SELECT r.person_id, r.id, o.name AS account_name' +
            (', r.friend_accounts' if 'friend_accounts' in record_columns else '') +
            ' FROM resource_development_record r LEFT JOIN resource_development_option o ON o.id = r.account_id WHERE r.person_id IS NOT NULL')).mappings().all()
    additions, sources = {}, {}
    for row in rows:
        additions.setdefault(row['person_id'], []).extend(normalize_accounts(row['account_name']) + normalize_accounts(row.get('friend_accounts')))
        sources.setdefault(row['person_id'], []).append(str(row['id']))
    preview = []
    for person in people:
        old = normalize_accounts(person.get('wechat_accounts') or person['wechat_account'])
        # 历史字段中的删除标记不参与本次账号补齐，不推断联系状态。
        added = [v for v in additions.get(person['id'], []) if v not in {'已删微信', '已删企微'}]
        merged = normalize_accounts([*old, *added])
        if merged != old:
            preview.append(dict(person_id=str(person['id']), resource_code=person['resource_code'],
                before=old, after=merged, record_ids=sources[person['id']]))
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'历史账号合并预览：{len(preview)} 人；已保存 {output}')
    if not args.backfill:
        return
    if not args.actor_id:
        raise SystemExit('回填需要 --actor-id 指定实际操作人')
    import main  # noqa: F401
    from uuid import UUID
    from sqlalchemy.orm import Session
    from models import AppUser
    from resource_models import ResourcePerson
    from talent_wechat_accounts import lock_account_writes, store_accounts, person_accounts
    with Session(engine) as db, db.begin():
        lock_account_writes(db)
        actor = db.get(AppUser, UUID(args.actor_id))
        if not actor or not actor.is_active:
            raise SystemExit('操作人不存在或已停用')
        for entry in preview:
            person = db.get(ResourcePerson, UUID(entry['person_id']))
            if person_accounts(person) != entry['before']:
                raise SystemExit('预览后账号已变化，回填已回滚，请重新生成预览')
            store_accounts(db, person, entry['after'], actor=actor, source='migration', source_record_ids=entry['record_ids'])
    print(f'历史账号追加完成：{len(preview)} 人；未修改联系状态')


if __name__ == '__main__':
    main()
