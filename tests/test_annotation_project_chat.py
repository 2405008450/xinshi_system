from types import SimpleNamespace
from pathlib import Path
from uuid import uuid4

import pytest

import annotation_ops_models  # noqa: F401  # 注册标注关联模型，供 SQLAlchemy 完成 mapper 配置
import project_chat_crud
from models import ChatProjectMessage, ChatProjectMessageFavorite
from schemas import AnnotationProjectChatMessageCreate, ProjectChatMessageCreate


def test_chat_message_model_accepts_exactly_one_project_type():
    constraint_names = {item.name for item in ChatProjectMessage.__table__.constraints}
    index_names = {item.name for item in ChatProjectMessage.__table__.indexes}

    assert "ck_chat_project_message_exactly_one_project" in constraint_names
    assert "ix_chat_project_message_annotation_created_at" in index_names
    assert ChatProjectMessage.__table__.c.project_id.nullable is True
    assert ChatProjectMessage.__table__.c.annotation_project_id.nullable is True


def test_annotation_chat_routes_are_registered():
    source = (Path(__file__).resolve().parents[1] / "routers/project_chat.py").read_text(encoding="utf-8")

    assert "@router.get('/annotation/{project_id}/messages'" in source
    assert "@router.post('/annotation/{project_id}/messages'" in source
    assert "@router.put('/messages/{message_id}/favorite'" in source
    assert "@router.delete('/messages/{message_id}/favorite'" in source


def test_chat_favorite_model_is_private_unique_and_cascades():
    constraint_names = {item.name for item in ChatProjectMessageFavorite.__table__.constraints}
    foreign_keys = {item.name: item for item in ChatProjectMessageFavorite.__table__.foreign_key_constraints}

    assert "uq_chat_project_message_favorite_message_user" in constraint_names
    assert foreign_keys["fk_chat_project_message_favorite_message"].ondelete == "CASCADE"
    assert foreign_keys["fk_chat_project_message_favorite_user"].ondelete == "CASCADE"


def test_annotation_chat_request_has_no_rich_text_or_attachment_fields():
    payload = AnnotationProjectChatMessageCreate(content="纯文本留言")

    assert payload.content == "纯文本留言"
    assert set(payload.model_fields_set) == {"content"}
    with pytest.raises(Exception):
        AnnotationProjectChatMessageCreate(content="")
    with pytest.raises(Exception):
        AnnotationProjectChatMessageCreate(content="纯文本", attachment_ids=[uuid4()])


def test_chat_request_accepts_multiple_mentions_and_limits_twenty():
    user_ids = [uuid4() for _ in range(20)]
    payload = ProjectChatMessageCreate(content="多人提醒", mentioned_user_ids=user_ids)

    assert payload.mentioned_user_ids == user_ids
    with pytest.raises(Exception):
        ProjectChatMessageCreate(content="超出上限", mentioned_user_ids=[uuid4() for _ in range(21)])


def test_mention_normalization_deduplicates_and_excludes_sender():
    sender_id = uuid4()
    first_user_id = uuid4()
    legacy_user_id = uuid4()

    result = project_chat_crud._normalize_mentioned_user_ids(
        sender_id,
        mentioned_user_id=legacy_user_id,
        mentioned_user_ids=[first_user_id, sender_id, first_user_id],
    )

    assert result == [first_user_id, legacy_user_id]


def test_annotation_chat_saves_plain_text_and_only_notifies_mentioned_user(monkeypatch):
    project_id = uuid4()
    sender = SimpleNamespace(id=uuid4(), full_name="发送人", username="sender")
    mentioned = SimpleNamespace(id=uuid4(), full_name="被提醒人", username="mentioned")
    project = SimpleNamespace(id=project_id, order_no="AP-260908-001", project_name="语音标注")
    saved = {}

    class Query:
        def __init__(self, model):
            self.model = model

        def options(self, *_args):
            return self

        def filter(self, *_args):
            return self

        def first(self):
            return saved["message"]

        def all(self):
            return [mentioned] if self.model.__name__ == "AppUser" else []

    class FakeDb:
        def get(self, _model, entity_id):
            return project if entity_id == project_id else None

        def query(self, model):
            return Query(model)

        def add(self, value):
            if isinstance(value, ChatProjectMessage):
                saved["message"] = value

        def add_all(self, values):
            saved.setdefault("related", []).extend(values)

        def flush(self):
            saved["message"].id = uuid4()

        def commit(self):
            return None

    notifications = []
    monkeypatch.setattr(
        project_chat_crud,
        "create_notifications_for_users",
        lambda _db, **kwargs: notifications.append(kwargs) or [],
    )
    monkeypatch.setattr(project_chat_crud, "_push_notifications", lambda _items: None)

    message = project_chat_crud.create_annotation_project_chat_message(
        FakeDb(),
        annotation_project_id=project_id,
        sender=sender,
        content="  当前正在补充数据  ",
        mentioned_user_id=mentioned.id,
    )

    assert message.project_id is None
    assert message.annotation_project_id == project_id
    assert message.content == "当前正在补充数据"
    assert message.content_json is None
    assert len(saved["related"]) == 1
    assert saved["related"][0].mentioned_user_id == mentioned.id
    assert notifications == [{
        "recipient_user_ids": [mentioned.id],
        "title": "标注项目沟通提醒",
        "content": "发送人 在标注项目 AP-260908-001 / 语音标注 中 @了你：当前正在补充数据",
        "notification_type": "annotation_project_chat_mention",
        "related_project_type": "annotation",
        "related_entity_id": project_id,
        "commit": True,
    }]


def test_annotation_chat_rejects_blank_message():
    project_id = uuid4()
    db = SimpleNamespace(get=lambda *_args: SimpleNamespace(id=project_id))
    sender = SimpleNamespace(id=uuid4(), full_name="发送人", username="sender")

    with pytest.raises(ValueError, match="消息内容不能为空"):
        project_chat_crud.create_annotation_project_chat_message(
            db,
            annotation_project_id=project_id,
            sender=sender,
            content="   ",
        )


def test_mention_creation_rejects_inactive_or_missing_user():
    sender = SimpleNamespace(id=uuid4())
    message = SimpleNamespace(id=uuid4())
    missing_user_id = uuid4()

    class EmptyQuery:
        def filter(self, *_args):
            return self

        def all(self):
            return []

    db = SimpleNamespace(query=lambda *_args: EmptyQuery())
    with pytest.raises(ValueError, match="不存在或已停用"):
        project_chat_crud._create_chat_mentions(
            db,
            message,
            sender,
            mentioned_user_ids=[missing_user_id],
        )
