"""仅使用临时 SQLite 与模拟算力连接，不触碰业务数据库。"""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest
from pydantic import ValidationError
import thoughts_ai_service as service


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('thoughts_gateway_test', Path(__file__).resolve().parents[1] / 'deploy/thoughts_compute_gateway.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, '__file__', str(tmp_path / 'gateway.py'))
    monkeypatch.setitem(sys.modules, 'fcntl', SimpleNamespace(LOCK_EX=1, LOCK_NB=2, flock=lambda *_: None))
    return module


@pytest.fixture
def queue(tmp_path, monkeypatch):
    monkeypatch.setenv('THOUGHTS_AI_QUEUE_PATH', str(tmp_path / 'jobs.sqlite3'))
    monkeypatch.setenv('THOUGHTS_AI_ENABLED', 'true')
    monkeypatch.setattr(service, 'ensure_worker', lambda: None)
    return str(uuid4()), str(uuid4())


def payload(content='测试个人思考'):
    return service.ThoughtRequest(action='organize', content=content)


def test_private_jobs_and_duplicate_submit(queue):
    owner, other = queue
    job = service.create(owner, payload())
    assert job['created_at'].endswith('+08:00')
    assert 'content' not in job and 'user_id' not in job
    assert service.latest(other)['job'] is None
    with pytest.raises(HTTPException) as denied:
        service.cancel(other, job['id'])
    assert denied.value.status_code == 404
    with pytest.raises(HTTPException) as duplicate:
        service.create(owner, payload())
    assert duplicate.value.status_code == 409
    assert service.cancel(owner, job['id'])['state'] == 'cancelled'
    assert service.create(owner, payload())['id'] != job['id']


def test_cross_process_claim_and_cancel_discards_result(queue):
    owner, other = queue
    first = service.create(owner, payload())
    service.create(other, payload())
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: service.claim(), range(2)))
    assert sum(row is not None for row in claims) == 1
    assert service.cancel(owner, first['id'])['state'] == 'cancelling'
    service.complete(first['id'], {'state': 'succeeded', 'result': '取消后的结果不应保留'})
    current = service.latest(owner)['job']
    assert current['state'] == 'cancelled' and current['result'] == ''
    assert service.claim()['user_id'] == other


def test_busy_wait_then_succeed_without_duplicate_calls(queue, monkeypatch):
    owner, _ = queue
    service.create(owner, payload())
    row = service.claim()
    calls = []
    def compute(request):
        calls.append(request)
        return {'state': 'busy'} if len(calls) == 1 else {'state': 'succeeded', 'result': '有效结果', 'truncated': True}
    monkeypatch.setattr(service, 'transport', compute)
    monkeypatch.setattr(service.time, 'sleep', lambda _: None)
    service.process(row)
    job = service.latest(owner)['job']
    assert job['state'] == 'succeeded' and job['result'] == '有效结果' and job['truncated']
    assert len(calls) == 2
    with service.connect() as db:
        assert db.execute('SELECT content FROM jobs').fetchone()[0] == ''


def test_restart_timeout_does_not_resubmit_and_retention(queue, monkeypatch):
    owner, _ = queue
    job = service.create(owner, payload())
    service.claim()
    with service.connect() as db:
        db.execute('UPDATE jobs SET deadline=?', (time.time() - 1,))
    assert service.latest(owner)['job']['state'] == 'failed'
    assert service.claim() is None
    service.complete(job['id'], {'state': 'succeeded', 'result': '过期结果'})
    assert service.latest(owner)['job']['result'] == ''
    with service.connect() as db:
        db.execute('UPDATE jobs SET finished=?', (time.time() - 86401,))
    assert service.latest(owner)['job'] is None


def test_text_budget_and_disabled_service(queue, monkeypatch):
    assert payload('文本\n![截图](screenshot://signed-reference)').content == '文本'
    for text in [' ', '![截图](screenshot://image)', '字' * 6001]:
        with pytest.raises(ValidationError):
            payload(text)
    monkeypatch.setenv('THOUGHTS_AI_ENABLED', 'false')
    with pytest.raises(HTTPException) as disabled:
        service.create(queue[0], payload())
    assert disabled.value.status_code == 503


def test_transport_pins_host_and_does_not_use_shell(monkeypatch):
    captured = {}
    def run(command, **kwargs):
        captured.update(command=command, **kwargs)
        return type('Response', (), {'returncode': 0, 'stdout': '{"state":"available"}'})()
    monkeypatch.setattr(service.subprocess, 'run', run)
    assert service.transport({'operation': 'status'})['state'] == 'available'
    assert 'StrictHostKeyChecking=yes' in captured['command']
    assert 'BatchMode=yes' in captured['command']
    assert not captured.get('shell')
    assert json.loads(captured['input']) == {'operation': 'status'}


def test_connection_failure_does_not_leak_prompt(queue, monkeypatch):
    service.create(queue[0], payload('私人正文不进入错误'))
    row = service.claim()
    def fail(_):
        raise RuntimeError('secret remote stderr')
    monkeypatch.setattr(service, 'transport', fail)
    service.process(row)
    current = service.latest(queue[0])['job']
    assert current['state'] == 'failed'
    assert 'secret' not in json.dumps(current) and '私人正文' not in json.dumps(current, ensure_ascii=False)


def test_analysis_scopes_keep_results_separate_but_share_admission_and_transport(queue, monkeypatch):
    owner, _ = queue
    personal = service.create(owner, payload())
    row = service.claim()
    service.complete(personal['id'], {'state': 'succeeded', 'result': '个人思考结果'})
    source = service.create(owner, service.ThoughtRequest(scope='customer_source', action='organize', content='客户来源原始项及计数'))
    assert source['scope'] == 'customer_source' and source['action'] == 'organize'
    assert service.latest(owner)['job']['result'] == '个人思考结果'
    assert service.latest(owner)['busy'] is True
    assert service.latest(owner, 'source_keyword')['job'] is None
    with pytest.raises(HTTPException) as duplicate:
        service.create(owner, service.ThoughtRequest(scope='source_keyword', action='organize', content='关键词'))
    assert duplicate.value.status_code == 409
    calls = []
    monkeypatch.setattr(service, 'transport', lambda request: calls.append(request) or {'state': 'succeeded', 'result': '来源分类结果'})
    service.process(service.claim())
    assert calls[0]['action'] == 'organize'
    assert service.latest(owner, 'customer_source')['job']['result'] == '来源分类结果'
    assert service.latest(owner)['job']['result'] == '个人思考结果'
    assert service.latest(owner)['busy'] is False
    with pytest.raises(HTTPException): service.latest(owner, 'invalid')


@pytest.mark.parametrize('load', [
    {'running': 5, 'waiting': 0, 'cache': .2},
    {'running': 4, 'waiting': 1, 'cache': .2},
    {'running': 4, 'waiting': 0, 'cache': .65},
])
def test_compute_load_guard_does_not_start_inference(gateway, monkeypatch, load):
    monkeypatch.setattr(gateway, 'metrics', lambda: load)
    def unexpected(*_args, **_kwargs):
        pytest.fail('繁忙时不得执行 tokenize 或模型推理')
    monkeypatch.setattr(gateway, 'request', unexpected)
    assert gateway.handle({'operation': 'generate', 'action': 'organize', 'content': '测试'})['state'] == 'busy'


def test_compute_admits_only_bounded_short_request(gateway, monkeypatch):
    monkeypatch.setattr(gateway, 'metrics', lambda: {'running': 4, 'waiting': 0, 'cache': .2})
    calls = []
    def upstream(path, body=None, timeout=5):
        calls.append((path, body, timeout))
        return {'count': 6400} if path == '/tokenize' else {'choices': [{'message': {'content': '有界结果'}, 'finish_reason': 'length'}]}
    monkeypatch.setattr(gateway, 'request', upstream)
    result = gateway.handle({'operation': 'generate', 'action': 'todos', 'content': '测试'})
    assert result['state'] == 'succeeded' and result['truncated']
    body = calls[-1][1]
    assert body['max_tokens'] == 768 and body['chat_template_kwargs']['enable_thinking'] is False
    assert calls[-1][2] == 90
    calls.clear()
    monkeypatch.setattr(gateway, 'request', lambda *_args, **_kwargs: {'count': 6501})
    assert gateway.handle({'operation': 'generate', 'action': 'todos', 'content': '测试'})['state'] == 'invalid'


def test_missing_compute_metrics_fail_closed(gateway, monkeypatch):
    monkeypatch.setattr(gateway, 'request', lambda *_: 'vllm:num_requests_running{engine="0"} 4\n')
    with pytest.raises(ValueError, match='missing_metrics'):
        gateway.metrics()
