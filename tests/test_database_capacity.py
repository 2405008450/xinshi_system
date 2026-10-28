import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError,TimeoutError
from database_capacity import capacity_response


@pytest.mark.parametrize('error',[
    OperationalError(None,None,Exception('connection failed: FATAL: sorry, too many clients already')),
    OperationalError(None,None,Exception('remaining connection slots are reserved for roles with SUPERUSER')),
    TimeoutError('QueuePool limit reached'),
])
def test_connection_capacity_is_retryable_without_technical_details(error):
    response=capacity_response(error)
    assert response.status_code==503
    assert response.headers['retry-after']=='2'
    assert '数据库连接繁忙' in json.loads(response.body)['detail']
    assert 'QueuePool' not in response.body.decode() and 'OperationalError' not in response.body.decode()


def test_unrelated_database_errors_remain_server_errors():
    assert capacity_response(OperationalError(None,None,Exception('column does not exist'))) is None
    assert capacity_response(ValueError('bad data')) is None


def test_actual_http_handler_returns_503_and_masks_connection_string():
    from main import database_connection_error_handler
    app=FastAPI();app.add_exception_handler(OperationalError,database_connection_error_handler)
    @app.get('/directory')
    def directory():raise OperationalError(None,None,Exception('FATAL: sorry, too many clients already; private-connection-string'))
    with TestClient(app) as client:
        response=client.get('/directory')
        assert response.status_code==503
        assert response.headers['Retry-After']=='2'
        assert 'private-connection-string' not in response.text


def test_report_category_check_uses_the_existing_connection(tmp_path,monkeypatch):
    from sqlalchemy import create_engine,text
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import QueuePool
    from types import SimpleNamespace
    from uuid import uuid4
    import work_report_categories as categories
    engine=create_engine(f'sqlite:///{tmp_path / "pool.db"}',poolclass=QueuePool,pool_size=1,max_overflow=0,pool_timeout=.1)
    categories.WorkReportCategory.__table__.create(engine)
    monkeypatch.setattr(categories,'can_add_project_category',lambda *_:False)
    try:
        with Session(engine) as db:
            db.execute(text('SELECT 1'))
            result=categories.category_catalog(db,SimpleNamespace(id=uuid4()))
            assert result['category_storage_ready'] and not result['can_add_project_category']
        assert engine.pool.checkedout()==0
    finally:engine.dispose()
