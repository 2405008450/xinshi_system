"""局域网真实页面文字跟进验收；隔离接口，不写业务数据。"""
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
BASE = 'http://127.0.0.1:12448'


def run():
    if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在局域网调试机执行')
    out = ROOT / '.tmp' / 'resource-follow-up-ui'
    out.mkdir(parents=True, exist_ok=True)
    uid, platform, rid = [str(uuid4()) for _ in range(3)]
    row = dict(id=rid, revision=1, full_name='跟进验收资源', owner_id=uid, owner_name='开拓人员', platform_id=platform,
               platform_name='测试平台', work_date='2026-10-08', actions=[], language_ids=[], phone='', wechat='',
               follow_up='', follow_ups=[], follow_up_count=0, latest_follow_up='', latest_follow_up_entry=None,
               remarks='', can_edit=True, can_delete=True, progress={})
    errors, saves, requests = [], [], []
    conflict = [False]

    def api(route):
        req = route.request
        path = urlparse(req.url).path.removeprefix('/api')
        query = parse_qs(urlparse(req.url).query)
        requests.append((req.method, path, query))
        result = {}
        if path == '/auth/session':
            result = dict(user_id=uid, username='qa', full_name='实际保存人员', roles=['admin'], permissions=['talents:read', 'talents:write'])
        elif path == '/resource-development/options':
            result = dict(options=[dict(id=platform, kind='platform', category='national', name='测试平台')],
                          users=[dict(id=uid, name='实际保存人员')], languages=[], user_id=uid,
                          can_delegate=True, can_write=True, default_date='2026-10-08')
        elif path == '/resource-development/days':
            result = dict(total=1, items=[dict(date='2026-10-08', count=1, people=[])])
        elif path == '/resource-development/records':
            if req.method == 'POST':
                payload = req.post_data_json
                saves.append(copy.deepcopy(payload))
                if conflict[0]:
                    conflict[0] = False
                    row['revision'] += 1
                    route.fulfill(status=409, json={'detail': '记录已被修改，请重新打开后再保存'})
                    return
                entries = [dict(**entry, operator_name='实际保存人员', created_at=f'2026-10-08T14:05:{len(row["follow_ups"])+index:02d}+08:00')
                           for index, entry in enumerate(payload.get('follow_ups', []))]
                row.update({key: value for key, value in payload.items() if key not in {'follow_ups', 'follow_up'}})
                row['revision'] += 1
                row['follow_ups'] = list(reversed(entries)) + row['follow_ups']
                row['follow_up_count'] = len(row['follow_ups'])
                row['latest_follow_up_entry'] = row['follow_ups'][0] if row['follow_ups'] else None
                row['latest_follow_up'] = row['latest_follow_up_entry']['content'] if row['latest_follow_up_entry'] else row['follow_up']
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
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/resource-follow-up-dist',
                                '--host', '127.0.0.1', '--port', '12448', '--strictPort'], cwd=ROOT / 'frontend',
                               stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(50):
            try:
                urlopen(BASE, timeout=1).close()
                break
            except Exception:
                time.sleep(.2)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel='msedge')
            context = browser.new_context(viewport=dict(width=1440, height=900), timezone_id='America/New_York')
            context.route('**/api/**', api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(BASE + '/resource-management/resource-development')
            expect(page.get_by_role('button', name='填写后续跟进情况')).to_be_visible()
            page.get_by_role('button', name='填写后续跟进情况').click()
            dialog = page.locator('.development-dialog:visible')
            expect(dialog).to_contain_text('后续跟进情况')
            expect(dialog.locator('.el-select')).to_have_count(0)
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog.get_by_text('请填写跟进内容或移除此条草稿')).to_be_visible()
            assert not saves
            expect(dialog.locator('textarea')).to_be_focused()
            dialog.locator('textarea').fill('已添加，等待回复\n明天继续联系')
            dialog.get_by_role('button', name='新增跟进情况', exact=True).click()
            dialog.locator('textarea').nth(1).fill('第二次跟进：已回复')
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog).to_have_count(0)
            assert len(saves[-1]['follow_ups']) == 2 and not saves[-1]['actions']
            assert all(set(entry) == {'id', 'content'} for entry in saves[-1]['follow_ups'])
            assert 'follow_up' not in saves[-1]
            latest_button = page.get_by_role('button', name='第二次跟进：已回复', exact=False)
            expect(latest_button).to_contain_text('实际保存人员 · 2026年10月08日 14:05:01')
            latest_button.click()
            expect(dialog.locator('.follow-up-history .el-descriptions')).to_have_count(2)
            expect(dialog.locator('.follow-up-history')).to_contain_text('已添加，等待回复')
            expect(dialog.locator('.follow-up-history input, .follow-up-history textarea, .follow-up-history button')).to_have_count(0)
            expect(dialog.locator('textarea')).to_have_count(1)
            page.screenshot(path=str(out / 'follow-up-history.png'), full_page=True)
            dialog.locator('textarea').fill('冲突仍保留的草稿')
            conflict[0] = True
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog.get_by_role('button', name='重新加载（保留文字草稿）')).to_be_visible()
            expect(dialog.locator('textarea')).to_have_value('冲突仍保留的草稿')
            dialog.get_by_role('button', name='重新加载（保留文字草稿）').click()
            expect(dialog.locator('textarea')).to_have_value('冲突仍保留的草稿')
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog).to_have_count(0)
            assert row['follow_up_count'] == 3
            # 详情是左侧 Popover，并显示多条文字历史。
            page.get_by_role('button', name='查看详情', exact=True).click()
            popover = page.locator('.development-detail:visible')
            expect(popover).to_have_attribute('data-popper-placement', 'left')
            expect(popover.locator('.follow-up-history .el-descriptions')).to_have_count(3)
            assert popover.locator('.development-detail-body').evaluate('(el) => getComputedStyle(el).overflowY') == 'auto'
            page.get_by_role('heading', name='资源开拓', exact=True).click()
            row['follow_up'] = '旧表原文，没有可推测的操作时间'
            for button, title in [('新增', '新增资源开拓'), ('编辑', '编辑资源开拓')]:
                page.get_by_role('button', name=button, exact=True).click()
                expect(dialog).to_contain_text(title)
                page.wait_for_timeout(350)
                preset = dialog.bounding_box()
                dialog.get_by_role('button', name='新增跟进情况', exact=True).click()
                dialog.locator('textarea[placeholder="请输入本次跟进情况"]').fill('未保存草稿')
                if button == '编辑':
                    expect(dialog.locator('.follow-up-history')).to_contain_text(row['follow_up'])
                body = dialog.locator('.el-dialog__body')
                body.evaluate('(el) => el.scrollTop = el.scrollHeight / 2')
                expect(dialog.get_by_role('button', name='取消', exact=True)).to_be_in_viewport()
                body.evaluate('(el) => el.scrollTop = el.scrollHeight')
                expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
                assert dialog.evaluate('(el) => el.scrollHeight <= el.clientHeight + 2')
                # DOM 自动发现新增的重复跟进字段。
                search = dialog.get_by_placeholder('搜索字段，如资源姓名')
                search.fill('后续跟进')
                page.get_by_role('option').filter(has_text='后续跟进情况').first.click()
                expect(dialog.locator('textarea[placeholder="请输入本次跟进情况"]')).to_be_focused()
                page.wait_for_timeout(350)
                initial = dialog.bounding_box()
                handle = dialog.locator('.el-dialog__header').bounding_box()
                page.mouse.move(handle['x'] + 15, handle['y'] + 12)
                page.mouse.down(); page.mouse.move(handle['x'] + 100, handle['y'] + 52); page.mouse.up()
                page.wait_for_timeout(150)
                moved = dialog.bounding_box()
                assert abs(moved['x'] - initial['x']) > 20
                page.mouse.move(moved['x'] + 15, moved['y'] + 12)
                page.mouse.down(); page.mouse.move(-800, -800); page.mouse.up()
                bounded = dialog.bounding_box()
                assert bounded['x'] >= -1 and bounded['y'] >= -1
                dialog.locator('.el-dialog__headerbtn').click()
                expect(dialog).to_have_count(0)
                page.get_by_role('button', name=button, exact=True).click()
                expect(dialog).to_be_visible()
                page.wait_for_timeout(350)
                reopened = dialog.bounding_box()
                assert abs(reopened['x'] - preset['x']) < 2 and abs(reopened['y'] - preset['y']) < 2, (preset, reopened)
                expect(dialog.locator('textarea[placeholder="请输入本次跟进情况"]')).to_have_count(0)
                dialog.get_by_role('button', name='取消', exact=True).click()
            page.set_viewport_size(dict(width=600, height=760))
            page.get_by_role('button', name='编辑', exact=True).click()
            expect(dialog).to_be_visible()
            page.wait_for_timeout(300)
            box = dialog.bounding_box()
            assert box['width'] <= 568 and box['x'] >= 0 and box['x'] + box['width'] <= 600
            dialog.locator('.el-dialog__body').evaluate('(el) => el.scrollTop = el.scrollHeight')
            expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
            page.screenshot(path=str(out / 'small-screen.png'), full_page=True)
            dialog.get_by_role('button', name='取消', exact=True).click()
            assert not errors, errors
            browser.close()
        print(json.dumps({'ok': True, 'checks': ['多条人工跟进', '空白定位', '自动人时展示', '历史只读', '冲突保留草稿',
              '历史原文', '左侧详情与滚动', '新增编辑与取消', '固定底部', '字段搜索', '拖拽边界与复位', '小屏']}, ensure_ascii=False))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


if __name__ == '__main__':
    run()
