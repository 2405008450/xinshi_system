"""仅使用临时 SQLite，验证业务响应生成截图授权时不会等待自己占用的连接。"""
from types import SimpleNamespace
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool


@pytest.mark.parametrize('concurrency', [1, 4])
def test_response_grant_does_not_wait_for_business_connection(tmp_path, monkeypatch, concurrency):
    import main  # 只注册模型，不运行启动钩子。
    import editor_screenshot_middleware as middleware
    import editor_screenshot_service as service
    source = create_engine(f'sqlite:///{tmp_path / "isolated.db"}', poolclass=QueuePool,
                           pool_size=concurrency, max_overflow=0, pool_timeout=.1,
                           connect_args={'check_same_thread': False})
    monkeypatch.setattr(middleware, 'engine', source)
    monkeypatch.setattr('routers.auth.get_user_from_token_value', lambda *args: SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(service, 'ready', lambda db: True)
    def grant(db, user_id, ids):
        assert db.get_bind() is not source
        db.execute(text('SELECT 1'))
        return 'isolated-grant', 9999999999
    monkeypatch.setattr(service, 'grant', grant)
    app = FastAPI()
    app.add_middleware(middleware.EditorScreenshotMiddleware)
    barrier = Barrier(concurrency)
    def route_db():
        with Session(source) as db:
            db.execute(text('SELECT 1'))
            barrier.wait(timeout=3)
            yield db
    @app.get('/chat/sessions')
    def sessions(db=Depends(route_db)):
        return {'items': [{'preview': service.signed_reference(uuid4())}]}
    try:
        with TestClient(app) as client:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                responses = list(executor.map(lambda _: client.get('/chat/sessions', headers={'Authorization': 'Bearer isolated-token'}), range(concurrency)))
        assert all(response.status_code == 200 for response in responses)
        assert all(response.headers.get('x-screenshot-grant') == 'isolated-grant' for response in responses)
    finally:
        if hasattr(middleware, 'screenshot_engine'):
            auxiliary = middleware.screenshot_engine(source)
            if auxiliary is not source: auxiliary.dispose()
        source.dispose()
