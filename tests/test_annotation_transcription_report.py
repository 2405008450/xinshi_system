import gzip
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import annotation_transcription_report_service as service
from routers import annotation_transcription_report as routes, auth


BASE = "/projects/annotation-transcription-report"


@pytest.fixture
def client(monkeypatch):
    # 单独挂载只读路由，不启动主应用，不创建数据库结构或连接业务数据库。
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[auth.get_db] = lambda: object()
    app.dependency_overrides[auth.get_current_user] = lambda: SimpleNamespace(id=uuid4())
    monkeypatch.setattr(auth, "user_has_permission", lambda db, user_id, code: code == "projects:read")
    with TestClient(app) as instance:
        yield instance


def test_summary_and_catalog_preserve_original_json(client):
    dataset = service.get_report_dataset()
    metadata = client.get(BASE).json()
    assert metadata["language_count"] == len(dataset.summary["languages"])
    assert metadata["methods"] == dataset.summary["methods"]
    assert len(metadata["revision"]) == 64
    assert client.get(BASE + "/summary").json() == json.loads(dataset.files["summary.json"])
    assert client.get(BASE + "/languages").json() == dataset.summary["languages"]


def test_combined_filters_pagination_and_null_values(client):
    dataset = service.get_report_dataset()
    original = json.loads(dataset.files["details/ko_kr.json"])
    expected = [row for row in original if row["model"] == "qwen"
                and row["cohort"] == "public_dataset" and row["success"] is True]
    response = client.get(BASE + "/languages/ko_kr/details", params={
        "model": "qwen", "cohort": "public_dataset", "success": "true", "skip": 2, "limit": 3,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == len(expected)
    assert [row["id"] for row in result["items"]] == [row["id"] for row in expected[2:5]]
    assert result["revision"] == dataset.revision
    for actual, source in zip(result["items"], expected[2:5]):
        assert actual["reference"] == source["reference"]
        assert actual["cer"] == source["cer"]
        assert "reference_diff_html" not in actual
    empty = client.get(BASE + "/languages/ko_kr/details", params={"skip": 100000}).json()
    assert empty["items"] == []
    assert empty["total"] == len(original)


def test_optional_html_does_not_mutate_cached_data(client):
    url = BASE + "/languages/ko_kr/details"
    assert "reference_diff_html" not in client.get(url).json()["items"][0]
    full = client.get(url, params={"include_diff_html": True}).json()["items"][0]
    assert "reference_diff_html" in full
    assert "reference_diff_html" not in client.get(url).json()["items"][0]


@pytest.mark.parametrize("params", [
    {"limit": 201}, {"limit": 0}, {"skip": -1}, {"cohort": "unknown"}, {"model": "unknown"},
])
def test_invalid_filters_are_rejected(client, params):
    assert client.get(BASE + "/languages/ko_kr/details", params=params).status_code == 422


def test_unknown_language_and_invalid_path(client):
    assert client.get(BASE + "/languages/unknown/details").status_code == 404
    assert client.get(BASE + "/languages/..%5Csummary/details").status_code == 422


def test_authentication_and_read_permission_required(client, monkeypatch):
    client.app.dependency_overrides.pop(auth.get_current_user)
    assert client.get(BASE).status_code == 401
    client.app.dependency_overrides[auth.get_current_user] = lambda: SimpleNamespace(id=uuid4())
    monkeypatch.setattr(auth, "user_has_permission", lambda *args: False)
    for suffix in ["", "/summary", "/languages", "/languages/ko_kr/details"]:
        assert client.get(BASE + suffix).status_code == 403


def test_missing_or_invalid_package_returns_service_unavailable(client, monkeypatch, tmp_path):
    package = tmp_path / "report.json.gz"
    monkeypatch.setattr(service, "REPORT_PACKAGE", package)
    assert client.get(BASE).status_code == 503
    package.write_bytes(b"not a gzip file")
    assert client.get(BASE).status_code == 503
    package.write_bytes(gzip.compress(json.dumps({"summary.json": "{}"}).encode()))
    assert client.get(BASE).status_code == 503


def test_cache_refreshes_after_package_update(monkeypatch, tmp_path):
    original = service.get_report_dataset()
    package = tmp_path / "report.json.gz"
    files = {"summary.json": json.dumps(original.summary)}
    package.write_bytes(gzip.compress(json.dumps(files).encode()))
    monkeypatch.setattr(service, "REPORT_PACKAGE", package)
    first = service.get_report_dataset()
    assert service.get_report_dataset() is first
    summary = dict(first.summary, generated_date="2026-11-14")
    files["summary.json"] = json.dumps(summary)
    files["test-extra.txt"] = "different-size"
    package.write_bytes(gzip.compress(json.dumps(files).encode()))
    second = service.get_report_dataset()
    assert second.summary["generated_date"] == "2026-11-14"
    assert first.revision != second.revision


def test_openapi_exposes_read_only_contract(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert len(paths) == 4
    assert all(set(operations) == {"get"} for operations in paths.values())
    details = paths[BASE + "/languages/{language_code}/details"]["get"]
    assert details["security"]
    assert {p["name"] for p in details["parameters"]} >= {"cohort", "model", "skip", "limit"}
