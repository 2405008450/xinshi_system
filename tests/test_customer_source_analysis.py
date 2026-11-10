"""咨询分析回归：仅内存 SQLite，覆盖计数、组合筛选、关联与权限。"""
from datetime import date, datetime
import json
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from test_chat_participant_access import environment
import customer_source_analysis as service


@pytest.fixture
def data(environment):
    from models import Client, Consultation
    db, users = environment
    clients = [Client(id=uuid4(), client_code=f'C-{i}', client_name=f'测试客户{i}') for i in range(2)]
    db.add_all(clients)
    rows = []
    for index, (client, source, when, kind, status, method) in enumerate([
        (0, ' 百度 ', '2026-10-31T23:59:59.999999', 'translation', 'following', 'phone'),
        (0, '百度', '2026-11-01T00:00:00', '笔译项目', 'success', '电话'),
        (1, '', '2026-11-02T00:00:00', '翻译软件/平台', 'failed', 'email'),
        (None, None, None, '翻译耳机', 'following', None),
        (1, '淘宝', '2026-11-03T13:00:00', '同传设备租赁', 'success', 'online'),
    ]):
        row = Consultation(id=uuid4(), consultation_code=f'ZX-{index}',
            client_id=clients[client].id if client is not None else None,
            client_source=source, consultation_time=datetime.fromisoformat(when) if when else None,
            consultation_type=kind, status=status, consultation_method=method,
            source_keyword='英语 翻译' if index < 2 else '软件_100%', project_intake={})
        db.add(row); rows.append(row)
    db.commit()
    return db, clients, rows, users


def test_source_totals_unknown_and_period_boundaries(data):
    db, _, _, _ = data
    result = service.summary(db)
    assert result['total'] == 5 and result['client_count'] == 2 and result['undated_count'] == 1
    assert {item['source']: item['count'] for item in result['sources']} == {'百度': 2, '未知': 2, '淘宝': 1}
    assert sum(item['count'] for item in result['periods']) == 4
    assert [item['count'] for item in service.summary(db, 'week')['periods']] == [2, 2]
    assert [item['period'] for item in service.summary(db, 'week')['periods']] == ['2026-10-26', '2026-11-02']
    assert [item['count'] for item in service.summary(db, 'month')['periods']] == [1, 3]
    filtered = service.summary(db, start=date(2026, 10, 31), end=date(2026, 10, 31))
    assert filtered['total'] == 1
    assert service.records(db, start=date(2026, 11, 1), end=date(2026, 11, 1))['total'] == 1


@pytest.mark.parametrize('dimension', list(service.DIMENSION_FIELDS))
def test_every_dimension_drills_down_to_identical_count(data, dimension):
    db, _, _, _ = data
    result = service.summary(db, dimension=dimension)
    assert sum(item['count'] for item in result['sources']) == (2 if dimension.endswith('_confirmed') else 5)
    for item in result['sources']:
        details = service.records(db, source=item['source'], dimension=dimension)
        assert details['total'] == item['count']
    if dimension == 'type':
        assert next(item for item in result['sources'] if item['source'] == '笔译项目')['count'] == 2
        assert {'同传设备租赁', '翻译耳机', '翻译软件/平台'}.issubset({item['source'] for item in result['sources']})
    if dimension == 'method':
        assert next(item for item in result['sources'] if item['source'] == '电话')['count'] == 2


def test_client_isolation_live_link_pagination_and_serialization(data):
    db, clients, rows, _ = data
    assert service.summary(db, client_id=clients[0].id)['total'] == 2
    assert service.records(db, client_id=clients[1].id, source='百度')['total'] == 0
    rows[0].client_source = '官网'; db.commit()
    assert service.records(db, client_id=clients[0].id, source='官网')['total'] == 1
    details = service.records(db, page=999, page_size=2)
    assert details['page'] == 3 and len(details['items']) == 1
    first = service.records(db, source='官网')['items'][0]
    assert first['consultation_time'].isoformat().endswith('+08:00')
    assert first['consultation_time'].hour == 23
    with pytest.raises(HTTPException): service.summary(db, client_id=uuid4())
    with pytest.raises(HTTPException): service.summary(db, start=date(2026, 11, 2), end=date(2026, 11, 1))
    with pytest.raises(HTTPException): service.records(db, dimension='type_status', source='not-json')
    combination = json.dumps(['笔译项目', 'success'], ensure_ascii=False)
    assert service.records(db, dimension='type_status', source=combination)['total'] == 1


def test_api_permissions_and_validation(data, monkeypatch):
    from database import get_db
    from routers import auth
    from routers.customer_source_analysis import router
    db, clients, _, users = data
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth.get_current_user] = lambda: users[0]
    permissions = {'clients:read'}
    monkeypatch.setattr(auth, 'user_has_permission', lambda db, user_id, code: code in permissions)
    with TestClient(app) as client:
        assert client.get('/data-analysis/customer-sources').status_code == 403
        assert client.get(f'/clients/{clients[0].id}/sources').json()['total'] == 2
        assert client.get(f'/clients/{clients[0].id}/sources/records').json()['total'] == 2
        permissions.clear(); permissions.add('consultations:read')
        assert client.get(f'/clients/{clients[0].id}/sources').status_code == 403
        assert client.get('/data-analysis/customer-sources?dimension=type_status').status_code == 200
        for dimension in ['type_confirmed', 'source_confirmed']:
            assert client.get(f'/data-analysis/customer-sources?dimension={dimension}&granularity=month').json()['total'] == 2
            response = client.get(f'/data-analysis/customer-sources/records?dimension={dimension}').json()
            assert response['total'] == 2 and all(item['status'] == 'success' for item in response['items'])
        assert client.get('/data-analysis/customer-sources/records?page=0').status_code == 422
        assert client.get('/data-analysis/customer-sources?dimension=invalid').status_code == 422


@pytest.mark.parametrize('kind', ['同传设备租赁', '翻译耳机', '翻译软件/平台'])
def test_added_types_pass_create_and_edit_validation(kind):
    from routers.consultations import consultation_task_type_label, validate_consultation_required_fields
    from schemas import ConsultationCreate, ConsultationUpdate
    fields = dict(consultation_type=kind, consultation_method='phone', client_source='官网',
                  consultation_description='设备或软件咨询', status='following')
    validate_consultation_required_fields(ConsultationCreate(**fields))
    validate_consultation_required_fields(ConsultationUpdate(**fields))
    assert consultation_task_type_label(kind) == kind


def test_subtitle_rename_keeps_legacy_filter_and_analysis_group(data):
    from models import Consultation
    from crud import _apply_consultation_filters
    from annotation_service import is_translation_type
    db, _, rows, _ = data
    renamed = '（音视频）转录/字幕项目'
    for row, kind in zip(rows, ['字幕项目', 'subtitle', renamed]):
        row.consultation_type = kind
    db.commit()
    for kind in ['字幕项目', 'subtitle', renamed]:
        assert is_translation_type(kind)
        assert _apply_consultation_filters(db.query(Consultation), consultation_type=kind).count() == 3
    result = service.summary(db, dimension='type')
    assert next(item for item in result['sources'] if item['source'] == renamed)['count'] == 3
    assert service.records(db, dimension='type', source=renamed)['total'] == 3


@pytest.mark.parametrize('dimension', ['type_confirmed', 'source_confirmed'])
def test_confirmed_analysis_week_month_date_range_and_live_status(data, dimension):
    db, clients, rows, _ = data
    rows[0].status = '已确认'  # 兼容历史中文值。
    rows[3].status = 'success'  # 无日期、无关联客户的已确认咨询。
    db.commit()
    weekly = service.summary(db, 'week', dimension=dimension)
    assert weekly['total'] == 4 and weekly['client_count'] == 2
    assert weekly['undated_count'] == 1
    assert [(item['period'], item['count']) for item in weekly['periods']] == [('2026-10-26', 2), ('2026-11-02', 1)]
    monthly = service.summary(db, 'month', dimension=dimension)
    assert [(item['period'], item['count']) for item in monthly['periods']] == [('2026-10-01', 1), ('2026-11-01', 2)]
    filtered = service.summary(db, 'month', dimension=dimension, start=date(2026, 11, 1), end=date(2026, 11, 2))
    detail = service.records(db, dimension=dimension, start=date(2026, 11, 1), end=date(2026, 11, 2))
    assert filtered['total'] == detail['total'] == 1
    assert all(item['status'] == 'success' for item in detail['items'])
    for category in weekly['sources']:
        assert service.records(db, dimension=dimension, source=category['source'])['total'] == category['count']
    assert service.summary(db, client_id=clients[0].id, dimension=dimension)['total'] == 2
    rows[4].status = 'following'; db.commit()
    assert service.summary(db, dimension=dimension)['total'] == 3
    assert service.summary(db)['total'] == 5
