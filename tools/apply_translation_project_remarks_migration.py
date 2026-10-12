"""备份笔译项目表后，显式执行单项备注字段迁移。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
TARGET = "43.132.156.72:15432/xinshi_system"


def run():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-target", required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    if socket.gethostname().upper() != "PC" or Path.cwd().resolve() != ROOT or str(ROOT).lower() != r"e:\xinshi_system":
        raise SystemExit("仅允许在 PC 的 E:\\xinshi_system 执行")
    if Path(sys.executable).resolve() != ROOT / ".venv/Scripts/python.exe":
        raise SystemExit("必须使用项目虚拟环境")
    sys.path.insert(0, str(ROOT))
    from database import engine
    from business_time import business_iso, business_now
    from sqlalchemy import text

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    url = engine.url
    if args.confirm_target != TARGET or (url.host, url.port, url.database) != ("43.132.156.72", 15432, "xinshi_system") or args.expected_commit != commit:
        raise SystemExit("主机、提交或数据库确认信息不匹配，未执行迁移")
    stamp = business_now().strftime("%Y%m%d-%H%M%S+0800")
    directory = Path(r"E:\xinshi_runtime\backups") / ("translation-remarks-" + stamp + "-" + uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=False)
    identity = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True)
    sid = next(csv.reader(identity.splitlines()))[1]
    subprocess.run(["icacls", str(directory), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"], check=True, capture_output=True)
    backup = directory / "translation_project_before.json"
    sql = (ROOT / "data/migrations/20261012_add_translation_project_remarks.sql").read_text(encoding="utf-8")
    snapshot_sql = text("""SELECT count(*) AS rows,
        md5(coalesce(string_agg((to_jsonb(t) - 'remarks')::text, '' ORDER BY id), '')) AS checksum
        FROM public.translation_project t""")
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(text("SET LOCAL statement_timeout = '30s'"))
        connection.execute(text("LOCK TABLE public.translation_project IN ACCESS EXCLUSIVE MODE"))
        before = dict(connection.execute(snapshot_sql).mappings().one())
        # 与项目现有增量迁移一致，结构化备份不依赖 pg_dump 客户端版本。
        rows = connection.execute(text("SELECT row_to_json(t) FROM public.translation_project t ORDER BY id")).scalars().all()
        columns = connection.execute(text("SELECT column_name,data_type,udt_name,character_maximum_length,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name='translation_project' ORDER BY ordinal_position")).mappings().all()
        constraints = connection.execute(text("SELECT conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid='public.translation_project'::regclass ORDER BY conname")).mappings().all()
        indexes = connection.execute(text("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='translation_project' ORDER BY indexname")).mappings().all()
        comments = connection.execute(text("SELECT attname,col_description(attrelid,attnum) AS comment FROM pg_attribute WHERE attrelid='public.translation_project'::regclass AND attnum>0 AND NOT attisdropped ORDER BY attnum")).mappings().all()
        payload = {"target": TARGET, "git_commit": commit, "created_at": business_iso(business_now()), "rows": rows, "columns": [dict(c) for c in columns], "constraints": [dict(c) for c in constraints], "indexes": [dict(i) for i in indexes], "comments": [dict(c) for c in comments], "snapshot": before, "migration_sha256": hashlib.sha256(sql.encode('utf-8')).hexdigest()}
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')
        backup.write_bytes(encoded)
        digest = hashlib.sha256(encoded).hexdigest()
        if hashlib.sha256(backup.read_bytes()).hexdigest() != digest or json.loads(backup.read_text(encoding='utf-8')) != payload or len(rows) != before['rows']:
            raise ValueError("备份校验失败，未执行迁移")
        (directory / "backup.sha256").write_text(digest + "\n", encoding="utf-8")
        previous = connection.execute(text("SELECT data_type, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='translation_project' AND column_name='remarks'")).mappings().first()
        if previous and dict(previous) != {"data_type": "text", "is_nullable": "YES"}:
            raise ValueError("已有 remarks 类型不匹配，事务回滚")
        connection.exec_driver_sql(sql)
        after = dict(connection.execute(snapshot_sql).mappings().one())
        if before != after:
            raise ValueError("原有项目数据变化，事务回滚")
        column = dict(connection.execute(text("SELECT data_type, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='translation_project' AND column_name='remarks'")).mappings().one())
        if column != {"data_type": "text", "is_nullable": "YES"}:
            raise ValueError("迁移结果不符，事务回滚")
        if not previous and connection.execute(text("SELECT count(*) FROM public.translation_project WHERE remarks IS NOT NULL")).scalar() != 0:
            raise ValueError("历史备注应为空，事务回滚")
    report = {"applied": True, "target": TARGET, "git_commit": commit, "backup": str(backup), "backup_sha256": digest, "existing_data_verified": before, "column": column, "completed_at": business_iso(business_now())}
    (directory / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    run()
