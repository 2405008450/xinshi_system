import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from resource_schemas import ResourcePersonCreate, ResourcePersonUpdate, ResourcePersonDetailResponse
from resource_service import TALENT_MANAGED_FIELDS
from tools.apply_talent_performance_domains_migration import apply_migration


@pytest.mark.parametrize('schema', [ResourcePersonCreate, ResourcePersonUpdate])
@pytest.mark.parametrize('rating,score', [(1, 1), (4, 8), (6, 10), (None, None)])
def test_domain_ratings_accept_valid_values_and_keep_annotation_fields(schema, rating, score):
    value = schema(full_name='分区评价', overall_score=9, overall_rating='原标注评价',
                   interpretation_rating=rating, interpretation_rating_note='  口译说明  ', interpretation_domains='  医学、商务  ',
                   written_translation_score=score, written_translation_evaluation='  笔译评价  ')
    assert value.overall_score == 9 and value.overall_rating == '原标注评价'
    assert value.interpretation_rating == rating
    assert value.written_translation_score == score
    assert value.interpretation_rating_note == '口译说明'
    assert value.interpretation_domains == '医学、商务'
    assert value.written_translation_evaluation == '笔译评价'


@pytest.mark.parametrize('field,value', [('interpretation_rating', 0), ('interpretation_rating', 7),
                                       ('interpretation_rating', 4.5), ('written_translation_score', 0),
                                       ('written_translation_score', 11), ('written_translation_score', 5.5)])
def test_domain_ratings_reject_invalid_values(field, value):
    with pytest.raises(ValidationError):
        ResourcePersonCreate(full_name='无效评价', **{field: value})


def test_domain_fields_are_returned_and_protected_from_recruitment_edits():
    for name in ['interpretation_rating', 'interpretation_rating_note', 'interpretation_domains', 'written_translation_score', 'written_translation_evaluation']:
        assert name in ResourcePersonDetailResponse.model_fields
        assert name in TALENT_MANAGED_FIELDS


def test_domain_filters_accept_ranges_and_new_select_fields():
    import json
    from routers.talents import _field_filters
    filters = {
        'interpretation_rating': {'op': 'between', 'min': 4, 'max': 6},
        'written_translation_score': {'op': 'between', 'min': 8, 'max': 10},
        'gender': {'op': 'in', 'value': ['未知', '不便透露']},
        'residence_timezone': {'op': 'in', 'value': ['UTC+8']},
        'contact_availability': {'op': 'in', 'value': ['evening']},
    }
    assert _field_filters(json.dumps(filters)) == filters


def test_migration_is_idempotent_preserves_annotation_and_checks_ranges():
    engine = create_engine('sqlite:///:memory:')
    try:
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE resource_person (id INTEGER PRIMARY KEY, overall_score INTEGER, overall_rating TEXT)'))
            connection.execute(text("INSERT INTO resource_person VALUES (1, 9, '历史评价')"))
            apply_migration(connection)
            assert tuple(connection.execute(text('SELECT overall_score, overall_rating, interpretation_rating, written_translation_score FROM resource_person')).one()) == (9, '历史评价', None, None)
            connection.execute(text("UPDATE resource_person SET interpretation_rating=4, interpretation_rating_note='说明', interpretation_domains='医学', written_translation_score=10, written_translation_evaluation='笔译评价'"))
            apply_migration(connection)
            assert tuple(connection.execute(text('SELECT interpretation_rating, interpretation_rating_note, interpretation_domains, written_translation_score, written_translation_evaluation FROM resource_person')).one()) == (4, '说明', '医学', 10, '笔译评价')
            for field, invalid in [('interpretation_rating', 7), ('written_translation_score', 11)]:
                with pytest.raises(IntegrityError):
                    connection.execute(text(f'UPDATE resource_person SET {field}={invalid}'))
    finally:
        engine.dispose()
