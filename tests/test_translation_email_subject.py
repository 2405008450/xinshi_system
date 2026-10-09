import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import business_mail_service as mail
from routers.consultations import _build_subject_preview
from translation_email_subject import build_translation_email_subject

CASES = json.loads((Path(__file__).parent / 'fixtures' / 'translation_email_subject_cases.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', CASES)
def test_shared_translation_subject_matches_confirmation_and_mail_window(case, monkeypatch):
    source = case['source']
    assert build_translation_email_subject(source)['subject'] == case['subject']
    parts, subject, _ = _build_subject_preview(
        project_type='translation', subject_prefix=source.get('subject_prefix'),
        order_no=source['order_no'], client_short_name=source['client_short_name'],
        manager_contact=source.get('manager_contact'), customer_order_no='不进入主题',
        project_name='不进入主题.docx', language_pair=source.get('language_pair'),
        customer_deadline_time=source.get('customer_deadline_time'), sub_order_count=source.get('sub_order_count', 0),
    )
    assert subject == case['subject'] == '，'.join(parts)
    monkeypatch.setattr(mail, 'policy_recipients', lambda *_: ([], []))
    monkeypatch.setattr(mail, 'resolve_project_sender', lambda *_: (None, {}))
    preview = mail.build_preview(object(), 'translation', source={**source, 'source_file_name': '真实文件.pdf；附件.xlsx'})
    assert preview['subject'] == case['subject']
    assert '项目名称：真实文件.pdf；附件.xlsx' in preview['body']
    if source.get('customer_order_no'):
        assert source['customer_order_no'] in preview['body']


def test_project_mail_preserves_manual_subject_and_uses_real_file_name(monkeypatch):
    project = SimpleNamespace(id=uuid4(), order_no='TP-261009-001', project_name='历史摘要',
        source_file_name='合同.docx', email_subject_preview='人工主题 TP-261009-001',
        client=SimpleNamespace(client_short_name='客户', manager_contact='经理'), sub_orders=[],
        service_content='翻译', language_pair='中文（简体）→英语（美国）')
    query = SimpleNamespace(filter=lambda *_: query, first=lambda: project)
    monkeypatch.setattr(mail, 'policy_recipients', lambda *_: ([], []))
    monkeypatch.setattr(mail, 'resolve_project_sender', lambda *_: (None, {}))
    monkeypatch.setattr(mail, 'get_word_count_matrix', lambda *_: {})
    preview = mail.build_preview(SimpleNamespace(query=lambda *_: query), 'translation', project_id=project.id)
    assert preview['subject'] == project.email_subject_preview
    assert '项目名称：合同.docx' in preview['body']
    assert '历史摘要' not in preview['body']
