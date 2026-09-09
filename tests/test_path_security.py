import pytest

from annotation_schemas import AnnotationProjectWrite
from interpretation_schemas import InterpretationProjectWrite
from manuscript_schemas import ManuscriptMailPathsUpdate
from recruitment_schemas import RecruitmentCandidateCreate, RecruitmentProjectCreate
from schemas import TranslationProjectCreate


@pytest.fixture(autouse=True)
def allowed_roots(monkeypatch):
    monkeypatch.setenv("OPENPATH_ALLOWED_ROOTS", r"\\fileserver\projects;\\fileserver\resumes")


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (AnnotationProjectWrite, {"project_path": r"\\attacker.example\share\payload.exe"}),
        (InterpretationProjectWrite, {"file_path": r"\\attacker.example\share\payload.exe"}),
        (RecruitmentProjectCreate, {"project_path": r"\\attacker.example\share\payload.exe"}),
        (RecruitmentCandidateCreate, {"resume_path": r"\\attacker.example\share\payload.exe"}),
        (ManuscriptMailPathsUpdate, {"dispatch_path": r"\\attacker.example\share\payload.exe"}),
        (TranslationProjectCreate, {"project_name": "安全测试", "network_file_path": r"\\attacker.example\share\payload.exe"}),
    ],
)
def test_write_schemas_reject_untrusted_unc_paths(model, payload):
    with pytest.raises(ValueError, match="不在企业允许"):
        model.model_validate(payload)


def test_rejects_traversal_inside_allowed_root():
    with pytest.raises(ValueError, match="路径穿越"):
        ManuscriptMailPathsUpdate(dispatch_path=r"\\fileserver\projects\safe\..\secret.txt")


@pytest.mark.parametrize("path", [
    r"\\fileserver\projects\payload.exe",
    r"\\fileserver\projects\payload.lnk",
])
def test_rejects_dangerous_file_inside_allowed_root(path):
    with pytest.raises(ValueError, match="禁止保存"):
        ManuscriptMailPathsUpdate(dispatch_path=path)


def test_accepts_normal_document_inside_allowed_root():
    model = ManuscriptMailPathsUpdate(dispatch_path=r"\\fileserver\projects\客户A\source.docx")
    assert model.dispatch_path == r"\\fileserver\projects\客户A\source.docx"


def test_accepts_cloud_saved_path_without_checking_share_reachability(monkeypatch):
    monkeypatch.setenv(
        "OPENPATH_ALLOWED_ROOTS",
        r"\\Win-server\服务器资料7;\\Win-server\服务器资料4",
    )
    project_path = (
        r"\\Win-server\服务器资料7\客户\其他客户翻译任务\2026年\9月"
        r"\连云港亚新钢铁\0908\3. 译文\沙柏霖"
    )

    model = AnnotationProjectWrite(project_path=project_path)

    assert model.project_path == project_path


def test_rejects_similar_but_unapproved_share_root(monkeypatch):
    monkeypatch.setenv("OPENPATH_ALLOWED_ROOTS", r"\\Win-server\服务器资料7")

    with pytest.raises(ValueError, match="不在企业允许"):
        AnnotationProjectWrite(project_path=r"\\Win-server\服务器资料70\客户\项目")
