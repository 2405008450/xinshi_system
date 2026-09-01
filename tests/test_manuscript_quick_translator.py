from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

import manuscript_service
from manuscript_schemas import ManuscriptQuickTranslatorCreate
from models import Translator


class _QueryStub:
    def __init__(self, existing=None):
        self.existing = existing

    def filter(self, *_args):
        return self

    def first(self):
        return self.existing


class _DbStub:
    def __init__(self, existing=None):
        self.existing = existing

    def query(self, model):
        assert model is Translator
        return _QueryStub(self.existing)


def _payload(**changes):
    values = {
        "translator_name": " 新译员 ",
        "email": "NEW@example.com",
        "languages": " 中英 ",
        "cooperation_type": "兼职",
    }
    values.update(changes)
    return ManuscriptQuickTranslatorCreate(**values)


def test_quick_translator_requires_name_email_and_languages():
    with pytest.raises(ValidationError):
        ManuscriptQuickTranslatorCreate(
            translator_name="",
            email="not-an-email",
            languages="",
        )


def test_quick_translator_creates_written_profile_and_normalizes_email(monkeypatch):
    captured = {}
    created = SimpleNamespace(
        id=uuid4(), translator_code=None, translator_name="新译员",
        cooperation_type="兼职", status="standby", languages="中英",
        translation_type="笔译", direction=None, quality_score=None,
        email1="new@example.com", email2=None, available_time_slot=None,
        daily_word_capacity=None, can_cloud_edit=None, can_revision=None,
        domain_skills=[], remarks=None,
    )

    def fake_create(_db, values):
        captured.update(values.model_dump())
        return created

    monkeypatch.setattr(manuscript_service, "create_translator_record", fake_create)

    result = manuscript_service.create_quick_translator(_DbStub(), _payload())

    assert captured["translator_name"] == "新译员"
    assert captured["email1"] == "new@example.com"
    assert captured["translation_type"] == "笔译"
    assert captured["status"] == "standby"
    assert result["id"] == created.id


def test_quick_translator_rejects_existing_email():
    existing = SimpleNamespace(translator_name="已有译员")

    with pytest.raises(ValueError, match="请直接搜索并选择"):
        manuscript_service.create_quick_translator(_DbStub(existing), _payload())
