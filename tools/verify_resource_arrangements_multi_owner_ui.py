"""使用隔离接口验收每日安排多人负责人和招聘项目入口。"""
import copy
import json
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:12458'


def run():
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('仅允许在本机项目目录验收')
    day = datetime.now(ZoneInfo('Asia/Hong_Kong')).date().isoformat()
    manager, first, second, platform, project = [str(uuid4()) for _ in range(5)]
    project_row = dict(source_type='recruitment', project_id=project, order_no='RP-QA-001',
                       project_name='全职招聘验收项目', languages=['英语 → 日语'])
    cell = dict(platform_id=platform, platform_name='招聘账号', owner_id=first, owner_name='甲',
                owner_ids=[first], owners=[dict(id=first, name='甲')], can_complete=True,
                targets=[], projects=[], manual_projects=[], role_tags=[], remarks='', completed=False)
    current = dict(work_date=day, revision=1, remarks='', cells=[cell])
    writes, errors = [], []

    def api(route):
        req = route.request
        path = urlparse(req.url).path.removeprefix('/api')
        if path == '/auth/session':
            result = dict(user_id=manager, username='qa', full_name='统筹', roles=['admin'], permissions=['talents:read', 'talents:write'])
        elif path == '/resource-development/options':
            result = dict(options=[dict(id=platform, kind='platform', category='national', name='招聘账号')],
                          users=[dict(id=first, name='甲'), dict(id=second, name='乙')], languages=[],
                          user_id=manager, can_write=True, can_delegate=True, can_configure=True)
        elif path == '/resource-development/arrangement-options':
            result = dict(targets=[], request_projects=[], projects=[], recruitment_projects=[project_row])
        elif path == '/resource-development/arrangements':
            result = dict(items=[copy.deepcopy(current)], total=1)
        elif path == f'/resource-development/arrangements/{day}':
            if req.method == 'PUT':
                payload = req.post_data_json
                writes.append(payload)
                selected = payload['cells'][0]
                cell.update(owner_ids=selected['owner_ids'], owners=[dict(id=value, name='甲' if value == first else '乙') for value in selected['owner_ids']],
                            owner_name='甲、乙', targets=[dict(kind='recruitment_project', project_id=project,
                            label=project_row['project_name'], project=project_row, active=True)],
                            projects=[project_row], completed=False)
                current['revision'] += 1
            result = copy.deepcopy(current)
        elif path.endswith('/completion') and req.method == 'PATCH':
            cell['completed'] = req.post_data_json['completed']
            cell['completed_by_name'] = '统筹' if cell['completed'] else ''
            cell['completed_at'] = day + 'T14:30:00+08:00' if cell['completed'] else None
            current['revision'] += 1
            result = copy.deepcopy(current)
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        else:
            result = {}
        route.fulfill(status=200, json=result)

    out = ROOT / '.tmp/resource-arrangements-multi-owner-ui'
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'preview.log').open('w', encoding='utf-8') as log:
        preview = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1',
                                    '--port', '12458', '--strictPort'], cwd=ROOT / 'frontend',
                                   stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for _ in range(60):
                try:
                    urlopen(BASE, timeout=1).close()
                    break
                except Exception:
                    time.sleep(.2)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, channel='msedge')
                context = browser.new_context(viewport=dict(width=1440, height=900))
                context.route('**/api/**', api)
                context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(BASE + '/resource-management/resource-development?section=arrangements')
                expect(page.get_by_role('tab', name='每日安排')).to_be_visible()
                page.get_by_role('button', name='编辑安排', exact=True).first.click()
                dialog = page.locator('.arrangement-editor:visible')
                expect(dialog).to_be_visible()
                owner_field = dialog.locator('.el-form-item').filter(has=page.get_by_text('负责人', exact=True)).first
                owner_field.locator('.el-select').click()
                page.get_by_role('option', name='乙', exact=True).click()
                expect(owner_field.locator('.el-tag')).to_have_count(2)
                page.keyboard.press('Escape')
                direction = dialog.locator('.el-form-item').filter(has=page.get_by_text('开拓方向（语种／方言）', exact=True)).first
                direction.locator('.el-select').click()
                dropdown = page.locator('.arrangement-target-dropdown:visible')
                expect(dropdown.get_by_text('全职招聘项目', exact=True)).to_be_visible()
                direction.locator('input').fill('RP-QA-001')
                dropdown.get_by_role('option', name='全职招聘验收项目 · RP-QA-001 · 英语 → 日语').click()
                expect(dialog.get_by_text('全职招聘验收项目', exact=False).first).to_be_visible()
                dialog.get_by_role('button', name='保存', exact=True).click()
                expect(dialog).not_to_be_visible()
                assert writes and writes[-1]['cells'][0]['owner_ids'] == [first, second]
                assert writes[-1]['cells'][0]['targets'][0]['project_id'] == project
                expect(page.locator('.arrangement-table')).to_contain_text('甲、乙')
                page.get_by_role('button', name='查看详情', exact=True).first.click()
                expect(page.locator('.arrangement-detail:visible')).to_contain_text('甲、乙')
                page.locator('.page-title').click()
                page.locator('.arrangement-table .el-checkbox').first.click()
                expect(page.locator('.arrangement-table .el-checkbox input').first).to_be_checked()
                page.get_by_role('button', name='编辑安排', exact=True).first.click()
                expect(dialog).to_be_visible()
                header = dialog.locator('.el-dialog__header')
                before = dialog.bounding_box()
                handle = header.bounding_box()
                page.mouse.move(handle['x'] + 30, handle['y'] + 20)
                page.mouse.down()
                page.mouse.move(handle['x'] + 120, handle['y'] + 60, steps=6)
                page.mouse.up()
                moved = dialog.bounding_box()
                assert abs(moved['x'] - before['x']) > 20
                dialog.get_by_role('button', name='关闭窗口').click()
                expect(dialog).not_to_be_visible()
                page.get_by_role('button', name='编辑安排', exact=True).first.click()
                expect(dialog).to_be_visible()
                restored = dialog.bounding_box()
                assert abs(restored['x'] - before['x']) < 3
                dialog.get_by_role('button', name='关闭窗口').click()
                expect(dialog).not_to_be_visible()
                assert not errors, errors
                page.screenshot(path=str(out / 'result.png'), full_page=True)
                browser.close()
        finally:
            preview.terminate()
            preview.wait(timeout=15)
    (out / 'result.json').write_text(json.dumps(dict(passed=True, writes=len(writes), errors=errors), ensure_ascii=False), encoding='utf-8')
    print('多人负责人和招聘项目页面验收通过')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    run()
