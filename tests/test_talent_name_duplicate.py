"""在临时 PostgreSQL schema 验证同名标记，不修改业务人才。"""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text


def test_name_duplicate_backfill_changes_and_concurrency():
    url = os.getenv("TALENT_NUMBERING_TEST_DATABASE_URL")
    if not url:
        pytest.skip("需要显式指定 PostgreSQL 测试数据库")
    engine = create_engine(url)
    schema = "test_talent_name_" + uuid4().hex
    sql = (Path(__file__).resolve().parents[1] / "data/migrations/20261012_talent_name_duplicate.sql").read_text(encoding="utf-8")
    sql = sql.strip().removeprefix("BEGIN;").removesuffix("COMMIT;")
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            conn.execute(text("CREATE TABLE resource_person (id integer PRIMARY KEY, full_name text NOT NULL, note text)"))
            conn.execute(text("INSERT INTO resource_person VALUES (1, '张三', NULL), (2, ' 张三 ', NULL), (3, '李四', NULL), (4, '', NULL), (5, ' ', NULL)"))
            conn.execute(text(sql))
            conn.execute(text(sql))
            flags = dict(conn.execute(text("SELECT id, name_duplicate FROM resource_person")).all())
            assert flags == {1: True, 2: True, 3: False, 4: False, 5: False}
            # 筛选后只返回一条，仍保留全库同名标记。
            assert conn.scalar(text("SELECT name_duplicate FROM resource_person WHERE id=1 LIMIT 1"))
            conn.execute(text("UPDATE resource_person SET full_name='李四' WHERE id=2"))
            assert dict(conn.execute(text("SELECT id, name_duplicate FROM resource_person WHERE id<=3")).all()) == {1: False, 2: True, 3: True}
            conn.execute(text("DELETE FROM resource_person WHERE id=2"))
            assert not conn.scalar(text("SELECT name_duplicate FROM resource_person WHERE id=3"))
            # 普通字段编辑不应触发同名计算。
            conn.execute(text("CREATE OR REPLACE FUNCTION refresh_resource_person_name_duplicates() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'unexpected recomputation'; END; $$ LANGUAGE plpgsql"))
            conn.execute(text("UPDATE resource_person SET note='备注' WHERE id=1"))
            conn.execute(text(sql))

        def insert_person(identifier):
            with engine.begin() as conn:
                conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                conn.execute(text("INSERT INTO resource_person(id, full_name) VALUES (:id, '并发同名')"), {"id": identifier})

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(insert_person, range(10, 18)))
        with engine.begin() as conn:
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            assert conn.scalar(text("SELECT count(*) FROM resource_person WHERE name_duplicate AND full_name='并发同名'")) == 8
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()
