"""需求到每日安排的真实页面验收；所有 API 均拦截到内存，禁止写入业务数据库。"""
import copy
import json
import re
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://localhost:3000'
TODAY = '2026-10-12'


def run():
    assert socket.gethostname().upper() == 'PC' and ROOT == Path(r'E:\xinshi_system')
    output = ROOT / '.tmp' / 'resource-request-arrangement-ui'
    output.mkdir(parents=True, exist_ok=True)
    uid, project, language, platform_a, platform_b = [str(uuid4()) for _ in range(5)]
    rows = {}
    for source in ['annotation', 'recruitment', 'interpretation', 'translation', 'other']:
        rid = str(uuid4())
        rows[source] = dict(id=rid, request_no='RR-测试-' + source, source_type=source,
                           request_category='annotation_trial' if source == 'annotation' else source,
                           demand_status='confirmed', request_status='submitted', request_detail='原始需求',
                           priority='medium', items=[], owner_id=None, progress_percent=0,
                           source_project_name_snapshot='快捷安排测试-' + source,
                           source_order_no_snapshot='AP-测试-' + source, source_project_types_snapshot=[],
                           requested_at='2026-10-12T00:20:00+08:00', updated_at='2026-10-12T00:20:00+08:00')
        if source == 'other':
            rows[source]['other_source_name'] = '其他测试项目'
        else:
            rows[source][source + '_project_id'] = project
    for status in ['draft', 'cancelled']:
        rows[status] = copy.deepcopy(rows['annotation']) | dict(id=str(uuid4()), request_no='RR-测试-' + status,
                                                               demand_status=status, request_status=status)
    options = dict(can_delegate=True, can_write=True, options=[], users=[], languages=[], user_id=uid,
                   arrangement_platforms=[dict(id=p, kind='platform', name=n, category='national', has_accounts=False)
                                         for p, n in [(platform_a, '测试账号A'), (platform_b, '测试账号B')]])
    day = dict(work_date=TODAY, revision=0, cells=[])
    calls, saves, errors, pending = [], [], [], []
    flags = dict(save_error=False, detail_error=False, options_error=False, day_error=False, conflict=False, hold_save=False)

    def current(rid):
        return next(r for r in rows.values() if r['id'] == rid)

    def summary(row):
        return dict(id=row['id'], request_no=row['request_no'], source_type=row['source_type'],
                    order_no=row['source_order_no_snapshot'], project_name=row['source_project_name_snapshot'],
                    request_status=row['request_status'], demand_status=row['demand_status'], arrangements=[])

    def api(route):
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path.removeprefix('/api')
        calls.append((request.method, path))
        result = []
        if path == '/auth/session':
            result = dict(user_id=uid, username='隔离验收', full_name='隔离验收', roles=['admin'], permissions=['*'])
        elif path == '/resource-requests/page':
            result = dict(total=len(rows), items=list(rows.values()))
        elif path == '/resource-requests/source-options':
            source = parse_qs(parsed.query)['source_type'][0]
            result = [dict(id=project, order_no='AP-测试-' + source, project_name='快捷安排测试-' + source)]
        elif path == '/resource-requests/source-request':
            result = rows[parse_qs(parsed.query)['source_type'][0]]
        elif path.endswith('/send') and path.startswith('/resource-requests/'):
            result = current(path.split('/')[2])
            result.update(demand_status='confirmed', request_status='submitted')
        elif path.startswith('/resource-requests/') and path.rsplit('/', 1)[-1] in {r['id'] for r in rows.values()}:
            row = current(path.rsplit('/', 1)[-1])
            result = row
            if request.method == 'PUT':
                if flags['save_error']:
                    route.fulfill(status=500, json=dict(detail='隔离测试：需求保存失败'))
                    return
                payload = request.post_data_json
                row.update(payload)
                saves.append(('request', copy.deepcopy(payload)))
                if flags['hold_save']:
                    pending.append((route, copy.deepcopy(row)))
                    return
        elif path == '/resource-development/options':
            if flags['options_error']:
                route.fulfill(status=500, json=dict(detail='隔离测试：安排权限加载失败'))
                return
            result = options
        elif path.startswith('/resource-development/arrangement-requests/'):
            rid = path.split('/')[3]
            if request.method == 'GET':
                if flags['detail_error']:
                    route.fulfill(status=404, json=dict(detail='隔离测试：需求不存在'))
                    return
                result = summary(current(rid))
            else:
                if flags['conflict']:
                    route.fulfill(status=409, json=dict(detail='这一天刚刚被其他人保存，请重新加载后重试'))
                    return
                payload = request.post_data_json
                assert payload['revision'] == day['revision']
                date = path.rsplit('/', 1)[-1]
                day['work_date'] = date
                # 仅用于 UI 的响应模型，后端幂等及其他需求保护由隔离数据库回归验证。
                day['cells'] = [dict(platform_id=p, platform_name='测试账号A' if p == platform_a else '测试账号B',
                                     targets=[dict(kind='request_project', request_id=rid)])
                                for p in payload['platform_ids']]
                day['revision'] += 1
                saves.append(('arrangement', copy.deepcopy(payload)))
                result = day
        elif path.startswith('/resource-development/arrangements/'):
            if flags['day_error']:
                route.fulfill(status=500, json=dict(detail='隔离测试：安排加载失败'))
                return
            result = day | dict(work_date=path.rsplit('/', 1)[-1])
        elif path.endswith('/access'):
            result = dict(can_enter=True, can_resource=True, can_collect=False, can_manage=False)
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        route.fulfill(status=200, json=result)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        context = browser.new_context(viewport=dict(width=1234, height=884), timezone_id='America/Los_Angeles', service_workers='block')
        context.route(re.compile(r'^http://localhost:3000/api/'), api)
        context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
        page = context.new_page()
        page.on('pageerror', lambda error: (errors.append(str(error)), print('页面异常:', error)))
        page.clock.install(time=datetime(2026, 10, 12, 0, 30, tzinfo=timezone(timedelta(hours=8))))
        page.goto(BASE + '/resource-requests')
        parent = page.locator('.resource-dialog')
        child = page.locator('.request-arrangement-dialog')

        def open_editor(key):
            page.locator('.el-table__body-wrapper tr').filter(has_text=rows[key]['request_no']).first.get_by_role('button', name='编辑', exact=True).click()
            expect(parent).to_be_visible()

        def shortcut():
            parent.get_by_role('button', name='发到每日安排', exact=True).click()
            expect(child).to_be_visible()
            expect(child.locator('label.el-checkbox').filter(has_text='测试账号A')).to_be_visible()

        def close_child():
            child.get_by_role('button', name='取消', exact=True).click()
            expect(child).not_to_be_visible()
            expect(parent.get_by_role('button', name='保存', exact=True)).to_be_enabled()

        def check_layout(dialog):
            box = dialog.bounding_box()
            viewport = page.viewport_size
            assert box['x'] >= -1 and box['y'] >= -1
            assert box['x'] + box['width'] <= viewport['width'] + 1
            assert box['y'] + box['height'] <= viewport['height'] + 1
            expect(dialog.get_by_role('button', name='保存安排' if dialog == child else '保存', exact=True)).to_be_in_viewport()
            body = dialog.locator('.el-dialog__body')
            assert body.evaluate("el => getComputedStyle(el).overflowY") == 'auto'
            body.evaluate('el => el.scrollTop = el.scrollHeight')
            expect(dialog.locator('.el-dialog__footer')).to_be_in_viewport()

        # 从标注项目入口传入的来源参数可定位需求，主流程覆盖未保存修改与保存顺序。
        page.goto(BASE + f'/resource-requests?sourceType=annotation&sourceProjectId={project}')
        try:
            expect(parent).to_be_visible()
        except AssertionError:
            print('已拦截请求:', calls)
            print('当前页面:', page.locator('body').inner_text())
            raise
        text = parent.locator('.el-form-item').filter(has=page.locator('label', has_text='需求详情')).get_by_role('textbox')
        text.fill('修改后的需求，安排前应保存')
        before = len(calls)
        shortcut()
        relevant = [p for method, p in calls[before:] if method == 'PUT' or '/arrangement-requests/' in p or '/arrangements/' in p]
        assert relevant[0] == '/resource-requests/' + rows['annotation']['id'], relevant
        assert saves[-1][1]['request_detail'] == '修改后的需求，安排前应保存'
        expect(child.locator('.el-date-editor input')).to_have_value(TODAY)
        expect(child.get_by_role('textbox').nth(1)).to_have_value(rows['annotation']['source_order_no_snapshot'])
        expect(parent.get_by_role('button', name='保存', exact=True)).to_be_disabled()
        assert text.is_disabled()
        assert parent.locator('[inert]').count() == 1
        check_layout(parent)
        check_layout(child)
        child.locator('label.el-checkbox').filter(has_text='测试账号A').click()
        child.locator('label.el-checkbox').filter(has_text='测试账号B').click()
        expect(child.get_by_role('checkbox', name='测试账号A')).to_be_checked()
        expect(child.get_by_role('checkbox', name='测试账号B')).to_be_checked()
        page.screenshot(path=str(output / 'arrangement-desktop.png'))
        child.get_by_role('button', name='保存安排', exact=True).click()
        expect(child).not_to_be_visible()
        expect(parent).to_be_visible()
        expect(text).to_have_value('修改后的需求，安排前应保存')

        # 回显、重复安排、冲突保护和重新加载。
        shortcut()
        expect(child.get_by_role('checkbox', name='测试账号A')).to_be_checked()
        expect(child.get_by_role('checkbox', name='测试账号B')).to_be_checked()
        flags['conflict'] = True
        child.get_by_role('button', name='保存安排', exact=True).click()
        expect(child.get_by_text('这一天刚刚被其他人保存', exact=False)).to_be_visible()
        expect(child.get_by_role('checkbox', name='测试账号A')).to_be_checked()
        flags['conflict'] = False
        child.get_by_role('button', name='重新加载', exact=True).click()
        expect(child.get_by_role('button', name='保存安排', exact=True)).to_be_enabled()
        close_child()

        # 拖拽、视口边界、关闭按钮及重新打开复位。
        shortcut()
        original = child.bounding_box()
        title = child.locator('.dialog-field-search-header__title').bounding_box()
        page.mouse.move(title['x'] + 30, title['y'] + 8)
        page.mouse.down()
        page.mouse.move(title['x'] + 140, title['y'] + 90, steps=10)
        page.mouse.up()
        assert child.bounding_box()['x'] > original['x'] + 50
        page.mouse.move(title['x'] + 140, title['y'] + 90)
        page.mouse.down()
        page.mouse.move(-1000, -1000, steps=10)
        page.mouse.up()
        check_layout(child)
        child.locator('.el-dialog__headerbtn').click()
        expect(child).not_to_be_visible()
        shortcut()
        assert abs(child.bounding_box()['x'] - original['x']) < 2
        assert abs(child.bounding_box()['y'] - original['y']) < 2
        focused = child.evaluate('el => el.contains(document.activeElement)')
        assert focused
        page.keyboard.press('Escape')
        expect(child).not_to_be_visible()
        expect(parent).to_be_visible()

        # 保存失败和详情失败均可重试，未打开安排窗口。
        for flag in ['save_error', 'detail_error', 'options_error']:
            flags[flag] = True
            parent.get_by_role('button', name='发到每日安排', exact=True).click()
            expect(parent.get_by_role('button', name='发到每日安排', exact=True)).to_be_enabled()
            expect(child).not_to_be_visible()
            expect(text).to_have_value('修改后的需求，安排前应保存')
            flags[flag] = False
            shortcut()
            close_child()

        # 日期加载失败可在窗口内重试。
        flags['day_error'] = True
        parent.get_by_role('button', name='发到每日安排', exact=True).click()
        expect(child.get_by_text('隔离测试：安排加载失败', exact=True)).to_be_visible()
        expect(child.get_by_role('button', name='保存安排', exact=True)).to_be_disabled()
        flags['day_error'] = False
        child.get_by_role('button', name='重新加载', exact=True).click()
        close_child()

        # 等待已有自动保存，再保存最新内容；重复点击与父窗口关闭受到保护。
        flags['hold_save'] = True
        text.fill('自动保存进行中')
        page.clock.fast_forward(10001)
        page.wait_for_function("() => document.querySelector('.autosave-state')?.textContent.includes('自动保存中')")
        assert len(pending) == 1
        text.fill('自动保存后继续修改')
        parent.get_by_role('button', name='发到每日安排', exact=True).click()
        expect(parent.get_by_role('button', name='发到每日安排', exact=True)).to_be_disabled()
        expect(parent.get_by_role('button', name='关闭', exact=True)).to_be_disabled()
        assert len(pending) == 1
        flags['hold_save'] = False
        route, response = pending.pop()
        route.fulfill(status=200, json=response)
        expect(child).to_be_visible()
        assert saves[-1][1]['request_detail'] == '自动保存后继续修改'
        close_child()
        parent.get_by_role('button', name='关闭', exact=True).click()

        # 所有来源均有入口，草稿和取消态隐藏；权限取接口结果。
        for key in ['recruitment', 'interpretation', 'translation', 'other']:
            open_editor(key)
            shortcut()
            close_child()
            parent.get_by_role('button', name='关闭', exact=True).click()
        for key in ['draft', 'cancelled']:
            open_editor(key)
            expect(parent.get_by_role('button', name='发到每日安排', exact=True)).to_have_count(0)
            parent.get_by_role('button', name='关闭', exact=True).click()
        open_editor('draft')
        parent.get_by_role('button', name='发送', exact=True).click()
        expect(parent).not_to_be_visible()
        open_editor('draft')
        shortcut()
        close_child()
        parent.get_by_role('button', name='关闭', exact=True).click()
        options['can_delegate'] = False
        open_editor('annotation')
        expect(parent.get_by_role('button', name='发到每日安排', exact=True)).to_have_count(0)
        parent.get_by_role('button', name='关闭', exact=True).click()
        options['can_delegate'] = True

        # 空账号校验、字段定位及小屏长内容滚动，保持底部操作可见。
        day.update(revision=0, cells=[])
        options['arrangement_platforms'] = []
        open_editor('annotation')
        parent.get_by_role('button', name='发到每日安排', exact=True).click()
        expect(child.get_by_text('暂无可安排的平台账号，请先维护平台')).to_be_visible()
        child.get_by_role('button', name='保存安排', exact=True).click()
        expect(child.get_by_text('请至少选择一个平台账号')).to_be_visible()
        close_child()
        parent.get_by_role('button', name='关闭', exact=True).click()
        options['arrangement_platforms'] = [dict(id=str(uuid4()), name=f'测试账号{i}', kind='platform', category='national') for i in range(30)]
        page.set_viewport_size(dict(width=390, height=720))
        open_editor('annotation')
        parent.get_by_role('button', name='发到每日安排', exact=True).click()
        expect(child.locator('label.el-checkbox').filter(has_text=re.compile(r'^测试账号0$'))).to_be_visible()
        check_layout(parent)
        check_layout(child)
        body = child.locator('.el-dialog__body')
        assert body.evaluate('el => el.scrollHeight > el.clientHeight')
        search = child.get_by_placeholder('搜索字段，如日期、平台账号')
        search.fill('平台')
        page.get_by_role('option').filter(has_text='平台账号').first.click()
        expect(child.locator('.el-form-item').filter(has=page.locator('label', has_text='平台账号'))).to_be_in_viewport()
        page.screenshot(path=str(output / 'arrangement-mobile.png'))
        close_child()
        assert page.url == BASE + '/resource-requests'
        assert not errors, errors
        (output / 'result.json').write_text(json.dumps(dict(checks='passed', api_calls=len(calls), request_saves=sum(t == 'request' for t, _ in saves),
                                                           arrangement_saves=sum(t == 'arrangement' for t, _ in saves), page_errors=errors), ensure_ascii=False, indent=2), encoding='utf-8')
        browser.close()
        print('需求每日安排 UI 验收通过，所有 API 使用隔离内存数据。')


if __name__ == '__main__':
    run()
