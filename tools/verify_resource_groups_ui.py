"""局域网企微群交互验收：真实构建页面、隔离接口，不修改业务数据。"""
import copy
import argparse
import json
import socket
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:12448'


def run(base_url=None):
    global BASE
    if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在局域网调试机执行')
    if base_url:
        parsed = urlparse(base_url)
        if parsed.scheme != 'https' or parsed.hostname != 'oa.xinshify.com.cn' or socket.gethostbyname(parsed.hostname) != '192.168.31.144':
            raise SystemExit('已发布页面验收仅允许局域网 HTTPS 入口')
        BASE = base_url.rstrip('/')
    out = ROOT / ('.tmp/resource-groups-ui/live' if base_url else '.tmp/resource-groups-ui')
    out.mkdir(parents=True, exist_ok=True)
    log = None if base_url else (out / 'preview.log').open('w', encoding='utf-8')
    process = None if base_url else subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/resource-groups-dist', '--host', '127.0.0.1', '--port', '12448', '--strictPort'], cwd=ROOT / 'frontend', stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    uid, owner, platform, person = [str(uuid4()) for _ in range(4)]
    today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    record = dict(id=str(uuid4()), revision=1, full_name='企微群验收人才', owner_id=owner, owner_name='原开拓人', platform_id=platform, platform_name='验收平台', account_id=None, work_date=today, language_ids=[], language_names='', phone='', wechat='', follow_up='', remarks='', actions=[], capabilities=[], person_id=person, resource_code='QA-GROUP', progress={'group': {'status': '已拉群', 'operator_name': '历史操作人', 'action_date': '2026-09-24'}}, historical_markers={'group': {'status': '已邀进群', 'operator_name': '历史操作人', 'action_date': '2026-09-24'}}, can_edit=True, can_delete=True, follow_ups=[])
    saves, requests, errors = [], [], []
    fail_next = False

    def apply_action(action):
        action.update(operator_id=uid, operator_name='实际操作人', action_date=today, created_at=today + 'T10:00:00', created_by_name='实际操作人', updated_by_name='实际操作人')
        record['actions'].append(action)
        record['progress'][action['channel']] = {key: action[key] for key in ['status', 'operator_name', 'action_date']}

    def api(route):
        nonlocal fail_next
        request = route.request
        path = urlparse(request.url).path.removeprefix('/api')
        requests.append((request.method, path, parse_qs(urlparse(request.url).query)))
        result = []
        if path == '/auth/session':
            result = dict(id=uid, username='qa', full_name='实际操作人', roles=['admin'], permissions=['talents:read', 'talents:write', 'resource_development:delegate'])
        elif path == '/resource-development/options':
            result = dict(options=[dict(id=platform, kind='platform', category='national', name='验收平台')], users=[dict(id=uid, name='实际操作人'), dict(id=owner, name='原开拓人')], languages=[], user_id=uid, can_delegate=True, is_admin=True, can_write=True)
        elif path == '/resource-development/days':
            result = dict(total=1, items=[dict(date=today, count=1, people=[dict(owner_id=owner, duration_minutes=0)])])
        elif path.endswith('/group-actions'):
            payload = request.post_data_json
            assert not {'operator_id', 'action_date'} & payload.keys()
            if fail_next:
                fail_next = False
                route.fulfill(status=409, json={'detail': '记录已被修改，请重新打开后再保存'})
                return
            saves.append(copy.deepcopy(payload))
            apply_action(dict(id=payload['id'], channel=payload['channel'], status=payload['status']))
            record['revision'] += 1
            result = record
        elif path == '/resource-development/records' and request.method == 'POST':
            payload = request.post_data_json
            saves.append(copy.deepcopy(payload))
            old_ids = {a['id'] for a in record['actions']}
            for action in payload['actions']:
                if action['id'] not in old_ids:
                    apply_action(action)
            record.update(revision=record['revision'] + 1, person_id=person)
            result = record
        elif path == '/resource-development/records':
            result = dict(total=1, items=[record])
        elif path.startswith('/resource-development/records/'):
            result = record
        elif path == '/resource-development/duplicates':
            result = dict(items=[])
        elif path == '/resource-development/friend-daily/options':
            result = dict(accounts=[], languages=[], overview_rows=[], can_write=True)
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        route.fulfill(status=200, json=result)

    try:
        for _ in range(0 if base_url else 50):
            try:
                urlopen(BASE, timeout=1).close()
                break
            except Exception:
                time.sleep(0.2)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel='msedge', args=['--no-proxy-server'])
            page = browser.new_page(viewport=dict(width=1600, height=1000))
            page.set_default_timeout(10000)
            page.set_default_navigation_timeout(30000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('**/api/**', api)
            page.goto(BASE, wait_until='domcontentloaded')
            page.evaluate("localStorage.setItem('token','qa')")
            page.goto(BASE + '/resource-management/resource-development', wait_until='domcontentloaded')
            expect(page.get_by_role('button', name='企微群验收人才的企微小群状态')).to_be_visible()

            def cell(channel):
                label = '企微小群' if channel == 'group' else '企微大群'
                return page.get_by_role('button', name=f'企微群验收人才的{label}状态').locator('xpath=ancestor::div[contains(@class,"development-group-progress")]')

            for channel, statuses in [('group', ['未处理', '已拉群', '已进群', '已退群']), ('group_large', ['未处理', '已拉群', '已发码', '已进群', '已退群'])]:
                current = cell(channel)
                current.get_by_role('button').first.click()
                expect(page.locator('.el-dropdown-menu:visible .el-dropdown-menu__item')).to_have_text(statuses)
                page.screenshot(path=str(out / f'{channel}-dropdown.png'), full_page=True)
                page.mouse.click(30, 20)
                expect(page.locator('.el-dropdown-menu:visible')).to_have_count(0)
                page.wait_for_timeout(250)
                for status in [s for s in statuses if s != record['progress'].get(channel, {}).get('status', '未处理')]:
                    current = cell(channel)
                    current.get_by_role('button').first.click()
                    expect(page.locator('.el-dropdown-menu:visible')).to_be_visible()
                    page.get_by_role('menuitem', name=status, exact=True).click()
                    expect(cell(channel)).to_contain_text(status)
                    expect(cell(channel)).to_contain_text('实际操作人')
                    expect(page.locator('.el-loading-mask:visible')).to_have_count(0)
                current = cell(channel)
                current.get_by_role('button', name='查看历史', exact=True).click()
                history = page.locator('.development-group-history:visible')
                expect(history.locator('.group-history-record')).to_have_count(len([a for a in record['actions'] if a['channel'] == channel]) + (1 if channel == 'group' else 0))
                expect(history).to_contain_text('实际操作人')
                if channel == 'group':
                    expect(history).to_contain_text('历史操作人')
                    expect(history).not_to_contain_text('已邀进群')
                page.screenshot(path=str(out / f'{channel}-history.png'), full_page=True)
                page.mouse.click(30, 20)
            expected_actions = [('group', '未处理'), ('group', '已进群'), ('group', '已退群'), ('group_large', '已拉群'), ('group_large', '已发码'), ('group_large', '已进群'), ('group_large', '已退群')]
            assert [(entry['channel'], entry['status']) for entry in saves] == expected_actions
            # 保存失败不伪造最新状态，也不增加历史。
            count = len(record['actions'])
            fail_next = True
            cell('group_large').get_by_role('button').first.click()
            page.get_by_role('menuitem', name='已发码', exact=True).click()
            expect(page.get_by_text('记录已被修改，请重新打开后再保存', exact=True)).to_be_visible()
            expect(cell('group_large')).to_contain_text('已退群')
            assert len(record['actions']) == count
            # 尚未入库时走现有专业分类校验，操作人、日期不可手工改写。
            record['person_id'] = None
            page.reload(wait_until='domcontentloaded')
            cell('group_large').get_by_role('button').first.click()
            page.get_by_role('menuitem', name='已进群', exact=True).click()
            dialog = page.locator('.development-dialog:visible')
            expect(dialog.get_by_text('进入人才总库', exact=True)).to_be_visible()
            action = dialog.locator('.development-action:visible').last
            expect(action.get_by_role('textbox', name='*操作人员', exact=True)).to_have_value('实际操作人')
            expect(action.locator('.el-input__inner[readonly]')).to_have_count(2)
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog).to_be_visible()
            dialog.get_by_text('标注', exact=True).click()
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(cell('group_large')).to_contain_text('已进群')
            # 两列的漏斗选项与状态下拉一致。
            page.get_by_role('button', name='企微大群筛选', exact=True).click()
            funnel = page.locator('.column-header-filter-popover:visible')
            expect(funnel.locator('.el-checkbox__label')).to_have_text(['未处理', '已拉群', '已发码', '已进群', '已退群'])
            funnel.get_by_text('已发码', exact=True).click()
            funnel.get_by_role('button', name='确定', exact=True).click()
            expect(page.locator('.el-loading-mask:visible')).to_have_count(0)
            for suffix in ['/days', '/records']:
                query = next(q for _, path, q in reversed(requests) if path.endswith(suffix))
                assert json.loads(query['column_filters'][0])['group_large_status'] == ['已发码']
            page.get_by_role('button', name='清空列筛选', exact=True).click()
            page.set_viewport_size(dict(width=600, height=760))
            page.get_by_role('button', name='企微群验收人才的企微小群状态').scroll_into_view_if_needed()
            cell('group').get_by_role('button', name='查看历史', exact=True).click()
            history = page.locator('.development-group-history:visible')
            expect(history).to_be_visible()
            expect(history.locator('.group-history-record')).to_have_count(len([a for a in record['actions'] if a['channel'] == 'group']) + 1)
            expect(history.locator('.group-history-record .el-descriptions__content').filter(has_text='已进群')).to_have_count(1)
            page.wait_for_timeout(250)  # 等待浮层动画结束后检查最终布局并截图。
            box = history.bounding_box()
            page.screenshot(path=str(out / 'small-screen.png'), full_page=True)
            assert box['width'] <= 569 and box['x'] >= 0 and box['x'] + box['width'] <= 601, box
            page.mouse.click(30, 20)
            record['can_edit'] = False
            page.set_viewport_size(dict(width=1600, height=1000))
            page.reload(wait_until='domcontentloaded')
            expect(page.get_by_role('button', name='企微群验收人才的企微小群状态')).to_have_count(0)
            expect(page.locator('.development-group-progress').get_by_role('button', name='查看历史', exact=True)).to_have_count(2)
            assert not errors, errors
            browser.close()
        print(json.dumps(dict(ok=True, saves=len(saves), checks=['两类群完整状态下拉', '实际操作人和日期', '独立历史与旧状态兼容', '保存失败保护', '入库分类校验', '漏斗筛选参数', '小屏历史窗口']), ensure_ascii=False))
    finally:
        if process:
            process.terminate()
            process.wait(timeout=15)
            log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', help='验收已发布的局域网 HTTPS 页面')
    run(parser.parse_args().base)
