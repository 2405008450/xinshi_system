"""共性漏项回归；使用合成内容，不写真实简历及数据库。"""
import pytest
from tools.resume_alignment import certificate_language, reconcile_lines, extraction_contract


def test_composite_line_is_not_consumed_by_one_field():
    rows = [{'id': 1, 'location': '第1行', 'text': '硕士 未婚 户籍：甲市'}]
    text, ledger = reconcile_lines(rows, [('highest_education', '硕士')])
    assert text == rows[0]['text']
    assert ledger[0]['status'] == 'retained_unmapped'
    assert ledger[0]['targets'] == ['highest_education', 'remarks']


def test_full_experience_keeps_header_but_does_not_repeat_in_remarks():
    rows = [{'id': 1, 'location': '第1行', 'text': '甲公司（1000人）[11个月]'},
            {'id': 2, 'location': '第2行', 'text': '负责项目协调。'}]
    text, ledger = reconcile_lines(rows, [('resume_profile.other.0.description', '\n'.join(r['text'] for r in rows))])
    assert not text
    assert all(row['status'] == 'mapped' for row in ledger)


def test_exclusions_require_reason_and_budget_never_truncates():
    rows = [{'id': 1, 'location': '第1行', 'text': '未映射的重要内容'}]
    with pytest.raises(ValueError, match='requires_reason'):
        reconcile_lines(rows, [], excluded={1: ''})
    with pytest.raises(ValueError, match='exceeds_budget'):
        reconcile_lines(rows, [], max_remark_chars=3)


def test_certificates_use_language_context_and_existing_catalog_only():
    catalog = {'英语': 'en-id', '粤语': 'yue-id', '汉语': 'zh-id', '日语': 'ja-id'}
    assert certificate_language('AS Chinese (Cantonese)', '', catalog) == 'yue-id'
    assert certificate_language('HSK6', '', catalog) == 'zh-id'
    assert certificate_language('专业八级', '', catalog) is None
    assert certificate_language('专业八级', '', catalog, context='英语专业') == 'en-id'
    assert certificate_language('计算机二级', '', catalog) is None
    assert certificate_language('日语N1', '', {}) is None


def test_field_contract_covers_previously_missing_fields():
    schema = extraction_contract()['schema']
    assert 'identity_number' in schema['properties']
    assert 'secondary_phone' in schema['properties']
    assert 'minor_major' in schema['$defs']['EducationExperienceInput']['properties']


def test_contact_dedup_keeps_unmapped_business_fact():
    rows = [{'id': 1, 'location': '第1行', 'text': '手机：12345678901 | 户口：甲市 | 未婚'}]
    text, ledger = reconcile_lines(rows, [('primary_phone', '12345678901')])
    assert '12345678901' not in text
    assert '户口：甲市' in text and '未婚' in text
    assert ledger[0]['status'] == 'retained_unmapped'
