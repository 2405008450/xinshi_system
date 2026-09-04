from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

import annotation_service
import workflow_models  # noqa: F401
from annotation_models import AnnotationProject, AnnotationProjectPriceItem
from annotation_ops_models import AnnotationAccountAssignment, AnnotationCustomFieldImage
from annotation_schemas import (
    AnnotationProjectCreate,
    AnnotationProjectListResponse,
    AnnotationProjectManagersUpdate,
    AnnotationProjectOrderNoUpdate,
    AnnotationProjectPriorityUpdate,
)
from annotation_service import (
    build_annotation_project_name,
    ensure_annotation_project_for_consultation,
    generate_annotation_order_no,
    update_annotation_project_order_no,
)
from interpretation_models import InterpretationProject
from models import TranslationProject
from project_audit_models import ProjectOperationAudit
from project_order_no_models import ProjectOrderNoReservation
from resource_request_models import ResourceRequest


class OrderQuery:
    def __init__(self, value):
        self.value = value

    def filter(self, *_args):
        return self

    def all(self):
        if self.value is None:
            return []
        values = self.value if isinstance(self.value, list) else [self.value]
        return [(value,) for value in values]


class OrderDb:
    def __init__(self, value=None):
        self.value = value

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    def query(self, *_args):
        return OrderQuery(self.value)


def test_annotation_order_number_uses_required_format_and_increments():
    now = datetime(2026, 8, 1, 9)
    assert generate_annotation_order_no(OrderDb(), now) == "AP-260801-001"
    assert generate_annotation_order_no(OrderDb("AP-260801-009"), now) == "AP-260801-010"


def test_annotation_order_number_never_reuses_reserved_sequence():
    now = datetime(2026, 8, 1, 9)
    db = OrderDb(["AP-260801-004", "AP-260801-005", "AP-LEGACY-001"])

    assert generate_annotation_order_no(db, now) == "AP-260801-006"


def test_annotation_order_no_payload_normalizes_and_validates():
    payload = AnnotationProjectOrderNoUpdate(
        new_order_no="  ap-old_2024.001  ", reason="  老系统单号对齐  ",
    )
    assert payload.new_order_no == "AP-OLD_2024.001"
    assert payload.reason == "老系统单号对齐"

    for invalid in ("", "TP-260801-001", "AP-中文", "AP-WITH SPACE"):
        with pytest.raises(ValueError):
            AnnotationProjectOrderNoUpdate(new_order_no=invalid, reason="测试")

    with pytest.raises(ValueError, match="修改原因"):
        AnnotationProjectOrderNoUpdate(new_order_no="AP-OLD-001", reason="  ")


def test_annotation_project_name_lists_first_three_directions():
    assert build_annotation_project_name(
        "测试客户",
        ["audio_annotation", "quality_inspection"],
        ["英文", "粤语→普通话", "日文→中文", "法文→中文"],
        date(2026, 8, 13),
    ) == "【测试客户-20260813-英文、粤语→普通话、日文→中文等方向-音频标注、质检】"


def test_annotation_project_name_stays_empty_without_business_fields():
    assert build_annotation_project_name("", [], [], date(2026, 8, 13)) == ""


def test_annotation_project_list_response_keeps_language_items():
    language_id = uuid4()
    response = AnnotationProjectListResponse.model_validate(
        SimpleNamespace(
            id=uuid4(),
            order_no="AP-260826-001",
            project_status="initial_consultation",
            priority="medium",
            status_effective_on=date(2026, 8, 26),
            language_items=[
                SimpleNamespace(
                    id=uuid4(),
                    source_language_id=language_id,
                    target_language_id=None,
                    sequence_no=1,
                    source_language_label="温州话",
                    target_language_label=None,
                    display="温州话",
                )
            ],
            created_at=datetime(2026, 8, 26, 9),
            updated_at=datetime(2026, 8, 26, 9),
        )
    )

    assert response.language_items[0].source_language_id == language_id
    assert response.language_items[0].display == "温州话"


def test_annotation_project_priority_defaults_to_medium_and_rejects_invalid_value():
    assert AnnotationProjectCreate().priority == "medium"
    assert AnnotationProjectPriorityUpdate(priority="high").priority == "high"

    with pytest.raises(ValueError, match="不支持的标注项目优先次序"):
        AnnotationProjectPriorityUpdate(priority="urgent")


def test_annotation_project_create_accepts_ai_evaluation_type():
    payload = AnnotationProjectCreate(project_types=["ai_evaluation"])

    assert payload.project_types == ["ai_evaluation"]


def test_annotation_project_manager_update_accepts_user_relations_and_clearing():
    client_manager_id = uuid4()
    project_manager_id = uuid4()

    payload = AnnotationProjectManagersUpdate(
        client_manager_id=client_manager_id,
        project_manager_id=project_manager_id,
    )
    assert payload.client_manager_id == client_manager_id
    assert payload.project_manager_id == project_manager_id
    assert AnnotationProjectManagersUpdate().project_manager_id is None


def test_update_annotation_project_managers_persists_role_relation(monkeypatch):
    project_id = uuid4()
    project_manager_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        client_manager_id=None,
        workbench_responsibilities=[],
        updated_at=None,
    )
    assignments_seen = []

    class ManagerDb:
        def commit(self):
            pass

    monkeypatch.setattr(annotation_service, "get_annotation_project", lambda *_args: project)
    monkeypatch.setattr(
        "project_workbench_service.validate_assignment_map",
        lambda _db, assignments: assignments_seen.append(("validate", assignments)),
    )
    monkeypatch.setattr(
        "project_workbench_service.ensure_project_responsibilities",
        lambda _db, project_type, saved_project_id, assignments: assignments_seen.append(
            (project_type, saved_project_id, assignments)
        ),
    )

    result = annotation_service.update_annotation_project_managers(
        ManagerDb(), project_id, None, project_manager_id,
    )

    assert result is project
    assert assignments_seen == [
        ("validate", {"project_manager": project_manager_id}),
        ("annotation", project_id, {"project_manager": project_manager_id}),
    ]


def test_customer_price_summary_shows_amount_only():
    project = AnnotationProject()
    project.price_items = [
        AnnotationProjectPriceItem(
            amount=Decimal("123123"),
            currency="CNY",
            unit="条",
            project_type="audio_annotation",
        ),
        AnnotationProjectPriceItem(
            amount=Decimal("0.15"),
            currency="USD",
            unit="小时",
            project_type="quality_inspection",
        ),
    ]

    assert project.customer_price_summary == "￥123123/条；$0.15/小时"
    assert project.price_items[0].amount_display == "￥123123/条"
    assert project.price_items[1].amount_display == "$0.15/小时"
    assert AnnotationProjectPriceItem(amount=Decimal("8"), unit="条").amount_display == "￥8/条"


def test_price_item_currency_is_optional():
    payload = AnnotationProjectCreate(
        project_types=["audio_annotation"],
        price_items=[{
            "project_type": "audio_annotation",
            "amount": "0.15",
            "unit": "条",
        }],
    )
    assert payload.price_items[0].currency is None

    payload = AnnotationProjectCreate(
        project_types=["audio_annotation"],
        price_items=[{
            "project_type": "audio_annotation",
            "amount": "0.15",
            "currency": "cny",
            "unit": "条",
        }],
    )
    assert payload.price_items[0].currency == "CNY"

    payload = AnnotationProjectCreate(
        project_types=["audio_annotation"],
        price_items=[{
            "project_type": "audio_annotation",
            "amount": "0.15",
            "currency": "usd",
            "unit": "条",
        }],
    )
    assert payload.price_items[0].currency == "USD"

    with pytest.raises(ValueError, match="三位代码"):
        AnnotationProjectCreate(
            project_types=["audio_annotation"],
            price_items=[{
                "project_type": "audio_annotation",
                "amount": "0.15",
                "currency": "US",
                "unit": "条",
            }],
        )


def test_payload_rejects_duplicate_language_and_invalid_price_scope():
    language_id = uuid4()
    with pytest.raises(ValueError, match="不能重复"):
        AnnotationProjectCreate(language_items=[
            {"source_language_id": language_id},
            {"source_language_id": language_id},
        ])

    with pytest.raises(ValueError, match="未选择的项目类型"):
        AnnotationProjectCreate(
            project_types=["audio_annotation"],
            price_items=[{
                "project_type": "quality_inspection",
                "amount": "0.15",
                "currency": "CNY",
                "unit": "条",
            }],
        )


def test_payload_normalizes_annotation_project_paths(monkeypatch):
    monkeypatch.setenv("OPENPATH_ALLOWED_ROOTS", r"\\server\annotation")
    payload = AnnotationProjectCreate(
        project_path=r"  \\server\annotation  ",
        quotation_path="  D:/报价单  ",
        contract_path="   ",
    )

    assert payload.project_path == r"\\server\annotation"
    assert payload.quotation_path == "D:/报价单"
    assert payload.contract_path is None


def test_payload_rejects_submitted_time_before_dispatch():
    with pytest.raises(ValueError, match="提交时间不能早于"):
        AnnotationProjectCreate(
            task_dispatched_at=datetime(2026, 8, 11, 10),
            task_submitted_at=datetime(2026, 8, 11, 9),
        )


class EnsureQuery:
    def __init__(self, db, target):
        self.db = db
        self.target = target

    def filter(self, *_args):
        return self

    def first(self):
        if self.target is AnnotationProject:
            return self.db.annotation_project
        if self.target is InterpretationProject.id:
            return self.db.interpretation_project
        if self.target is TranslationProject:
            return self.db.translation_project
        return None


class EnsureDb:
    def __init__(self):
        self.annotation_project = None
        self.interpretation_project = None
        self.translation_project = None
        self.added = []

    def query(self, target):
        return EnsureQuery(self, target)

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    def add(self, value):
        self.added.append(value)
        if isinstance(value, AnnotationProject):
            self.annotation_project = value

    def flush(self):
        pass


def test_confirmed_annotation_consultation_creation_is_idempotent(monkeypatch):
    db = EnsureDb()
    consultation = SimpleNamespace(
        id=uuid4(), client_id=uuid4(), consultation_time=datetime(2026, 8, 11, 9)
    )
    monkeypatch.setattr(
        "annotation_service.generate_annotation_order_no",
        lambda _db: "AP-260811-001",
    )

    project, created = ensure_annotation_project_for_consultation(
        db, consultation, uuid4()
    )
    same_project, created_again = ensure_annotation_project_for_consultation(
        db, consultation, uuid4()
    )

    assert created is True
    assert created_again is False
    assert project is same_project
    assert project.project_status == "initial_consultation"
    assert len(db.added) == 3
    reservation = next(item for item in db.added if isinstance(item, ProjectOrderNoReservation))
    assert reservation.order_no_key == "AP-260811-001"
    audit = next(item for item in db.added if isinstance(item, ProjectOperationAudit))
    assert audit.operation_type == "create"
    assert audit.order_no == "AP-260811-001"


class OrderNoChangeQuery:
    def __init__(self, db, target):
        self.db = db
        self.target = target

    def filter(self, *_args):
        return self

    def with_for_update(self):
        return self

    def first(self):
        if self.target is AnnotationProject:
            return self.db.project
        if self.target is ProjectOrderNoReservation.id:
            return self.db.existing_reservation
        return None


class OrderNoChangeDb:
    def __init__(self, project, existing_reservation=None):
        self.project = project
        self.existing_reservation = existing_reservation
        self.added = []
        self.commit_count = 0

    def query(self, target):
        return OrderNoChangeQuery(self, target)

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commit_count += 1


def test_update_annotation_order_no_reserves_updates_subject_and_audits(monkeypatch):
    project = AnnotationProject(
        id=uuid4(),
        order_no="AP-260801-001",
        project_name="历史标注项目",
        email_subject_preview="紧急，AP-260801-001，历史标注项目",
        updated_at=datetime(2026, 8, 1, 9),
    )
    db = OrderNoChangeDb(project)
    monkeypatch.setattr(annotation_service, "get_annotation_project", lambda *_args: project)

    result = update_annotation_project_order_no(
        db,
        project.id,
        "ap-old-001",
        "老系统单号对齐",
        datetime(2026, 8, 1, 9),
        uuid4(),
    )

    assert result is project
    assert project.order_no == "AP-OLD-001"
    assert project.email_subject_preview == "紧急，AP-OLD-001，历史标注项目"
    assert db.commit_count == 1
    reservation = next(item for item in db.added if isinstance(item, ProjectOrderNoReservation))
    assert reservation.order_no_key == "AP-OLD-001"
    audit = next(item for item in db.added if isinstance(item, ProjectOperationAudit))
    assert audit.operation_type == "order_no_change"
    assert audit.previous_order_no == "AP-260801-001"
    assert audit.order_no == "AP-OLD-001"
    assert audit.change_reason == "老系统单号对齐"


def test_update_annotation_order_no_rejects_current_or_historical_conflict(monkeypatch):
    project = AnnotationProject(
        id=uuid4(), order_no="AP-260801-001", updated_at=datetime(2026, 8, 1, 9),
    )
    db = OrderNoChangeDb(project, existing_reservation=(uuid4(),))
    monkeypatch.setattr(annotation_service, "get_annotation_project", lambda *_args: project)

    with pytest.raises(annotation_service.AnnotationOrderNoConflict, match="历史标注项目"):
        update_annotation_project_order_no(
            db, project.id, "AP-OLD-001", "测试冲突", None, uuid4(),
        )

    assert project.order_no == "AP-260801-001"
    assert db.commit_count == 0


class DeleteQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class DeleteDb:
    def __init__(self, project, *, resource_requests=None, assignments=None, images=None):
        self.project = project
        self.resource_requests = resource_requests or []
        self.assignments = assignments or []
        self.images = images or []
        self.deleted = []
        self.flush_count = 0
        self.commit_count = 0

    def query(self, target):
        if target is AnnotationProject:
            return DeleteQuery([self.project] if self.project else [])
        if target is ResourceRequest:
            return DeleteQuery(self.resource_requests)
        if target is AnnotationAccountAssignment:
            return DeleteQuery(self.assignments)
        if target is AnnotationCustomFieldImage.storage_name:
            return DeleteQuery([(value,) for value in self.images])
        raise AssertionError(f"未处理的删除测试查询：{target}")

    def delete(self, value):
        self.deleted.append(value)

    def flush(self):
        self.flush_count += 1

    def commit(self):
        self.commit_count += 1


def _patch_annotation_delete_side_effects(monkeypatch, cleaned_images):
    monkeypatch.setattr(annotation_service, "record_project_operation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "project_workbench_service.cancel_pending_project_handovers",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        annotation_service,
        "delete_custom_field_image_files",
        lambda values: cleaned_images.extend(values),
    )


def test_delete_annotation_project_blocks_active_account_assignment(monkeypatch):
    project = SimpleNamespace(id=uuid4(), order_no="AP-260817-001")
    assignment = SimpleNamespace(
        id=uuid4(),
        released_on=None,
        account=SimpleNamespace(
            nickname="测试账号",
            platform=SimpleNamespace(platform_name="测试平台"),
        ),
    )
    db = DeleteDb(project, assignments=[assignment])
    _patch_annotation_delete_side_effects(monkeypatch, [])

    with pytest.raises(
        annotation_service.AnnotationProjectDeleteConflict,
        match="未释放的标注账号分配 1 条（测试平台 / 测试账号）",
    ):
        annotation_service.delete_annotation_project(db, project.id)

    assert db.deleted == []
    assert db.commit_count == 0


def test_delete_annotation_project_blocks_resource_requests(monkeypatch):
    project = SimpleNamespace(id=uuid4(), order_no="AP-260817-002")
    request = SimpleNamespace(request_no="RR-260817-001")
    db = DeleteDb(project, resource_requests=[request])
    _patch_annotation_delete_side_effects(monkeypatch, [])

    with pytest.raises(
        annotation_service.AnnotationProjectDeleteConflict,
        match="关联资源需求 1 条（RR-260817-001）",
    ):
        annotation_service.delete_annotation_project(db, project.id)

    assert db.deleted == []
    assert db.commit_count == 0


def test_delete_annotation_project_cleans_released_assignment_and_image_files(monkeypatch):
    project = SimpleNamespace(id=uuid4(), order_no="AP-260817-003")
    assignment = SimpleNamespace(id=uuid4(), released_on=date(2026, 8, 30))
    db = DeleteDb(project, assignments=[assignment], images=["project-image.png"])
    cleaned_images = []
    _patch_annotation_delete_side_effects(monkeypatch, cleaned_images)

    assert annotation_service.delete_annotation_project(db, project.id) is True

    assert db.deleted == [assignment, project]
    assert db.flush_count == 1
    assert db.commit_count == 1
    assert cleaned_images == ["project-image.png"]
