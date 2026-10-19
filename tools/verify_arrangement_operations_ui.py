"""本机每日安排交互验收；全部 API 拦截，写操作仅作用于内存数据。"""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import socket
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://localhost:3000'


def run():
    assert socket.gethostname().upper() == 'PC' and ROOT == Path(r'E:\xinshi_system')
    output = ROOT / 'artifacts' / 'arrangement-operations'
    output.mkdir(parents=True, exist_ok=True)
    uid, owner, platform, language, request, project, cell_id = [str(uuid4()) for _ in range(7)]
    tomorrow = (datetime.now(timezone(timedelta(hours=8))).date() + timedelta(days=1)).isoformat()
    project_row = dict(source_type='annotation', project_id=project, order_no='AP-QA-001', project_name='双人对话采集项目', languages=['粤语'], parent_project_id='')
    child_id = str(uuid4())
    child_project = project_row | dict(project_id=child_id, order_no='AP-QA-001-01', languages=['闽南语'], parent_project_id=project)
    target = dict(kind='request_project', request_id=request, language_id=None, label='双人对话采集项目',
                  request_no='RR-QA-001', demand_status='confirmed', active=True, project=project_row,
                  scope=[dict(key='a', language_label='粤语', city='广州', district='天河区', label='粤语 · 广州 / 天河区'),
                         dict(key='b', language_label='闽南语', city='厦门', label='闽南语 · 厦门')], arrangement_note='只安排以上两个地区')
    def event(action, label, name='录入人员', clock='2026-10-19T08:30:00+08:00', changes=None):
        return dict(id=str(uuid4()), action=action, label=label, actor_name=name, operated_at=clock, changes=changes or [])
    first = event('create', '录入安排')
    history = [first]
    cell = dict(id=cell_id, platform_id=platform, platform_name='智联招聘2', owner_id=owner, owner_name='执行负责人',
                targets=[target], role_tags=['译员'], projects=[project_row], manual_projects=[], remarks='账号说明',
                completed=False, completed_by=None, completed_by_name='', completed_at=None, can_edit=True,
                operations=dict(created=first, edited=first, status=None))
    day = dict(work_date=tomorrow, revision=1, remarks='每日备注', cells=[cell], can_manage=True)
    project_detail = dict(id=project, order_no='AP-QA-001', project_name='双人对话采集项目', project_status='trial_preparation',
                          role_assignments=[], areas=[], area_labels=[], project_types=[], language_items=[],
                          task_description='完整项目内容。' * 300, created_at='2026-10-19T00:30:00Z', updated_at='2026-10-19T08:30:00+08:00')
    flags = dict(history_error=False, project_error=False)
    errors, writes, checks = [], [], []

    def api(route):
        req = route.request
        if not urlparse(req.url).path.startswith('/api/'):
            route.continue_(); return
        path = urlparse(req.url).path.removeprefix('/api')
        result = []
        if path == '/auth/session':
            result = dict(user_id=uid, username='隔离验收', full_name='隔离验收', roles=['admin'], permissions=['*'])
        elif path.endswith('/issues/access'):
            result = dict(ready=True, can_enter=True, can_resource=True, can_manage=True, user_id=uid)
        elif path == '/resource-development/options':
            result = dict(options=[dict(id=platform, kind='platform', category='national', name='智联招聘2')],
                          users=[dict(id=uid, name='状态操作人员'), dict(id=owner, name='执行负责人')],
                          languages=[dict(id=language, label='粤语')], user_id=uid, can_delegate=True, can_write=True, is_admin=True)
        elif path in {'/resource-requests/page', '/resource-development/days'}:
            result = dict(items=[], total=0)
        elif path == '/resource-development/arrangement-options':
            keyword = parse_qs(urlparse(req.url).query).get('keyword', [''])[0]
            candidates = [p for p in [project_row, child_project] if not keyword or keyword in ' '.join([p['project_name'], p['order_no'], *p['languages']])]
            result = dict(targets=[], request_projects=[target], projects=candidates)
        elif path == f'/resource-requests/{request}':
            result = dict(id=request, request_no='RR-QA-001', source_type='annotation', annotation_project_id=project,
                          current_project_name=project_row['project_name'], current_order_no=project_row['order_no'],
                          demand_status='confirmed', request_status='submitted', request_detail='下拉方向的完整需求说明',
                          source_project_types_snapshot=[], requested_at='2026-10-19T08:30:00+08:00', items=[])
        elif path == '/resource-development/arrangement-project-detail':
            result = project_row | dict(project_status='trial_preparation', requirements=[], arrangements=[])
        elif path == '/resource-development/arrangements':
            result = dict(items=[day], total=1)
        elif path.endswith('/history') and '/arrangements/' in path:
            if flags['history_error']:
                route.fulfill(status=503, json=dict(detail='历史加载失败，请重试')); return
            result = dict(items=list(reversed(history)), total=len(history))
        elif path.endswith('/completion'):
            assert req.method == 'PATCH'
            value = req.post_data_json
            assert set(value) == {'revision', 'completed'} and value['revision'] == day['revision']
            writes.append(copy.deepcopy(value))
            completed = value['completed']
            status = event('complete' if completed else 'reopen', '确认完成' if completed else '取消完成', '状态操作人员')
            history.append(status)
            cell.update(completed=completed, completed_by=uid if completed else None,
                        completed_by_name='状态操作人员' if completed else '', completed_at=status['operated_at'] if completed else None)
            cell['operations']['status'] = status
            day['revision'] += 1
            result = day
        elif path == f'/resource-development/arrangements/{tomorrow}':
            if req.method == 'PUT':
                value = req.post_data_json
                writes.append(copy.deepcopy(value))
                updated = value['cells'][0]
                assert not {'operations', 'completed_by', 'completed_at'} & updated.keys()
                change = event('update', '修改安排', '内容修改人员', changes=[dict(field='remarks', label='账号备注', before=cell['remarks'], after=updated['remarks'])])
                history.append(change); cell['remarks'] = updated['remarks']; cell['operations']['edited'] = change
                day['revision'] += 1
            result = day
        elif path == f'/projects/annotation/{project}':
            if flags['project_error']:
                route.fulfill(status=403, json=dict(detail='没有权限查看项目')); return
            result = project_detail
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        elif req.method not in {'GET', 'HEAD'}:
            raise AssertionError(f'未预期的写请求：{req.method} {path}')
        route.fulfill(status=200, json=result)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        context = browser.new_context(viewport=dict(width=1273, height=884), timezone_id='America/Los_Angeles')
        context.route('**/api/**', api)
        context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
        page = context.new_page(); page.set_default_timeout(8000); page.on('pageerror', lambda error: errors.append(str(error)))
        def capture(name):
            page.wait_for_function("document.getAnimations().every(a => a.effect.getTiming().iterations === Infinity || a.playState !== 'running')")
            page.screenshot(path=str(output / name))
        page.goto(BASE + '/resource-management/resource-development?section=arrangements')
        table = page.locator('.arrangement-table')
        expect(table).to_contain_text('粤语 · 广州 / 天河区')
        expect(table).to_contain_text('闽南语 · 厦门')
        expect(table).not_to_contain_text('AP-QA-001')
        expect(table).not_to_contain_text('RR-QA-001')
        expect(table).to_contain_text('最近修改：录入人员 · 2026/10/19 08:30:00')
        table.scroll_into_view_if_needed()
        capture('list.png')
        checks.append('精简列表、范围配对、跨时区时间展示')
        more = table.get_by_role('button', name='双人对话采集项目 更多', exact=True)
        more.click()
        popup = page.get_by_role('tooltip', name='项目安排详情', exact=True)
        expect(popup).to_contain_text('AP-QA-001'); expect(popup).to_contain_text('录入安排')
        expect(popup).to_contain_text('只安排以上两个地区')
        assert popup.bounding_box()['x'] >= 0
        popup.locator('.arrangement-project-detail-body').evaluate('(el) => el.scrollTop = 0')
        popup.locator('.arrangement-open-project-detail').click()
        child = page.locator('.associated-project-detail:visible')
        expect(child).to_contain_text('完整项目内容')
        assert page.url.endswith('section=arrangements')
        capture('project-detail.png')
        page.keyboard.press('Escape'); expect(child).not_to_be_visible(); expect(popup).to_be_visible()
        expect(popup.locator('.arrangement-open-project-detail')).to_be_focused()
        page.keyboard.press('Escape'); expect(popup).not_to_be_visible()
        checks.append('更多小窗、二级项目详情、ESC逐层关闭与焦点恢复')
        checkbox = table.locator('.el-checkbox')
        checkbox.click(); expect(table.get_by_role('checkbox')).to_be_checked(); expect(table).to_contain_text('确认完成：状态操作人员')
        expect(table).to_contain_text('最近修改：录入人员')
        checkbox.click(); expect(table.get_by_role('checkbox')).not_to_be_checked(); expect(table).to_contain_text('取消完成：状态操作人员')
        more.click(); expect(popup).to_contain_text('取消完成'); expect(popup.locator('article')).to_have_count(3)
        popup.locator('.arrangement-project-detail-body').evaluate('(el) => el.scrollTop = el.scrollHeight')
        capture('history.png')
        page.keyboard.press('Escape')
        table.get_by_role('button', name='编辑安排', exact=True).click()
        dialog = page.locator('.arrangement-editor:visible')
        expect(dialog).to_be_visible()
        target_field = dialog.locator('.el-form-item').filter(has=page.get_by_text('开拓方向（语种／方言）', exact=True))
        target_field.locator('.el-select').click()
        dropdown = page.locator('.el-popper.arrangement-target-dropdown:visible')
        expect(dropdown.locator('.arrangement-option-title')).to_have_text(['双人对话采集项目'])
        expect(dropdown).not_to_contain_text('AP-QA-001')
        expect(target_field.locator('.el-tag')).not_to_contain_text('AP-QA-001')
        capture('dropdown-list.png')
        option = dropdown.locator('li.el-select-dropdown__item').filter(has=page.locator('.arrangement-option-title', has_text='双人对话采集项目'))
        selected = option.get_attribute('aria-selected')
        dropdown.get_by_role('button', name='双人对话采集项目 更多信息', exact=True).click()
        direction_popup = page.locator('.resource-detail-popover[aria-label="开拓方向详情"]:visible')
        expect(direction_popup).to_contain_text('下拉方向的完整需求说明')
        expect(direction_popup).to_contain_text('AP-QA-001')
        expect(dropdown).to_be_visible()
        assert option.get_attribute('aria-selected') == selected
        direction_popup.get_by_role('button', name='双人对话采集项目', exact=True).click()
        expect(child).to_contain_text('完整项目内容')
        page.keyboard.press('Escape'); expect(child).not_to_be_visible(); expect(direction_popup).to_be_visible()
        capture('dropdown-details.png')
        direction_popup.get_by_role('button', name='关闭', exact=True).click()
        expect(direction_popup).not_to_be_visible()
        expect(dropdown).to_be_visible()
        assert option.get_attribute('aria-selected') == selected
        page.keyboard.press('Escape'); expect(dropdown).not_to_be_visible(); expect(dialog).to_be_visible()
        # 手动关联项目采用相同的精简名称与更多信息入口。
        dialog.locator('.arrangement-project-selector .el-select').nth(1).click()
        expect(dropdown.locator('.arrangement-option-title')).to_have_text(['双人对话采集项目', '双人对话采集项目'])
        expect(dropdown.locator('.arrangement-project-languages')).to_have_text(['语种：粤语', '语种：闽南语'])
        expect(dropdown.locator('.arrangement-child-order-badge')).to_have_text('子订单')
        expect(dropdown).not_to_contain_text('AP-QA-001')
        capture('project-language-options.png')
        dropdown.get_by_role('button', name='双人对话采集项目 更多信息', exact=True).first.click()
        expect(direction_popup).to_contain_text('AP-QA-001')
        direction_popup.get_by_role('button', name='关闭', exact=True).click()
        project_select = dialog.locator('.arrangement-project-selector .el-select').nth(1)
        expect(direction_popup).not_to_be_visible()
        page.wait_for_function("document.getAnimations().every(a => a.effect.getTiming().iterations === Infinity || a.playState !== 'running')")
        project_select.locator('input.el-select__input').click()
        project_select.locator('input.el-select__input').fill('闽南语')
        expect(project_select.locator('input.el-select__input')).to_have_value('闽南语')
        expect(dropdown.locator('.arrangement-project-option')).to_have_count(1)
        expect(dropdown.locator('.arrangement-project-languages')).to_contain_text('闽南语')
        expect(dropdown.locator('.arrangement-child-order-badge')).to_be_visible()
        capture('child-language-search.png')
        project_select.locator('input.el-select__input').fill('')
        expect(dropdown.locator('.arrangement-project-option')).to_have_count(2)
        project_select.locator('input.el-select__input').fill('闽南语')
        expect(dropdown.locator('.arrangement-project-option')).to_have_count(1)
        dropdown.locator('.arrangement-option-title').click()
        expect(dialog.locator('.arrangement-project-tags')).to_contain_text('AP-QA-001-01')
        page.keyboard.press('Escape')
        checks.append('下拉名称去重、不显示订单号；更多信息和二级项目详情不影响选择')
        checks.append('母子同名项目独立语种标签、子订单标记、按语种搜索及精确关联子订单')
        dialog.locator('.el-form-item').filter(has=page.get_by_text('账号备注', exact=True)).locator('textarea').fill('修改后的账号说明')
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible(); expect(table).to_contain_text('最近修改：内容修改人员')
        assert writes[-1]['cells'][0]['projects'] == [dict(source_type='annotation', project_id=child_id)]
        expect(table).to_contain_text('取消完成：状态操作人员')
        page.reload(); expect(table).to_contain_text('最近修改：内容修改人员')
        checks.append('完成和取消留痕、内容修改与状态操作分离、刷新保留')
        flags['history_error'] = True
        more.click(); expect(popup).to_contain_text('历史加载失败，请重试')
        flags['history_error'] = False
        popup.get_by_role('button', name='重新加载', exact=True).click(); expect(popup.locator('article')).to_have_count(4)
        page.keyboard.press('Escape')
        table.get_by_role('button', name='查看详情', exact=True).click()
        account = page.locator('.arrangement-detail:visible')
        expect(account).to_contain_text('录入人'); expect(account).to_contain_text('修改后的账号说明')
        page.mouse.click(1200, 100)
        checks.append('历史错误重试、账号详情复用操作历史')
        page.set_viewport_size(dict(width=390, height=844))
        more.click(); expect(popup).to_be_visible()
        bounds = popup.bounding_box(); assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= 391, bounds
        popup.locator('.arrangement-project-detail-body').evaluate('(el) => el.scrollTop = 0')
        popup.locator('.arrangement-open-project-detail').click(); expect(child).to_contain_text('完整项目内容')
        bounds = page.locator('.resource-detail-popover:visible').bounding_box()
        assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= 391, bounds
        capture('mobile.png')
        page.keyboard.press('Escape'); expect(popup).to_be_visible()
        page.keyboard.press('Escape'); expect(popup).not_to_be_visible()
        checks.append('390px视口、内部滚动、移动端逐层返回')
        table.get_by_role('button', name='编辑安排', exact=True).click()
        expect(dialog).to_be_visible()
        target_field.locator('.el-select').click()
        dropdown.get_by_role('button', name='双人对话采集项目 更多信息', exact=True).click()
        expect(direction_popup).to_contain_text('下拉方向的完整需求说明')
        box = direction_popup.bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= 391 and box['y'] + box['height'] <= 845
        capture('dropdown-mobile.png')
        direction_popup.get_by_role('button', name='关闭', exact=True).click()
        page.keyboard.press('Escape')
        dialog.get_by_role('button', name='取消', exact=True).click()
        expect(dialog).not_to_be_visible()
        checks.append('390px下拉详情不溢出，查看不触发选择或保存')
        # 历史暂停项保留在已选标签中，不再混入默认候选；仍能主动移除。
        paused = copy.deepcopy(target) | dict(request_id=str(uuid4()), label='历史暂停项目', active=False, inactive_reason='需求已暂停', demand_status='paused', project=project_row | dict(project_id=str(uuid4()), project_name='历史暂停项目'))
        cell['targets'].append(paused)
        table.get_by_role('button', name='编辑安排', exact=True).click()
        expect(target_field.locator('.el-tag').filter(has_text='历史暂停项目')).to_be_visible()
        target_field.locator('.el-select').click()
        expect(dropdown.locator('.el-select-group__title').filter(has_text='需求确认')).to_be_visible()
        expect(dropdown).not_to_contain_text('历史暂停项目')
        expect(dropdown.locator('.arrangement-option-title')).to_have_text(['双人对话采集项目'])
        page.keyboard.press('Escape')
        target_field.locator('.el-tag').filter(has_text='历史暂停项目').locator('.el-tag__close').click()
        expect(target_field.locator('.el-tag').filter(has_text='历史暂停项目')).to_have_count(0)
        dialog.get_by_role('button', name='取消', exact=True).click()
        page.get_by_role('button', name='放弃修改', exact=True).click()
        expect(dialog).not_to_be_visible()
        checks.append('开拓方向默认需求确认，历史暂停项不混入候选且可移除')
        assert not errors, errors
        (output / 'result.json').write_text(json.dumps(dict(checks=checks, writes=len(writes), errors=errors, business_database_writes=0), ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(dict(checks=checks, writes=len(writes), errors=errors), ensure_ascii=False))
        context.close(); browser.close()


if __name__ == '__main__':
    run()

