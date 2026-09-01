import manuscript_service
from mail_service import SmtpSettings


def test_manuscript_service_uses_dedicated_smtp_settings(monkeypatch):
    """稿件安排不得依赖个人邮箱解析服务。"""
    dedicated_settings = object()
    monkeypatch.setattr(
        manuscript_service.SmtpSettings,
        "from_env",
        lambda: dedicated_settings,
    )

    assert not hasattr(manuscript_service, "resolve_project_sender")
    assert manuscript_service.SmtpSettings is SmtpSettings
    assert manuscript_service._manuscript_smtp_settings() is dedicated_settings
