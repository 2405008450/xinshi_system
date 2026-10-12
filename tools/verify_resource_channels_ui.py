"""本机渠道管理真实前后端浏览器验收，仅连接临时隔离服务。"""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv('CHANNEL_UI_BASE', '')
OUTPUT = ROOT / '.tmp/resource-channels-ui'


def run():
    if os.getenv('CHANNEL_RESOURCE_QA') != '1' or urlparse(BASE).hostname != 'localhost' or urlparse(BASE).port in {None, 3000, 8000}:
        raise SystemExit('仅允许本机专用渠道隔离服务，禁止向业务库写入验收数据')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    errors, requests, results = [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')

        def context_for(token='isolated-channel-editor', width=1440, height=900):
            context = browser.new_context(viewport=dict(width=width, height=height), timezone_id='America/New_York')
            context.add_init_script(f"localStorage.setItem('token',{json.dumps(token)});localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page(); page.set_default_timeout(10000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append((request.method, request.url)))
            page.goto(BASE + '/resource-management/resource-channels')
            expect(page.get_by_role('heading', name='渠道管理', exact=True)).to_be_visible()
            expect(page.locator('.el-loading-mask:visible')).to_have_count(0)
            return context, page

        context, page = context_for()
        headers = {'Authorization': 'Bearer isolated-channel-editor'}
        path = '/resource-development/channels'

        def api(method, route, data=None):
            response = context.request.fetch(BASE + '/api' + route, method=method, data=data, headers=headers)
            assert response.ok, f'{method} {route}: {response.status} {response.text()}'
            return response.json()

        def update(row, **changes):
            return api('PUT', path + '/' + row['id'], dict(name=row['name'], category=row['category'], purpose=row['purpose'], description=row['description'],
                       maintainer_ids=[p['id'] for p in row['direct_maintainers']], user_ids=[p['id'] for p in row['direct_users']], revision=row['revision']) | changes)

        def form_item(target, label):
            return target.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=label)).first

        def choose(target, label, value):
            control = form_item(target, label).locator('.el-select'); control.click()
            menu_id = control.get_by_role('combobox').get_attribute('aria-controls')
            page.locator(f'#{menu_id}').get_by_role('option', name=value, exact=True).click()
            page.keyboard.press('Escape')

        def footer(target):
            for position in [0, 300, 100000]:
                target.locator('.el-dialog__body').evaluate('(el, value) => el.scrollTop = value', position)
                box = target.locator('.el-dialog__footer').bounding_box()
                assert box['y'] >= 0 and box['y'] + box['height'] <= page.viewport_size['height'] + 1

        root = page.locator('.resource-channels-page .el-table').first
        rows = root.locator('.el-table__body').first.locator('> tbody > tr.el-table__row')
        search = page.get_by_placeholder('平台名称、账号名称、平台用途')
        expect(rows).to_have_count(20)
        expect(page.get_by_role('button', name='编辑情况说明', exact=True)).to_have_count(0)
        expect(root.locator('.el-table__header').get_by_text('平台情况说明', exact=True)).to_be_visible()
        page.screenshot(path=str(OUTPUT / 'channel-list.png'), full_page=True)
        count = lambda: len([r for r in requests if r[0] == 'GET' and '/channels?' in r[1]])
        before = count(); search.fill('验收BOSS'); page.wait_for_timeout(150); assert count() == before
        expect(rows).to_have_count(1)
        preview = page.get_by_role('button', name='查看验收BOSS直聘情况说明全文', exact=True)
        assert preview.locator('.channel-text-summary').evaluate('el=>el.scrollHeight>el.clientHeight')
        preview.click()
        popover = page.locator('.channel-text-popover:visible')
        expect(popover.locator('textarea,input')).to_have_count(0)
        expect(popover.get_by_role('button', name='保存', exact=True)).to_have_count(0)
        assert popover.locator('.channel-text-body').evaluate('el=>el.scrollHeight>el.clientHeight')
        assert popover.bounding_box()['x'] < preview.bounding_box()['x']
        page.wait_for_timeout(250)
        page.screenshot(path=str(OUTPUT / 'channel-description.png'))
        popover.get_by_role('button', name='关闭', exact=True).click()
        results.append('默认说明摘要、三行省略、点击只读全文、左向小窗及内部滚动')

        panel = page.locator('.channel-account-panel')
        expect(panel).to_be_visible()
        page.get_by_role('button', name='收起账号', exact=True).click()
        expect(panel).not_to_be_visible()
        page.get_by_role('button', name='展开账号', exact=True).click()
        expect(panel.get_by_text('验收BOSS 1', exact=True)).to_be_visible()
        expect(panel.get_by_text('验收BOSS 2', exact=True)).to_be_visible()
        expect(rows).to_have_count(1)
        assert rows.first.locator('td').nth(5).inner_text().count('验收维护人') == 1
        page.screenshot(path=str(OUTPUT / 'channel-accounts.png'), full_page=True)
        page.get_by_role('button', name='收起账号', exact=True).click(); expect(panel).not_to_be_visible()
        search.fill('验收BOSS 1'); expect(panel).to_be_visible(); expect(rows).to_have_count(1)
        results.append('平台分页、账号展开收起、人员去重、账号搜索自动展开')

        page.get_by_role('button', name='编辑', exact=True).click()
        editor = page.locator('.channel-dialog:visible')
        expect(form_item(editor, '维护人').locator('input')).to_have_attribute('readonly', '')
        expect(form_item(editor, '账号管理').locator('.el-select')).to_be_visible()
        footer(editor)
        field = editor.get_by_placeholder('搜索字段，如维护人'); field.fill('账号')
        page.locator('.project-field-search-popper:visible').get_by_text('账号管理', exact=True).click()
        expect(form_item(editor, '账号管理').locator('.el-select__wrapper')).to_be_focused()
        page.screenshot(path=str(OUTPUT / 'channel-editor.png'))
        editor.get_by_role('button', name='取消', exact=True).click()
        results.append('平台编辑人员只读汇总、账号管理字段定位、内容独立滚动及固定底栏')

        panel.get_by_role('button', name='编辑账号', exact=True).first.click()
        expect(form_item(editor, '所属平台').locator('input')).to_have_value('验收BOSS直聘')
        expect(form_item(editor, '平台情况说明').locator('textarea')).to_have_value('账号独立原说明')
        choose(editor, '使用人', '第二维护人')
        editor.get_by_role('button', name='保存', exact=True).click(); expect(editor).not_to_be_visible()
        expect(rows.first).to_contain_text('第二维护人')
        page.reload(); expect(page.locator('.el-loading-mask:visible')).to_have_count(0)
        search.fill('验收BOSS'); expect(rows).to_have_count(1)
        results.append('子账号独立说明、人员编辑后汇总刷新及重新进入保留')

        rows.first.get_by_role('button', name='新增账号', exact=True).click()
        expect(editor).to_be_visible()
        editor.get_by_role('button', name='保存', exact=True).click()
        expect(form_item(editor, '渠道／平台名称').locator('input')).to_be_focused()
        form_item(editor, '渠道／平台名称').locator('input').fill('验收BOSS 3')
        choose(editor, '维护人', '第二维护人'); footer(editor)
        editor.get_by_role('button', name='保存', exact=True).click(); expect(editor).not_to_be_visible()
        expect(rows.first).to_contain_text('3个账号')
        results.append('新增账号必填校验定位、所属平台只读、保存后原地汇总')

        page.get_by_role('button', name='编辑', exact=True).click()
        expect(editor).to_be_visible(); page.wait_for_timeout(300)
        original = editor.bounding_box(); header = editor.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 6, header['y'] + 6); page.mouse.down()
        page.mouse.move(header['x'] + 110, header['y'] + 45, steps=10); page.mouse.up()
        assert abs(editor.bounding_box()['x'] - original['x']) > 30
        header = editor.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 6, header['y'] + 6); page.mouse.down(); page.mouse.move(3000, 3000, steps=10); page.mouse.up()
        bounds = editor.bounding_box()
        assert bounds['x'] >= -1 and bounds['y'] >= -1 and bounds['x'] + bounds['width'] <= 1441 and bounds['y'] + bounds['height'] <= 901
        editor.locator('.el-dialog__headerbtn').click()
        page.get_by_role('button', name='编辑', exact=True).click(); expect(editor).to_be_visible(); page.wait_for_timeout(300)
        assert abs(editor.bounding_box()['x'] - original['x']) < 2
        form_item(editor, '平台用途').locator('textarea').fill('并发草稿')
        current = api('GET', path + '?keyword=验收BOSS')['items'][0]
        update(current, purpose='其他人员的新用途')
        editor.get_by_role('button', name='保存', exact=True).click()
        expect(editor.get_by_text('渠道已被修改，草稿已保留。请重新读取最新内容后再保存。')).to_be_visible()
        expect(form_item(editor, '平台用途').locator('textarea')).to_have_value('并发草稿')
        editor.get_by_role('button', name='重新读取最新内容').click(); editor.get_by_role('button', name='恢复保留的草稿').click()
        editor.get_by_role('button', name='保存', exact=True).click(); expect(editor).not_to_be_visible()
        results.append('标题拖动、视口边界、关闭可点、重新打开复位、真实409冲突与草稿恢复')

        search.fill('验收智联'); expect(rows).to_have_count(1); expect(rows.first).to_contain_text('验收智联')
        page.get_by_role('button', name='编辑', exact=True).click(); expect(editor).to_be_visible()
        choose(editor, '账号管理', '验收BOSS 1（当前归属：验收BOSS直聘）')
        editor.get_by_role('button', name='保存', exact=True).click()
        confirm = page.locator('.el-message-box:visible')
        expect(confirm).to_contain_text('原平台：验收BOSS直聘')
        confirm.get_by_role('button', name='确认转移', exact=True).click(); expect(editor).not_to_be_visible()
        expect(rows.first).to_contain_text('1个账号')
        search.fill('验收BOSS'); expect(rows).to_have_count(2); expect(rows.first).to_contain_text('2个账号')
        results.append('账号跨平台转移明确确认、原平台与新平台汇总刷新')

        page.get_by_role('button', name='字段设置', exact=True).click()
        columns = page.locator('.el-popper:visible').filter(has=page.locator('.channel-column-options'))
        for checkbox in columns.locator('.el-checkbox').all():
            if checkbox.locator('input').is_checked(): checkbox.click()
        expect(root.locator('.el-table__header').first.locator('th')).to_have_count(4)
        columns.get_by_role('button', name='恢复默认', exact=True).click()
        columns.locator('.el-checkbox').filter(has_text='平台用途').click()
        page.reload(); expect(root.locator('.el-table__header').get_by_text('平台用途', exact=True)).to_have_count(0)
        results.append('全部取消保留结构列、恢复默认、个人字段配置刷新保留')

        reader_context, reader = context_for('isolated-channel-reader')
        expect(reader.get_by_role('button', name='新增渠道', exact=True)).to_have_count(0)
        expect(reader.get_by_role('button', name='编辑', exact=True)).to_have_count(0)
        expect(reader.locator('.el-table__header').get_by_text('平台用途', exact=True)).to_be_visible()
        reader.get_by_placeholder('平台名称、账号名称、平台用途').fill('验收BOSS')
        expect(reader.locator('.channel-account-panel').first).to_be_visible()
        expect(reader.get_by_role('button', name='编辑账号', exact=True)).to_have_count(0)
        results.append('只读角色可展开与查看，写入口隐藏，不同用户字段配置隔离')
        reader_context.close()

        page.set_viewport_size(dict(width=390, height=844)); search.fill('验收BOSS'); expect(rows).to_have_count(2)
        # 横向移动到说明列左沿，避开一直固定在右侧的详情及操作列。
        root.locator('.el-scrollbar__wrap').first.evaluate("el => { const target = el.querySelector('.channel-text-preview'); el.scrollLeft += target.getBoundingClientRect().left - el.getBoundingClientRect().left; }")
        page.get_by_role('button', name='查看验收BOSS直聘情况说明全文', exact=True).click()
        expect(popover).to_be_visible(); page.wait_for_timeout(250); box = popover.bounding_box()
        page.screenshot(path=str(OUTPUT / 'channel-small-screen.png'))
        assert box['width'] <= 359 and box['x'] >= -1 and box['x'] + box['width'] <= 391, box
        popover.get_by_role('button', name='关闭', exact=True).click()
        rows.first.get_by_role('button', name='编辑', exact=True).click(); expect(editor).to_be_visible(); footer(editor)
        assert editor.bounding_box()['width'] <= 359
        editor.get_by_role('button', name='取消', exact=True).click()
        results.append('390px小屏说明小窗受视口限制、单列表单及固定操作栏')
        assert not errors, errors
        report = dict(scenarios=results, page_errors=errors, real_backend=True, database='isolated localhost PostgreSQL')
        (OUTPUT / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
        context.close(); browser.close()


if __name__ == '__main__':
    run()
