"""渠道表单内账号管理的隔离浏览器回归，不访问业务库。"""
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import expect, sync_playwright

BASE = os.getenv('CHANNEL_UI_BASE', '')
OUTPUT = Path(__file__).resolve().parents[1] / '.tmp/resource-channels-ui'


def run():
    if os.getenv('CHANNEL_RESOURCE_QA') != '1' or urlparse(BASE).hostname != 'localhost' or urlparse(BASE).port in {None, 3000, 8000}:
        raise SystemExit('仅允许本机专用渠道隔离服务')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        context = browser.new_context(viewport=dict(width=1440, height=900))
        context.add_init_script("localStorage.setItem('token','isolated-channel-editor');localStorage.setItem('user_roles','[\"admin\"]')")
        page = context.new_page()
        errors, results = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/resource-management/resource-channels')
        expect(page.locator('.page-title')).to_have_text('渠道管理')
        expect(page.locator('.el-loading-mask:visible')).to_have_count(0)
        editor = page.locator('.channel-dialog:visible')
        search = page.get_by_placeholder('平台名称、账号名称、平台用途')
        root = page.locator('.resource-channels-page .el-table').first
        rows = root.locator('.el-table__body').first.locator('> tbody > tr.el-table__row')
        path = '/resource-development/channels'

        def api(method, route, data=None):
            response = context.request.fetch(BASE + '/api' + route, method=method, data=data,
                headers={'Authorization': 'Bearer isolated-channel-editor'})
            assert response.ok, response.text()
            return response.json()

        def form_item(target, label):
            return target.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=label)).first

        def choose(target, label, value):
            page.wait_for_timeout(350)
            control = form_item(target, label).locator('.el-select'); control.click()
            menu_id = control.get_by_role('combobox').get_attribute('aria-controls')
            option = page.locator(f'#{menu_id}').get_by_role('option', name=value, exact=True)
            if option.get_attribute('aria-selected') != 'true':
                option.click()
            page.keyboard.press('Escape')

        def footer(target):
            page.wait_for_timeout(400)
            for position in [0, 300, 100000]:
                target.locator('.el-dialog__body').evaluate('(el, value) => el.scrollTop = value', position)
                box = target.locator('.el-dialog__footer').bounding_box()
                if box['y'] + box['height'] > page.viewport_size['height'] + 1:
                    page.screenshot(path=str(OUTPUT / 'inline-small-debug.png'))
                    print('弹窗与底栏边界', target.bounding_box(), box, flush=True)
                assert box['y'] >= 0 and box['y'] + box['height'] <= page.viewport_size['height'] + 1

        page.get_by_role('button', name='新增渠道', exact=True).click()
        form_item(editor, '渠道／平台名称').locator('input').fill('内联新增渠道')
        choose(editor, '平台性质', '全国性平台')
        editor.get_by_role('button', name='新增账号', exact=True).click()
        child = page.locator('.channel-dialog:visible').last
        child.get_by_role('button', name='确定', exact=True).click()
        expect(form_item(child, '渠道／平台名称').locator('input')).to_be_focused()
        form_item(child, '渠道／平台名称').locator('input').fill('内联草稿账号')
        choose(child, '维护人', '第二维护人')
        footer(child)
        child.get_by_role('button', name='确定', exact=True).click()
        expect(page.locator('.channel-dialog:visible')).to_have_count(1)
        expect(editor.locator('.channel-account-draft-row')).to_contain_text('内联草稿账号')
        assert api('GET', path + '?keyword=内联草稿账号')['total'] == 0
        editor.get_by_role('button', name='取消', exact=True).click()
        assert api('GET', path + '?keyword=内联草稿账号')['total'] == 0

        page.get_by_role('button', name='新增渠道', exact=True).click()
        form_item(editor, '渠道／平台名称').locator('input').fill('内联新增渠道')
        choose(editor, '平台性质', '全国性平台')
        editor.get_by_role('button', name='新增账号', exact=True).click()
        form_item(child, '渠道／平台名称').locator('input').fill('内联保存账号')
        choose(child, '维护人', '第二维护人')
        child.get_by_role('button', name='确定', exact=True).click()
        editor.get_by_role('button', name='保存', exact=True).click()
        expect(editor).not_to_be_visible()
        search.fill('内联新增渠道'); expect(rows).to_have_count(1)
        expect(rows.first).to_contain_text('第二维护人')
        rows.first.get_by_role('button', name='编辑', exact=True).click()
        editor.locator('.channel-account-draft-row').get_by_role('button', name='编辑账号').click()
        form_item(child, '平台情况说明').locator('textarea').fill('内联更新说明')
        child.get_by_role('button', name='确定', exact=True).click()
        editor.get_by_role('button', name='保存', exact=True).click(); expect(editor).not_to_be_visible()
        page.reload(); expect(page.locator('.el-loading-mask:visible')).to_have_count(0)
        search.fill('内联新增渠道'); expect(rows).to_have_count(1)
        rows.first.get_by_role('button', name='编辑', exact=True).click()
        editor.locator('.channel-account-draft-row').get_by_role('button', name='编辑账号').click()
        expect(form_item(child, '平台情况说明').locator('textarea')).to_have_value('内联更新说明')
        page.screenshot(path=str(OUTPUT / 'channel-inline-account.png'))
        child.get_by_role('button', name='取消', exact=True).click()
        expect(page.locator('.channel-dialog:visible')).to_have_count(1)
        footer(editor)
        original = editor.bounding_box()
        handle = editor.locator('.app-window-drag-strip').bounding_box()
        page.mouse.move(handle['x'] + 10, handle['y'] + 3); page.mouse.down()
        page.mouse.move(handle['x'] + 70, handle['y'] + 23, steps=10); page.mouse.up()
        assert abs(editor.bounding_box()['x'] - original['x']) > 20
        handle = editor.locator('.app-window-drag-strip').bounding_box()
        page.mouse.move(handle['x'] + 10, handle['y'] + 3); page.mouse.down()
        page.mouse.move(3000, 3000, steps=10); page.mouse.up()
        box = editor.bounding_box()
        assert box['x'] >= -1 and box['y'] >= -1 and box['x'] + box['width'] <= 1441 and box['y'] + box['height'] <= 901
        editor.get_by_role('button', name='关闭窗口').click()
        expect(editor).not_to_be_visible()
        rows.first.get_by_role('button', name='编辑', exact=True).click()
        expect(editor).to_be_visible()
        assert abs(editor.bounding_box()['x'] - original['x']) < 2
        editor.get_by_role('button', name='取消', exact=True).click()
        expect(editor).not_to_be_visible()
        page.set_viewport_size(dict(width=390, height=844))
        rows.first.get_by_role('button', name='编辑', exact=True).click()
        expect(editor).to_be_visible(); footer(editor)
        assert editor.bounding_box()['width'] <= 359
        editor.get_by_role('button', name='取消', exact=True).click()
        results.append('新增渠道内直接新增账号、必填定位、嵌套固定底栏、取消无写入、统一保存、编辑账号刷新保留')

        assert not errors, errors
        print(json.dumps(dict(scenarios=results, page_errors=errors), ensure_ascii=False))
        context.close(); browser.close()


if __name__ == '__main__':
    run()
