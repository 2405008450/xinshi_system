import json
from unittest.mock import Mock

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

import request_failure_logging as failures


class Payload(BaseModel):
    revision: int


def test_validation_and_business_failures_keep_safe_context(monkeypatch):
    logger = Mock()
    monkeypatch.setattr(failures, '_logger', logger)
    app = FastAPI()
    app.add_middleware(failures.RequestFailureLoggingMiddleware)

    @app.post('/actions')
    def submit(data: Payload, request: Request):
        request.state.failure_actor = {'id': 'user-1', 'name': '测试人'}
        raise HTTPException(422, '任务归属无效')

    with TestClient(app) as client:
        result = client.post('/actions?mode=children&token=private', json={
            'revision': 1, 'action': 'move_tasks', 'password': 'private',
            'data': {'board_id': 'board-1', 'proofs': 'private'},
        })
        assert result.status_code == 422
        event = json.loads(logger.warning.call_args.args[0])
        assert event['reason']['detail'] == '任务归属无效'
        assert event['body']['action'] == 'move_tasks'
        assert event['body']['data']['board_id'] == 'board-1'
        assert event['actor']['name'] == '测试人'
        assert 'private' not in json.dumps(event)
        assert event['time'].endswith('+08:00')
        result = client.post('/actions', json={'revision': 'invalid', 'password': 'private'})
        assert result.status_code == 422
        event = json.loads(logger.warning.call_args.args[0])
        assert event['reason']['detail'][0]['loc'] == ['body', 'revision']
        assert event['reason']['detail'][0]['input'] == '[redacted]'


def test_large_and_malformed_bodies_do_not_leak_or_change_response(monkeypatch):
    logger = Mock()
    monkeypatch.setattr(failures, '_logger', logger)
    app = FastAPI()
    app.add_middleware(failures.RequestFailureLoggingMiddleware)

    @app.post('/test')
    def submit(data: Payload):
        return {'ok': True}

    with TestClient(app) as client:
        assert client.post('/test', json={'revision': 1}).json() == {'ok': True}
        logger.warning.assert_not_called()
        assert client.post('/test', content='{' + 'x' * failures.BODY_LIMIT,
                           headers={'content-type': 'application/json'}).status_code == 422
        event = json.loads(logger.warning.call_args.args[0])
        assert event['body'] == {'omitted': 'body exceeds 32 KiB'}
        assert len(json.dumps(event)) < 10000


def test_failure_log_is_written_and_rotates(monkeypatch, tmp_path):
    path = tmp_path / 'request-validation.jsonl'
    monkeypatch.setattr(failures, 'LOG_PATH', path)
    monkeypatch.setattr(failures, '_logger', None)
    logger = failures.failure_logger()
    handler = logger.handlers[-1]
    try:
        handler.maxBytes = 100
        logger.warning(json.dumps({'event': 'first', 'reason': 'x' * 80}))
        logger.warning(json.dumps({'event': 'second'}))
        assert json.loads(path.read_text(encoding='utf-8'))['event'] == 'second'
        assert path.with_suffix('.jsonl.1').exists()
    finally:
        logger.removeHandler(handler)
        handler.close()
