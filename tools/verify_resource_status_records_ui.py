"""本机跨日期开拓列表验收；页面使用隔离接口，不写入真实业务数据。"""
import asyncio
import copy
import json
import re
import socket
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:12439'


async def run(out):
    uid, other, platform, second_platform, account = [str(uuid4()) for _ in range(5)]
    viewer_id = uid
    requests, errors, saves, checks = [], [], [], []
    fixtures = []
    for index in range(10):
        fixtures.append(dict(full_name=f'一次候选{index:02}', work_date=(date(2026, 10, 8) - timedelta(days=index % 6)).isoformat(),
            wechat_status='一次请求' if index % 3 != 2 else '已添加', enterprise_status='一次请求' if index % 3 != 1 else '已添加'))
    fixtures += [
        dict(full_name='历史别名候选', work_date='2026-09-15', wechat_status='已发请求', enterprise_status='已添加'),
        dict(full_name='未处理候选甲', work_date='2026-10-07', wechat_status='未处理', enterprise_status='已添加'),
        dict(full_name='未处理候选乙', work_date='2026-10-06', wechat_status='已添加', enterprise_status='未处理'),
        dict(full_name='未处理候选丙', work_date='2026-09-20', wechat_status='未处理', enterprise_status='未处理', owner_id=other, platform_id=second_platform, can_edit=False),
        dict(full_name='请求未通过候选', work_date='2026-10-08', wechat_status='一次请求未通过', enterprise_status='二次请求'),
    ]
    for row in fixtures:
        defaults = dict(id=str(uuid4()), revision=1, owner_id=uid, owner_name='验收人员', platform_id=platform,
            platform_name='测试平台', account_id=account, account_name='HR1', phone='', wechat='', language_ids=[],
            language_names='英语', greeting_no='QA-' + uuid4().hex[:8], person_id=None, resource_code='',
            follow_up='', remarks='长备注\n' * 100, actions=[], audit=[], capabilities=[], historical_markers={},
            updated_at='2026-10-08T12:00:00', can_edit=True, can_delete=True, add_friend_follow_up='')
        row.update({key: value for key, value in defaults.items() if key not in row})
        row['progress'] = {channel: dict(status='一次请求' if row[field] == '已发请求' else row[field],
            action_date=row['work_date'], operator_name='验收人员') for channel, field in [('wechat', 'wechat_status'), ('enterprise', 'enterprise_status')]}
    fixtures[-2]['platform_name'] = '其他平台'
    fixtures[-2]['owner_name'] = '其他人员'

    def matching(query):
        result = []
        aliases = {'已发请求': '一次请求'}
        columns = json.loads(query.get('column_filters', ['{}'])[0])
        for row in fixtures:
            if not query.get('start', [''])[0] <= row['work_date'] <= query.get('end', ['9999-12-31'])[0]:
                continue
            if any(query.get(key, [''])[0] and query[key][0] != row[key] for key in ['owner_id', 'platform_id', 'account_id']):
                continue
            state = query.get('state', [''])[0]
            if state and state not in [aliases.get(row[field], row[field]) for field in ['wechat_status', 'enterprise_status']]:
                continue
            keyword = query.get('keyword', [''])[0]
            if keyword and not any(keyword in row.get(key, '') for key in ['full_name', 'platform_name', 'language_names', 'greeting_no', 'phone', 'wechat']):
                continue
            valid = True
            for key, value in columns.items():
                actual_key = {'platform_name': 'platform_id', 'owner_name': 'owner_id', 'account_name': 'account_id'}.get(key, key)
                actual = aliases.get(row.get(actual_key, ''), row.get(actual_key, ''))
                if isinstance(value, list):
                    valid &= not value or actual in value
                else:
                    valid &= value in actual
            if valid:
                result.append(row)
        return sorted(result, key=lambda row: (row['work_date'], row['full_name']), reverse=True)

    async def route_api(route):
        req = route.request
        path = urlparse(req.url).path.removeprefix('/api')
        query = parse_qs(urlparse(req.url).query)
        requests.append((req.method, path, query))
        result = []
        if path == '/auth/session':
            result = dict(id=viewer_id, username='qa', full_name='验收人员', roles=['admin'], permissions=['talents:read', 'talents:write', 'resource_development:delegate'])
        elif path == '/resource-development/options':
            result = dict(options=[dict(id=platform, kind='platform', name='测试平台', category='national'), dict(id=second_platform, kind='platform', name='其他平台', category='national'), dict(id=account, kind='account', name='HR1')],
                users=[dict(id=uid, name='验收人员'), dict(id=other, name='其他人员')], languages=[], user_id=viewer_id, can_write=True, can_delegate=True, is_admin=True, default_date='2026-10-08')
        elif path == '/resource-development/days':
            matches = matching(query)
            dates = sorted({row['work_date'] for row in matches}, reverse=True)
            selected = dates[int(query.get('skip', [0])[0]):][:int(query.get('limit', [3])[0])]
            result = dict(total=len(dates), items=[dict(date=day, count=sum(row['work_date'] == day for row in matches), people=[dict(duration_minutes=0)]) for day in selected])
        elif path == '/resource-development/records' and req.method == 'GET':
            # 延迟旧查询，验证新查询和关闭窗口能够使旧响应失效。
            if query.get('keyword', [''])[0] == '旧响应':
                await asyncio.sleep(1.5)
            matches = matching(query)
            result = dict(total=len(matches), items=matches[int(query.get('skip', [0])[0]):][:int(query.get('limit', [10])[0])])
        elif path == '/resource-development/records' and req.method == 'POST':
            payload = req.post_data_json
            saves.append(copy.deepcopy(payload))
            row = next(row for row in fixtures if row['id'] == payload['id'])
            row.update(payload, revision=row['revision'] + 1)
            for action in row['actions']:
                row[action['channel'] + '_status'] = action['status']
                row['progress'][action['channel']] = dict(status=action['status'], action_date=action['action_date'], operator_name='验收人员')
            result = row
        elif path.startswith('/resource-development/records/'):
            result = next(row for row in fixtures if row['id'] == path.rsplit('/', 1)[-1])
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        try:
            await route.fulfill(status=200, json=result)
        except Exception:
            if not req.is_navigation_request() and query.get('keyword', [''])[0] == '旧响应':
                return
            raise

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, channel='msedge')
        context = await browser.new_context(viewport=dict(width=1440, height=900), timezone_id='Asia/Hong_Kong')
        await context.route('**/api/**', route_api)
        # 独立预览不连接业务通知服务；与 HTTP 数据一起隔离，仍检查页面的全部错误。
        await context.route_web_socket('**/api/notifications/ws*', lambda ws: ws.on_message(lambda message: None))
        await context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
        page = await context.new_page()
        page.set_default_timeout(10000)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        # 保持香港业务日期确定，同时让时间继续流动，避免冻结 Date.now 影响 Vue 退出动画。
        await page.clock.set_system_time(datetime(2026, 10, 8, 4, tzinfo=timezone.utc))
        await page.goto(BASE + '/resource-management/resource-development')
        await expect(page.get_by_role('heading', name='资源开拓', exact=True)).to_be_visible()
        main = page.locator('.resource-development-page')
        dialog = page.locator('.development-status-dialog')

        async def open_dialog(state):
            await main.locator('.development-status-entry').get_by_role('button', name=state, exact=True).click()
            await expect(dialog).to_be_visible()
            await expect(dialog.locator('.el-loading-mask:visible')).to_have_count(0)
            await page.wait_for_timeout(300)

        async def close_dialog():
            await dialog.locator('.el-dialog__footer').get_by_role('button', name='关闭', exact=True).click()
            await expect(dialog).to_have_count(0)

        def latest_records():
            return next(query for method, path, query in reversed(requests) if method == 'GET' and path == '/resource-development/records')

        async def expect_query(**wanted):
            for _ in range(40):
                current = latest_records()
                if all(current.get(key) == value for key, value in wanted.items()):
                    break
                await page.wait_for_timeout(50)
            else:
                raise AssertionError((current, wanted))
            await expect(dialog.locator('.el-loading-mask:visible')).to_have_count(0)

        await expect(main.locator('.el-table__body tr').first).to_be_visible()
        main_headers = await main.locator('.el-table__header').all_text_contents()
        main_day = latest_records()['start']
        assert main_day == latest_records()['end']
        await open_dialog('未处理')
        await expect_query(state=['未处理'], start=None, end=None)
        await expect(dialog.locator('.el-table__body tr')).to_have_count(3)
        await expect(dialog.get_by_text('未处理候选甲', exact=True)).to_be_visible()
        await expect(dialog.get_by_text('未处理候选乙', exact=True)).to_be_visible()
        await expect(dialog.get_by_text('未处理候选丙', exact=True)).to_be_visible()
        assert '日期' in await dialog.locator('.el-table__header').inner_text()
        assert len({row['work_date'] for row in matching(latest_records())}) == 3
        await page.screenshot(path=str(out / 'unhandled.png'), full_page=True)
        checks.append('未处理跨日、任一渠道符合及只读权限')

        ranges = {'昨日': ('2026-10-07', '2026-10-07'), '本周': ('2026-10-05', '2026-10-08'), '过去一周': ('2026-10-02', '2026-10-08'), '本月': ('2026-10-01', '2026-10-08'), '过去一月': ('2026-09-09', '2026-10-08')}
        for label, (start, end) in ranges.items():
            await dialog.get_by_role('button', name=label, exact=True).click()
            await expect_query(start=[start], end=[end], state=['未处理'])
        date_editor = dialog.locator('.el-date-editor')
        await date_editor.hover()
        await date_editor.locator('.el-range__close-icon').click()
        await expect_query(start=None, end=None)
        date_inputs = date_editor.locator('input')
        await date_inputs.nth(0).click()
        await date_inputs.nth(0).fill('2026-10-06')
        await date_inputs.nth(1).fill('2026-10-07')
        await date_inputs.nth(1).press('Enter')
        await dialog.locator('.el-dialog__header').click(position=dict(x=40, y=15))
        await expect_query(start=['2026-10-06'], end=['2026-10-07'])
        await expect(dialog.locator('.el-table__body tr')).to_have_count(2)
        await dialog.get_by_role('button', name='重置', exact=True).click()
        await expect_query(state=None, start=None, end=None)
        await close_dialog()
        await open_dialog('一次请求')
        await expect_query(state=['一次请求'], start=None, end=None, keyword=None)
        await expect(dialog.locator('.el-table__body tr')).to_have_count(10)
        await expect(dialog.locator('.el-pagination')).to_contain_text('共 11 条')
        assert all(row['full_name'] != '请求未通过候选' for row in matching(latest_records()))
        state_selector = dialog.get_by_label('添加状态（任一渠道）', exact=True)
        await state_selector.click()
        await page.get_by_role('option', name='未处理', exact=True).click()
        await expect_query(state=['未处理'])
        await expect(dialog.locator('.el-table__body tr')).to_have_count(3)
        state_field = dialog.locator('.development-filters > .el-select')
        await state_field.hover()
        await state_field.locator('.el-select__clear').click()
        await expect_query(state=None)
        await expect(dialog.locator('.el-pagination')).to_contain_text('共 15 条')
        await close_dialog()
        await open_dialog('一次请求')
        await expect_query(state=['一次请求'])
        checks.append('五种快捷日期、清空、重置、重新打开及一次请求精确筛选')

        # 高级筛选不能改变主表高度，清空高级条件保留状态和日期。
        before = await dialog.locator('.status-records-area').bounding_box()
        await dialog.get_by_role('button', name='高级筛选', exact=True).click()
        advanced = page.locator('.development-advanced:visible')
        await advanced.get_by_role('combobox', name='开拓平台', exact=True).click()
        await page.get_by_role('option', name='测试平台', exact=True).click()
        await expect_query(platform_id=[platform], state=['一次请求'])
        await expect(advanced).to_be_visible()
        await expect(dialog.get_by_role('button', name='高级筛选（1）')).to_be_visible()
        after = await dialog.locator('.status-records-area').bounding_box()
        assert abs(before['height'] - after['height']) < 1
        for label, option, enabled in [('开拓人员', '验收人员', 2), ('交换账号', 'HR1', 3)]:
            await advanced.get_by_role('combobox', name=label, exact=True).click()
            await page.get_by_role('option', name=option, exact=True).click()
            await expect(dialog.get_by_role('button', name=f'高级筛选（{enabled}）', exact=True)).to_be_visible()
            await expect(advanced).to_be_visible()
        await expect_query(platform_id=[platform], owner_id=[uid], account_id=[account], state=['一次请求'])
        await advanced.get_by_role('button', name='清空高级条件', exact=True).click()
        await expect_query(platform_id=None, owner_id=None, account_id=None, state=['一次请求'])
        await advanced.get_by_role('button', name='关闭', exact=True).click()
        await dialog.get_by_role('button', name=re.compile(r'^(?:添加)?微信筛选$')).click()
        funnel = page.locator('.column-header-filter-popover:visible')
        count_before = len(requests)
        await funnel.get_by_text('一次请求', exact=True).click()
        assert len(requests) == count_before
        await funnel.get_by_role('button', name='确定', exact=True).click()
        await expect_query(column_filters=['{"wechat_status":["一次请求"]}'])
        await dialog.get_by_role('button', name='清空列筛选', exact=True).click()
        await expect_query(column_filters=None)
        checks.append('高级条件计数、AND组合、主表高度及表头确认筛选')

        search = dialog.get_by_placeholder('姓名、招呼编号、联系方式、语种/方言、开拓平台', exact=True)
        count_before = len(requests)
        await search.fill('旧响应')
        await page.wait_for_timeout(200)
        assert len(requests) == count_before
        await page.wait_for_timeout(250)
        await search.fill('一次候选')
        await expect_query(keyword=['一次候选'])
        await page.wait_for_timeout(1600)
        await expect(dialog.locator('.el-table__body tr')).to_have_count(10)
        await search.fill('')
        await expect_query(keyword=None)
        await search.fill('历史别名候选')
        await search.press('Enter')
        await expect_query(keyword=['历史别名候选'])
        await expect(dialog.locator('.el-table__body tr')).to_have_count(1)
        await search.fill('')
        await expect_query(keyword=None)
        checks.append('400ms防抖、旧响应保护、清空立即查及回车查询')

        await dialog.locator('.el-pagination .btn-next').click()
        await expect_query(skip=['10'])
        await expect(dialog.locator('.el-table__body tr')).to_have_count(1)
        await dialog.get_by_role('button', name='查看详情', exact=True).click()
        detail = page.locator('.development-detail:visible')
        await expect(detail.locator('.el-descriptions')).to_be_visible()
        detail_box = await detail.bounding_box()
        reference = await dialog.get_by_role('button', name='查看详情', exact=True).bounding_box()
        assert detail_box['x'] < reference['x']
        assert await detail.locator('.development-detail-body').evaluate('el => el.scrollHeight > el.clientHeight')
        await dialog.locator('.el-dialog__header').click(position=dict(x=40, y=15))
        await dialog.get_by_role('button', name='编辑', exact=True).click()
        editor = page.locator('.development-dialog')
        await expect(editor).to_be_visible()
        assert await editor.evaluate('el => el.contains(document.activeElement)')
        assert await editor.evaluate('el => Number(getComputedStyle(el.closest(".el-overlay")).zIndex)') > await dialog.evaluate('el => Number(getComputedStyle(el.closest(".el-overlay")).zIndex)')
        for position in [0, 400, 100000]:
            await editor.locator('.el-dialog__body').evaluate('(el, pos) => el.scrollTop = pos', position)
            await expect(editor.get_by_role('button', name='保存', exact=True)).to_be_visible()
        await editor.locator('.el-form-item').filter(has=page.locator('label', has_text='资源姓名')).locator('input').fill('历史别名候选更新')
        await editor.get_by_role('button', name='保存', exact=True).click()
        await expect(editor).not_to_be_visible()
        await expect(dialog.get_by_text('历史别名候选更新', exact=True)).to_be_visible()
        detail_requests = len([path for _, path, _ in requests if path == '/resource-development/records/' + fixtures[10]['id']])
        await dialog.get_by_role('button', name='查看详情', exact=True).click()
        await expect(detail.locator('h3')).to_have_text('历史别名候选更新')
        assert len([path for _, path, _ in requests if path == '/resource-development/records/' + fixtures[10]['id']]) > detail_requests
        await dialog.locator('.el-dialog__header').click(position=dict(x=40, y=15))
        await dialog.locator('.development-progress').first.click()
        await expect(editor).to_be_visible()
        status = editor.locator('.el-form-item').filter(has=page.locator('label', has_text='跟进状态')).last.locator('.el-select')
        await status.click()
        await page.get_by_role('option', name='二次请求', exact=True).click()
        await editor.get_by_role('button', name='保存', exact=True).click()
        await expect(editor).not_to_be_visible()
        await expect_query(skip=['0'], state=['一次请求'])
        await expect(dialog.locator('.el-pagination')).to_contain_text('共 10 条')
        await expect(dialog.get_by_text('历史别名候选更新', exact=True)).to_have_count(0)
        assert saves[-1]['actions'][-1]['status'] == '二次请求'
        assert any(path.endswith('/days') for _, path, _ in requests[-6:])
        checks.append('详情左侧小窗滚动、编辑后详情缓存更新、二级编辑层级与焦点、固定操作栏、编辑移出及末页回退')

        # 字段全部取消时结构列仍保留，并按用户持久化；两入口共用弹窗配置。
        await dialog.get_by_role('button', name='字段设置', exact=True).click()
        columns = page.locator('.development-status-columns:visible')
        await expect(columns.locator('.el-checkbox').first).to_be_visible()
        for checkbox in await columns.locator('.el-checkbox').all():
            if await checkbox.locator('input').is_checked():
                await checkbox.click()
                await expect(checkbox.locator('input')).not_to_be_checked()
        await expect(dialog.locator('.el-table__header th')).to_have_count(3)
        assert await main.locator('.el-table__header').all_text_contents() == main_headers
        key = f'resource-development:status-records:columns:{uid}'
        assert await page.evaluate('(key) => localStorage.getItem(key)', key) == '[]'
        await dialog.locator('.el-dialog__header').click(position=dict(x=40, y=15))
        await close_dialog()
        await open_dialog('未处理')
        await expect(dialog.locator('.el-table__header th')).to_have_count(3)
        await close_dialog()
        viewer_id = other
        await page.reload()
        await expect(main.locator('.el-table__body tr').first).to_be_visible()
        await open_dialog('未处理')
        await expect(dialog.locator('.el-table__header')).to_contain_text('日期')
        await close_dialog()
        viewer_id = uid
        await page.reload()
        await expect(main.locator('.el-table__body tr').first).to_be_visible()
        await open_dialog('未处理')
        await expect(dialog.locator('.el-table__header th')).to_have_count(3)
        await dialog.get_by_role('button', name='字段设置', exact=True).click()
        await page.locator('.development-status-columns:visible').get_by_role('button', name='恢复默认', exact=True).click()
        await expect(dialog.locator('.el-table__header')).to_contain_text('日期')
        await dialog.locator('.el-dialog__header').click(position=dict(x=40, y=15))
        checks.append('字段全隐藏、恢复默认、跨入口及刷新保留、不同用户配置隔离')

        await page.wait_for_timeout(350)
        original = await dialog.bounding_box()
        header = await dialog.locator('.el-dialog__header').bounding_box()
        await page.mouse.move(header['x'] + 35, header['y'] + 15)
        await page.mouse.down(); await page.mouse.move(header['x'] + 110, header['y'] + 45, steps=8); await page.mouse.up()
        moved = await dialog.bounding_box()
        assert abs(moved['x'] - original['x']) > 15 or abs(moved['y'] - original['y']) > 15
        await page.mouse.move(moved['x'] + 35, moved['y'] + 15)
        await page.mouse.down(); await page.mouse.move(3000, 3000, steps=8); await page.mouse.up()
        bounds = await dialog.bounding_box()
        assert bounds['x'] >= -1 and bounds['y'] >= -1 and bounds['x'] + bounds['width'] <= 1441 and bounds['y'] + bounds['height'] <= 901
        await dialog.locator('.el-dialog__headerbtn').click()
        await expect(dialog).to_have_count(0)
        await open_dialog('未处理')
        restored = await dialog.bounding_box()
        assert abs(restored['x'] - original['x']) < 2 and abs(restored['y'] - original['y']) < 2
        assert await dialog.locator('.el-table__body-wrapper .el-scrollbar__wrap').evaluate('el => el.scrollLeft') == 0
        await page.screenshot(path=str(out / 'cross-date-desktop.png'), full_page=True)
        await close_dialog()
        await page.set_viewport_size(dict(width=600, height=760))
        await open_dialog('一次请求')
        bounds = await dialog.bounding_box()
        assert bounds['width'] <= 568 and bounds['y'] + bounds['height'] <= 761
        await expect(dialog.locator('.el-dialog__footer')).to_be_visible()
        await dialog.locator('.el-table__body-wrapper .el-scrollbar__wrap').evaluate('el => { el.scrollTop = 10000; el.scrollLeft = 10000 }')
        await expect(dialog.locator('.el-dialog__footer').get_by_role('button', name='关闭', exact=True)).to_be_visible()
        await page.screenshot(path=str(out / 'cross-date-small.png'), full_page=True)
        await dialog.get_by_role('button', name='高级筛选', exact=True).click()
        small_advanced = page.locator('.development-status-advanced:visible')
        await expect(small_advanced).to_be_visible()
        advanced_bounds = await small_advanced.bounding_box()
        assert advanced_bounds['width'] <= 568 and advanced_bounds['x'] >= 0
        assert advanced_bounds['x'] + advanced_bounds['width'] <= 601 and advanced_bounds['y'] + advanced_bounds['height'] <= 761
        await small_advanced.get_by_role('combobox', name='交换账号', exact=True).click()
        await expect(small_advanced.get_by_role('option', name='HR1', exact=True)).to_be_visible()
        await small_advanced.get_by_role('option', name='HR1', exact=True).click()
        await expect(small_advanced).to_be_visible()
        await small_advanced.get_by_role('button', name='清空高级条件', exact=True).click()
        await expect_query(account_id=None, state=['一次请求'])
        await small_advanced.get_by_role('button', name='关闭', exact=True).click()
        await dialog.get_by_role('button', name='查看详情', exact=True).first.click()
        small_detail = page.locator('.development-detail:visible')
        await expect(small_detail.locator('.el-descriptions')).to_be_visible()
        detail_bounds = await small_detail.bounding_box()
        assert detail_bounds['x'] >= 0 and detail_bounds['x'] + detail_bounds['width'] <= 601
        assert detail_bounds['y'] >= 0 and detail_bounds['y'] + detail_bounds['height'] <= 761
        await dialog.locator('.el-dialog__header').click(position=dict(x=40, y=15))
        await dialog.get_by_role('button', name='编辑', exact=True).first.click()
        await expect(editor).to_be_visible()
        await editor.locator('.el-dialog__body').evaluate('el => { el.scrollTop = 10000 }')
        await expect(editor.get_by_role('button', name='保存', exact=True)).to_be_visible()
        editor_bounds = await editor.bounding_box()
        assert editor_bounds['width'] <= 568 and editor_bounds['y'] + editor_bounds['height'] <= 761
        await editor.get_by_role('button', name='取消', exact=True).click()
        await expect(editor).not_to_be_visible()
        await search.fill('旧响应')
        await page.wait_for_timeout(450)
        await close_dialog()
        await open_dialog('未处理')
        await page.wait_for_timeout(1600)
        await expect(dialog.locator('.el-table__body tr')).to_have_count(3)
        checks.append('拖动边界、关闭按钮、位置复位、小屏高级筛选/详情/编辑窗口、固定分页、关闭后旧请求失效')
        await close_dialog()
        await main.get_by_role('button', name='删除管理', exact=True).click()
        await expect(main.get_by_role('button', name='删除所选（0）', exact=True)).to_be_disabled()
        await expect(main.locator('.development-status-entry')).to_have_count(0)
        await main.locator('.el-table__body tr').first.locator('.el-checkbox').click()
        await expect(main.get_by_role('button', name='删除所选（1）', exact=True)).to_be_enabled()
        await main.get_by_role('button', name='退出', exact=True).click()
        await expect(main.locator('.el-table__body').get_by_role('checkbox')).to_have_count(0)
        checks.append('原按日列表删除选择与退出回归')
        assert not errors, errors
        await browser.close()
    print(json.dumps(dict(ok=True, checks=checks), ensure_ascii=False))


def main():
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在本机执行')
    out = ROOT / '.tmp' / 'resource-status-records-ui'
    out.mkdir(parents=True, exist_ok=True)
    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/resource-status-records-dist', '--host', '127.0.0.1', '--port', '12439', '--strictPort'],
        cwd=ROOT / 'frontend', stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(50):
            try:
                urlopen(BASE, timeout=1).close()
                break
            except Exception:
                import time
                time.sleep(.2)
        asyncio.run(run(out))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


if __name__ == '__main__':
    main()
