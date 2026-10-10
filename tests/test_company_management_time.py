"""公司管理时区回归测试，无需数据库连接。"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import company_management_service as service
from annotation_notice_schemas import AnnotationNoticeSectionResponse
from concurrency import parse_expected_updated_at


def test_company_clock_uses_business_timezone(monkeypatch):
    class ServerUtcClock(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = datetime(2026, 10, 9, 9, 18, 43, tzinfo=timezone.utc)
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(service, "datetime", ServerUtcClock)
    assert service._business_now() == datetime(2026, 10, 9, 17, 18, 43)
    assert service._business_now().tzinfo is None


def test_company_response_has_offset_and_preserves_version():
    stored_time = datetime(2026, 10, 9, 17, 18, 43, 787825)
    row = SimpleNamespace(
        id=uuid4(), section_key="company_rules", title="公司制度", parent_id=None,
        sort_order=1, has_content=True, is_active=True, content_json=None,
        updated_by=None, editor=None, updated_at=stored_time, structure_updated_at=None,
    )
    result = service._serialize(row, {}, include_content=True)
    response = AnnotationNoticeSectionResponse.model_validate(result).model_dump(mode="json")
    assert response["updated_at"] == "2026-10-09T17:18:43.787825+08:00"
    assert parse_expected_updated_at(response["updated_at"]) == stored_time
    assert row.updated_at == stored_time

    row.updated_at = datetime(2026, 10, 9, 9, 18, 43, tzinfo=timezone.utc)
    assert service._serialize(row, {}, include_content=True)["updated_at"].utcoffset() == timedelta(0)
    row.updated_at = None
    assert service._serialize(row, {}, include_content=True)["updated_at"] is None
