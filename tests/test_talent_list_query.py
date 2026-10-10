"""人才列表查询回归：隔离数据验证分页与关联筛选，禁止整行 JSON 去重。"""

import json
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import Column, JSON, MetaData, Table, create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

# 注册完整 ORM 关系，不运行应用生命周期、迁移或业务库查询。
import main  # noqa: F401
from resource_models import ResourceCapability, ResourceCareerProfile, ResourcePerson
import resource_service


@pytest.fixture
def talent_db(monkeypatch):
    engine = create_engine("sqlite://", json_serializer=lambda value: json.dumps(value, ensure_ascii=False))
    metadata = MetaData()
    # 只在隔离内存库创建当前查询涉及的三张表，不连接业务库。
    tables = {}
    for model in (ResourcePerson, ResourceCapability, ResourceCareerProfile):
        tables[model] = Table(model.__tablename__, metadata, *[
            Column(column.name, JSON if isinstance(column.type, JSONB) else column.type,
                   primary_key=column.primary_key, nullable=True)
            for column in model.__table__.columns
        ])
    metadata.create_all(engine)
    monkeypatch.setattr(resource_service, "_person_options", lambda: ())
    ids = [uuid4() for _ in range(3)]
    with engine.begin() as connection:
        for index, person_id in enumerate(ids):
            connection.execute(tables[ResourcePerson].insert().values(
                id=person_id, full_name=f"测试人才{index}", status="active",
                updated_at=datetime(2026, 10, 9, 10, index),
                overall_score=index + 1,
                wechat_accounts=[{"account": f"微信{index}"}],
                wechat_contact_state={"状态": "已联系"},
            ))
        for index, capability, status in (
            (0, "annotation", "active"), (0, "interpretation", "active"),
            (1, "annotation", "inactive"), (1, "interpretation", "active"),
            (2, "annotation", "active"),
        ):
            connection.execute(tables[ResourceCapability].insert().values(
                id=uuid4(), person_id=ids[index], capability_type=capability, status=status,
            ))
        for index, industries in enumerate((["教育"], ["教育", "科技"], ["科技"])):
            connection.execute(tables[ResourceCareerProfile].insert().values(
                person_id=ids[index], industries=industries, years_experience=index + 1,
            ))
    try:
        with Session(engine) as session:
            yield session, ids
    finally:
        engine.dispose()


def test_json_fields_and_page_totals_survive_pagination(talent_db):
    db, ids = talent_db
    first = resource_service.get_talents(db, limit=2)
    second = resource_service.get_talents(db, skip=2, limit=2)
    assert [person.id for person in first + second] == list(reversed(ids))
    assert all(person._page_total == 3 for person in first + second)
    assert first[0].wechat_accounts == [{"account": "微信2"}]
    assert first[0].wechat_contact_state == {"状态": "已联系"}
    assert resource_service.count_talents(db) == 3
    assert resource_service.get_talents(db, skip=3, limit=2) == []


def test_capability_type_and_status_match_the_same_record(talent_db):
    db, ids = talent_db
    filters = {"capability_type": "annotation"}
    people = resource_service.get_talents(db, **filters)
    assert [person.id for person in people] == [ids[2], ids[0]]
    assert all(person._page_total == 2 for person in people)
    assert resource_service.count_talents(db, **filters) == 2
    inactive = resource_service.get_talents(db, capability_status="inactive", **filters)
    assert [person.id for person in inactive] == [ids[1]]


def test_combined_industry_and_capability_filters_share_page_count(talent_db):
    db, ids = talent_db
    filters = {"industry_keyword": " 教育 ", "capability_type": "interpretation"}
    first = resource_service.get_talents(db, limit=1, **filters)
    second = resource_service.get_talents(db, skip=1, limit=1, **filters)
    assert [person.id for person in first + second] == [ids[1], ids[0]]
    assert all(person._page_total == 2 for person in first + second)
    assert resource_service.count_talents(db, **filters) == 2
    sorted_people = resource_service.get_talents(db, sort="overall_score_asc", **filters)
    assert [person.id for person in sorted_people] == [ids[0], ids[1]]


@pytest.mark.parametrize("filters", [
    {}, {"capability_type": "annotation"},
    {"industry_keyword": "教育", "capability_type": "interpretation"},
])
def test_postgres_query_does_not_compare_json_rows(filters):
    with Session() as db:
        statement = resource_service._talent_query(db, **filters).statement
        sql = str(statement.compile(dialect=postgresql.dialect())).upper()
    assert "RESOURCE_PERSON.WECHAT_ACCOUNTS" in sql
    assert "DISTINCT" not in sql
    assert " JOIN " not in sql
    if filters:
        assert "EXISTS" in sql
