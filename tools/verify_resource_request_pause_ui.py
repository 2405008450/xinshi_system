"""构建页面验收暂停/恢复；全部 API 使用内存数据，不访问业务数据库。"""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:12459'


def run():
    global BASE
    sys.stdout.reconfigure(encoding='utf-8')
    assert socket.gethostname().upper() == 'PC' and ROOT == Path(r'E:\xinshi_system')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    BASE = f'http://127.0.0.1:{port}'
    out = ROOT / '.tmp/resource-request-pause-ui'
    out.mkdir(parents=True, exist_ok=True)
    actor = str(uuid4())
    platform = dict(id=str(uuid4()), kind='platform', category='national', name='暂停验收平台', description='隔离验收账号')
    rows = {}
    for status in ['confirmed', 'draft', 'cancelled', 'fulfilled']:
        rows[status] = dict(id=str(uuid4()), request_no='RR-QA-' + status, source_type='other', request_category='other',
                            other_source_name='暂停验收项目', source_project_name_snapshot='暂停验收项目',
                            source_project_types_snapshot=['暂停验收项目'], demand_status='confirmed' if status == 'fulfilled' else status,
                            request_status='in_progress' if status == 'confirmed' else status, progress_percent=100 if status == 'fulfilled' else 35,
                            owner_id=None, request_detail='原始需求内容', priority='medium', items=[],
                            requested_at='2026-10-01T10:00:00+08:00', created_at='2026-10-01T10:00:00+08:00',
                            updated_at='2026-10-15T10:00:00.000001+08:00', completed_at=None)
    calls, pending, errors, checks = [], [], [], []
    flags = dict(save_error=False, action_error=False, hold_save=False, hold_action=False, readonly=False)
    serial = [1]

    def version():
        serial[0] += 1
        return f'2026-10-15T10:00:00.{serial[0]:06d}+08:00'

    def api(route):
        req = route.request
        path = urlparse(req.url).path.removeprefix('/api')
        payload = req.post_data_json if req.method in {'POST', 'PUT', 'PATCH'} else None
        calls.append((req.method, path, copy.deepcopy(payload)))
        result = []
        if path == '/auth/session':
            result = dict(user_id=actor, username='隔离验收', full_name='隔离验收', roles=['staff'] if flags['readonly'] else ['admin'],
                          permissions=['projects:read'] if flags['readonly'] else ['*'])
        elif path == '/resource-requests/page':
            result = dict(total=len(rows), items=list(rows.values()))
        elif path == '/resource-development/options':
            result = dict(can_delegate=True, can_write=True, is_admin=True, user_id=actor, default_date='2026-10-15',
                          users=[dict(id=actor, name='隔离验收')], languages=[], options=[platform], arrangement_platforms=[platform])
        elif path == '/resource-development/days':
            result = dict(items=[], total=0)
        elif path == '/resource-development/arrangement-options':
            result = dict(targets=[], request_projects=[], projects=[])
        elif path == '/resource-development/arrangement-requests':
            result = dict(items=[], total=0)
        elif path.startswith('/resource-development/arrangements'):
            paused = rows['confirmed']['demand_status'] == 'paused'
            target = dict(kind='request_project', request_id=rows['confirmed']['id'], label='暂停验收项目',
                          request_no=rows['confirmed']['request_no'], active=not paused,
                          inactive_reason='需求已暂停' if paused else '', project=None)
            day = dict(work_date='2026-10-15', revision=1, remarks='保留已有安排', can_manage=True,
                       cells=[dict(platform_id=platform['id'], platform_name=platform['name'], owner_id=actor, owner_name='隔离验收',
                                   targets=[target], projects=[], manual_projects=[], role_tags=[], remarks='原有完成记录',
                                   completed=True, completed_by=actor, completed_by_name='隔离验收', completed_at='2026-10-15T09:30:00+08:00', can_edit=True)])
            result = dict(items=[day], total=1) if path == '/resource-development/arrangements' else day
        elif path.startswith('/resource-requests/') and path.split('/')[2] in {row['id'] for row in rows.values()}:
            row = next(row for row in rows.values() if row['id'] == path.split('/')[2])
            result = row
            if path.endswith(('/pause', '/resume')):
                if flags['action_error']:
                    route.fulfill(status=409, json=dict(detail='隔离验收：需求已被其他人修改，请重新打开后重试'))
                    return
                assert payload['expected_updated_at'] == row['updated_at'], payload
                row.update(demand_status='confirmed' if path.endswith('/resume') else 'paused', updated_at=version())
                if flags['hold_action']:
                    pending.append((route, copy.deepcopy(row))); return
            elif path.endswith('/cancel'):
                row.update(demand_status='cancelled', request_status='cancelled', updated_at=version())
            elif req.method == 'PUT':
                if flags['save_error']:
                    route.fulfill(status=500, json=dict(detail='隔离验收：需求保存失败')); return
                assert payload['expected_updated_at'] == row['updated_at'], payload
                row.update({key: value for key, value in payload.items() if key != 'expected_updated_at'})
                row['updated_at'] = version()
                if flags['hold_save']:
                    pending.append((route, copy.deepcopy(row))); return
        elif path.endswith('/access'):
            result = dict(can_enter=True, can_resource=True, can_collect=False, can_manage=False)
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        elif req.method not in {'GET', 'HEAD'}:
            raise AssertionError(f'未预期的写入接口：{req.method} {path}')
        route.fulfill(status=200, json=result)

    log = (out / 'preview.log').open('w', encoding='utf-8')
    preview = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/resource-request-pause-dist',
                                '--host', '127.0.0.1', '--port', str(port), '--strictPort'], cwd=ROOT / 'frontend',
                               stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(60):
            if preview.poll() is not None:
                raise RuntimeError('隔离预览启动失败，请检查 preview.log')
            try:
                urlopen(BASE, timeout=1).close(); break
            except OSError:
                time.sleep(.2)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel='msedge')
            context = browser.new_context(viewport=dict(width=1239, height=884), timezone_id='America/Los_Angeles', service_workers='block')
            context.route(re.compile(r'/api/'), api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.clock.install(time=datetime(2026, 10, 15, 10, 30, tzinfo=timezone(timedelta(hours=8))))
            page.goto(BASE + '/resource-requests')
            parent = page.locator('.resource-dialog')
            child = page.locator('.resource-lifecycle-dialog')

            def open_editor(key='confirmed'):
                page.locator('.el-table__body-wrapper tr').filter(has_text=rows[key]['request_no']).first.get_by_role('button', name='编辑', exact=True).click()
                expect(parent).to_be_visible()
                page.clock.run_for(350)

            def field():
                return parent.locator('.el-form-item').filter(has=page.locator('label', has_text='需求详情')).get_by_role('textbox')

            def open_action(resume=False):
                parent.get_by_role('button', name='恢复需求' if resume else '暂停需求', exact=True).click()
                expect(child).to_be_visible()
                page.clock.run_for(350)
                expect(parent.get_by_role('button', name='保存', exact=True)).to_be_disabled()

            def submit(resume=False):
                child.get_by_role('button', name='确认恢复' if resume else '确认暂停', exact=True).click()

            def closed():
                expect(child).not_to_be_visible()
                expect(parent).not_to_be_visible()
                page.clock.run_for(350)

            def check_layout(dialog):
                bounds = dialog.bounding_box()
                viewport = page.viewport_size
                assert bounds['x'] >= -1 and bounds['y'] >= -1, bounds
                assert bounds['x'] + bounds['width'] <= viewport['width'] + 1, bounds
                assert bounds['y'] + bounds['height'] <= viewport['height'] + 1, bounds
                expect(dialog.locator('.el-dialog__footer')).to_be_in_viewport()

            def drag(dialog, dx=90, dy=45):
                bounds = dialog.locator('.el-dialog__header').bounding_box()
                page.mouse.move(bounds['x'] + 20, bounds['y'] + 16)
                page.mouse.down(); page.mouse.move(bounds['x'] + 20 + dx, bounds['y'] + 16 + dy, steps=12); page.mouse.up()

            # 不同状态的入口规则与新增状态。
            for key in ['draft', 'cancelled', 'fulfilled']:
                open_editor(key)
                expect(parent.get_by_role('button', name='暂停需求', exact=True)).to_have_count(0)
                expect(parent.get_by_role('button', name='恢复需求', exact=True)).to_have_count(0)
                parent.get_by_role('button', name='关闭', exact=True).click()
                expect(parent).not_to_be_visible()
            page.get_by_role('button', name='新增资源需求', exact=True).click()
            expect(parent).to_be_visible()
            expect(parent.get_by_role('button', name='暂停需求', exact=True)).to_have_count(0)
            parent.get_by_role('button', name='关闭', exact=True).click()
            expect(parent).not_to_be_visible()
            checks.append('草稿、取消、完成及新增状态入口')

            open_editor()
            initial = parent.bounding_box()
            drag(parent)
            moved = parent.bounding_box()
            assert abs(moved['x'] - initial['x']) > 10
            drag(parent, 2000, 2000); check_layout(parent)
            parent.get_by_role('button', name='关闭', exact=True).click()
            expect(parent).not_to_be_visible(); open_editor()
            assert abs(parent.bounding_box()['x'] - initial['x']) < 2
            check_layout(parent)
            field().fill('暂停前修改的内容应先保存')
            preserved = {key: rows['confirmed'][key] for key in ['progress_percent', 'requested_at', 'request_status', 'owner_id']}
            open_action()
            reason = child.get_by_role('textbox')
            reason.fill('等' * 501)
            assert len(reason.input_value()) == 500
            reason.fill('等待客户确认')
            check_layout(child)
            position = child.bounding_box()
            drag(child)
            assert abs(child.bounding_box()['x'] - position['x']) > 10
            drag(child, 2000, 2000); check_layout(child)
            child.locator('.el-dialog__headerbtn').click()
            expect(child).not_to_be_visible(); open_action()
            assert abs(child.bounding_box()['x'] - position['x']) < 2
            expect(child.get_by_role('textbox')).to_have_value('')
            child.get_by_role('textbox').fill('等待客户确认')
            assert child.get_by_role('textbox').evaluate('el => el === document.activeElement')
            page.clock.run_for(3500)
            page.screenshot(path=str(out / 'pause-desktop.png'))
            before = len(calls)
            submit(); closed()
            writes = [(path, payload) for method, path, payload in calls[before:] if method in {'POST', 'PUT'}]
            assert writes[0][0].endswith(rows['confirmed']['id']) and writes[1][0].endswith('/pause'), writes
            assert writes[0][1]['request_detail'] == '暂停前修改的内容应先保存'
            assert writes[1][1]['reason'] == '等待客户确认'
            assert all(rows['confirmed'][key] == value for key, value in preserved.items())
            expect(page.locator('.el-table__body-wrapper tr').filter(has_text=rows['confirmed']['request_no']).first).to_contain_text('需求已暂停')
            checks.extend(['编辑弹窗拖动边界复位及固定底栏', '暂停窗口拖动、关闭与复位', '原因可选及500字限制', '先保存后暂停与状态刷新'])

            # 暂停态仅允许内容保存、恢复或取消；恢复保留进度和发送时间。
            row = page.locator('.el-table__body-wrapper tr').filter(has_text=rows['confirmed']['request_no']).first
            expect(row.get_by_role('button', name='更新进度', exact=True)).to_be_disabled()
            open_editor()
            expect(parent.get_by_role('button', name='发送', exact=True)).to_have_count(0)
            expect(parent.get_by_role('button', name='发到每日安排', exact=True)).to_have_count(0)
            expect(parent.get_by_role('button', name='取消需求', exact=True)).to_be_visible()
            field().fill('暂停期间仍可修改并保存')
            parent.get_by_role('button', name='保存', exact=True).click()
            expect(parent).not_to_be_visible()
            assert rows['confirmed']['demand_status'] == 'paused'
            open_editor(); open_action(True); submit(True); closed()
            assert rows['confirmed']['demand_status'] == 'confirmed'
            assert all(rows['confirmed'][key] == value for key, value in preserved.items())
            checks.append('暂停期间编辑及恢复保留原进度')

            # 保存失败和状态冲突均保留窗口与输入；不发出后续状态请求。
            open_editor(); field().fill('保存失败应保留此内容'); open_action()
            child.get_by_role('textbox').fill('保存失败后重试')
            flags['save_error'] = True
            count = sum(path.endswith('/pause') for _, path, _ in calls)
            submit()
            expect(page.get_by_text('隔离验收：需求保存失败', exact=True)).to_be_visible()
            expect(child.get_by_role('button', name='确认暂停', exact=True)).to_be_enabled()
            assert count == sum(path.endswith('/pause') for _, path, _ in calls)
            expect(child.get_by_role('textbox')).to_have_value('保存失败后重试')
            expect(field()).to_have_value('保存失败应保留此内容')
            flags.update(save_error=False, action_error=True)
            submit()
            expect(page.get_by_text('隔离验收：需求已被其他人修改，请重新打开后重试', exact=True)).to_be_visible()
            expect(child).to_be_visible()
            flags['action_error'] = False
            submit(); closed()
            checks.extend(['保存失败不暂停且保留输入', '状态冲突保留窗口可重试'])

            open_editor(); open_action(True); submit(True); closed()
            open_editor(); field().fill('等待正在执行的自动保存完成')
            flags['hold_save'] = True
            page.clock.fast_forward(10010)
            expect(parent.get_by_text('自动保存中…', exact=True)).to_be_visible()
            assert len(pending) == 1
            open_action()
            count = sum(path.endswith('/pause') for _, path, _ in calls)
            submit()
            expect(child.get_by_role('button', name='确认暂停', exact=True)).to_be_disabled()
            assert count == sum(path.endswith('/pause') for _, path, _ in calls)
            flags['hold_save'] = False
            route, value = pending.pop(); route.fulfill(status=200, json=value)
            closed()
            assert count + 1 == sum(path.endswith('/pause') for _, path, _ in calls)
            checks.append('等待自动保存队列及重复提交保护')

            # 小屏长内容只在正文滚动；嵌套确认窗保留固定操作栏。
            page.set_viewport_size(dict(width=390, height=720))
            open_editor()
            body = parent.locator('.el-dialog__body')
            assert body.evaluate('el => el.scrollHeight > el.clientHeight')
            for ratio in [.5, 1]:
                body.evaluate('(el, ratio) => el.scrollTop = el.scrollHeight * ratio', ratio)
                check_layout(parent)
                expect(parent.get_by_role('button', name='恢复需求', exact=True)).to_be_in_viewport()
            open_action(True); check_layout(child)
            page.clock.run_for(3500)
            page.screenshot(path=str(out / 'resume-mobile.png'))
            submit(True); closed()
            open_editor(); open_action(); check_layout(child)
            child.get_by_role('textbox').fill('')
            page.clock.run_for(3500)
            page.screenshot(path=str(out / 'pause-mobile.png'))
            submit(); closed()
            checks.extend(['小屏独立滚动和固定操作栏', '原因留空可暂停'])

            page.set_viewport_size(dict(width=1239, height=884))
            page.goto(BASE + '/resource-management/resource-development')
            page.get_by_role('tab', name='每日安排', exact=True).click()
            expect(page.locator('.arrangement-table')).to_contain_text('需求已暂停')
            expect(page.locator('.arrangement-table .el-checkbox input').first).to_be_checked()
            page.get_by_role('button', name='查看详情', exact=True).first.click()
            detail = page.locator('.arrangement-detail:visible')
            expect(detail).to_contain_text('需求已暂停')
            expect(detail).to_contain_text('原有完成记录')
            page.clock.run_for(500)
            page.screenshot(path=str(out / 'arrangement-paused.png'))
            checks.append('每日安排保留暂停标记及完成记录')
            page.goto(BASE + '/resource-requests')
            open_editor()
            parent.get_by_role('button', name='取消需求', exact=True).click()
            page.get_by_role('button', name='确认取消', exact=True).click()
            expect(parent).not_to_be_visible()
            assert rows['confirmed']['demand_status'] == 'cancelled'
            checks.append('暂停后取消需求')
            flags['readonly'] = True
            context.clear_cookies()
            page.evaluate("localStorage.clear();sessionStorage.clear();localStorage.setItem('token','isolated-qa')")
            page.reload()
            expect(page.get_by_role('button', name='新增资源需求', exact=True)).to_have_count(0)
            expect(page.get_by_role('button', name='编辑', exact=True)).to_have_count(0)
            checks.append('只读用户无状态修改入口')
            assert not errors, errors
            (out / 'result.json').write_text(json.dumps(dict(passed=True, scenarios=checks, api_calls=len(calls), errors=errors), ensure_ascii=False, indent=2), encoding='utf-8')
            browser.close()
            print(f'暂停需求浏览器验收通过：{len(checks)} 组场景，全部 API 均为隔离内存数据。')
    finally:
        preview.terminate(); preview.wait(timeout=15); log.close()


if __name__ == '__main__':
    run()
