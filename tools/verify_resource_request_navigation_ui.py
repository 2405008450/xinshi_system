"""需求入口迁移验收：拦截全部 API，在内存中模拟读写，不连接业务数据库。"""
import copy
import json
import re
import socket
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://localhost:3000'
PATH = '/resource-management/resource-development'


def run():
    assert socket.gethostname().upper() == 'PC' and ROOT == Path(r'E:\xinshi_system')
    output = ROOT / 'artifacts' / 'resource-request-navigation'
    output.mkdir(parents=True, exist_ok=True)
    uid, project = str(uuid4()), str(uuid4())
    sources = ['annotation', 'translation', 'interpretation', 'recruitment']
    rows = {}
    for source in sources:
        rows[source] = dict(id=str(uuid4()), request_no='RR-QA-' + source,
                            source_type=source, request_category='annotation_trial' if source == 'annotation' else source,
                            demand_status='confirmed', request_status='submitted', request_detail='隔离需求',
                            priority='medium', items=[], owner_id=None, progress_percent=0,
                            source_project_name_snapshot='隔离项目-' + source,
                            source_order_no_snapshot='QA-' + source, source_project_types_snapshot=[],
                            updated_at='2026-10-19T10:00:00+08:00', **{source + '_project_id': project})
    errors, cases = [], []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')

        def scenario(name, permissions, resource=False, issues=False, admin=False, access_error=False):
            calls, writes = [], []
            state = dict(existing=True, options_error=False)
            context = browser.new_context(viewport=dict(width=968, height=884), timezone_id='Asia/Hong_Kong', service_workers='block')
            context.add_init_script("localStorage.setItem('token','isolated-navigation-qa')")

            def api(route):
                request = route.request
                parsed = urlparse(request.url)
                path = parsed.path.removeprefix('/api')
                query = parse_qs(parsed.query)
                calls.append((request.method, path, query))
                result = []
                if path == '/auth/session':
                    result = dict(user_id=uid, username='隔离验收', full_name='隔离验收', roles=['admin'] if admin else ['验收角色'], permissions=permissions)
                elif path.endswith('/issues/access'):
                    if access_error:
                        route.fulfill(status=503, json=dict(detail='隔离测试：开拓权限暂时不可用'))
                        return
                    result = dict(ready=True, can_enter=issues or resource, can_resource=resource, can_collect=False, can_manage=False, user_id=uid)
                elif path == '/resource-requests/page':
                    items = list(rows.values())
                    keyword = query.get('keyword', [''])[0]
                    if keyword:
                        items = [row for row in items if keyword in row['request_no']]
                    result = dict(total=len(items), items=items)
                elif path == '/resource-requests/source-request':
                    result = rows[query['source_type'][0]] if state['existing'] else None
                elif path == '/resource-requests/source-options':
                    result = [dict(id=project, order_no='QA-' + query['source_type'][0], project_name='隔离来源项目')]
                elif path == '/resource-requests/source-prefill':
                    source = query['source_type'][0]
                    result = dict(project_name='隔离预填项目-' + source, order_no='QA-' + source, request_detail='预填需求', items=[])
                elif path.startswith('/resource-requests/'):
                    row = next((row for row in rows.values() if row['id'] == path.rsplit('/', 1)[-1]), None)
                    result = row or []
                    if request.method == 'PUT' and row:
                        row.update(request.post_data_json)
                        writes.append(copy.deepcopy(request.post_data_json))
                        result = row
                elif path == '/resource-development/options':
                    if state['options_error']:
                        route.fulfill(status=503, json=dict(detail='隔离测试：日志选项加载失败'))
                        return
                    result = dict(options=[], users=[], languages=[], user_id=uid, can_write=admin, can_delegate=admin)
                elif path in ['/resource-development/days', '/resource-development/records', '/resource-development/arrangements', '/resource-development/arrangement-requests', '/resource-development/issues']:
                    result = dict(total=0, items=[])
                elif path.startswith('/resource-development/arrangements/'):
                    result = dict(work_date=path.rsplit('/', 1)[-1], revision=0, cells=[])
                elif path.endswith('/friend-daily/options'):
                    result = dict(accounts=[], languages=[], overview_rows=[], can_write=False)
                elif '/friend-daily/' in path:
                    result = dict(revision=0, rows=[], audit=[])
                elif path.endswith('/unread-count'):
                    result = dict(count=0)
                route.fulfill(status=200, json=result)

            context.route(re.compile(r'^http://localhost:3000/api/'), api)
            page = context.new_page()
            page.set_default_timeout(8000)
            page.set_default_navigation_timeout(15000)
            page.on('pageerror', lambda error: errors.append(f'{name}: {error}'))
            print('开始场景：' + name, flush=True)
            return context, page, calls, writes, state

        def selected(page, label):
            expect(page.get_by_role('tab', name=label, exact=True)).to_have_attribute('aria-selected', 'true')

        def navigate(page, location):
            page.evaluate('location => document.querySelector("#app").__vue_app__.config.globalProperties.$router.push(location)', location)

        def check_dialog(page, dialog):
            page.wait_for_function('!document.querySelector(".resource-dialog").closest(".el-overlay").className.includes("dialog-fade")')
            original = dialog.bounding_box()
            footer = dialog.locator('.el-dialog__footer')
            expect(footer).to_be_in_viewport()
            body = dialog.locator('.el-dialog__body')
            body.evaluate('el => el.scrollTop = el.scrollHeight / 2')
            expect(footer).to_be_in_viewport()
            body.evaluate('el => el.scrollTop = el.scrollHeight')
            expect(footer).to_be_in_viewport()
            header = dialog.locator('.dialog-field-search-header__title').bounding_box()
            x, y = header['x'] + 15, header['y'] + 8
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 65, y + 45, steps=8)
            page.mouse.up()
            assert dialog.bounding_box()['y'] > original['y'] + 20
            page.mouse.move(x + 65, y + 45)
            page.mouse.down()
            page.mouse.move(-1000, -1000, steps=8)
            page.mouse.up()
            moved = dialog.bounding_box()
            assert moved['x'] >= -1 and moved['y'] >= -1
            assert moved['x'] + moved['width'] <= page.viewport_size['width'] + 1
            assert moved['y'] + moved['height'] <= page.viewport_size['height'] + 1
            dialog.locator('.el-dialog__headerbtn').click()
            expect(dialog).not_to_be_visible()
            return original

        context, page, calls, writes, state = scenario('管理员', ['*'], resource=True, admin=True)
        page.goto(BASE + PATH)
        print('默认页面已加载', flush=True)
        selected(page, '开拓日志')
        assert page.get_by_role('tab').all_text_contents() == ['需求管理', '开拓日志', '每日安排', '开拓问题']
        expect(page.get_by_role('menuitem', name='需求管理', exact=True)).to_have_count(0)
        assert not any(path == '/resource-requests/page' for _, path, _ in calls)
        page.get_by_role('tab', name='需求管理', exact=True).click()
        print('已切换需求页签', flush=True)
        selected(page, '需求管理')
        panel = page.locator('.resource-request-panel')
        expect(panel.get_by_text('RR-QA-annotation', exact=True)).to_be_visible()
        expect(panel.locator('.el-card')).to_have_count(0)
        expect(page.get_by_role('heading', name='资源需求管理', exact=True)).to_have_count(0)
        expect(page.locator('.sidebar .el-menu-item.is-active')).to_contain_text('人才资源管理')
        page.screenshot(path=str(output / 'requests-968.png'))
        page.reload()
        selected(page, '需求管理')
        keyword = page.get_by_placeholder('搜索请求编号、项目、客户或需求详情')
        keyword.fill('annotation')
        expect(panel.locator('.el-table__body-wrapper tr')).to_have_count(1)
        keyword.fill('')
        expect(panel.locator('.el-table__body-wrapper tr')).to_have_count(4)
        page.get_by_role('tab', name='开拓日志', exact=True).click()
        expect(panel).to_have_count(0)
        page.get_by_role('tab', name='每日安排', exact=True).click()
        expect(page.locator('.arrangement-panel')).to_be_visible()
        page.get_by_role('tab', name='开拓问题', exact=True).click()
        expect(page.locator('.issue-panel')).to_be_visible()
        navigate(page, dict(path=PATH, query=dict(section='requests')))
        selected(page, '需求管理')
        page.go_back()
        selected(page, '开拓问题')
        page.go_forward()
        selected(page, '需求管理')
        # 来源参数在已经挂载的页签内变化，四类项目均应打开对应的原需求。
        for source in sources:
            navigate(page, dict(name='ResourceRequests', query=dict(sourceType=source, sourceProjectId=project, keyword='保留参数'), hash='#qa'))
            dialog = page.locator('.resource-dialog')
            expect(dialog).to_be_visible()
            expect(dialog.get_by_text('隔离项目-' + source, exact=True)).to_be_visible()
            page.wait_for_url(re.compile(r'.*section=requests.*'))
            page.wait_for_function('!new URL(location.href).searchParams.has("sourceProjectId")')
            assert page.url.endswith('#qa') and 'keyword=' in page.url
            if source == 'annotation':
                dialog.get_by_role('textbox', name='需求详情', exact=True).fill('隔离编辑已保存')
                dialog.get_by_role('button', name='保存', exact=True).click()
                expect(dialog).not_to_be_visible()
                assert writes and writes[-1]['request_detail'] == '隔离编辑已保存'
            else:
                dialog.locator('.el-dialog__headerbtn').click()
                expect(dialog).not_to_be_visible()
            # 等待关闭动画结束，防止上一次 closed 回调清空新打开的表单。
            page.wait_for_function('!document.querySelector(".resource-dialog")?.getClientRects().length')
        state['existing'] = False
        navigate(page, dict(name='ResourceRequests', query=dict(sourceType='recruitment', sourceProjectId=project)))
        dialog = page.locator('.resource-dialog')
        expect(dialog.get_by_text('隔离预填项目-recruitment', exact=True)).to_be_visible()
        expect(dialog.get_by_text('新增资源需求', exact=True)).to_be_visible()
        original = check_dialog(page, dialog)
        page.get_by_role('button', name='新增资源需求', exact=True).click()
        expect(dialog).to_be_visible()
        page.wait_for_function('!document.querySelector(".resource-dialog").closest(".el-overlay").className.includes("dialog-fade")')
        assert abs(dialog.bounding_box()['y'] - original['y']) < 2
        expect(dialog.locator('.el-dialog__footer')).to_be_in_viewport()
        page.screenshot(path=str(output / 'create-968.png'))
        dialog.locator('.el-dialog__headerbtn').click()
        expect(dialog).not_to_be_visible()
        page.set_viewport_size(dict(width=390, height=844))
        page.screenshot(path=str(output / 'requests-390.png'))
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        context.close()
        cases.append('管理员：顺序、默认日志、刷新、历史、按需挂载、筛选、四类来源、已有需求编辑与预填新增、小屏')
        cases.append('新增表单：固定操作栏、内容滚动、拖拽边界、关闭按钮、重开复位')

        for name, permissions, resource, issues, tabs, default in [
            ('仅需求', ['projects:read'], False, False, ['需求管理'], '需求管理'),
            ('仅开拓', ['talents:read'], True, False, ['开拓日志', '每日安排', '开拓问题'], '开拓日志'),
            ('仅问题', [], False, True, ['开拓问题'], '开拓问题'),
        ]:
            context, page, calls, _, _ = scenario(name, permissions, resource, issues)
            page.goto(BASE + '/resource-requests?keyword=qa#legacy')
            selected(page, default)
            assert page.get_by_role('tab').all_text_contents() == tabs
            assert 'keyword=qa' in page.url and page.url.endswith('#legacy')
            navigate(page, dict(path='/resource-management/talent-overview'))
            page.locator('.resource-nav__primary').get_by_role('button', name='资源开拓', exact=True).click()
            selected(page, default)
            if not resource:
                assert not any(path in ['/resource-development/options', '/resource-development/days'] for _, path, _ in calls)
            if name == '仅需求':
                expect(page.get_by_role('button', name='新增资源需求', exact=True)).to_have_count(0)
            context.close()
            cases.append(name + '：旧入口兼容、权限隔离、资源开拓导航')

        context, page, calls, _, _ = scenario('权限接口故障', ['projects:read'], access_error=True)
        page.goto(BASE + '/resource-requests')
        selected(page, '需求管理')
        expect(page.get_by_placeholder('搜索请求编号、项目、客户或需求详情')).to_be_visible()
        context.close()
        cases.append('开拓权限接口故障不阻断需求列表')
        context, page, calls, _, state = scenario('日志加载故障', ['*'], resource=True, admin=True)
        state['options_error'] = True
        page.goto(BASE + PATH + '?section=requests')
        selected(page, '需求管理')
        expect(page.get_by_placeholder('搜索请求编号、项目、客户或需求详情')).to_be_visible()
        assert not any(path == '/resource-development/options' for _, path, _ in calls)
        page.get_by_role('tab', name='开拓日志', exact=True).click()
        expect(page.get_by_text('日志选项加载失败', exact=False)).to_be_visible()
        page.get_by_role('tab', name='需求管理', exact=True).click()
        expect(page.get_by_placeholder('搜索请求编号、项目、客户或需求详情')).to_be_visible()
        context.close()
        cases.append('需求页按需加载，日志选项故障后仍能返回需求页')
        browser.close()
    assert not errors, errors
    report = dict(cases=cases, page_errors=errors, api_mode='全部 API 已拦截，读写仅在内存中模拟')
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    run()
