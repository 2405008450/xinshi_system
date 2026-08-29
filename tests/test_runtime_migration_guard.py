import sys
from types import SimpleNamespace

import pytest

from tools import run_runtime_migrations


def test_migration_rejects_production_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOCAL_SCHEMA_MIGRATIONS_ENABLED", "true")

    with pytest.raises(RuntimeError, match="APP_ENV=development"):
        run_runtime_migrations.require_local_migration_environment()


def test_migration_requires_explicit_local_authorization(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("LOCAL_SCHEMA_MIGRATIONS_ENABLED", raising=False)

    with pytest.raises(RuntimeError, match="LOCAL_SCHEMA_MIGRATIONS_ENABLED=true"):
        run_runtime_migrations.require_local_migration_environment()


def test_migration_tool_calls_migration_only_when_locally_authorized(monkeypatch):
    called = []
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("LOCAL_SCHEMA_MIGRATIONS_ENABLED", "true")
    monkeypatch.setitem(
        sys.modules,
        "main",
        SimpleNamespace(run_runtime_migrations=lambda: called.append(True)),
    )

    run_runtime_migrations.main()

    assert called == [True]
