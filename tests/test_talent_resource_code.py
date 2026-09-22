"""在指定 PostgreSQL 的临时 schema 中验证编号迁移，不接触业务表。"""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import FetchedValue, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


@pytest.fixture
def numbering_db():
    url = os.getenv("TALENT_NUMBERING_TEST_DATABASE_URL")
    if not url:
        pytest.skip("需要显式指定 PostgreSQL 编号测试数据库")
    engine = create_engine(url)
    schema = "test_talent_code_" + uuid4().hex
    migration = (Path(__file__).resolve().parents[1] / "data/migrations/20261011_auto_talent_resource_code.sql").read_text(encoding="utf-8")
    migration = migration.strip().removeprefix("BEGIN;").removesuffix("COMMIT;")
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        conn.execute(text("CREATE TABLE resource_person (id integer PRIMARY KEY, resource_code varchar(50) UNIQUE)"))
        conn.execute(text("CREATE TABLE translator (id integer PRIMARY KEY, resource_person_id integer, translator_code varchar(50) UNIQUE)"))
    try:
        yield engine, schema, migration
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_numbering_backfill_preservation_import_and_concurrency(numbering_db):
    engine, schema, migration = numbering_db
    with engine.begin() as conn:
        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        conn.execute(text("INSERT INTO resource_person VALUES (1, 'MANUAL-01'), (2, NULL), (3, '   '), (4, 'RC000001')"))
        conn.execute(text("INSERT INTO translator VALUES (1, 2, NULL), (2, NULL, 'RC000002')"))
        conn.execute(text(migration))
        before = dict(conn.execute(text("SELECT id, resource_code FROM resource_person")).all())
        assert before[1] == "MANUAL-01"
        assert before[4] == "RC000001"
        assert len(set(before.values())) == 4
        assert before[2] not in (None, "", "RC000002")
        assert before[3].startswith("RC")
        assert conn.scalar(text("SELECT translator_code FROM translator WHERE id=1")) == before[2]
        conn.execute(text(migration))
        assert dict(conn.execute(text("SELECT id, resource_code FROM resource_person")).all()) == before
        conn.execute(text("UPDATE resource_person SET resource_code=NULL WHERE id=1"))
        assert conn.scalar(text("SELECT resource_code FROM resource_person WHERE id=1")) == "MANUAL-01"
        conn.execute(text("INSERT INTO resource_person VALUES (5, ''), (6, NULL)"))
        assert conn.scalar(text("SELECT count(*) FROM resource_person WHERE nullif(btrim(resource_code), '') IS NULL")) == 0

    class Base(DeclarativeBase):
        pass

    class Person(Base):
        __tablename__ = "resource_person"
        __table_args__ = {"schema": schema}
        id: Mapped[int] = mapped_column(primary_key=True)
        resource_code: Mapped[str] = mapped_column(String(50), server_default=FetchedValue())

    # 与问卷导入相同：显式传入 None，flush 后立即能读到数据库生成的编号。
    with Session(engine) as session:
        session.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        person = Person(id=7, resource_code=None)
        session.add(person)
        session.flush()
        assert person.resource_code.startswith("RC")
        session.commit()

    def insert_person(identifier):
        with engine.begin() as conn:
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            return conn.scalar(text("INSERT INTO resource_person(id) VALUES (:id) RETURNING resource_code"), {"id": identifier})

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(insert_person, range(100, 132)))
    assert len(set(codes)) == 32
    assert all(code.startswith("RC") for code in codes)

    # 超过六位后不可被 lpad 截断。
    with engine.begin() as conn:
        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        conn.execute(text("SELECT setval('resource_person_code_seq', 999999)"))
        assert conn.scalar(text("INSERT INTO resource_person(id) VALUES (200) RETURNING resource_code")) == "RC1000000"
