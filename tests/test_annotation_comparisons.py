from datetime import datetime
import inspect
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import configure_mappers

from annotation_comparison_schemas import (
    AnnotationComparisonGroupCreate,
    AnnotationComparisonGroupUpdate,
)
from annotation_comparison_service import serialize_group
from routers.annotation_comparisons import router as comparison_router


def test_comparison_models_and_routes_are_registered():
    import main

    configure_mappers()
    paths = set(main.app.openapi()["paths"])
    assert "/projects/annotation-comparisons/page" in paths
    assert "/projects/annotation-comparisons/{group_id}" in paths


def test_comparison_group_payload_normalizes_text_and_preserves_project_order():
    project_ids = [uuid4(), uuid4()]
    payload = AnnotationComparisonGroupCreate(
        name="  同类语音项目  ",
        description="  对比客户报价与资源需求  ",
        project_ids=project_ids,
    )
    assert payload.name == "同类语音项目"
    assert payload.description == "对比客户报价与资源需求"
    assert payload.project_ids == project_ids


@pytest.mark.parametrize("count", [0, 1, 11])
def test_comparison_group_requires_two_to_ten_projects(count):
    with pytest.raises(ValidationError):
        AnnotationComparisonGroupCreate(
            name="比较组", description="比较说明", project_ids=[uuid4() for _ in range(count)]
        )


def test_comparison_group_rejects_duplicate_projects_on_create_and_update():
    project_id = uuid4()
    with pytest.raises(ValidationError, match="不能重复选择项目"):
        AnnotationComparisonGroupCreate(
            name="比较组", description="比较说明", project_ids=[project_id, project_id]
        )
    with pytest.raises(ValidationError, match="不能重复选择项目"):
        AnnotationComparisonGroupUpdate(project_ids=[project_id, project_id])


def test_group_serialization_uses_current_project_values_and_member_order():
    first_id, second_id = uuid4(), uuid4()
    first = SimpleNamespace(
        id=first_id, order_no="AP-002", project_name="项目二", client_short_name="客户乙",
        client_full_name="客户乙有限公司", project_types=["audio_annotation"],
        language_items_display="英语", customer_price_summary="￥200/小时",
        client_manager_name="客户经理乙", role_assignments=[{
            "role_code": "project_manager", "assignee_name": "项目经理乙",
        }], project_status="project_in_progress", potential_demand="20小时",
    )
    second = SimpleNamespace(
        id=second_id, order_no="AP-001", project_name="项目一", client_short_name="客户甲",
        client_full_name="客户甲有限公司", project_types=["audio_collection"],
        language_items_display="日语", customer_price_summary="￥100/小时",
        client_manager_name="客户经理甲", role_assignments=[],
        project_status="trial_preparation", potential_demand="10小时",
    )
    group = SimpleNamespace(
        id=uuid4(), name="报价比较", description="比较报价", created_by=uuid4(),
        created_by_name="创建人", created_at=datetime(2026, 9, 26, 10),
        updated_at=datetime(2026, 9, 26, 10),
        members=[
            SimpleNamespace(project_id=second_id, sequence_no=2, project=second),
            SimpleNamespace(project_id=first_id, sequence_no=1, project=first),
        ],
    )
    result = serialize_group(group, detail=True)
    assert [item["project_id"] for item in result["projects"]] == [first_id, second_id]
    assert result["projects"][0]["customer_price_summary"] == "￥200/小时"
    assert result["projects"][0]["project_manager_name"] == "项目经理乙"


def test_comparison_routes_reuse_project_read_and_write_permissions():
    read_route = next(item for item in comparison_router.routes if item.path.endswith("/page"))
    write_route = next(item for item in comparison_router.routes if item.path == "/projects/annotation-comparisons")
    read_dependencies = [inspect.getclosurevars(item.call).nonlocals for item in read_route.dependant.dependencies]
    write_dependencies = [inspect.getclosurevars(item.call).nonlocals for item in write_route.dependant.dependencies]
    assert any(item.get("read_permission") == "projects:read" for item in read_dependencies)
    assert any(item.get("permission_codes") == ("projects:write",) for item in write_dependencies)


def test_comparison_migration_keeps_groups_when_projects_are_deleted():
    migration = Path("data/migrations/20260926_annotation_project_comparison_groups.sql").read_text(encoding="utf-8")
    assert "REFERENCES annotation_project(id) ON DELETE CASCADE" in migration
    assert "UNIQUE (group_id, project_id)" in migration
    assert "sequence_no >= 1 AND sequence_no <= 10" in migration
