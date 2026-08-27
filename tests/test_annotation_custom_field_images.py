import datetime as dt
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from openpyxl import Workbook
from pydantic import ValidationError

import annotation_account_import_service as import_service
import annotation_custom_field_image_service as image_service
from annotation_custom_field_image_service import (
    MAX_IMAGE_BYTES,
    normalize_image_value,
    sync_assignment_image_links,
    validate_image_content,
)
from annotation_ops_models import (
    AnnotationAccountAssignmentImage,
    AnnotationCustomFieldDefinition,
    AnnotationCustomFieldImage,
)
from annotation_ops_schemas import CustomFieldWrite


class _Query:
    def __init__(self, rows=None, first=None):
        self.rows = list(rows or [])
        self.first_value = first

    def filter(self, *_conditions):
        return self

    def outerjoin(self, *_args, **_kwargs):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.first_value


class _ImageValueDb:
    def __init__(self, image, *, linked=False):
        self.image = image
        self.linked = linked

    def get(self, model, value):
        if model is AnnotationCustomFieldImage and value == self.image.id:
            return self.image
        return None

    def query(self, *_entities):
        return _Query(first=(uuid4(),) if self.linked else None)


def _definition(project_id=None):
    return SimpleNamespace(
        id=uuid4(),
        project_id=project_id or uuid4(),
        table_code="account_assignment",
        data_type="image",
        field_label="账号截图",
        is_active=True,
    )


def test_image_type_is_limited_to_project_account_fields():
    project_id = uuid4()
    payload = CustomFieldWrite(
        project_id=project_id,
        table_code="account_assignment",
        field_key="account_screenshot",
        field_label="账号截图",
        data_type="image",
        is_required=True,
    )
    assert payload.data_type == "image"

    with pytest.raises(ValidationError, match="图片字段仅支持项目账号表"):
        CustomFieldWrite(
            table_code="account",
            field_key="account_screenshot",
            field_label="账号截图",
            data_type="image",
        )

    type_constraint = next(
        item for item in AnnotationCustomFieldDefinition.__table__.constraints
        if item.name == "ck_annotation_custom_field_type"
    )
    assert "data_type = 'image' AND table_code = 'account_assignment'" in str(type_constraint.sqltext)


@pytest.mark.parametrize(
    ("content_type", "content"),
    [
        ("image/jpeg", b"\xff\xd8\xff\xe0jpeg"),
        ("image/png", b"\x89PNG\r\n\x1a\npng"),
        ("image/gif", b"GIF89agif"),
        ("image/webp", b"RIFF\x04\x00\x00\x00WEBPwebp"),
    ],
)
def test_image_signature_validation_accepts_supported_formats(content_type, content):
    assert validate_image_content(content, content_type) == content_type


@pytest.mark.parametrize(
    ("content_type", "content", "message"),
    [
        ("image/svg+xml", b"<svg/>", "仅支持"),
        ("image/png", b"", "内容为空"),
        ("image/png", b"not-a-png", "不匹配"),
    ],
)
def test_image_signature_validation_rejects_unsafe_content(content_type, content, message):
    with pytest.raises(ValueError, match=message):
        validate_image_content(content, content_type)


def test_image_signature_validation_rejects_oversized_file():
    with pytest.raises(ValueError, match="10MB"):
        validate_image_content(b"x" * (MAX_IMAGE_BYTES + 1), "image/jpeg")


def test_image_value_rejects_cross_project_cross_field_and_foreign_pending_upload():
    owner_id, other_user_id = uuid4(), uuid4()
    definition = _definition()
    image = SimpleNamespace(
        id=uuid4(),
        project_id=definition.project_id,
        field_definition_id=definition.id,
        uploaded_by=owner_id,
    )
    db = _ImageValueDb(image)

    assert normalize_image_value(
        db, definition, definition.project_id, image.id, user_id=owner_id
    ) == str(image.id)

    with pytest.raises(ValueError, match="不属于当前项目或字段"):
        normalize_image_value(db, definition, uuid4(), image.id, user_id=owner_id)

    image.field_definition_id = uuid4()
    with pytest.raises(ValueError, match="不属于当前项目或字段"):
        normalize_image_value(db, definition, definition.project_id, image.id, user_id=owner_id)
    image.field_definition_id = definition.id

    with pytest.raises(ValueError, match="不属于当前用户"):
        normalize_image_value(db, definition, definition.project_id, image.id, user_id=other_user_id)

    linked_db = _ImageValueDb(image, linked=True)
    assert normalize_image_value(
        linked_db, definition, definition.project_id, image.id, user_id=other_user_id
    ) == str(image.id)


def test_assignment_image_link_is_replaced_or_removed_without_making_image_globally_unique():
    assignment_id, project_id, field_id = uuid4(), uuid4(), uuid4()
    old_image_id, new_image_id = uuid4(), uuid4()
    definition = SimpleNamespace(id=field_id)
    link = SimpleNamespace(
        assignment_id=assignment_id,
        field_definition_id=field_id,
        image_id=old_image_id,
    )

    class Db:
        def __init__(self):
            self.queries = [_Query(rows=[definition]), _Query(rows=[link])]
            self.added = []
            self.deleted = []

        def query(self, *_entities):
            return self.queries.pop(0)

        def add(self, value):
            self.added.append(value)

        def delete(self, value):
            self.deleted.append(value)

    replace_db = Db()
    sync_assignment_image_links(
        replace_db, assignment_id, project_id, {str(field_id): str(new_image_id)}
    )
    assert link.image_id == new_image_id
    assert replace_db.deleted == []

    clear_db = Db()
    sync_assignment_image_links(clear_db, assignment_id, project_id, {str(field_id): None})
    assert clear_db.deleted == [link]

    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in AnnotationAccountAssignmentImage.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("assignment_id", "field_definition_id") in unique_columns
    assert ("image_id",) not in unique_columns


def test_xlsx_preview_rejects_image_mapping_and_required_image_field(monkeypatch):
    project_id, platform_id, field_id = uuid4(), uuid4(), uuid4()
    workbook = Workbook()
    workbook.active.append(["账号截图"])
    workbook.active.append(["不应作为图片导入"])
    image_field = SimpleNamespace(
        id=field_id,
        field_key="account_screenshot",
        field_label="账号截图",
        data_type="image",
        is_active=True,
        is_required=False,
    )
    monkeypatch.setattr(import_service, "_load_workbook", lambda _content: workbook)
    monkeypatch.setattr(
        import_service,
        "_validate_defaults",
        lambda _db, _defaults: (None, project_id, platform_id, None),
    )
    monkeypatch.setattr(import_service, "list_custom_fields", lambda *_args, **_kwargs: [image_field])

    with pytest.raises(ValueError, match="图片字段不支持通过 XLSX"):
        import_service.parse_import_payload(
            SimpleNamespace(),
            b"xlsx",
            {},
            mapping=[{"index": 0, "target": "custom", "fieldId": str(field_id)}],
        )

    image_field.is_required = True
    with pytest.raises(ValueError, match="必填图片字段"):
        import_service.parse_import_payload(
            SimpleNamespace(),
            b"xlsx",
            {},
            mapping=[{"index": 0, "target": "ignore"}],
        )


def test_startup_cleanup_removes_expired_database_and_untracked_files(monkeypatch, tmp_path):
    expired = SimpleNamespace(storage_name="expired.png")
    tracked = tmp_path / "tracked.png"
    expired_path = tmp_path / expired.storage_name
    old_untracked = tmp_path / "old-untracked.png"
    recent_untracked = tmp_path / "recent-untracked.png"
    for path in (tracked, expired_path, old_untracked, recent_untracked):
        path.write_bytes(b"image")
    old_timestamp = (dt.datetime.now() - dt.timedelta(hours=25)).timestamp()
    os.utime(old_untracked, (old_timestamp, old_timestamp))

    class CleanupDb:
        def __init__(self):
            self.deleted = []
            self.committed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def query(self, entity):
            if entity is AnnotationCustomFieldImage:
                return _Query(rows=[expired])
            return _Query(rows=[("tracked.png",)])

        def delete(self, value):
            self.deleted.append(value)

        def commit(self):
            self.committed = True

    db = CleanupDb()
    monkeypatch.setattr(image_service, "get_custom_field_image_dir", lambda: tmp_path)
    monkeypatch.setattr(image_service, "Session", lambda _engine: db)

    image_service.cleanup_orphan_custom_field_images()

    assert db.deleted == [expired]
    assert db.committed is True
    assert not expired_path.exists()
    assert not old_untracked.exists()
    assert tracked.exists()
    assert recent_untracked.exists()
