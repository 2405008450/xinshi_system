"""交接时间轴的真实浏览器验收；所有接口均进入独立本机测试库。"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from annotation_manager_change_models import AnnotationManagerChangeLog
from test_annotation_manager_changes import environment, reader_client


@pytest.fixture
def timeline_data(environment):
    db, users, parent, child, _ = environment
    parent.project_name = child.project_name = '同名交接验收项目·' + '客户经理与项目经理历史记录展示' * 12
    latest = datetime(2026, 10, 16, 9, 30, 15, tzinfo=timezone.utc)
    long_reason = '第一行：客户对接分工调整\n第二行：' + '需要保留完整原因并自动换行。' * 24
    def add(project, role, previous, new, previous_name, new_name, moment, mode, reason):
        row = AnnotationManagerChangeLog(
            id=uuid4(), project_id=project.id, order_no=project.order_no, project_name=project.project_name,
            manager_role=role, previous_manager_id=previous, new_manager_id=new,
            previous_manager_name=previous_name, new_manager_name=new_name,
            actor_user_id=users[0].id, actor_name_snapshot=users[0].full_name,
            change_mode=mode, changed_at=moment, reason=reason,
        )
        db.add(row)
        return row
    replacement = add(parent, 'client_manager', users[0].id, users[1].id, 'Jimmy', 'Ethan', latest, 'inline_edit', long_reason)
    removed = add(parent, 'project_manager', users[0].id, None, 'Jimmy', None, latest - timedelta(seconds=1), 'inline_edit', '移除与新增是独立历史事实')
    added = add(parent, 'project_manager', None, users[1].id, None, 'Ethan', latest - timedelta(seconds=1), 'inline_edit', '移除与新增是独立历史事实')
    add(child, 'client_manager', users[0].id, None, 'Jimmy', None, latest - timedelta(seconds=2), 'inheritance', '继承上级订单负责人')
    add(child, 'client_manager', None, users[0].id, None, 'Jimmy', latest - timedelta(seconds=3), 'project_edit', '首次分配')
    add(parent, 'client_manager', None, users[2].id, None, 'Lulu', latest - timedelta(seconds=4), 'project_edit', None)
    for index in range(52):
        add(parent if index % 2 == 0 else child, 'client_manager', users[0].id, users[1].id, 'Jimmy', 'Ethan',
            latest - timedelta(days=1, minutes=index), 'direct_transfer', f'批量交接记录 {index}')
    db.commit()
    return db, users, parent, child, replacement, removed, added, long_reason


def test_manager_history_project_role_date_filters_and_original_rows(timeline_data):
    db, users, parent, child, replacement, removed, added, _ = timeline_data
    client = reader_client(db, users[0])
    path = '/projects/annotation/manager-change-logs'
    result = client.get(path, params={'project_id':str(parent.id), 'manager_role':'client_manager', 'keyword':'批量交接记录'}).json()
    assert result['total'] == 26 and {row['project_id'] for row in result['items']} == {str(parent.id)}
    result = client.get(path, params={'project_id':str(parent.id), 'manager_role':'project_manager',
        'changed_from':'2026-10-16T17:30:14+08:00', 'changed_to':'2026-10-16T09:30:15Z'}).json()
    assert result['total'] == 2 and {row['id'] for row in result['items']} == {str(removed.id), str(added.id)}
    assert all(row['changed_at'].endswith('+08:00') for row in result['items'])
    assert client.get(path, params={'keyword':'不存在的交接原因'}).json()['total'] == 0
    assert db.query(AnnotationManagerChangeLog).count() == 58


def test_manager_history_timeline_browser(timeline_data):
    from playwright.sync_api import sync_playwright, expect
    db, users, parent, child, replacement, removed, added, long_reason = timeline_data
    client = reader_client(db, users[0])
    requests, errors = [], []
    fail_next = False
    output = Path(__file__).resolve().parents[1] / '.tmp' / 'annotation-manager-timeline-ui'
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width':1303, 'height':884}, timezone_id='America/Los_Angeles')
        info = {'token':'isolated-timeline-test', 'user_id':str(users[0].id), 'user_name':users[0].username,
            'user_full_name':users[0].full_name, 'user_roles':'[]', 'user_permissions':json.dumps(['projects:read'])}
        auth_script = 'Object.entries('+json.dumps(info)+').forEach(([key,value])=>localStorage.setItem(key,value))'
        context.add_init_script(auth_script)
        def route_api(route):
            nonlocal fail_next
            request = route.request
            split = urlsplit(request.url)
            assert split.path.startswith('/api/')
            path = split.path[4:] + ('?' + split.query if split.query else '')
            if split.path.endswith('/manager-change-logs'):
                requests.append(parse_qs(split.query))
                if fail_next:
                    fail_next = False
                    route.fulfill(status=503, json={'detail':'隔离验收：暂时无法加载交接记录'})
                    return
            response = client.request(request.method, path, content=request.post_data_buffer,
                headers={key:value for key,value in request.headers.items() if key.lower() in {'authorization','content-type'}})
            if response.status_code >= 500:
                errors.append((path, response.status_code, response.text[:200]))
            route.fulfill(status=response.status_code, body=response.content, headers={'content-type':response.headers.get('content-type','application/json')})
        context.route(re.compile(r'^http://localhost:3000/api/'), route_api)
        page = context.new_page()
        page.route_web_socket(re.compile(r'^ws://localhost:3000/api/'), lambda socket:None)
        page.on('pageerror', lambda error:errors.append(str(error)))
        page.set_default_timeout(15000)
        try:
            page.goto('http://localhost:3000/annotation-details', wait_until='networkidle')
            page.get_by_role('button',name='交接',exact=True).click()
            dialog = page.locator('.annotation-manager-transfer-dialog')
            panel = dialog.locator('.annotation-manager-change-log-panel')
            events = panel.locator('.manager-change-event')
            expect(events).to_have_count(50)
            assert panel.locator('table').count() == 0
            assert dialog.get_by_role('tab',name='批量交接').count() == 0
            expect(events.first.locator('strong')).to_have_text('客户经理：Jimmy → Ethan')
            expect(events.first.locator('time')).to_have_text('2026/10/16 17:30:15')
            expect(events.first.locator('.manager-change-reason>div')).to_have_text(long_reason)
            assert events.first.locator('.manager-change-reason>div').evaluate('element => getComputedStyle(element).whiteSpace') == 'pre-wrap'
            expect(panel.locator(f'[data-change-id="{removed.id}"] strong')).to_have_text('项目经理：移除 Jimmy')
            expect(panel.locator(f'[data-change-id="{added.id}"] strong')).to_have_text('项目经理：新增 Ethan')
            expect(panel.get_by_text('上级同步',exact=True)).to_be_visible()
            expect(panel.get_by_text('首次分配',exact=True)).to_be_visible()
            original_dialog = dialog.bounding_box()
            header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x']+40,header['y']+20); page.mouse.down()
            page.mouse.move(header['x']+70,header['y']+40,steps=8); page.mouse.up()
            moved = dialog.bounding_box()
            assert moved['x'] > original_dialog['x']+10
            page.mouse.move(moved['x']+40,moved['y']+20); page.mouse.down()
            page.mouse.move(-900,-900,steps=8); page.mouse.up()
            assert dialog.bounding_box()['x'] >= -1 and dialog.bounding_box()['y'] >= -1
            dialog.locator('.el-dialog__headerbtn').click()
            expect(dialog).not_to_be_visible()
            page.get_by_role('button',name='交接',exact=True).click()
            expect(events).to_have_count(50)
            page.wait_for_function('expected => {const box=document.querySelector(".annotation-manager-transfer-dialog").getBoundingClientRect();return Math.abs(box.x-expected.x)<3 && Math.abs(box.y-expected.y)<3}',arg=original_dialog)
            page.screenshot(path=str(output/'timeline-desktop.png'), full_page=True)
            # 秒级时间在其他浏览器时区仍保持香港时间。
            for zone in ['UTC','Asia/Hong_Kong']:
                zone_context = browser.new_context(viewport={'width':1303,'height':884}, timezone_id=zone)
                zone_context.add_init_script(auth_script)
                zone_context.route(re.compile(r'^http://localhost:3000/api/'), route_api)
                zone_page = zone_context.new_page()
                zone_page.route_web_socket(re.compile(r'^ws://localhost:3000/api/'), lambda socket:None)
                zone_page.on('pageerror', lambda error:errors.append(str(error)))
                try:
                    zone_page.goto('http://localhost:3000/annotation-details', wait_until='networkidle')
                    zone_page.get_by_role('button',name='交接',exact=True).click()
                    expect(zone_page.locator('.manager-change-event').first.locator('time')).to_have_text('2026/10/16 17:30:15')
                finally:
                    zone_context.close()
            panel.locator('.manager-log-pagination .btn-next').click()
            expect(events).to_have_count(8)
            assert requests[-1]['skip'] == ['50']
            parent_event = panel.locator(f'.manager-change-event[data-project-id="{parent.id}"]').first
            parent_event.get_by_role('button',name='仅看该项目',exact=True).click()
            expect(events).to_have_count(30)
            expect(panel.locator('.manager-log-project-filter')).to_contain_text(parent.order_no)
            assert requests[-1]['project_id'] == [str(parent.id)] and requests[-1]['skip'] == ['0']
            assert {node.get_attribute('data-project-id') for node in events.all()} == {str(parent.id)}
            # 经理类型、关键词与项目条件共同生效，返回汇总只清除项目。
            panel.locator('.manager-log-filters .el-select').click()
            page.locator('.el-select-dropdown:visible').get_by_text('客户经理',exact=True).click()
            expect(events).to_have_count(28)
            keyword = panel.get_by_placeholder('订单号、项目名称、负责人、操作人或原因')
            keyword.fill('批量交接记录')
            expect(events).to_have_count(26)
            panel.get_by_role('button',name='查看全部项目',exact=True).click()
            expect(events).to_have_count(50)
            assert 'project_id' not in requests[-1]
            assert requests[-1]['manager_role'] == ['client_manager'] and requests[-1]['keyword'] == ['批量交接记录']
            expect(keyword).to_have_value('批量交接记录')
            panel.get_by_role('button',name='重置',exact=True).click()
            expect(keyword).to_have_value('')
            expect(events).to_have_count(50)
            assert not {'project_id','manager_role','keyword'} & requests[-1].keys()
            # 失败时清除旧节点并允许重试；无结果时给出明确空状态。
            fail_next = True
            panel.get_by_role('button',name='查询',exact=True).click()
            expect(panel.get_by_text('隔离验收：暂时无法加载交接记录',exact=True)).to_be_visible()
            expect(events).to_have_count(0)
            panel.get_by_role('button',name='重试加载',exact=True).click()
            expect(events).to_have_count(50)
            keyword.fill('不存在的交接原因')
            expect(panel.get_by_text('暂无符合条件的负责人变更记录',exact=True)).to_be_visible()
            keyword.fill('')
            expect(events).to_have_count(50)
            # 长项目名、长原因及大量节点仅在弹窗内容区滚动。
            page.set_viewport_size({'width':520,'height':700})
            expect(dialog.get_by_role('button',name='关闭',exact=True)).to_be_visible()
            assert dialog.evaluate('element => element.scrollWidth <= element.clientWidth + 1')
            body = dialog.locator('.el-dialog__body')
            assert body.evaluate('element => element.scrollHeight > element.clientHeight')
            footer_before = dialog.locator('.el-dialog__footer').bounding_box()
            body.evaluate('element => { element.scrollTop = element.scrollHeight }')
            expect(dialog.get_by_role('button',name='关闭',exact=True)).to_be_visible()
            assert abs(dialog.locator('.el-dialog__footer').bounding_box()['y'] - footer_before['y']) < 2
            body.evaluate('element => { element.scrollTop = 0 }')
            page.screenshot(path=str(output/'timeline-small.png'), full_page=True)
            assert db.query(AnnotationManagerChangeLog).count() == 58
            assert not errors, errors
        except Exception:
            page.screenshot(path=str(output/'failure.png'), full_page=True)
            raise
        finally:
            context.close(); browser.close()
