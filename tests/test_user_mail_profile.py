from types import SimpleNamespace

from user_mail_profile_service import (
    active_signature,
    append_signature,
    recipient_display_name,
    sanitize_signature_html,
)


def test_recipient_display_name_prefers_database_profile_and_falls_back():
    user = SimpleNamespace(full_name="彭舒婷", username="shuting")
    profile = SimpleNamespace(recipient_display_name="信实翻译-HR专员彭舒婷")

    assert recipient_display_name(user, profile) == "信实翻译-HR专员彭舒婷"
    assert recipient_display_name(user, None) == "彭舒婷"


def test_signature_sanitizer_keeps_basic_formatting_and_safe_color():
    safe_html, plain_text = sanitize_signature_html(
        '<p>Best wishes!</p><p><strong>李娴 Tokito</strong></p>'
        '<p><span style="color:#2563eb;font-size:30px">项目经理丨信实翻译公司</span></p>'
        '<script>alert(1)</script><a href="javascript:alert(1)">危险链接</a>'
    )

    assert "<strong>李娴 Tokito</strong>" in safe_html
    assert '<span style="color:#2563eb;">项目经理丨信实翻译公司</span>' in safe_html
    assert "font-size" not in safe_html
    assert "<script" not in safe_html
    assert "javascript:" not in safe_html
    assert "alert(1)" in plain_text
    assert "李娴 Tokito" in plain_text


def test_signature_sanitizer_keeps_only_safe_links():
    safe_html, _plain_text = sanitize_signature_html(
        '<a href="https://www.xinshify.com.cn">官网</a>'
        '<a href="mailto:test@xinshifanyi.com.cn">邮箱</a>'
    )

    assert 'href="https://www.xinshify.com.cn"' in safe_html
    assert 'href="mailto:test@xinshifanyi.com.cn"' in safe_html
    assert safe_html.count('rel="noopener noreferrer"') == 2


def test_enabled_signature_is_appended_to_html_and_plain_text():
    profile = SimpleNamespace(
        signature_enabled=True,
        signature_html='<p>Best wishes!</p><p><strong>李娴 Tokito</strong></p>',
        signature_text="Best wishes!\n李娴 Tokito",
    )

    assert active_signature(profile) == (
        '<p>Best wishes!</p><p><strong>李娴 Tokito</strong></p>',
        "Best wishes!\n李娴 Tokito",
    )
    html_body, text_body = append_signature("<p>正文</p>", "正文", profile)
    assert 'data-mail-signature="true"' in html_body
    assert html_body.endswith('<p>Best wishes!</p><p><strong>李娴 Tokito</strong></p></div>')
    assert text_body == "正文\n\nBest wishes!\n李娴 Tokito"


def test_disabled_signature_is_not_appended():
    profile = SimpleNamespace(
        signature_enabled=False,
        signature_html="<p>签名</p>",
        signature_text="签名",
    )

    assert append_signature("<p>正文</p>", "正文", profile) == ("<p>正文</p>", "正文")
