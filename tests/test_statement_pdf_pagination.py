from io import BytesIO

from pypdf import PdfReader

from statement_pdf import pdf_bytes


def test_merged_direction_rows_keep_one_header_at_top_of_each_page():
    rows = []
    for index in range(22):
        rows.append({
            'order_no': f'TP-261107-{index:03}', 'received_date': '2026-11-07',
            'project_name': f'普通订单{index}.docx', 'language_pair': '日语→中文（简体）',
            'quantity': '1000', 'basis': '我司统计 · 字数', 'unit_price': '0.2',
            'currency': 'CNY', 'subtotal': '200.00', 'remarks': '',
        })
    parent = {**rows[-1], 'order_no': 'TP-PARENT', 'root_id': 'root',
              'project_name': '跨页母订单.docx', 'direction_parent_summary': True,
              'counted_in_total': False}
    rows.append(parent)
    rows.extend({
        **rows[0], 'order_no': f'TP-PARENT.{index:03}', 'root_id': 'root',
        'project_name': '', 'quantity': None, 'direction_detail': True,
        'direction_parent_no': 'TP-PARENT', 'language_pair': '中文（简体）→葡萄牙语（巴西）',
    } for index in range(40))
    statement = {
        'company': '信实翻译', 'client_name': '分页测试客户', 'title': '对账单',
        'month': '2026-11', 'rows': rows, 'totals': {'CNY': '12400.00'},
        'pending': [], 'settings': {}, 'private_settings_available': False,
    }
    reader = PdfReader(BytesIO(pdf_bytes([statement])))
    assert len(reader.pages) > 3
    for index, page in enumerate(reader.pages):
        text = page.extract_text()
        assert text.count('来稿日期') == 1
        assert text.index('来稿日期') < text.index('2026-11-07')
        positions = []

        def header_position(value, cm, tm, font, size):
            if '来稿日期' in value:
                positions.append(float(page.mediabox.height) - (cm[3] * tm[5] + cm[5]))

        page.extract_text(visitor_text=header_position)
        if index:
            assert all(position < 70 for position in positions)
        if '葡萄牙语' in text:
            assert '跨页母订单.docx' in text
    assert sum(
        line.strip() == '合计'
        for page in reader.pages for line in page.extract_text().splitlines()
    ) == 1
