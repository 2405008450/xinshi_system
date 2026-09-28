"""在局域网调试机运行人才连续新增 UI 回归；所有 API 均拦截，不写业务库。"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:3000')
    parser.add_argument('--playwright-path')
    parser.add_argument('--output', default='test-results/talent-continuous')
    args = parser.parse_args()
    if args.playwright_path:
        sys.path.insert(0, args.playwright_path)
    from playwright.sync_api import sync_playwright, expect

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    records, writes, uploads, errors = {}, [], [], []
    state = {'upload_fail': False, 'duplicate': False, 'list_fail': False, 'save_fail': False}

    def api(route):
        request = route.request
        if not urlparse(request.url).path.startswith('/api/'):
            route.continue_()
            return
        path = urlparse(request.url).path.removeprefix('/api').rstrip('/')
        status, result = 200, []
        if path == '/auth/session':
            result = {'user_id': 'talent-ui-test', 'username': 'UI测试', 'roles': ['admin'], 'permissions': ['*']}
        elif path.startswith('/projects/languages'):
            result = [{'id': 'zh-test', 'code': 'zh-CN', 'name_zh': '汉语', 'name_en': 'Chinese', 'label': '汉语 / Chinese'}]
        elif path == '/talents/page':
            if state['list_fail']:
                status, result = 500, {'detail': '测试列表刷新失败'}
            else:
                result = {'items': list(records.values()), 'total': len(records)}
        elif path == '/talents' and request.method == 'POST':
            assert page.locator('.talent-editor-body').evaluate('(el) => el.inert')
            assert page.locator('.talent-editor-actions button').evaluate_all('(els) => els.every(el => el.disabled)')
            page.locator('.talent-editor-dialog .el-dialog__headerbtn').evaluate('(el) => el.click()')
            assert page.locator('.talent-editor-dialog').is_visible()
            data = request.post_data_json
            writes.append(('POST', data))
            if state['save_fail']:
                status, result = 500, {'detail': '测试保存失败'}
            elif state['duplicate'] and not data.get('allow_duplicate'):
                status, result = 409, {'detail': {'code': 'duplicate_talent', 'duplicates': [records['1']]}}
            else:
                ident = str(len(records) + 1)
                result = {**data, 'id': ident, 'resource_code': 'TEST-' + ident, 'attachments': []}
                records[ident] = result
        elif re.fullmatch(r'/talents/\d+/attachments', path):
            uploads.append(path)
            if state['upload_fail'] and len(uploads) == 2:
                status, result = 500, {'detail': '模拟第二个附件失败'}
            else:
                result = {'id': str(len(uploads)), 'category': 'photo', 'original_name': '测试照片.png'}
        elif re.fullmatch(r'/talents/\d+', path):
            ident = path.rsplit('/', 1)[-1]
            if request.method == 'PUT':
                writes.append(('PUT', request.post_data_json))
                records[ident].update(request.post_data_json)
            result = records[ident]
        route.fulfill(status=status, content_type='application/json', body=json.dumps(result, ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True, args=[
            '--no-proxy-server', '--host-resolver-rules=MAP oa.xinshify.com.cn 127.0.0.1',
        ])
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        context.add_init_script("localStorage.setItem('token','ui-test-only');")
        context.route('**/api/**', api)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('requestfailed', lambda request: errors.append(request.url + ': ' + str(request.failure)))
        page.goto(args.url + '/resource-management/talents')
        page.wait_for_timeout(2000)
        (output / 'initial.txt').write_text(page.url + '\n' + page.content() + '\n' + json.dumps(errors, ensure_ascii=False), encoding='utf-8')
        page.get_by_role('button', name='新增人才', exact=True).click()
        dialog = page.locator('.talent-editor-dialog:visible')

        def field(label):
            return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=re.compile('^' + re.escape(label) + '$')))

        def fill_person(name):
            field('中文姓名').locator('input').fill(name)
            field('专业能力').locator('label.el-checkbox').filter(has_text='笔译').click()

        def save_next():
            dialog.get_by_role('button', name='保存并继续新增', exact=True).click()

        def ready():
            expect(field('中文姓名').locator('input')).to_have_value('')
            expect(field('中文姓名').locator('input')).to_be_focused()
            expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_enabled()

        # 校验失败后仍可编辑，并定位姓名。
        save_next()
        expect(field('中文姓名').locator('input')).to_be_focused()
        assert not writes
        fill_person('连续甲')
        field('来源').locator('input').fill('同批来源')
        field('所在微信').locator('.el-select').click()
        page.get_by_role('option', name='其他（自主添加）', exact=True).click()
        field('所在微信').locator('input[maxlength="100"]').fill('自定义工作微信')
        field('所在微信群').locator('textarea').fill('资源一群\n资源二群')
        field('手机').locator('input').fill('13800000001')
        dialog.locator('label.el-checkbox').filter(has_text='沿用本批公共信息').click()
        # 同一轮事件内重复触发按钮，也只能创建一份档案。
        dialog.get_by_role('button', name='保存并继续新增').evaluate('(el) => { el.click(); el.click() }')
        ready()
        assert len(writes) == 1
        expect(field('来源').locator('input')).to_have_value('同批来源')
        expect(field('所在微信').locator('input[maxlength="100"]')).to_have_value('自定义工作微信')
        expect(field('手机').locator('input')).to_have_value('')
        assert page.evaluate("sessionStorage.getItem('form-drafts:talent:talent-ui-test')") is None
        assert records['1']['language_skills'][0]['language_id'] == 'zh-test'
        fill_person('连续乙')
        dialog.locator('label.el-checkbox').filter(has_text='沿用本批公共信息').click()
        save_next()
        ready()
        expect(field('来源').locator('input')).to_have_value('')
        expect(field('所在微信群').locator('textarea')).to_have_value('')
        fill_person('连续丙')
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        assert len(records) == 3
        print('PASS: three people, public fields, defaults, validation and submission lock', flush=True)

        # 编辑不提供连续新增；关闭后新一批不沿用勾选状态。
        page.get_by_role('button', name='编辑', exact=True).first.click()
        expect(dialog.get_by_role('button', name='保存并继续新增')).to_have_count(0)
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        page.get_by_role('button', name='新增人才', exact=True).click()
        expect(dialog.get_by_label('沿用本批公共信息')).not_to_be_checked()
        fill_person('附件失败重试')
        state['upload_fail'] = True
        field('照片').locator('input[type=file]').set_input_files([
            {'name': '一.png', 'mimeType': 'image/png', 'buffer': b'first'},
            {'name': '二.png', 'mimeType': 'image/png', 'buffer': b'second'},
        ])
        save_next()
        expect(page.get_by_text(re.compile('人才档案已保存，附件未全部上传'))).to_be_visible()
        expect(field('中文姓名').locator('input')).to_have_value('附件失败重试')
        assert len(records) == 4 and len(uploads) == 2
        save_next()
        ready()
        assert len(records) == 4 and len(uploads) == 3 and writes[-1][0] == 'PUT'
        expect(dialog.locator('.el-upload-list__item')).to_have_count(0)
        print('PASS: attachment retry uses PUT and uploads only the remaining file', flush=True)

        # 重复档案：取消确认框保持输入、仍然新建、打开已有档案。
        state['duplicate'] = True
        fill_person('重复仍然新建')
        save_next()
        box = page.locator('.el-message-box')
        box.locator('.el-message-box__headerbtn').click()
        expect(field('中文姓名').locator('input')).to_have_value('重复仍然新建')
        save_next()
        box.get_by_role('button', name='仍然新建').click()
        ready()
        assert len(records) == 5 and writes[-1][1]['allow_duplicate']
        fill_person('重复打开已有')
        save_next()
        box.get_by_role('button', name='打开已有档案').click()
        expect(dialog.get_by_role('button', name='保存并继续新增')).to_have_count(0)
        expect(dialog.locator('.name-collapsed-summary')).to_contain_text('连续甲')
        dialog.get_by_role('button', name='取消', exact=True).click()
        expect(dialog).not_to_be_visible()
        state['duplicate'] = False
        page.get_by_role('button', name='新增人才', exact=True).click()
        # 打开已有档案不会丢弃原先未提交的新增草稿。
        page.locator('.el-message-box').get_by_role('button', name='放弃草稿').click()
        fill_person('保存失败保留')
        state['save_fail'] = True
        save_next()
        expect(page.get_by_text('测试保存失败', exact=True)).to_be_visible()
        expect(field('中文姓名').locator('input')).to_have_value('保存失败保留')
        state['save_fail'] = False
        state['list_fail'] = True
        save_next()
        ready()
        expect(page.get_by_text('测试列表刷新失败', exact=True)).to_be_visible()
        state['list_fail'] = False
        print('PASS: duplicate branches, save failure and independent list failure', flush=True)

        # 拖动、边界、固定底栏、小屏，以及关闭重开的位置复位。
        initial = dialog.bounding_box()
        header = dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 15, header['y'] + 15)
        page.mouse.down()
        page.mouse.move(header['x'] + 50, header['y'] + 35, steps=8)
        page.mouse.up()
        moved = dialog.bounding_box()
        assert abs(moved['x'] - initial['x']) > 5
        fill_person('拖动后继续')
        save_next()
        ready()
        assert abs(dialog.bounding_box()['x'] - moved['x']) < 2
        header = dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 15, header['y'] + 15)
        page.mouse.down()
        page.mouse.move(0, 0, steps=8)
        page.mouse.up()
        bounds = dialog.bounding_box()
        assert bounds['x'] >= -1 and bounds['y'] >= -1
        dialog.locator('.el-dialog__headerbtn').click()
        expect(dialog).not_to_be_visible()
        page.get_by_role('button', name='新增人才', exact=True).click()
        assert abs(dialog.bounding_box()['x'] - initial['x']) < 2
        # 验证最后修正的跨字段错误定位，输入未完成的标注语言方向。
        field('中文姓名').locator('input').fill('标注方向校验')
        field('专业能力').locator('label.el-checkbox').filter(has_text='标注').click()
        direction_field = field('语言方向')
        direction_field.get_by_role('button', name='新增方向', exact=True).click()
        before_writes = len(writes)
        save_next()
        expect(direction_field).to_have_class(re.compile('is-dialog-field-search-highlight'))
        assert len(writes) == before_writes
        page.screenshot(path=str(output / 'annotation-validation.png'))
        page.set_viewport_size({'width': 390, 'height': 844})
        search = dialog.get_by_placeholder('搜索人才表单字段，如出生日期')
        search.fill('来源')
        page.locator('.project-field-search-option').filter(has_text='来源').click()
        expect(field('来源').locator('input')).to_be_focused()
        for position in (0, 2000, 100000):
            dialog.locator('.el-dialog__body').evaluate('(el, top) => el.scrollTop = top', position)
            bounds = dialog.get_by_role('button', name='保存并继续新增').bounding_box()
            assert 0 <= bounds['y'] and bounds['y'] + bounds['height'] <= 844
        page.screenshot(path=str(output / 'small-screen.png'))
        assert dialog.bounding_box()['width'] <= 390 - 32 + 1
        assert not errors, errors
        (output / 'result.json').write_text(json.dumps({'records': len(records), 'writes': len(writes), 'uploads': len(uploads), 'pageErrors': errors, 'passed': True}, ensure_ascii=False, indent=2), encoding='utf-8')
        browser.close()
        print('PASS: continuous create, drafts, attachments, duplicate branches, failures and responsive dialog')


if __name__ == '__main__':
    main()
