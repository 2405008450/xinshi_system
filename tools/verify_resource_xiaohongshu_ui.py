"""局域网真实页面验收：微信与小红书字段、列配置和弹窗；隔离接口。"""
import copy
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:12449"
DEFAULTS = ['platform_name', 'full_name', 'language_names', 'wechat', 'xiaohongshu', 'owner_name',
            'account_name', 'friend_accounts_text', 'wechat_status', 'enterprise_status', 'latest_follow_up',
            'group_status', 'group_large_status', 'communication_status', 'project_status']


def run():
    if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在局域网调试机执行')
    out = ROOT / '.tmp' / 'resource-xiaohongshu-ui'
    out.mkdir(parents=True, exist_ok=True)
    uid, platform, rid = [str(uuid4()) for _ in range(3)]
    current_user = [uid]
    row = dict(id=rid, revision=1, full_name='小红书验收资源', owner_id=uid, owner_name='验收人员', platform_id=platform,
               platform_name='测试平台', work_date='2026-10-08', actions=[], language_ids=[], language_names='中文',
               phone='13800000000', wechat='wx_001', xiaohongshu='xhs_001', follow_up='', follow_ups=[],
               remarks='', can_edit=True, can_delete=True, progress={})
    saves, requests, errors = [], [], []

    def api(route):
        req = route.request
        path = urlparse(req.url).path.removeprefix('/api')
        query = parse_qs(urlparse(req.url).query)
        requests.append((path, query))
        result = {}
        if path == '/auth/session':
            result = dict(id=current_user[0], user_id=current_user[0], username='qa', full_name='验收人员', roles=['admin'], permissions=['talents:read', 'talents:write'])
        elif path == '/resource-development/options':
            result = dict(options=[dict(id=platform, kind='platform', category='national', name='测试平台')],
                          users=[dict(id=current_user[0], name='验收人员')], languages=[], user_id=current_user[0],
                          can_delegate=True, can_write=True, default_date='2026-10-08')
        elif path == '/resource-development/days':
            result = dict(total=1, items=[dict(date='2026-10-08', count=1, people=[])])
        elif path == '/resource-development/records':
            if req.method == 'POST':
                value = copy.deepcopy(req.post_data_json)
                saves.append(value)
                row.update(value)
                row['xiaohongshu'] = value['xiaohongshu'].strip()
                row['revision'] += 1
                result = row
            else:
                result = dict(total=1, items=[row])
        elif path.startswith('/resource-development/records/'):
            result = row
        elif path in {'/resource-development/record-duplicates', '/resource-development/duplicates'}:
            result = dict(total=0, items=[])
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        route.fulfill(status=200, json=result)

    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/resource-xiaohongshu-dist',
                                '--host', '127.0.0.1', '--port', '12449', '--strictPort'], cwd=ROOT / 'frontend',
                               stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(50):
            try:
                urlopen(BASE, timeout=1).close()
                break
            except OSError:
                time.sleep(.2)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel='msedge')
            context = browser.new_context(viewport=dict(width=1440, height=900))
            context.route('**/api/**', api)
            # 验证已有旧默认配置也会自动加入两种联系方式。
            key = f'resource-development:columns:{uid}'
            old = [key for key in DEFAULTS if key not in {'wechat', 'xiaohongshu'}]
            context.add_init_script("if (!sessionStorage.getItem('qa-init')) { localStorage.setItem('token','isolated-qa'); "
                                    "localStorage.setItem('user_roles','[\"admin\"]'); localStorage.setItem("
                                    + json.dumps(key) + "," + json.dumps(json.dumps(old)) + "); sessionStorage.setItem('qa-init','1'); }")
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(BASE + '/resource-management/resource-development')
            table = page.locator('.el-table').first
            expect(table).to_be_visible()

            def headers():
                return [text.strip() for text in table.locator('.el-table__header-wrapper th').all_text_contents()]

            labels = ['开拓平台', '姓名', '语种/方言', '资源微信号', '资源小红书号', '开拓人']
            assert headers()[1:7] == labels, headers()
            assert json.loads(page.evaluate('(key) => localStorage.getItem(key)', key)) == DEFAULTS
            page.screenshot(path=str(out / 'default-columns.png'), full_page=True)

            page.get_by_role('button', name='字段设置', exact=True).click()
            columns = page.locator('.development-column-options:visible')
            columns.get_by_text('资源小红书号', exact=True).click()
            assert '资源小红书号' not in headers()
            page.get_by_role('heading', name='资源开拓', exact=True).click()
            page.reload()
            expect(table).to_be_visible()
            assert '资源小红书号' not in headers()
            page.get_by_role('button', name='字段设置', exact=True).click()
            columns = page.locator('.development-column-options:visible')
            expect(columns.locator('.el-checkbox.is-checked')).to_have_count(len(DEFAULTS) - 1)
            while columns.locator('.el-checkbox.is-checked').count():
                count = columns.locator('.el-checkbox.is-checked').count()
                columns.locator('.el-checkbox.is-checked').first.click()
                expect(columns.locator('.el-checkbox.is-checked')).to_have_count(count - 1)
            expect(table.locator('.el-table__header-wrapper th')).to_have_count(3)
            assert headers() == ['序号', '详情', '操作'], headers()
            page.get_by_role('button', name='恢复默认', exact=True).click()
            expect(table.locator('.el-table__header-wrapper th')).to_have_count(len(DEFAULTS) + 3)
            assert headers()[1:7] == labels
            page.get_by_role('heading', name='资源开拓', exact=True).click()

            # 表头文字筛选复用同一份列表及总数参数。
            header = table.locator('.el-table__header-wrapper th').filter(has_text='资源小红书号')
            header.locator('button').click()
            filter_popover = page.locator('.el-popover:visible').last
            filter_popover.locator('input').fill('xhs_001')
            page.wait_for_timeout(550)
            matching = [(path, query) for path, query in requests if query.get('column_filters') and
                        json.loads(query['column_filters'][0]).get('xiaohongshu') == 'xhs_001']
            assert {'/resource-development/days', '/resource-development/records'} <= {path for path, _ in matching}
            page.get_by_role('heading', name='资源开拓', exact=True).click()
            page.get_by_role('button', name='重置', exact=True).click()

            dialog = page.locator('.development-dialog:visible')

            def field(label):
                return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=label)).first

            for button in ['新增', '编辑']:
                page.get_by_role('button', name=button, exact=True).click()
                expect(dialog).to_be_visible()
                page.wait_for_timeout(300)
                phone, wechat, xhs = [field(label).bounding_box() for label in ['资源手机', '资源微信号', '资源小红书号']]
                assert abs(wechat['y'] - xhs['y']) < 2 and wechat['x'] < xhs['x']
                assert phone['width'] > wechat['width'] * 1.8 and phone['y'] < wechat['y']
                expect(field('资源小红书号').locator('input')).to_have_value('' if button == '新增' else 'xhs_001')
                assert field('资源小红书号').locator('input').get_attribute('maxlength') == '100'
                preset = dialog.bounding_box()
                dialog.locator('.el-dialog__body').evaluate('(el) => el.scrollTop = el.scrollHeight')
                expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
                expect(dialog.get_by_role('button', name='取消', exact=True)).to_be_in_viewport()
                dialog.get_by_placeholder('搜索字段，如资源姓名').fill('小红书')
                page.get_by_role('option').filter(has_text='资源小红书号').first.click()
                expect(field('资源小红书号').locator('input')).to_be_focused()
                handle = dialog.locator('.el-dialog__header').bounding_box()
                page.mouse.move(handle['x'] + 15, handle['y'] + 12)
                page.mouse.down(); page.mouse.move(handle['x'] + 100, handle['y'] + 52); page.mouse.up()
                assert abs(dialog.bounding_box()['x'] - preset['x']) > 20
                moved = dialog.bounding_box()
                page.mouse.move(moved['x'] + 15, moved['y'] + 12)
                page.mouse.down(); page.mouse.move(-800, -800); page.mouse.up()
                bounded = dialog.bounding_box()
                assert bounded['x'] >= -1 and bounded['y'] >= -1
                dialog.locator('.el-dialog__headerbtn').click()
                page.get_by_role('button', name=button, exact=True).click()
                page.wait_for_timeout(300)
                reopened = dialog.bounding_box()
                assert abs(reopened['x'] - preset['x']) < 2 and abs(reopened['y'] - preset['y']) < 2
                dialog.get_by_role('button', name='取消', exact=True).click()

            page.get_by_role('button', name='编辑', exact=True).click()
            field('资源小红书号').locator('input').fill('xhs_saved')
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog).to_have_count(0)
            assert saves[-1]['xiaohongshu'] == 'xhs_saved'
            page.get_by_role('button', name='查看详情', exact=True).click()
            popover = page.locator('.development-detail:visible')
            expect(popover).to_contain_text('资源小红书号')
            expect(popover).to_contain_text('xhs_saved')
            expect(popover).to_have_attribute('data-popper-placement', 'left')
            page.get_by_role('heading', name='资源开拓', exact=True).click()
            page.get_by_role('button', name='新增', exact=True).click()
            field('开拓平台').locator('.el-select').click()
            page.get_by_role('option', name='测试平台', exact=True).click()
            field('资源姓名').locator('input').fill('连续新增验收')
            field('资源微信号').locator('input').fill('wx_new')
            field('资源小红书号').locator('input').fill('xhs_new')
            dialog.get_by_role('button', name='保存并继续新增', exact=True).click()
            expect(field('资源小红书号').locator('input')).to_have_value('')
            expect(field('资源微信号').locator('input')).to_have_value('')
            assert saves[-1]['xiaohongshu'] == 'xhs_new'
            dialog.get_by_role('button', name='取消', exact=True).click()

            page.set_viewport_size(dict(width=600, height=760))
            for button in ['新增', '编辑']:
                page.get_by_role('button', name=button, exact=True).click()
                expect(dialog).to_be_visible()
                page.wait_for_timeout(300)
                wechat, xhs = field('资源微信号').bounding_box(), field('资源小红书号').bounding_box()
                assert abs(wechat['x'] - xhs['x']) < 2 and wechat['y'] < xhs['y']
                box = dialog.bounding_box()
                assert box['width'] <= 568 and box['x'] >= 0 and box['x'] + box['width'] <= 600
                dialog.locator('.el-dialog__body').evaluate('(el) => el.scrollTop = el.scrollHeight / 2')
                expect(dialog.get_by_role('button', name='取消', exact=True)).to_be_in_viewport()
                dialog.locator('.el-dialog__body').evaluate('(el) => el.scrollTop = el.scrollHeight')
                expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
                assert dialog.evaluate('(el) => el.scrollHeight <= el.clientHeight + 2')
                page.screenshot(path=str(out / f'small-{button}.png'), full_page=True)
                dialog.get_by_role('button', name='取消', exact=True).click()

            # 切换用户后独立读取配置，无配置的新用户采用默认值。
            page.evaluate('([key, uid]) => { localStorage.setItem(key, JSON.stringify(["full_name"])); localStorage.setItem("resource-development:columns:" + uid, JSON.stringify(["wechat"])); }', [key, 'other-user'])
            page.reload()
            expect(table).to_be_visible()
            assert headers() == ['序号', '姓名', '详情', '操作']
            assert page.evaluate('localStorage.getItem("resource-development:columns:other-user")') == '["wechat"]'
            current_user[0] = 'other-user'
            page.reload()
            expect(table).to_be_visible()
            assert headers() == ['序号', '资源微信号', '详情', '操作']
            current_user[0] = str(uuid4())
            page.reload()
            expect(table).to_be_visible()
            assert headers()[1:7] == labels
            assert page.evaluate('(key) => localStorage.getItem(key)', key) == '["full_name"]'
            assert not errors, errors
            browser.close()
        print(json.dumps({'ok': True, 'checks': ['旧默认升级', '联系方式顺序', '字段隐藏及刷新', '全部隐藏及恢复',
              '列筛选参数', '新增编辑布局', '字段搜索', '拖拽边界及复位', '保存回显', '详情', '连续新增清空', '小屏及固定底部', '用户配置隔离']}, ensure_ascii=False))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


if __name__ == '__main__':
    run()
