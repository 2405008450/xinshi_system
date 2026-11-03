"""本机确认弹窗回归：所有 API 均拦截为测试数据，不连接数据库或发送邮件。"""
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, expect


def main():
    submissions = []
    previews = []
    row = {
        'id': '11111111-1111-4111-8111-111111111111', 'client_short_name': '文件名回归测试',
        'client_name': '文件名回归测试', 'consultation_type': '笔译项目', 'status': 'following',
        'project_name': '客户简称，英译阿，11月4日16点回稿',
        'project_intake': {'service_content': '翻译', 'language_pair': '英语（美国）→阿拉伯语'},
    }
    user = {'id': '22222222-2222-4222-8222-222222222222', 'user_id': '22222222-2222-4222-8222-222222222222',
            'username': 'test', 'full_name': '测试用户', 'email': 'test@example.invalid', 'is_active': True}

    def mock(route):
        request = route.request
        path = urlparse(request.url).path
        if not path.startswith('/api/'):
            route.continue_()
            return
        data = []
        if path == '/api/auth/session':
            data = {**user, 'roles': ['admin'], 'permissions': ['*'], 'can_manage_hr': True}
        elif path == '/api/consultations/page':
            data = {'items': [row], 'total': 1}
        elif path == '/api/consultations/confirmation-preview':
            payload = request.post_data_json
            previews.append(payload)
            data = {
                'project_type': 'translation', 'order_no': 'TP-261103-990',
                'project_name': payload.get('project_name') or '', 'sub_order_count': 0,
                'client_short_name': row['client_short_name'], 'manager_contact': '',
                'language_pair': row['project_intake']['language_pair'],
                'to_users': [user], 'cc_users': [], 'missing_fields': [], 'blocking_reasons': [],
                'email_subject_preview': '测试主题', 'email_body': '文件：' + (payload.get('project_name') or '待填写'),
                'can_send': True, 'sender_name': '测试发件人', 'sender_mode': 'system',
            }
        elif path.endswith('/confirm'):
            submissions.append(request.post_data_json)
            data = {'mail': {'status': 'sent'}}
        elif path.startswith('/api/users'):
            data = [user]
        elif path == '/api/consultations/' + row['id']:
            data = row
        route.fulfill(status=200, content_type='application/json', body=json.dumps(data, ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        context.add_init_script("localStorage.setItem('token','isolated-ui-test')")
        context.route('**/api/**', mock)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://127.0.0.1:3000/consultations')
        page.wait_for_timeout(2500)
        if page.locator('.status-switch-tag').count() == 0:
            raise AssertionError((page.url, page.locator('body').inner_text()[:2000], errors))
        dialog = page.locator('.consultation-confirmation-dialog:visible')

        def open_dialog():
            page.locator('.status-switch-tag').first.click()
            page.get_by_role('menuitem').filter(has_text='已确认').click()
            expect(dialog).to_be_visible()
            expect(dialog.locator('.el-loading-mask')).to_have_count(0)

        open_dialog()
        field = dialog.locator('.el-form-item').filter(has=page.locator('label', has_text='文件名称')).locator('input')
        expect(field).to_have_value('')
        assert 'project_name' not in previews[0]
        for bad in ['', '没有后缀', '甲.pdf；乙.docx']:
            field.fill(bad)
            page.wait_for_timeout(650)
            dialog.get_by_role('button', name='只建项（不发邮件）', exact=True).click()
            expect(dialog.locator('.el-form-item.is-error').first).to_contain_text('文件名称')
            expect(field).to_be_focused()
            assert not submissions

        field.fill('中文合同.docx')
        page.wait_for_timeout(650)
        expect(field).to_have_value('中文合同.docx')
        # 验证公共字段搜索及正文独立滚动。
        search = dialog.get_by_placeholder('搜索字段，如文件名称')
        search.fill('文件')
        page.locator('.project-field-search-option').filter(has_text='文件名称').click()
        expect(field).to_be_focused()
        footer = dialog.locator('.el-dialog__footer')
        before = footer.bounding_box()
        dialog.locator('.el-dialog__body').evaluate('(el) => el.scrollTop = el.scrollHeight')
        assert abs(footer.bounding_box()['y'] - before['y']) < 2
        # 标题拖动后仍在视口内；重新打开恢复初始位置。
        initial = dialog.bounding_box()
        title = dialog.locator('.dialog-field-search-header__title').bounding_box()
        page.mouse.move(title['x'] + 20, title['y'] + 10)
        page.mouse.down()
        page.mouse.move(title['x'] + 100, title['y'] + 60, steps=10)
        page.mouse.up()
        moved = dialog.bounding_box()
        assert abs(moved['x'] - initial['x']) > 20
        assert moved['x'] >= 0 and moved['y'] >= 0
        dialog.get_by_role('button', name='取消', exact=True).click()
        expect(dialog).not_to_be_visible()
        open_dialog()
        restored = dialog.bounding_box()
        assert abs(restored['x'] - initial['x']) < 2
        field.click()
        page.wait_for_timeout(200)
        field.fill('中文合同.docx')
        # 在防抖期间立即提交也必须取得最新预览。
        dialog.get_by_role('button', name='只建项（不发邮件）', exact=True).click()
        expect(dialog).not_to_be_visible()
        assert submissions[-1]['confirmation']['project_name'] == '中文合同.docx', (submissions, previews)
        assert previews[-1]['project_name'] == '中文合同.docx'
        assert submissions[-1]['confirmation']['to_user_ids'] == []
        open_dialog()
        field.click()
        page.wait_for_timeout(200)
        field.fill('邮件附件.pdf')
        page.wait_for_timeout(650)
        dialog.get_by_role('button', name='确认建项并发送邮件', exact=True).click()
        expect(dialog).not_to_be_visible()
        assert submissions[-1]['confirmation']['project_name'] == '邮件附件.pdf'
        assert submissions[-1]['confirmation']['to_user_ids'] == [user['id']]
        open_dialog()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.wait_for_timeout(300)
        bounds = dialog.bounding_box()
        assert bounds['width'] <= 390 - 32
        expect(footer.get_by_role('button', name='只建项（不发邮件）', exact=True)).to_be_visible()
        for button in footer.get_by_role('button').all():
            box = button.bounding_box()
            assert box['y'] + box['height'] <= 844, box
        output = Path('artifacts/consultation-confirmation-filename.png')
        output.parent.mkdir(exist_ok=True)
        page.wait_for_timeout(3500)
        page.screenshot(path=str(output))
        assert not errors, errors
        print('PASS: 文件名错误定位、修正提交、两类提交、字段搜索、固定底栏、拖动复位及小屏检查；所有 API 已隔离。')
        browser.close()


if __name__ == '__main__':
    main()
