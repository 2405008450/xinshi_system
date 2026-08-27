from types import SimpleNamespace
from uuid import uuid4

import pytest

from annotation_custom_field_service import _validate_scope
from annotation_models import AnnotationProjectAssignee
from annotation_ops_models import (
    AnnotationCustomFieldDefinition,
    AnnotationPlatformAccount,
    AnnotationTrialRecord,
)
from annotation_ops_schemas import AccountWrite
from annotation_ops_service import _validate_trial_member
from annotation_schemas import AnnotationProjectStatusUpdate
from resource_request_schemas import ResourceRequestWrite
from resource_request_service import _project_type_values, _source_detail, _sync_items, _view_filter_sql


def test_custom_field_scope_is_enforced_by_service_and_model():
    with pytest.raises(ValueError, match="必须指定项目"):
        _validate_scope("trial", None)
    with pytest.raises(ValueError, match="必须是全局字段"):
        _validate_scope("project", uuid4())
    with pytest.raises(ValueError, match="必须是全局字段"):
        _validate_scope("account", uuid4())
    _validate_scope("account", None)

    constraint_names = {
        constraint.name for constraint in AnnotationCustomFieldDefinition.__table__.constraints
    }
    assert "ck_annotation_custom_field_scope" in constraint_names


def test_trial_and_workflow_rows_reuse_project_details_through_foreign_keys():
    for model in (AnnotationTrialRecord, AnnotationProjectAssignee):
        project_column = model.__table__.c.project_id
        targets = {foreign_key.target_fullname for foreign_key in project_column.foreign_keys}
        assert targets == {"annotation_project.id"}

        # 项目基本信息由外键关联项目详情带出，不在流程记录中重复保存。
        assert "project_name" not in model.__table__.c
        assert "client_short_name" not in model.__table__.c


def test_platform_account_can_be_saved_before_assigning_a_talent():
    payload = AccountWrite(platform_id=uuid4())

    assert payload.login_account is None
    assert payload.password is None
    assert AnnotationPlatformAccount.__table__.c.login_account.nullable is True


class _TrialValidationQuery:
    def __init__(self, *, first=None, rows=None):
        self.first_value = first
        self.rows = rows or []

    def filter(self, *_conditions):
        return self

    def first(self):
        return self.first_value

    def all(self):
        return self.rows


class _TrialValidationDb:
    def __init__(self, project, account=None, queries=None):
        self.project = project
        self.account = account
        self.queries = list(queries or [])

    def get(self, model, value):
        if model.__name__ == "AnnotationProject":
            return self.project
        if model.__name__ == "AnnotationPlatformAccount":
            return self.account
        return None

    def query(self, *_entities):
        return self.queries.pop(0)


def test_trial_annotator_must_match_at_least_one_project_language():
    project_id, person_id = uuid4(), uuid4()
    db = _TrialValidationDb(
        SimpleNamespace(id=project_id),
        queries=[
            _TrialValidationQuery(first=(uuid4(),)),
            _TrialValidationQuery(rows=[(uuid4(), None)]),
            _TrialValidationQuery(rows=[(uuid4(), None)]),
        ],
    )

    with pytest.raises(ValueError, match="语言方向与项目语种不匹配"):
        _validate_trial_member(db, project_id, person_id, None)


def test_trial_platform_account_must_be_current_project_person_binding():
    project_id, person_id, account_id = uuid4(), uuid4(), uuid4()
    db = _TrialValidationDb(
        SimpleNamespace(id=project_id),
        account=SimpleNamespace(id=account_id),
        queries=[
            _TrialValidationQuery(first=(uuid4(),)),
            _TrialValidationQuery(rows=[]),
            _TrialValidationQuery(first=None),
        ],
    )

    with pytest.raises(ValueError, match="标注员账号.*当前绑定"):
        _validate_trial_member(db, project_id, person_id, account_id)


def test_resource_request_rejects_mismatched_source_and_category():
    with pytest.raises(ValueError, match="来源类型与请求类别不一致"):
        ResourceRequestWrite(
            source_type="annotation",
            request_category="translation",
            annotation_project_id=uuid4(),
            request_detail="需要补充标注资源",
        )


def test_resource_request_list_and_count_share_current_project_keyword_filter():
    where_sql, params = _view_filter_sql(keyword=" 新项目名 ", request_status="submitted")

    assert "current_project_name ILIKE :keyword" in where_sql
    assert "source_project_name_snapshot ILIKE :keyword" in where_sql
    assert "c.client_name ILIKE :keyword" in where_sql
    assert "sc.client_name ILIKE :keyword" in where_sql
    assert "request_status = :request_status" in where_sql
    assert params == {"request_status": "submitted", "keyword": "%新项目名%"}


def test_resource_request_allows_empty_detail_for_source_without_requirement_text():
    payload = ResourceRequestWrite(
        source_type="annotation",
        request_category="annotation_trial",
        annotation_project_id=uuid4(),
    )
    assert payload.request_detail == ""


def test_resource_request_prefill_uses_source_specific_detail_and_project_types():
    annotation = SimpleNamespace(potential_demand=" 20 人 ", task_description="标注任务", project_types=["音频标注"])
    recruitment = SimpleNamespace(resource_request="需要英语招聘人员", job_description="职位描述")
    interpretation = SimpleNamespace(resource_request=None, interpreter_special_requirements="同传经验", task_description="会议口译")
    translation = SimpleNamespace(customer_requirement_professional="法律领域", customer_requirement_special="需排版", service_content=None, task_type="笔译")

    assert _source_detail(annotation, "annotation") == "20 人"
    assert _source_detail(recruitment, "recruitment") == "需要英语招聘人员"
    assert _source_detail(interpretation, "interpretation") == "同传经验"
    assert _source_detail(translation, "translation") == "法律领域\n需排版"
    assert _project_type_values(annotation, "annotation") == ["音频标注"]
    assert _project_type_values(recruitment, "recruitment") == ["招聘"]
    assert _project_type_values(translation, "translation") == ["笔译"]


class _PayloadItem:
    def __init__(self, item_id, detail):
        self.id = item_id
        self.detail = detail

    def model_dump(self, exclude=None):
        return {
            "source_language_id": None,
            "target_language_id": None,
            "required_count": 1,
            "requirement_detail": self.detail,
        }


class _FlushRecorder:
    def __init__(self, request):
        self.request = request
        self.snapshots = []

    def flush(self):
        self.snapshots.append([row.sequence_no for row in self.request.items])


def test_resource_request_item_reorder_moves_old_sequences_out_of_the_way():
    first_id, second_id = uuid4(), uuid4()
    first = SimpleNamespace(id=first_id, sequence_no=1)
    second = SimpleNamespace(id=second_id, sequence_no=2)
    request = SimpleNamespace(items=[first, second])
    db = _FlushRecorder(request)

    _sync_items(
        db,
        request,
        [_PayloadItem(second_id, "第二条提前"), _PayloadItem(first_id, "第一条后移")],
    )

    assert db.snapshots == [[-1, -2]]
    assert second.sequence_no == 1
    assert first.sequence_no == 2


def test_annotation_status_update_accepts_confirmed_phase3_statuses():
    payload = AnnotationProjectStatusUpdate(
        project_status="trial_partially_passed",
        effective_on="2026-08-25",
        change_note="部分语种通过",
    )
    assert payload.project_status == "trial_partially_passed"
