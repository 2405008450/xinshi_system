from pathlib import Path

from deploy.prepare_cloud_env import prepare_cloud_env, read_env


ALLOWED_ROOTS = r"\\Win-server\服务器资料7;\\Win-server\服务器资料4"


def test_prepare_cloud_env_preserves_explicit_path_policy(tmp_path: Path):
    source = tmp_path / ".env.source"
    target = tmp_path / ".env"
    source.write_text(
        "EXISTING_VALUE=保留\n"
        f"OPENPATH_ALLOWED_ROOTS={ALLOWED_ROOTS}\n"
        f"VITE_OPENPATH_ALLOWED_ROOTS={ALLOWED_ROOTS}\n",
        encoding="utf-8",
    )

    values = prepare_cloud_env(source, target)
    written = read_env(target)

    assert values["OPENPATH_ALLOWED_ROOTS"] == ALLOWED_ROOTS
    assert values["VITE_OPENPATH_ALLOWED_ROOTS"] == ALLOWED_ROOTS
    assert written["OPENPATH_ALLOWED_ROOTS"] == ALLOWED_ROOTS
    assert written["VITE_OPENPATH_ALLOWED_ROOTS"] == ALLOWED_ROOTS
    assert written["EXISTING_VALUE"] == "保留"
    assert not source.exists()


def test_prepare_cloud_env_emits_empty_path_policy_when_not_provided(tmp_path: Path):
    source = tmp_path / ".env.source"
    target = tmp_path / ".env"
    source.write_text("APP_ENV=development\n", encoding="utf-8")

    prepare_cloud_env(source, target)
    written = read_env(target)

    assert written["OPENPATH_ALLOWED_ROOTS"] == ""
    assert written["VITE_OPENPATH_ALLOWED_ROOTS"] == ""
