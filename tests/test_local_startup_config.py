import json

import pytest

from tools.local_startup_config import startup_config


def test_approved_remote_database_target_does_not_expose_credentials():
    result = startup_config({"DATABASE_URL": "postgresql+psycopg2://private_user:private_password@43.132.156.72:15432/xinshi_system"})
    assert result["database_host"] == "43.132.156.72"
    assert result["database_port"] == 15432
    assert result["database_name"] == "xinshi_system"
    assert "private_user" not in json.dumps(result)
    assert "private_password" not in json.dumps(result)


def test_database_url_has_priority_over_db_fields():
    result = startup_config({"DATABASE_URL": "sqlite://", "DB_HOST": "ignored"})
    assert result["database_driver"] == "sqlite"


@pytest.mark.parametrize("enabled", ["true", "1", "YES"])
def test_running_service_rejects_migration_switch(enabled):
    with pytest.raises(ValueError, match="常驻服务"):
        startup_config({"DATABASE_URL": "sqlite://", "LOCAL_SCHEMA_MIGRATIONS_ENABLED": enabled})


def test_custom_shared_paths_replace_defaults():
    result = startup_config({"DATABASE_URL": "sqlite://", "OPENPATH_ALLOWED_ROOTS": " \\\\server\\one ; \\\\server\\two "})
    assert result["share_paths"] == [r"\\server\one", r"\\server\two"]


def test_db_fields_and_default_shared_paths():
    result = startup_config({"DB_PASSWORD": "private_password", "DB_HOST": "43.132.156.72", "DB_PORT": "15432"})
    assert result["database_port"] == 15432
    assert result["share_paths"] == [r"\\Win-server\服务器资料7", r"\\Win-server\服务器资料4"]
