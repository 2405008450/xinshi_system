"""组合字段筛选必须命中同一条明细，且不修改业务数据库。"""
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from resource_models import ResourcePerson
from resource_service import _apply_talent_detail_filters
from routers.talents import _field_filters


@pytest.fixture
def detail_db():
    engine = create_engine("sqlite://")
    # 只创建筛选所需列，隔离 PostgreSQL 专有类型及业务库数据。
    with engine.begin() as connection:
        for ddl in (
            "CREATE TABLE resource_person (id CHAR(32) PRIMARY KEY)",
            "CREATE TABLE resource_education_experience (id CHAR(32), person_id CHAR(32), institution TEXT, major TEXT, graduation_year INTEGER, education_level TEXT, institution_category TEXT, major_category TEXT, minor_major TEXT, degree_name TEXT)",
            "CREATE TABLE interpretation_language (id CHAR(32), label TEXT)",
            "CREATE TABLE resource_language_skill (id CHAR(32), person_id CHAR(32), language_id CHAR(32), role TEXT, proficiency TEXT)",
            "CREATE TABLE resource_certificate (id CHAR(32), person_id CHAR(32), language_id CHAR(32), certificate_type TEXT, name TEXT, issuer TEXT, material_received BOOLEAN)",
        ):
            connection.execute(text(ddl))
        for number in (1, 2, 3):
            connection.execute(text("INSERT INTO resource_person VALUES (:id)"), {"id": f"{number:032x}"})
    with Session(engine) as session:
        yield session
    engine.dispose()


def matches(session, filters):
    parsed = _field_filters(json.dumps(filters))
    query = _apply_talent_detail_filters(select(ResourcePerson.id), parsed)
    return {value.int for value in session.scalars(query)}


def test_education_conditions_cannot_match_different_experiences(detail_db):
    for person, school, major, year in ((1, "甲校", "英语", 2020), (1, "乙校", "计算机", 2024), (2, "甲校", "计算机", 2024)):
        detail_db.execute(text("INSERT INTO resource_education_experience (person_id, institution, major, graduation_year, education_level) VALUES (:person, :school, :major, :year, 'bachelor')"),
                          dict(person=f"{person:032x}", school=school, major=major, year=year))
    filters = {"education_institution": {"op": "contains", "value": "甲校"}, "education_major": {"op": "contains", "value": "计算机"}, "education_level": {"op": "in", "value": ["bachelor", "master"]}, "education_graduation_year": {"op": "between", "min": 2023, "max": 2025}}
    assert matches(detail_db, filters) == {2}
    del filters["education_institution"]
    assert matches(detail_db, filters) == {1, 2}
    assert matches(detail_db, {}) == {1, 2, 3}


def test_certificate_name_and_received_match_same_certificate(detail_db):
    for person, name, received in ((1, "证书A", True), (1, "证书B", False), (2, "证书A", False)):
        detail_db.execute(text("INSERT INTO resource_certificate (person_id, name, material_received, certificate_type, issuer) VALUES (:person, :name, :received, 'language', '考试中心')"),
                          dict(person=f"{person:032x}", name=name, received=received))
    filters = {"certificate_name": {"op": "contains", "value": "证书A"}, "certificate_received": {"op": "eq", "value": False}, "certificate_type": {"op": "in", "value": ["language"]}, "certificate_issuer": {"op": "contains", "value": "中心"}}
    assert matches(detail_db, filters) == {2}
    assert matches(detail_db, {"certificate_received": {"op": "eq", "value": False}}) == {1, 2}
    assert matches(detail_db, {"certificate_received": {"op": "eq", "value": "false"}}) == {1, 2}


def test_language_role_and_proficiency_match_same_language(detail_db):
    for number, label in ((1, "英语"), (2, "日语")):
        detail_db.execute(text("INSERT INTO interpretation_language VALUES (:id, :label)"), dict(id=f"{number:032x}", label=label))
    for person, language, role, proficiency in ((1, 1, "foreign", "basic"), (1, 2, "native", "very_familiar"), (2, 1, "native", "very_familiar")):
        detail_db.execute(text("INSERT INTO resource_language_skill (person_id, language_id, role, proficiency) VALUES (:person, :language, :role, :proficiency)"),
                          dict(person=f"{person:032x}", language=f"{language:032x}", role=role, proficiency=proficiency))
    filters = {"language_skills": {"op": "contains", "value": "英语"}, "language_role": {"op": "in", "value": ["native"]}, "language_proficiency": {"op": "in", "value": ["very_familiar"]}}
    assert matches(detail_db, filters) == {2}
    detail_db.execute(text("INSERT INTO resource_certificate (person_id, name, language_id) VALUES (:person, '证书', :language)"), dict(person=f"{2:032x}", language=f"{2:032x}"))
    filters["certificate_language"] = {"op": "contains", "value": "日语"}
    assert matches(detail_db, filters) == {2}
    filters["certificate_language"]["value"] = "英语"
    assert matches(detail_db, filters) == set()


@pytest.mark.parametrize("field, descriptor", [
    ("education_level", {"op": "contains", "value": "本科"}),
    ("education_graduation_year", {"op": "eq", "value": 2024}),
    ("language_role", {"op": "eq", "value": "native"}),
    ("certificate_name", {"op": "in", "value": ["证书A"]}),
])
def test_grouped_filters_reject_wrong_operators(field, descriptor):
    with pytest.raises(HTTPException) as error:
        _field_filters(json.dumps({field: descriptor}))
    assert error.value.status_code == 422
