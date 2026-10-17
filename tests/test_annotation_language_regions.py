"""语种地区输入、接口、快照和迁移；数据库案例只使用隔离 PostgreSQL。"""
from pathlib import Path
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text

import annotation_service as service
from annotation_models import AnnotationArea
from annotation_schemas import AnnotationLanguageItemInput, AnnotationProjectCreate
from test_annotation_child_orders import sessions, context, item, update_payload, add_test_language


REGIONS = [dict(city='广州', district='越秀区', street=None),
           dict(city='佛山', district='禅城区', street='祖庙街道')]


def save(db, project_id, **changes):
    project = service.get_annotation_project(db, project_id)
    return service.update_annotation_project(db, project_id, update_payload(project, **changes))


def language_item(project, **changes):
    row = project.language_items[0]
    return dict(id=row.id, source_language_id=row.source_language_id,
                target_language_id=row.target_language_id, **changes)


def test_optional_regions_trim_and_partial_fields():
    row = AnnotationLanguageItemInput(source_language_id=uuid4(), regions=[
        dict(city=' 广州 ', district=' 越秀区 ', street=' '),
        dict(district='禅城区'), dict(street='祖庙街道'), dict(city=' '), {},
    ])
    assert [region.model_dump() for region in row.regions] == [
        REGIONS[0], dict(city=None, district='禅城区', street=None),
        dict(city=None, district=None, street='祖庙街道')]
    assert AnnotationLanguageItemInput(source_language_id=uuid4()).regions == []


@pytest.mark.parametrize('field', ['city', 'district', 'street'])
def test_region_length_limit(field):
    with pytest.raises(ValidationError):
        AnnotationLanguageItemInput(source_language_id=uuid4(), regions=[{field: '字' * 101}])
    assert len(AnnotationLanguageItemInput(source_language_id=uuid4(),
        regions=[{field: ' ' + '字' * 100 + ' '}]).regions) == 1


def test_multiple_regions_do_not_split_and_empty_array_clears(context):
    db, parent_id, _language_id = context
    parent = service.get_annotation_project(db, parent_id)
    parent = save(db, parent_id, language_items=[language_item(parent, regions=REGIONS)])
    assert parent.language_items[0].regions == REGIONS and parent.child_count == 0
    # 旧客户端省略地区字段时不能清空新数据。
    parent = save(db, parent_id, language_items=[language_item(parent)], project_name='旧客户端编辑')
    assert parent.language_items[0].regions == REGIONS
    parent = save(db, parent_id, language_items=[dict(source_language_id=parent.language_items[0].source_language_id)])
    assert parent.language_items[0].regions == REGIONS
    parent = save(db, parent_id, language_items=[language_item(parent, regions=[])])
    assert parent.language_items[0].regions == []


def test_automatic_children_copy_only_matching_language_regions(context):
    db, parent_id, language_id = context
    second = add_test_language(db)
    parent = service.get_annotation_project(db, parent_id)
    parent = save(db, parent_id, language_items=[language_item(parent, regions=REGIONS),
        dict(source_language_id=second, regions=[dict(street='另一街道')])])
    children = service.get_annotation_projects(db, order_scope='all', parent_project_id=parent_id)
    assert parent.child_count == len(children) == 2
    by_language = {child.language_items[0].source_language_id: child for child in children}
    assert by_language[language_id].language_items[0].regions == REGIONS
    assert by_language[second].language_items[0].regions == [dict(city=None, district=None, street='另一街道')]
    local = by_language[language_id]
    save(db, local.id, language_items=[language_item(local, regions=[dict(city='深圳')])])
    parent = save(db, parent_id, language_items=[language_item(parent, regions=[dict(city='珠海')]),
        dict(id=parent.language_items[1].id, source_language_id=second, regions=[])])
    assert parent.child_count == 2
    assert service.get_annotation_project(db, local.id).language_items[0].regions[0]['city'] == '深圳'
    assert service.get_annotation_project(db, by_language[second].id).language_items[0].regions[0]['street'] == '另一街道'


def test_manual_children_snapshot_and_local_grandchild_regions(context):
    db, parent_id, language_id = context
    parent = service.get_annotation_project(db, parent_id)
    parent = save(db, parent_id, language_items=[language_item(parent, regions=REGIONS)])
    child = service.create_annotation_children(db, parent_id, [item(language_id)], None, uuid4().hex)[0]
    assert child.language_items[0].regions == REGIONS
    empty_child = service.create_annotation_children(db, parent_id, [AnnotationProjectCreate(
        language_items=[dict(source_language_id=language_id, regions=[])])], None, uuid4().hex)[0]
    assert empty_child.language_items[0].regions == []
    area = AnnotationArea(label='地区测试片区', name_key=uuid4().hex)
    db.add(area); db.commit()
    leaf = service.create_annotation_children(db, child.id,
        [item(language_id, area_id=area.id)], None, uuid4().hex)[0]
    leaf = save(db, leaf.id, language_items=[language_item(leaf, regions=[dict(street='本地街道')])])
    assert leaf.language_items[0].regions == [dict(city=None, district=None, street='本地街道')]
    # 恢复其他字段继承也不能把旧客户端省略的地区变成空数组。
    leaf = save(db, leaf.id, language_items=[language_item(leaf)], restore_inheritance=['potential_demand'])
    assert leaf.language_items[0].regions[0]['street'] == '本地街道'
    # 父级强制同步语种时，三级订单的本地地区仍保留。
    other = add_test_language(db)
    child = service.get_annotation_project(db, child.id)
    save(db, child.id, language_items=[dict(id=child.language_items[0].id, source_language_id=other,
        regions=[dict(city='其他城市')])])
    leaf = service.get_annotation_project(db, leaf.id)
    assert leaf.language_items[0].source_language_id == other
    assert leaf.language_items[0].regions[0]['street'] == '本地街道'
    assert service.get_annotation_project(db, parent_id).language_items[0].regions == REGIONS


def test_region_filter_combination_uses_one_region_and_one_language(context):
    db, parent_id, language_id = context
    other = add_test_language(db)
    parent = service.get_annotation_project(db, parent_id)
    unique = '地区组合检索' + uuid4().hex
    save(db, parent_id, project_name=unique, language_items=[language_item(parent, regions=REGIONS),
        dict(source_language_id=other, regions=[dict(city='深圳',district='南山区',street='科技园')])])

    def found(**terms):
        filters = {'project_name': {'op': 'contains', 'value': unique}, **{
            f'region_{key}': {'op': 'contains', 'value': value} for key, value in terms.items()}}
        return service.get_annotation_projects(db, order_scope='parent', field_filters=filters)

    assert [project.id for project in found(city='广州', district='越秀')] == [parent_id]
    assert found(city='广州', district='禅城') == []
    assert found(city='广州', street='科技园') == []
    assert [project.id for project in found(district='南山')] == [parent_id]
    filters = {'project_name': {'op': 'contains', 'value': unique},
        'region_city': {'op': 'contains', 'value': '广州'},
        'language_id': {'op': 'in', 'value': [str(other)]}}
    assert service.get_annotation_projects(db, order_scope='parent', field_filters=filters) == []
    filters['language_id']['value'] = [str(language_id)]
    assert service.count_annotation_projects(db, order_scope='parent', field_filters=filters) == 1
    rows = service.get_annotation_projects(db, order_scope='parent', keyword='祖庙街道',
        field_filters={'project_name': {'op': 'contains', 'value': unique}})
    assert [project.id for project in rows] == [parent_id]


def test_region_contains_treats_wildcards_as_literal_text(context):
    db, parent_id, _language_id = context
    parent = service.get_annotation_project(db, parent_id)
    unique = '地区特殊字符' + uuid4().hex
    save(db, parent_id, project_name=unique, language_items=[language_item(parent,
        regions=[dict(city='自定义_%地区')])])
    filters = {'project_name': {'op': 'contains', 'value': unique},
        'region_city': {'op': 'contains', 'value': '_%'}}
    assert service.count_annotation_projects(db, order_scope='parent', field_filters=filters) == 1
    filters['region_city']['value'] = '不存在%'
    assert service.count_annotation_projects(db, order_scope='parent', field_filters=filters) == 0


def test_api_create_list_detail_update_and_validation(context, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers import annotation_projects as routes, auth
    db, _parent_id, language_id = context
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: SimpleNamespace(id=None)
    monkeypatch.setattr(auth, 'user_has_permission', lambda *_args: True)
    monkeypatch.setattr(auth, 'get_user_permission_codes', lambda *_args: {'projects:read', 'projects:write'})
    with TestClient(app) as client:
        created = client.post('/projects/annotation/', json=dict(project_name='语种地区接口验收',
            language_items=[dict(source_language_id=str(language_id), regions=REGIONS)]))
        assert created.status_code == 201, created.text
        project = created.json()
        project_id = project['id']
        assert project['language_items'][0]['regions'] == REGIONS
        detail = client.get(f'/projects/annotation/{project_id}').json()
        assert detail['language_items'][0]['regions'] == REGIONS
        page = client.get('/projects/annotation/page', params={'keyword': '语种地区接口验收'}).json()
        assert next(row for row in page['items'] if row['id'] == project_id)['language_items'][0]['regions'] == REGIONS
        region_filters = {'project_name': {'op': 'contains', 'value': '语种地区接口验收'},
            'region_city': {'op': 'contains', 'value': '广州'},
            'region_district': {'op': 'contains', 'value': '越秀'}}
        params = {'order_scope':'parent', 'field_filters':json.dumps(region_filters), 'skip':0, 'limit':1}
        paged = client.get('/projects/annotation/page', params=params)
        assert paged.status_code == 200, paged.text
        assert paged.json()['total'] == 1 and paged.json()['items'][0]['id'] == project_id
        count = client.get('/projects/annotation/count', params=params).json()
        listed = client.get('/projects/annotation/', params=params).json()
        assert count['total'] == len(listed) == 1 and listed[0]['id'] == project_id
        from datetime import date
        from project_export_routes import build_export_filters
        export_filters = build_export_filters('annotation', routes._field_filters, db,
            time_field='created_at', date_start=date(2000,1,1), date_end=date(2099,1,1),
            field_filters=json.dumps(region_filters), order_scope='parent')
        assert service.count_annotation_projects(db, **export_filters) == 1
        schema = client.get('/openapi.json').json()
        assert schema['paths']['/projects/annotation/page']['get']['x-annotation-region-filters'] == ['city','district','street']
        region_filters['region_city'] = {'op':'in','value':['广州']}
        assert client.get('/projects/annotation/page', params={'field_filters':json.dumps(region_filters)}).status_code == 422
        old = project['language_items'][0]
        old.pop('regions')
        payload = dict(language_items=[old], expected_updated_at=project['updated_at'])
        updated = client.put(f'/projects/annotation/{project_id}', json=payload)
        assert updated.status_code == 200, updated.text
        assert updated.json()['language_items'][0]['regions'] == REGIONS
        payload.update(expected_updated_at=updated.json()['updated_at'])
        payload['language_items'][0]['regions'] = []
        cleared = client.put(f'/projects/annotation/{project_id}', json=payload)
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()['language_items'][0]['regions'] == []
        payload['language_items'][0]['regions'] = [dict(city='字' * 101)]
        invalid = client.put(f'/projects/annotation/{project_id}', json=payload)
        assert invalid.status_code == 422
        assert invalid.json()['detail'][0]['loc'][-3:] == ['regions', 0, 'city']


def test_incremental_migration_is_repeatable_and_keeps_legacy_rows(context, sessions):
    db, parent_id, _language_id = context
    db.rollback()
    sql = (Path(__file__).resolve().parents[1] / 'data/migrations/20261017_annotation_language_regions.sql').read_text(encoding='utf-8')
    engine = sessions.kw['bind']
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        connection.exec_driver_sql('ALTER TABLE annotation_project_language_item DROP COLUMN regions CASCADE')
        connection.exec_driver_sql(sql)
        connection.exec_driver_sql(sql)
        regions = connection.execute(text('SELECT regions FROM annotation_project_language_item WHERE project_id=:id'), dict(id=parent_id)).scalar_one()
        assert regions == []
        connection.execute(text("UPDATE annotation_project_language_item SET regions=CAST(:regions AS jsonb) WHERE project_id=:id"),
            dict(id=parent_id, regions='[{"city":"广州"}]'))
        connection.exec_driver_sql(sql)
        assert connection.execute(text('SELECT regions FROM annotation_project_language_item WHERE project_id=:id'), dict(id=parent_id)).scalar_one() == [dict(city='广州')]
