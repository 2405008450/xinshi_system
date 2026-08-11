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

    def query(self, model):
        return QueryStub(self.values.get(model))

    def commit(self):
        self.committed = True

    def refresh(self, value):
        return value


def test_mail_preview_uses_project_file_dispatch_path():
    project_id = uuid4()
    translator_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        order_no="XS-001",
        project_name="测试项目",
        language_pair="中英",
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
        milestones=[],
        translation_scope=None,
        planned=None,
    )
    db = DbStub({
        TranslationProject: project,
        ProjectFile: project_file,
        Translator: translator,
    })

    preview = manuscript_service._mail_preview_values(db, arrangement)

    assert preview["dispatch_path"] == r"\\server\dispatch"
    assert "派稿文路径：\\\\server\\dispatch" in preview["body"]
    assert "legacy-network-path" not in preview["body"]


def test_update_mail_paths_writes_back_to_project_detail(monkeypatch):
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
