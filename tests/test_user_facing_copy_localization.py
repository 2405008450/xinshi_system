import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

BACKEND_USER_MESSAGE_FILES = [
    ROOT / "project_chat_crud.py",
    ROOT / "workflow_crud.py",
    *(ROOT / "routers").glob("*.py"),
]

DENIED_BACKEND_PHRASES = (
    "Client not found",
    "Sub client not found",
    "Client contact not found",
    "Consultation not found",
    "Notification not found",
    "Project not found",
    "Role name already exists",
    "Role not found",
    "Translator not found",
    "User not found",
    "Username already registered",
    "User role already exists",
    "User role not found",
    "Workflow not initialized",
    "Workflow not found",
    "Could not validate credentials",
    "Path ID and Body ID mismatch",
    "Database integrity error",
    "Database error",
    "Unexpected error",
    "Message content or attachment is required",
    "You do not have permission",
)


def test_known_backend_user_messages_do_not_regress_to_english():
    source = "\n".join(path.read_text(encoding="utf-8") for path in BACKEND_USER_MESSAGE_FILES)
    found = [phrase for phrase in DENIED_BACKEND_PHRASES if phrase in source]
    assert found == []


def test_database_exception_details_are_not_interpolated_into_responses():
    unsafe_patterns = (
        re.compile(r"detail\s*=\s*f?[\"'][^\n]*error_msg"),
        re.compile(r"detail\s*=\s*str\((?:exc|e)\.orig\)"),
    )
    violations = []
    for path in (ROOT / "routers").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern in unsafe_patterns:
            if pattern.search(source):
                violations.append(f"{path.name}: {pattern.pattern}")
    assert violations == []


def test_consultation_form_does_not_generate_automatic_english_required_rules():
    source = (ROOT / "frontend/src/views/client/Consultations.vue").read_text(encoding="utf-8")
    prop_required = re.compile(
        r"<el-form-item(?=[^>]*\bprop=)(?=[^>]*\s(?::?required)(?:\s|=|>))[^>]*>"
    )
    assert prop_required.search(source) is None
    assert "message: '请输入地点'" in source
    assert "message: '请至少添加一个预定时段'" in source
    assert "message: '请至少添加一个口译方向'" in source


def test_frontend_has_global_chinese_validation_and_error_guards():
    validation_source = (ROOT / "frontend/src/utils/validationLocale.js").read_text(encoding="utf-8")
    error_source = (ROOT / "frontend/src/utils/errorMessages.js").read_text(encoding="utf-8")
    api_source = (ROOT / "frontend/src/api/index.js").read_text(encoding="utf-8")

    assert "required: '此项为必填项'" in validation_source
    assert "installChineseMessageGuard" in error_source
    assert "rawDetail" in error_source
    assert "normalizeApiError(error)" in api_source
    assert "loc.filter" not in api_source


def test_user_message_code_does_not_read_raw_error_text_directly():
    violations = []
    for path in (ROOT / "frontend/src").rglob("*"):
        if path.suffix not in {".vue", ".js", ".ts"} or path.name == "errorMessages.js":
            continue
        source = path.read_text(encoding="utf-8")
        if re.search(r"response\??\.data\??\.detail", source) or re.search(
            r"\b(?:error|err)\??\.message\b", source
        ):
            violations.append(str(path.relative_to(ROOT)))
    assert violations == []
