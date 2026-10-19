"""关联项目二级详情验收：所有 API 均拦截，业务读写只在内存模拟。"""
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
REQUESTS = '/resource-management/resource-development?section=requests'


def run():
    assert socket.gethostname().upper() == 'PC' and ROOT == Path(r'E:\xinshi_system')
    output = ROOT / 'artifacts' / 'associated-project-detail'
    output.mkdir(parents=True, exist_ok=True)
    uid, custom_id = str(uuid4()), str(uuid4())
    sources = ['annotation', 'translation', 'interpretation', 'recruitment']
    projects, requests = {}, {}
    for source in sources:
        pid, rid = str(uuid4()), str(uuid4())
        projects[source] = dict(id=pid, order_no='QA-' + source, project_name='最新项目-' + source,
                                source_file_name='最新项目-' + source, task_description='只读任务内容',
                                project_status={'annotation': 'trial_preparation', 'translation': 'confirmed', 'interpretation': 'in_progress', 'recruitment': 'sourcing'}[source],
                                role_assignments=[], areas=[], area_labels=[], project_types=[], language_items=[], language_directions=[],
                                price_items=[], assignees=[], time_ranges=[], locations=[], interpreter_assignments=[], assigned_translators=[],
                                headcount_min=2, headcount_max=5, service_fee_type='fixed', service_fee_amount=100,
                                latest_customer_progress_note='客户进度已更新', remarks='长内容验收。' * 300,
                                custom_values={custom_id: '自定义项目内容'}, created_at='2026-10-19T00:30:00Z', updated_at='2026-10-19T08:30:00+08:00')
        requests[source] = dict(id=rid, request_no='RR-' + source, source_type=source,
                                request_category='annotation_trial' if source == 'annotation' else source,
                                demand_status='confirmed', request_status='submitted', request_detail='需求原文。' * 250,
                                source_project_name_snapshot='历史项目-' + source, source_order_no_snapshot='QA-' + source,
                                items=[], priority='medium', progress_percent=0, **{source + '_project_id': pid})
    requests['other'] = dict(id=str(uuid4()), request_no='RR-other', source_type='other', other_source_name='其他来源', items=[])
    requests['missing'] = dict(id=str(uuid4()), request_no='RR-missing', source_type='annotation', source_project_name_snapshot='历史无 ID 项目', items=[])
    flags = dict(status=200, hold=False)
    calls, errors, writes, pending, checks = [], [], [], [], []

    def api(route):
        req = route.request
        parsed = urlparse(req.url)
        path, query = parsed.path.removeprefix('/api'), parse_qs(parsed.query)
        calls.append((req.method, path))
        result = []
        if path == '/auth/session':
            result = dict(user_id=uid, username='隔离验收', full_name='隔离验收', roles=['admin'], permissions=['*'])
        elif path.endswith('/issues/access'):
            result = dict(ready=True, can_enter=True, can_resource=True, can_manage=True, user_id=uid)
        elif path == '/resource-requests/page':
            result = dict(total=len(requests), items=list(requests.values()))
        elif path.startswith('/resource-requests/'):
            result = next((row for row in requests.values() if row['id'] == path.split('/')[2]), [])
            if req.method == 'PATCH':
                result['request_detail'] = req.post_data_json['value']
                writes.append((path, req.post_data_json))
        elif path == '/annotation-ops/custom-fields':
            result = [dict(id=custom_id, field_label='验收自定义字段', data_type='text', is_active=True)] if query.get('table_code') == ['project'] else []
        elif path.endswith('/status-history'):
            result = [dict(id='history-1', to_status='trial_preparation', effective_on='2026-10-19T00:30:00Z', changed_at='2026-10-19T00:30:00Z', change_note='隔离状态履历')]
        elif path.endswith('/materials'):
            result = [dict(id='file-1', file_id='file-1', original_name='只读资料.pdf', version_no=1, file_size=100, category='project', created_at='2026-10-19T00:30:00Z')]
        elif path.startswith('/projects/'):
            parts = path.strip('/').split('/')
            source = parts[1]
            row = projects.get(source, {})
            if len(parts) == 3 and parts[2] == row.get('id'):
                if flags['hold']:
                    pending.append(route)
                    return
                if flags['status'] != 200:
                    route.fulfill(status=flags['status'], json=dict(detail='隔离异常'))
                    return
                result = copy.deepcopy(row)
            elif path.endswith('/page'):
                result = dict(total=1, items=[row])
            elif path.endswith('/count'):
                result = 1
            elif len(parts) == 2:
                result = [row]
            if req.method == 'PATCH':
                row[req.post_data_json['field']] = req.post_data_json['value']
                result = row
                writes.append((path, req.post_data_json))
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        elif path.endswith('/page') or path.endswith('/days'):
            result = dict(total=0, items=[])
        route.fulfill(status=200, json=result)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        context = browser.new_context(viewport=dict(width=968, height=884), timezone_id='America/Los_Angeles', service_workers='block')
        context.route(re.compile(r'^http://localhost:3000/api/'), api)
        context.add_init_script("localStorage.setItem('token','isolated-associated-project');localStorage.setItem('user_roles','[\"admin\"]')")
        page = context.new_page()
        page.set_default_timeout(8000)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + REQUESTS)
        parent = page.locator('.resource-detail-popover:visible')
        child = page.locator('.associated-project-popover:visible')

        def open_parent(source):
            page.get_by_role('button', name='RR-' + source, exact=True).click()
            expect(parent).to_be_visible()
            page.wait_for_function("Array.from(document.querySelectorAll('.resource-detail-popover')).some(el => el.getClientRects().length && getComputedStyle(el).opacity === '1')")

        def open_child():
            parent.get_by_title('点击查看项目详情', exact=True).click()
            expect(child).to_be_visible()
            expect(child.locator('.associated-project-detail__body .el-descriptions')).to_be_visible()
            page.wait_for_function("Array.from(document.querySelectorAll('.associated-project-popover')).some(el => el.getClientRects().length && getComputedStyle(el).opacity === '1')")

        def close_all():
            page.mouse.click(12, 12)
            expect(parent).to_have_count(0)
            expect(child).to_have_count(0)

        for source in sources:
            print('验收二级详情：' + source, flush=True)
            open_parent(source)
            before = len(calls)
            open_child()
            expect(child).to_contain_text('最新项目-' + source)
            expect(parent).to_contain_text('历史项目-' + source)
            assert any(path == f'/projects/{source}/{projects[source]["id"]}' for _, path in calls[before:])
            assert not child.locator('input,textarea').count()
            assert not child.get_by_role('button', name=re.compile('保存|编辑|查看详情|历史版本|下载')).count()
            page.wait_for_function('''() => { const el = document.querySelector('.associated-project-popover'); if (!el) return false; const r = el.getBoundingClientRect(); return r.y >= 0 && r.bottom <= innerHeight; }''')
            box = child.bounding_box()
            assert box['x'] >= 15 and box['x'] + box['width'] <= 953
            assert box['y'] >= 0 and box['y'] + box['height'] <= 885
            assert child.locator('.associated-project-detail__body').evaluate('el => el.scrollHeight > el.clientHeight')
            expect(child).to_contain_text('08:30')
            if source == 'annotation':
                expect(child).to_contain_text('自定义项目内容')
                expect(child).to_contain_text('隔离状态履历')
                expect(child).to_contain_text('只读资料.pdf')
                page.screenshot(path=str(output / 'annotation-desktop.png'))
            child.get_by_role('button', name='关闭', exact=True).click()
            expect(child).to_have_count(0)
            expect(parent).to_be_visible()
            expect(parent.get_by_title('点击查看项目详情')).to_be_focused()
            close_all()
        checks.append('四类项目按 ID 加载最新只读详情，历史快照保留；UTC+8 时间、标注自定义字段/履历/资料')

        # ESC 逐层关闭、父区点击、父窗滚动位置、重复打开重新读取。
        open_parent('annotation')
        parent.locator('.detail').evaluate('el => el.scrollTop = 45')
        scroll = parent.locator('.detail').evaluate('el => el.scrollTop')
        assert scroll > 0
        open_child()
        page.keyboard.press('Escape')
        expect(child).to_have_count(0)
        expect(parent).to_be_visible()
        assert parent.locator('.detail').evaluate('el => el.scrollTop') == scroll
        open_child()
        point = page.evaluate('''() => {
          const p = document.querySelector('.resource-detail-popover:not([style*="display: none"])');
          const c = document.querySelector('.associated-project-popover:not([style*="display: none"])');
          const r = p.getBoundingClientRect();
          for (let y = r.top + 10; y < Math.min(innerHeight, r.bottom) - 5; y += 15)
            for (let x = r.left + 10; x < r.right - 5; x += 30) {
              const el = document.elementFromPoint(x,y);
              if (p.contains(el) && !c.contains(el)) return {x,y};
            }
        }''')
        assert point, '父窗应有可操作的露出区域'
        page.mouse.click(point['x'], point['y'])
        expect(child).to_have_count(0)
        expect(parent).to_be_visible()
        open_child()
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        expect(parent).to_have_count(0)
        checks.append('ESC、父区点击、外部点击、焦点恢复和父窗滚动位置')

        for source in ['other', 'missing']:
            open_parent(source)
            expect(parent.get_by_title('点击查看项目详情')).to_have_count(0)
            close_all()
        for status, message in [(403, '没有权限'), (404, '不存在或已被删除'), (503, '加载失败')]:
            flags['status'] = status
            open_parent('annotation')
            parent.get_by_title('点击查看项目详情').click()
            expect(child.get_by_text(message, exact=False)).to_be_visible()
            flags['status'] = 200
            child.get_by_role('button', name='重新加载', exact=True).click()
            expect(child).to_contain_text('最新项目-annotation')
            close_all()
        checks.append('其他类型、缺失 ID、403/404/网络异常及重试')

        # 关闭后迟到的响应不能打开或回写已经关闭的小窗。
        flags['hold'] = True
        open_parent('annotation')
        parent.get_by_title('点击查看项目详情').click()
        expect(child.get_by_text('正在加载项目详情…')).to_be_visible()
        page.keyboard.press('Escape')
        flags['hold'] = False
        for route in pending:
            try:
                route.fulfill(status=200, json=projects['annotation'])
            except Exception:
                pass
        expect(child).to_have_count(0)
        close_all()
        checks.append('加载中关闭与旧响应保护')
        assert not writes, '二级只读详情不能产生业务写请求'

        page.set_viewport_size(dict(width=390, height=844))
        open_parent('annotation')
        parent.locator('.detail').evaluate('el => el.scrollTop = 45')
        before = parent.locator('.detail').evaluate('el => el.scrollTop')
        parent.get_by_title('点击查看项目详情').click()
        panel = parent.locator('.associated-project-detail')
        expect(panel).to_contain_text('最新项目-annotation')
        expect(panel.get_by_text('试标准备', exact=True).first).to_be_in_viewport()
        expect(child).to_have_count(0)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(output / 'annotation-mobile.png'))
        panel.get_by_role('button', name='返回资源需求', exact=True).click()
        expect(parent.locator('.detail')).to_be_visible()
        assert parent.locator('.detail').evaluate('el => el.scrollTop') == before
        expect(parent.get_by_title('点击查看项目详情')).to_be_focused()
        close_all()
        checks.append('390px 小屏同窗切换、返回、滚动恢复和无横向溢出')

        page.set_viewport_size(dict(width=968, height=884))
        open_parent('annotation')
        parent.get_by_role('button', name='编辑需求详情', exact=True).click()
        parent.get_by_role('textbox', name='编辑需求详情', exact=True).fill('原需求详情仍可编辑')
        parent.get_by_role('button', name='保存需求详情', exact=True).click()
        expect(parent).to_contain_text('原需求详情仍可编辑')
        assert writes[-1][1]['value'] == '原需求详情仍可编辑'
        close_all()
        checks.append('资源需求原有行内编辑与保存回归')

        # 原模块详情使用共享内容，仍保留原有行内编辑能力。
        page.set_viewport_size(dict(width=1440, height=1000))
        for source, path, selector in [
            ('annotation', '/annotation-details', '.annotation-detail-popover:visible'),
            ('translation', '/translation-details', '.business-detail-popover:visible'),
            ('interpretation', '/interpretation-details', '.interpretation-detail-popover:visible'),
            ('recruitment', '/recruitment-details', '.business-detail-popover:visible'),
        ]:
            print('回归原项目小窗：' + source, flush=True)
            page.goto(BASE + path)
            page.get_by_role('button', name='QA-' + source, exact=True).first.click()
            original = page.locator(selector)
            expect(original).to_be_visible()
            expect(original).to_contain_text('最新项目-' + source)
            expect(original.locator('.inline-text-field').filter(has=page.get_by_role('button', name=re.compile('编辑'))).first).to_be_visible()
            field = {'annotation': '具体任务', 'translation': '服务内容', 'interpretation': '具体任务', 'recruitment': '职位描述'}[source]
            original.get_by_role('button', name='编辑' + field, exact=True).click()
            original.get_by_role('textbox', name='编辑' + field, exact=True).fill('原项目编辑正常-' + source)
            original.get_by_role('button', name='保存' + field, exact=True).click()
            expect(original).to_contain_text('原项目编辑正常-' + source)
            assert writes[-1][1]['value'] == '原项目编辑正常-' + source
        checks.append('四类原项目详情、行内编辑及实际保存回归')
        page.set_viewport_size(dict(width=968, height=884))
        for source, route_path in [('annotation', '/annotation-details'), ('translation', '/translation-details'), ('interpretation', '/interpretation-details'), ('recruitment', '/recruitment-details')]:
            page.goto(BASE + REQUESTS)
            open_parent(source)
            open_child()
            child.get_by_role('button', name='进入项目', exact=True).click()
            page.wait_for_url(re.compile(re.escape(BASE + route_path) + r'\?.*projectId='))
            assert parse_qs(urlparse(page.url).query)['projectId'] == [projects[source]['id']]
            assert 'openEditor' not in page.url
        checks.append('四类进入项目定位，不自动打开编辑表单')
        assert not errors, errors
        report = dict(checks=checks, api_calls=len(calls), page_errors=errors, mode='全部 API 拦截，仅使用隔离内存数据')
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False), flush=True)
        browser.close()


if __name__ == '__main__':
    run()
