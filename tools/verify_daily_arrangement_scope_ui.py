"""每日安排界面验收：所有 API 在浏览器内拦截，不访问业务数据库。"""
import copy
import json
import re
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://localhost:3000'
DAY = '2026-10-20'


def run():
    assert socket.gethostname().upper() == 'PC' and ROOT == Path(r'E:\xinshi_system')
    output = ROOT / 'artifacts' / 'daily-arrangement-scope'
    output.mkdir(parents=True, exist_ok=True)
    uid, pid, language, account_a, account_b = [str(uuid4()) for _ in range(5)]
    scope = [dict(key='scope-a', label='粤语 · 广州', language_ids=[language], language_label='粤语', city='广州'),
             dict(key='scope-b', label='粤语 · 深圳', language_ids=[language], language_label='粤语', city='深圳')]
    rows = []
    for i, status in enumerate(['confirmed', 'draft', 'paused', 'cancelled', 'confirmed', 'confirmed', 'confirmed']):
        rows.append(dict(id=str(uuid4()), request_no=f'RR-QA-{i+1:02}', source_type='annotation', request_category='annotation_trial',
                         annotation_project_id=pid, source_order_no_snapshot='AP-QA-01', source_project_name_snapshot=f'安排验收项目{i+1}',
                         current_project_name=f'安排验收项目{i+1}', current_order_no='AP-QA-01', source_project_types_snapshot=['audio_collection'],
                         request_detail='仅用于隔离验收的需求说明', priority='medium', demand_status=status,
                         request_status='submitted' if status == 'confirmed' else status, progress_percent=35, owner_id=uid,
                         items=[dict(id=str(uuid4()), language_ids=[language], language_labels=['粤语'], source_language_id=language, required_count=2)],
                         requested_at='2026-10-19T09:00:00+08:00', updated_at='2026-10-19T09:00:00+08:00'))
    options = dict(can_delegate=True, can_write=True, options=[], users=[dict(id=uid, name='验收人员')], languages=[], user_id=uid,
                   arrangement_platforms=[dict(id=a, kind='platform', name=n, category='national', has_accounts=False)
                                         for a, n in [(account_a, '测试账号A'), (account_b, '测试账号B')]])
    days, calls, writes, errors = {}, [], [], []
    flags = dict(conflict=False, fail_delete=False)

    def day(date):
        return days.setdefault(date, dict(work_date=date, revision=0, cells=[], remarks=''))

    def current(rid):
        return next(row for row in rows if row['id'] == rid)

    def summaries(rid):
        return [dict(work_date=d['work_date'], platform_id=c['platform_id'], platform_name=c['platform_name'], completed=False)
                for d in days.values() for c in d['cells'] if any(t['request_id'] == rid for t in c['targets'])]

    def api(route):
        req = route.request
        parsed = urlparse(req.url)
        path, query = parsed.path.removeprefix('/api'), parse_qs(parsed.query)
        calls.append((req.method, path, query))
        result = []
        if path == '/auth/session':
            result = dict(user_id=uid, username='隔离验收', full_name='隔离验收', roles=['admin'], permissions=['*'])
        elif path.endswith('/issues/access'):
            result = dict(ready=True, can_enter=True, can_resource=True, can_manage=True, user_id=uid)
        elif path == '/resource-development/options':
            result = options
        elif path == '/resource-requests/page':
            candidates = rows
            if query.get('keyword'):
                candidates = [r for r in rows if query['keyword'][0] in r['request_no'] or query['keyword'][0] in r['current_project_name']]
            skip, limit = int(query.get('skip', ['0'])[0]), int(query.get('limit', ['10'])[0])
            result = dict(total=len(candidates), items=[r | dict(arrangements=summaries(r['id'])) for r in candidates[skip:skip+limit]])
        elif path == '/resource-requests/source-options':
            result = [dict(id=pid, order_no='AP-QA-01', project_name='安排验收项目1')]
        elif path == '/resource-requests/source-prefill':
            result = rows[0]
        elif path == '/resource-requests/' and req.method == 'POST':
            row = copy.deepcopy(rows[0]) | req.post_data_json | dict(id=str(uuid4()), request_no='RR-QA-新增', demand_status='draft', request_status='draft')
            rows.insert(0, row); result = row; writes.append(('create', copy.deepcopy(req.post_data_json)))
        elif path.startswith('/resource-requests/') and path.rsplit('/', 1)[-1] in {r['id'] for r in rows}:
            row = current(path.rsplit('/', 1)[-1]); result = row
            if req.method == 'DELETE':
                if flags['fail_delete'] and row['request_no'] == 'RR-QA-03':
                    route.fulfill(status=409, json=dict(detail='隔离验收：存在关联安排')); return
                rows.remove(row); writes.append(('delete', row['id'])); result = dict(ok=True)
            elif req.method == 'PUT':
                row.update(req.post_data_json); writes.append(('edit', copy.deepcopy(req.post_data_json)))
        elif path.startswith('/resource-development/arrangement-requests/'):
            rid = path.split('/')[3]; row = current(rid)
            if '/dates/' not in path:
                result = dict(id=rid, request_no=row['request_no'], source_type='annotation', order_no='AP-QA-01',
                              project_name=row['current_project_name'], request_detail=row['request_detail'], languages=['粤语'],
                              demand_status=row['demand_status'], request_status=row['request_status'], scope_options=scope,
                              project=dict(source_type='annotation', project_id=pid, project_name=row['current_project_name'], order_no='AP-QA-01'), arrangements=summaries(rid))
            else:
                if flags['conflict']:
                    route.fulfill(status=409, json=dict(detail='这一天刚刚被其他人保存，请重新加载后重试')); return
                value = req.post_data_json; target_day = day(path.rsplit('/', 1)[-1])
                assert value['revision'] == target_day['revision']
                for cell in target_day['cells']:
                    cell['targets'] = [t for t in cell['targets'] if t['request_id'] != rid]
                for account in value['platform_ids']:
                    cell = next((c for c in target_day['cells'] if c['platform_id'] == account), None)
                    if cell is None:
                        cell = dict(platform_id=account, platform_name='测试账号A' if account == account_a else '测试账号B', targets=[], projects=[], role_tags=[], owner_id=uid, owner_name='验收人员', can_edit=True, remarks='', completed=False)
                        target_day['cells'].append(cell)
                    cell['targets'].append(dict(kind='request_project', request_id=rid, request_no=row['request_no'], label=row['current_project_name'],
                                                scope=[s for s in scope if s['key'] in value['selected_scope_keys']], arrangement_note=value['arrangement_note'], active=True))
                target_day['revision'] += 1; writes.append(('arrange', copy.deepcopy(value))); result = target_day
        elif path == '/resource-development/arrangements':
            result = dict(total=0, items=[])
        elif path.startswith('/resource-development/arrangements/'):
            result = day(path.rsplit('/', 1)[-1])
        elif path == '/projects/annotation/' + pid:
            result = dict(id=pid, order_no='AP-QA-01', project_name='安排验收项目1', project_types=['audio_collection'], project_status='trial_preparation', language_items=[], custom_fields={})
        elif path == '/projects/languages':
            result = [dict(id=language, label='粤语', is_active=True)]
        elif path == '/users/options':
            result = [dict(id=uid, display_name='验收人员')]
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        elif path == '/openapi.json':
            result = dict(components=dict(schemas={}))
        route.fulfill(status=200, json=result)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        context = browser.new_context(viewport=dict(width=1440, height=1000), timezone_id='America/Los_Angeles', service_workers='block')
        context.route(re.compile(r'^http://localhost:3000/api/'), api)
        context.add_init_script("localStorage.setItem('token','isolated-arrangement');localStorage.setItem('user_roles','[\"admin\"]')")
        page = context.new_page(); page.set_default_timeout(8000); page.on('pageerror', lambda e: errors.append(str(e)))
        page.clock.install(time=datetime(2026, 10, 19, 9, tzinfo=timezone(timedelta(hours=8))))
        page.goto(BASE + '/resource-management/resource-development?section=arrangements')
        panel = page.locator('.development-demand-panel')
        expect(panel.get_by_role('button', name='新增资源需求')).to_be_visible()
        expect(panel.locator('.el-table__body-wrapper tr')).to_have_count(5)
        expect(panel.get_by_role('button', name='更新进度')).to_have_count(0)
        expect(panel.get_by_text('需求已暂停', exact=True)).to_be_visible()
        expect(panel.get_by_text('需求取消', exact=True)).to_be_visible()
        assert any(q.get('start') == [DAY] for _, p, q in calls if p == '/resource-development/arrangements')
        assert any(q.get('include_arrangements') == ['true'] for _, p, q in calls if p == '/resource-requests/page')
        # 每页数量、搜索与清空。
        panel.locator('.el-pagination__sizes').click(); page.get_by_role('option', name='10条/页', exact=True).click()
        expect(panel.locator('.el-table__body-wrapper tr')).to_have_count(7)
        keyword = panel.get_by_placeholder('搜索请求编号、项目、客户或需求详情')
        keyword.fill('RR-QA-01'); page.clock.run_for(450)
        expect(panel.locator('.el-table__body-wrapper tr')).to_have_count(1)
        keyword.fill(''); expect(panel.locator('.el-table__body-wrapper tr')).to_have_count(7)
        # 新增、编辑弹窗及固定操作栏。
        panel.get_by_role('button', name='新增资源需求').click()
        resource = page.locator('.resource-dialog')
        expect(resource).to_be_visible(); expect(resource.locator('.el-dialog__footer')).to_be_in_viewport()
        resource.locator('.el-dialog__body').evaluate('el => el.scrollTop = el.scrollHeight')
        expect(resource.locator('.el-dialog__footer')).to_be_in_viewport()
        resource.get_by_role('button', name='关闭', exact=True).click(); expect(resource).not_to_be_visible()
        panel.locator('.el-table__body-wrapper tr').filter(has_text='RR-QA-01').get_by_role('button', name='编辑', exact=True).click()
        expect(resource).to_be_visible(); expect(resource.locator('.el-dialog__footer')).to_be_in_viewport()
        resource.get_by_role('button', name='关闭', exact=True).click(); expect(resource).not_to_be_visible()
        # 逐需求安排、详情、嵌套选择。
        def open_arrangement():
            panel.locator('.el-table__body-wrapper tr').filter(has_text='RR-QA-01').get_by_role('button', name='每日安排', exact=True).click()
            dialog = page.locator('.request-arrangement-dialog').filter(has=page.locator('.dialog-field-search-header__title', has_text='项目每日安排'))
            expect(dialog).to_be_visible(); expect(dialog.locator('.el-date-editor input')).to_have_value(DAY)
            expect(dialog.get_by_role('button', name='编辑安排内容')).to_be_enabled()
            page.wait_for_function("() => ![...document.querySelectorAll('.el-overlay')].some(el => /dialog-fade-(enter|leave)-active/.test(el.className))")
            return dialog
        dialog = open_arrangement()
        dialog.get_by_role('button', name='项目详情', exact=True).click()
        expect(page.locator('.associated-project-detail')).to_be_visible()
        expect(page.locator('.associated-project-detail').get_by_text('AP-QA-01', exact=True)).to_be_visible()
        page.locator('.associated-project-detail').get_by_role('button', name='关闭', exact=True).click()
        dialog.get_by_role('button', name='需求详情', exact=True).click()
        expect(page.locator('.request-arrangement-detail-body').get_by_text('仅用于隔离验收的需求说明')).to_be_visible()
        page.locator('.request-arrangement-detail-body').get_by_role('button', name='关闭', exact=True).click()
        dialog.get_by_role('button', name='编辑安排内容').click()
        editor = page.locator('.request-arrangement-dialog').filter(has=page.locator('.dialog-field-search-header__title', has_text='编辑安排内容'))
        expect(editor).to_be_visible()
        page.clock.run_for(400)
        page.screenshot(path=str(output / 'scope-editor.png'))
        editor.locator('label.el-checkbox').filter(has_text='粤语 · 广州').click()
        editor.locator('label.el-checkbox').filter(has_text='粤语 · 深圳').click()
        editor.get_by_role('button', name='确认', exact=True).click()
        expect(editor.get_by_text('请选择当前项目的语言与城市；已失效选项请重新选择')).to_be_visible()
        page.clock.run_for(400)
        assert editor.locator('.el-form-item.is-error').evaluate('el => el.contains(document.activeElement)')
        editor.locator('label.el-checkbox').filter(has_text='粤语 · 深圳').click()
        editor.get_by_placeholder('填写本次安排的补充要求').fill('只安排深圳，优先有经验人员')
        expect(editor.locator('.el-dialog__footer')).to_be_in_viewport()
        editor.get_by_role('button', name='确认', exact=True).click()
        expect(editor).not_to_be_visible(); expect(dialog.get_by_text('安排备注：只安排深圳，优先有经验人员')).to_be_visible()
        dialog.locator('label.el-checkbox').filter(has_text='测试账号A').click(); dialog.locator('label.el-checkbox').filter(has_text='测试账号B').click()
        # 拖动、边界和位置复位。
        page.wait_for_function("!document.querySelector('.request-arrangement-dialog').closest('.el-overlay').className.includes('dialog-fade')")
        original = dialog.bounding_box(); header = dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 10, header['y'] + 10); page.mouse.down(); page.mouse.move(header['x'] + 110, header['y'] + 50, steps=10); page.mouse.up()
        assert abs(dialog.bounding_box()['x'] - original['x']) > 50
        header = dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 10, header['y'] + 10); page.mouse.down(); page.mouse.move(-2000, -2000, steps=10); page.mouse.up()
        assert dialog.bounding_box()['x'] >= -1 and dialog.bounding_box()['y'] >= -1
        # 冲突保留内容，重新加载后继续保存。
        flags['conflict'] = True; dialog.get_by_role('button', name='保存安排', exact=True).click()
        expect(dialog.get_by_text('这一天刚刚被其他人保存', exact=False)).to_be_visible()
        expect(dialog.get_by_role('checkbox', name='测试账号B')).to_be_checked()
        flags['conflict'] = False; dialog.get_by_role('button', name='重新加载', exact=True).click()
        expect(dialog.get_by_role('button', name='保存安排', exact=True)).to_be_enabled()
        expect(dialog.get_by_text('安排备注：只安排深圳，优先有经验人员')).to_be_visible()
        dialog.get_by_role('button', name='保存安排', exact=True).click(); expect(dialog).not_to_be_visible()
        assert writes[-1][1]['selected_scope_keys'] == ['scope-b'] and len(writes[-1][1]['platform_ids']) == 2
        expect(panel.get_by_text('测试账号A、测试账号B', exact=True)).to_be_visible()
        expect(page.locator('.arrangement-cell-remarks').get_by_text('安排备注：只安排深圳，优先有经验人员')).to_have_count(2)
        dialog = open_arrangement()
        expect(dialog.get_by_role('checkbox', name='测试账号A')).to_be_checked()
        assert abs(dialog.bounding_box()['x'] - original['x']) < 2
        expect(dialog.get_by_text('安排备注：只安排深圳，优先有经验人员')).to_be_visible()
        page.screenshot(path=str(output / 'desktop.png'))
        dialog.locator('.el-dialog__headerbtn').click(); expect(dialog).not_to_be_visible()
        # 字段配置持久化、全部取消、恢复默认。
        panel.get_by_role('button', name='字段设置').click()
        settings = page.locator('.el-popover').filter(has_text='恢复默认').filter(visible=True)
        expect(settings.get_by_role('checkbox')).to_have_count(18)
        for label in settings.locator('label.el-checkbox').all():
            if label.get_by_role('checkbox').is_checked(): label.click()
        expect(panel.locator('.el-table__header-wrapper th')).to_have_count(3)
        settings.get_by_role('button', name='恢复默认').click()
        expect(panel.get_by_text('已安排平台', exact=True)).to_be_visible()
        panel.get_by_role('button', name='字段设置').click()
        page.reload(); expect(panel.locator('.el-table__body-wrapper tr')).to_have_count(5)
        expect(panel.get_by_text('已安排平台', exact=True)).to_be_visible()
        # 删除模式及分页退出。
        panel.get_by_role('button', name='删除管理', exact=True).click()
        expect(panel.get_by_role('button', name='新增资源需求')).to_have_count(0)
        expect(panel.get_by_role('button', name='删除所选', exact=False)).to_be_disabled()
        panel.locator('.el-pagination .btn-next').click()
        expect(panel.get_by_role('button', name='新增资源需求')).to_be_visible()
        # 在第二页新增草稿后回到第一页，并实际保存编辑。
        panel.get_by_role('button', name='新增资源需求').click()
        expect(resource).to_be_visible()
        resource.locator('.el-form-item').filter(has_text='来源项目').locator('.el-select').click()
        page.get_by_role('option', name='AP-QA-01 安排验收项目1', exact=True).click()
        expect(resource.get_by_placeholder('已从来源项目自动获取，可继续补充；无内容时列表自动隐藏')).to_have_value('仅用于隔离验收的需求说明')
        resource.get_by_role('button', name='保存', exact=True).click()
        expect(resource).not_to_be_visible(); expect(panel.get_by_text('RR-QA-新增', exact=True)).to_be_visible()
        panel.locator('.el-table__body-wrapper tr').filter(has_text='RR-QA-01').get_by_role('button', name='编辑', exact=True).click()
        resource.get_by_placeholder('已从来源项目自动获取，可继续补充；无内容时列表自动隐藏').fill('编辑后需求说明')
        resource.get_by_role('button', name='保存', exact=True).click(); expect(resource).not_to_be_visible()
        assert any(kind == 'edit' and value['request_detail'] == '编辑后需求说明' for kind, value in writes)
        # 单条普通确认，批量强确认及部分失败后保留失败选择。
        panel.get_by_role('button', name='删除管理', exact=True).click()
        panel.locator('.el-table__body-wrapper tr').filter(has_text='RR-QA-新增').locator('label.el-checkbox').click()
        panel.get_by_role('button', name='删除所选', exact=False).click()
        message = page.locator('.el-message-box'); expect(message).to_be_visible()
        message.get_by_role('button', name='确定删除', exact=True).click()
        expect(panel.get_by_text('RR-QA-新增', exact=True)).to_have_count(0)
        panel.get_by_role('button', name='删除管理', exact=True).click()
        for number in ['RR-QA-02', 'RR-QA-03']:
            panel.locator('.el-table__body-wrapper tr').filter(has_text=number).locator('label.el-checkbox').click()
        flags['fail_delete'] = True
        panel.get_by_role('button', name='删除所选', exact=False).click()
        expect(message.get_by_role('textbox')).to_be_visible(); message.get_by_role('textbox').fill('删除')
        message.get_by_role('button', name='确定删除', exact=True).click()
        expect(panel.get_by_text('RR-QA-02', exact=True)).to_have_count(0)
        expect(panel.locator('.el-table__body-wrapper tr').filter(has_text='RR-QA-03').get_by_role('checkbox')).to_be_checked()
        expect(page.get_by_text('隔离验收：存在关联安排', exact=False)).to_be_visible()
        panel.get_by_role('button', name='退出', exact=True).click()
        # 小屏固定操作栏与表单正文独立滚动。
        page.set_viewport_size(dict(width=390, height=844)); page.reload()
        dialog = open_arrangement()
        expect(dialog.locator('.el-dialog__footer')).to_be_in_viewport()
        dialog.locator('.el-dialog__body').evaluate('el => el.scrollTop = el.scrollHeight')
        expect(dialog.locator('.el-dialog__footer')).to_be_in_viewport()
        box = dialog.bounding_box(); assert box['x'] >= -1 and box['width'] <= 359 and box['y'] + box['height'] <= 844
        page.screenshot(path=str(output / 'mobile.png'))
        dialog.locator('.el-dialog__headerbtn').click()
        assert not errors, errors
        (output / 'result.json').write_text(json.dumps(dict(api_calls=len(calls), writes=writes, errors=errors, checks='列表维护、分页搜索、详情、范围编辑、多账号、冲突保留、拖拽复位、小屏、字段设置、删除模式'), ensure_ascii=False, indent=2), encoding='utf-8')
        browser.close()
    print('每日安排界面验收通过；全部 API 已隔离。')


if __name__ == '__main__':
    run()

