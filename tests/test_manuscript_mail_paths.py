from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import manuscript_service
from manuscript_schemas import ManuscriptMailPathsUpdate
from models import ProjectFile, TranslationProject, Translator


class QueryStub:
    def __init__(self, value):
        self.value = value

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return self.value


class DbStub:
    def __init__(self, values):
        self.values = values
        self.committed = False
        self.added = []

    def query(self, model):
        return QueryStub(self.values.get(model))

    def commit(self):
        self.committed = True

    def add(self, value):
        if getattr(value, "id", None) is None:
            value.id = uuid4()
        self.added.append(value)
        self.values[type(value)] = value

    def refresh(self, value):
        return value


def test_mail_preview_returns_paths_but_never_includes_them_in_body():
    project_id = uuid4()
    translator_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        order_no="XS-001",
        project_name="测试项目",
        language_pair="中英",
        customer_requirement_special="术语必须使用客户词库",
        project_status="confirmed",
        customer_deadline_time=None,
        reference_file_path_one=r"\\server\reference",
        network_file_path=r"\\server\legacy-network-path",
    )
    project_file = SimpleNamespace(
        dispatch_path=r"\\server\dispatch",
    )
    translator = SimpleNamespace(
        translator_name="测试译员",
        email1="translator@example.com",
        email2=None,
    )
    arrangement = SimpleNamespace(
        id=uuid4(),
        entity_type="project",
        translation_project_id=project_id,
        sub_order_id=None,
        translator_id=translator_id,
        milestones=[
            SimpleNamespace(
                milestone_type="final",
                name="译员交稿_全稿预定时间",
                sequence_no=1,
                planned_at=datetime(2026, 9, 2, 18, 0),
            )
        ],
        translation_scope=None,
        planned=None,
    )
    db = DbStub({
        TranslationProject: project,
        ProjectFile: project_file,
        Translator: translator,
    })

    preview = manuscript_service._mail_preview_values(db, arrangement)

    assert preview["subject"] == "信实翻译派发稿件 -- 测试译员"
    assert preview["dispatch_path"] == r"\\server\dispatch"
    assert preview["reference_file_path_one"] == r"\\server\reference"
    assert "派稿文路径" not in preview["body"]
    assert "参考文件路径一" not in preview["body"]
    assert r"\\server\dispatch" not in preview["body"]
    assert r"\\server\reference" not in preview["body"]
    assert "全稿预定时间" not in preview["body"]
    assert "客户特殊要求：术语必须使用客户词库" in preview["body"]
    assert "legacy-network-path" not in preview["body"]


def test_mail_preview_omits_empty_paths_and_unplanned_milestones():
    project_id = uuid4()
    translator_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        order_no="XS-002",
        project_name="空值隐藏测试",
        language_pair="中英",
        customer_requirement_special="   ",
        project_status="confirmed",
        customer_deadline_time=None,
        reference_file_path_one=None,
        network_file_path=None,
    )
    project_file = SimpleNamespace(dispatch_path=None)
    translator = SimpleNamespace(
        translator_name="测试译员",
        email1="translator@example.com",
        email2=None,
    )
    arrangement = SimpleNamespace(
        id=uuid4(),
        entity_type="project",
        translation_project_id=project_id,
        sub_order_id=None,
        translator_id=translator_id,
        milestones=[
            SimpleNamespace(
                milestone_type="phase",
                name="译员交稿_预定时间2",
                sequence_no=2,
                planned_at=None,
            ),
            SimpleNamespace(
                milestone_type="final",
                name="译员交稿_全稿预定时间",
                sequence_no=3,
                planned_at=None,
            ),
        ],
        translation_scope=None,
        planned=None,
    )
    db = DbStub({
        TranslationProject: project,
        ProjectFile: project_file,
        Translator: translator,
    })

    preview = manuscript_service._mail_preview_values(db, arrangement)

    assert "派稿文路径" not in preview["body"]
    assert "参考文件路径一" not in preview["body"]
    assert "译员交稿_预定时间2" not in preview["body"]
    assert "译员交稿全稿预定时间" not in preview["body"]
    assert "客户特殊要求" not in preview["body"]


def test_historical_mail_content_strips_internal_paths_and_empty_nodes():
    old_body = """正文开头
译员交稿_预定时间2：待确认
译员交稿_预定时间3：待确认
译员交稿全稿预定时间：待确认
派稿文路径：\\\\Win-server\\dispatch
参考文件路径一：\\\\Win-server\\reference
正文结尾"""
    old_html = """<p>正文开头</p>
<p>译员交稿_预定时间2：待确认</p>
<p>译员交稿_预定时间3：待确认</p>
<p>译员交稿全稿预定时间：待确认</p>
<p>派稿文路径：\\\\Win-server\\dispatch</p>
<p>参考文件路径一：\\\\Win-server\\reference</p>
<p>正文结尾</p>"""

    cleaned_text = manuscript_service._strip_internal_mail_text(old_body)
    cleaned_html = manuscript_service._strip_internal_mail_html(old_html)

    assert cleaned_text == "正文开头\n正文结尾"
    assert cleaned_html == "<p>正文开头</p>\n\n\n\n\n\n<p>正文结尾</p>"


def test_update_mail_paths_writes_back_to_project_detail(monkeypatch):
    monkeypatch.setenv("OPENPATH_ALLOWED_ROOTS", r"\\server\dispatch;\\server\reference")
    project_id = uuid4()
    project_file_id = uuid4()
    dispatch = SimpleNamespace(
        status="ready",
        entity_type="project",
        translation_project_id=project_id,
        sub_order_id=None,
    )
    project = SimpleNamespace(
        id=project_id,
        project_status="confirmed",
        reference_file_path_one=None,
        updated_at=None,
    )
    current_user = SimpleNamespace(id=uuid4())
    project_file = SimpleNamespace(
        id=project_file_id,
        dispatch_path=None,
    )
    db = DbStub({TranslationProject: project, ProjectFile: project_file})
    monkeypatch.setattr(
        manuscript_service,
        "_load_dispatch",
        lambda current_db, dispatch_id: dispatch,
    )
    monkeypatch.setattr(
        manuscript_service,
        "_ensure_can_manage_manuscript",
        lambda current_db, current_project, sub_order, actor: {},
    )

    result = manuscript_service.update_dispatch_mail_paths(
        db,
        uuid4(),
        ManuscriptMailPathsUpdate(
            dispatch_path=r"  \\server\dispatch  ",
            reference_file_path_one=r"  \\server\reference  ",
        ),
        current_user,
    )

    assert project_file.dispatch_path == r"\\server\dispatch"
    assert project.reference_file_path_one == r"\\server\reference"
    assert result["project_file_id"] == project_file_id
    assert db.committed is True


def test_update_mail_paths_creates_project_path_group_when_missing(monkeypatch):
    monkeypatch.setenv("OPENPATH_ALLOWED_ROOTS", r"\\server\dispatch")
    project_id = uuid4()
    dispatch = SimpleNamespace(
        status="ready",
        entity_type="project",
        translation_project_id=project_id,
        sub_order_id=None,
    )
    project = SimpleNamespace(
        id=project_id,
        order_no="XS-003",
        project_name="自动关联测试",
        project_status="confirmed",
        reference_file_path_one=None,
        updated_at=None,
    )
    current_user = SimpleNamespace(id=uuid4())
    db = DbStub({TranslationProject: project, ProjectFile: None})
    monkeypatch.setattr(
        manuscript_service,
        "_load_dispatch",
        lambda current_db, dispatch_id: dispatch,
    )
    monkeypatch.setattr(
        manuscript_service,
        "_ensure_can_manage_manuscript",
        lambda current_db, current_project, sub_order, actor: {},
    )
    monkeypatch.setattr(manuscript_service, "_get_project_file", lambda *args: None)
    monkeypatch.setattr(
        manuscript_service,
        "ProjectFile",
        lambda **values: SimpleNamespace(id=None, **values),
    )

    result = manuscript_service.update_dispatch_mail_paths(
        db,
        uuid4(),
        ManuscriptMailPathsUpdate(dispatch_path=r"\\server\dispatch"),
        current_user,
    )

    assert len(db.added) == 1
    project_file = db.added[0]
    assert project_file.translation_project_id == project_id
    assert project_file.file_name == "XS-003"
    assert project_file.storage_path == ""
    assert project_file.dispatch_path == r"\\server\dispatch"
    assert project_file.uploaded_by == current_user.id
    assert result["project_file_id"] == project_file.id
    assert db.committed is True
