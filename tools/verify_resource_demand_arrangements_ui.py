"""本机构建与隔离接口状态验收，不向日常业务数据库写入。"""
import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from business_time import business_iso, business_now
BASE = 'http://127.0.0.1:12459'


def run():
    global BASE
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在本机执行')
    out = ROOT / '.tmp/resource-demand-arrangements-ui'
    out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    BASE = f'http://127.0.0.1:{port}'
    today = business_now().date().isoformat()
    actor, owner, parent = [str(uuid4()) for _ in range(3)]
    accounts = [dict(id=str(uuid4()), kind='platform', category='national', name=name,
                     parent_id=parent, parent_name='BOSS') for name in ['BOSS1', 'BOSS2']]
    accounts.append(dict(id=str(uuid4()), kind='platform', category='international', name='Facebook'))
    accounts.extend(dict(id=str(uuid4()), kind='platform', category='local', name=f'本地平台{i}') for i in range(18))
    definitions = [dict(id=parent, kind='channel_group', category='national', name='BOSS', has_accounts=True), *accounts]
    requests = [dict(id=str(uuid4()), request_no=f'RR-QA-{i}', source_type='annotation', order_no=f'AP-QA-{i:02}',
                     project_name=f'验收需求项目{i}', request_detail='寻找项目人才', languages=[],
                     demand_status='confirmed', request_status='submitted', project=dict(source_type='annotation',
                     project_id=str(uuid4()), order_no=f'AP-QA-{i:02}', project_name=f'验收需求项目{i}')) for i in range(7)]
    existing = dict(platform_id=accounts[1]['id'], platform_name='BOSS2', owner_id=owner, owner_name='原负责人',
                    targets=[], role_tags=['HR'], projects=[requests[1]['project']], manual_projects=[requests[1]['project']],
                    remarks='保留其他项目及备注', completed=True, can_edit=True)
    days = {today: dict(work_date=today, revision=1, remarks='保留每日备注', cells=[existing], can_manage=True)}
    writes, errors, reads = [], [], []
    mode, conflict = ['manager'], [False]

    def summary(row):
        value = copy.deepcopy(row); value['arrangements'] = []
        for day in days.values():
            for cell in day['cells']:
                if any(t.get('request_id') == row['id'] for t in cell['targets']):
                    definition = next(p for p in accounts if p['id'] == cell['platform_id'])
                    value['arrangements'].append(dict(work_date=day['work_date'], platform_id=cell['platform_id'],
                        platform_name=definition.get('parent_name') or definition['name'],
                        account_name=definition['name'] if definition.get('parent_id') else '单账号',
                        owner_name=cell.get('owner_name', ''), completed=cell['completed'], active=row['demand_status'] == 'confirmed'))
        return value

    def api(route):
        req = route.request; path = urlparse(req.url).path.removeprefix('/api'); query = parse_qs(urlparse(req.url).query)
        if path == '/auth/session':
            result = dict(user_id=actor, username='qa', full_name='验收人员', roles=['admin'] if mode[0] == 'manager' else ['staff'], permissions=['talents:read', 'projects:read'])
        elif path == '/resource-development/options':
            result = dict(options=accounts, arrangement_platforms=definitions, users=[dict(id=owner, name='原负责人')],
                          languages=[], user_id=actor, is_admin=mode[0] == 'manager', can_delegate=mode[0] == 'manager', can_write=mode[0] == 'manager')
        elif path == '/resource-development/days': result = dict(items=[], total=0)
        elif path == '/resource-development/arrangement-options':
            result = dict(targets=[], projects=[], request_projects=[dict(kind='request_project', request_id=r['id'],
                language_id=None, label=r['project_name'], request_no=r['request_no'], project=r['project']) for r in requests])
        elif path == '/resource-development/arrangement-requests':
            reads.append(query)
            keyword = query.get('keyword', [''])[0]
            values = [summary(r) for r in requests if r['demand_status'] == 'confirmed' and any(keyword in r[k] for k in ['request_no', 'project_name', 'order_no'])]
            skip = int(query.get('skip', ['0'])[0]); limit = int(query.get('limit', ['5'])[0])
            result = dict(items=values[skip:skip+limit], total=len(values))
        elif path.startswith('/resource-development/arrangement-requests/'):
            parts = path.split('/'); row = next(r for r in requests if r['id'] == parts[3])
            if req.method == 'PUT':
                payload = req.post_data_json
                if conflict[0]:
                    conflict[0] = False; route.fulfill(status=409, json=dict(detail='这一天已被其他人修改，请重新加载')); return
                writes.append(copy.deepcopy(payload)); work_date = parts[5]
                result = copy.deepcopy(days.get(work_date, dict(work_date=work_date, revision=0, cells=[], remarks='', can_manage=True)))
                by_id = {c['platform_id']: c for c in result['cells']}
                linked = {key for key, cell in by_id.items() if any(t.get('request_id') == row['id'] for t in cell['targets'])}
                for key in set(payload['platform_ids']) | linked:
                    cell = by_id.get(key)
                    if cell is None:
                        definition = next(p for p in accounts if p['id'] == key)
                        cell = dict(platform_id=key, platform_name=definition['name'], owner_id=None, owner_name='', targets=[],
                                    role_tags=[], projects=[], manual_projects=[], remarks='', completed=False, can_edit=True)
                        result['cells'].append(cell)
                    cell['targets'] = [t for t in cell['targets'] if t.get('request_id') != row['id']]
                    if key in payload['platform_ids']:
                        cell['targets'].append(dict(kind='request_project', request_id=row['id'], language_id=None, label=row['project_name'],
                                                   request_no=row['request_no'], project=row['project'], active=True))
                    projects = cell['manual_projects'] + [t['project'] for t in cell['targets'] if t.get('project')]
                    cell['projects'] = list({p['project_id']: p for p in projects}.values()); cell['completed'] = False
                result['revision'] += 1; days[work_date] = copy.deepcopy(result)
            else: result = summary(row)
        elif path == '/resource-development/arrangements':
            values = [copy.deepcopy(d) for d in days.values() if query.get('start', [''])[0] <= d['work_date'] <= query.get('end', ['9999'])[0]]
            result = dict(items=values, total=len(values))
        elif path.startswith('/resource-development/arrangements/'):
            work_date = path.split('/')[3]
            result = copy.deepcopy(days.get(work_date, dict(work_date=work_date, revision=0, cells=[], remarks='', can_manage=True)))
            if req.method == 'PUT':
                for value in req.post_data_json['cells']:
                    cell = next(c for c in result['cells'] if c['platform_id'] == value['platform_id'])
                    targets = []
                    for target in value['targets']:
                        row = next(r for r in requests if r['id'] == target['request_id'])
                        targets.append(target | dict(label=row['project_name'], project=row['project'], active=True))
                    cell.update(remarks=value['remarks'], targets=targets)
                result['revision'] += 1; days[work_date] = copy.deepcopy(result)
        elif path == '/resource-development/arrangement-project-detail':
            row = next(r for r in requests if r['project']['project_id'] == query['project_id'][0])
            result = row['project'] | dict(project_status='resource_sourcing', requirements=[], arrangements=summary(row)['arrangements'])
        elif path.endswith('/unread-count'): result = dict(count=0)
        else: result = {}
        route.fulfill(status=200, json=result)

    log = (out / 'preview.log').open('w', encoding='utf-8')
    preview = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/resource-arrangements-dist',
                                '--host', '127.0.0.1', '--port', str(port), '--strictPort'], cwd=ROOT/'frontend',
                               stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(60):
            if preview.poll() is not None:
                raise RuntimeError('隔离前端启动失败，请查看 preview.log')
            try: urlopen(BASE, timeout=1).close(); break
            except Exception: time.sleep(.2)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel='msedge')
            context = browser.new_context(viewport=dict(width=1440, height=1000), timezone_id='America/Los_Angeles')
            context.route('**/api/**', api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(BASE + '/resource-management/resource-development')
            page.get_by_role('tab', name='每日安排', exact=True).click()
            panel = page.locator('.development-demand-panel'); table = panel.locator('.el-table__body tbody')
            expect(table.locator('tr')).to_have_count(5)
            assert panel.bounding_box()['y'] < page.locator('.arrangement-section-title').bounding_box()['y']
            panel.get_by_role('button', name='下一页', exact=True).click()
            expect(table).to_contain_text('验收需求项目6')
            search = panel.locator('.development-demand-search input')
            search.fill('AP-QA-00'); expect(table.locator('tr')).to_have_count(1)
            assert reads[-1].get('skip') == ['0'] and reads[-1]['keyword'] == ['AP-QA-00']
            search.fill(''); expect(table.locator('tr')).to_have_count(5)
            table.get_by_role('button', name='每日安排', exact=True).first.click()
            dialog = page.locator('.request-arrangement-dialog:visible')
            def toggle_account(name):
                dialog.locator('.el-checkbox').filter(has=page.get_by_role('checkbox', name=name, exact=True)).click()
            order = dialog.locator('.el-form-item').filter(has=page.get_by_text('订单号', exact=True)).locator('input')
            expect(order).to_have_value('AP-QA-00')
            expect(order).to_have_attribute('readonly', '')
            expect(dialog.get_by_role('checkbox', name='BOSS1', exact=True)).not_to_be_checked()
            before = dialog.bounding_box(); header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x']+25, header['y']+20); page.mouse.down(); page.mouse.move(header['x']+130, header['y']+60, steps=6); page.mouse.up()
            assert abs(dialog.bounding_box()['x'] - before['x']) > 30
            page.mouse.move(header['x']+130, header['y']+60); page.mouse.down(); page.mouse.move(4000, 3000, steps=8); page.mouse.up()
            bounded = dialog.bounding_box(); assert bounded['x'] >= -2 and bounded['y'] >= -2
            assert bounded['x']+bounded['width'] <= 1442 and bounded['y']+bounded['height'] <= 1002
            dialog.locator('.el-dialog__headerbtn').click(); expect(dialog).not_to_be_visible()
            table.get_by_role('button', name='每日安排', exact=True).first.click(); expect(dialog).to_be_visible()
            assert abs(dialog.bounding_box()['x'] - before['x']) < 3
            toggle_account('BOSS1')
            toggle_account('Facebook')
            expect(dialog.locator('.el-dialog__footer')).to_contain_text('已选 2 个账号')
            body = dialog.locator('.el-dialog__body'); footer = dialog.locator('.el-dialog__footer')
            body.evaluate('(el) => el.scrollTop = el.scrollHeight/2'); expect(footer.get_by_role('button', name='保存安排')).to_be_visible()
            body.evaluate('(el) => el.scrollTop = el.scrollHeight'); expect(footer.get_by_role('button', name='保存安排')).to_be_visible()
            footer.get_by_role('button', name='保存安排', exact=True).click(); expect(dialog).not_to_be_visible()
            expect(table.locator('tr').first).to_contain_text('BOSS')
            expect(table.locator('tr').first).to_contain_text('Facebook')
            expect(page.locator('.arrangement-table').get_by_role('button', name='AP-QA-00 · 验收需求项目0', exact=True)).to_have_count(2)
            assert days[today]['cells'][0]['remarks'] == '保留其他项目及备注'
            assert days[today]['cells'][0]['owner_id'] == owner and days[today]['remarks'] == '保留每日备注'
            # 原账号编辑器继续保留新加入的项目需求来源。
            daily_row = page.locator('.arrangement-table .el-table__row').filter(has=page.get_by_role('button', name='AP-QA-00 · 验收需求项目0', exact=True)).first
            daily_row.get_by_role('button', name='编辑安排', exact=True).click()
            original_editor = page.locator('.arrangement-editor:visible')
            expect(original_editor.locator('.arrangement-auto-projects')).to_contain_text('AP-QA-00')
            original_editor.locator('.el-form-item').filter(has=page.get_by_text('账号备注', exact=True)).locator('textarea').fill('通过原编辑器补充备注')
            original_editor.get_by_role('button', name='保存', exact=True).click(); expect(original_editor).not_to_be_visible()
            assert len(summary(requests[0])['arrangements']) == 2
            table.get_by_role('button', name='验收需求项目0', exact=True).click()
            detail = page.locator('.development-detail:visible').filter(has=page.get_by_text('需求项目详情', exact=True))
            expect(detail).to_contain_text('Facebook'); expect(detail).to_contain_text('BOSS1')
            expect(detail).to_have_attribute('data-popper-placement', 'left')
            page.get_by_role('heading', name='资源开拓', exact=True).click(); expect(detail).not_to_be_visible()
            table.get_by_role('button', name='每日安排', exact=True).first.click()
            expect(dialog.get_by_role('checkbox', name='BOSS1', exact=True)).to_be_checked()
            expect(dialog.get_by_role('checkbox', name='Facebook', exact=True)).to_be_checked()
            toggle_account('BOSS1')
            conflict[0] = True
            footer.get_by_role('button', name='保存安排', exact=True).click()
            expect(dialog).to_contain_text('选择已保留'); expect(dialog.get_by_role('checkbox', name='BOSS1', exact=True)).not_to_be_checked()
            dialog.get_by_role('button', name='重新加载', exact=True).click()
            expect(dialog.get_by_role('checkbox', name='BOSS1', exact=True)).to_be_checked()
            toggle_account('BOSS1')
            footer.get_by_role('button', name='保存安排', exact=True).click(); expect(dialog).not_to_be_visible()
            expect(table.locator('tr').first).to_contain_text('Facebook')
            table.get_by_role('button', name='验收需求项目0', exact=True).click(); expect(detail).not_to_contain_text('BOSS1')
            page.get_by_role('heading', name='资源开拓', exact=True).click()
            page.wait_for_function("document.getAnimations().every(a => a.playState !== 'running')")
            page.screenshot(path=str(out/'desktop.png'), full_page=True)
            table.get_by_role('button', name='每日安排', exact=True).first.click()
            page.set_viewport_size(dict(width=390, height=844))
            expect(dialog).to_be_visible(); body.evaluate('(el) => el.scrollTop = el.scrollHeight')
            expect(footer.get_by_role('button', name='保存安排')).to_be_visible()
            bounds = dialog.bounding_box(); assert bounds['width'] <= 360 and bounds['height'] <= 761
            assert body.evaluate('(el) => el.scrollHeight > el.clientHeight')
            page.wait_for_function("document.getAnimations().filter(a => a.effect?.target?.closest?.('.el-overlay')).every(a => a.playState !== 'running')")
            page.screenshot(path=str(out/'small-screen.png'), full_page=True)
            footer.get_by_role('button', name='取消', exact=True).click(); expect(dialog).not_to_be_visible()
            page.set_viewport_size(dict(width=1440, height=1000))
            # 日期范围不暗中选择某一天。
            inputs = page.locator('.arrangement-panel>.development-filters .el-range-input')
            inputs.first.fill('2026-10-01'); inputs.first.press('Enter')
            page.locator('.arrangement-panel>.development-filters').get_by_role('button', name='查询', exact=True).click()
            table.get_by_role('button', name='每日安排', exact=True).first.click()
            date = dialog.locator('.el-date-editor input'); expect(date).to_have_value('')
            expect(footer.get_by_role('button', name='保存安排')).to_be_disabled()
            date.fill(today); date.press('Enter')
            expect(dialog.get_by_role('checkbox', name='Facebook', exact=True)).to_be_checked()
            footer.get_by_role('button', name='取消', exact=True).click()
            mode[0] = 'readonly'; page.reload(); page.get_by_role('tab', name='每日安排', exact=True).click()
            expect(panel.locator('.development-demand-table').get_by_role('button', name='每日安排', exact=True)).to_have_count(0)
            table.get_by_role('button', name='验收需求项目0', exact=True).click(); expect(detail).to_contain_text('Facebook')
            assert not errors, errors
            (out/'result.json').write_text(json.dumps(dict(passed=True, writes=len(writes), errors=errors,
                scenarios=['需求每页5条及分页','订单号搜索及清空','日期范围显式选日','多平台账号分配','原安排保留','项目直接展示',
                           '原编辑器保留项目需求','详情反查及缓存失效','平台回显与撤回','并发冲突保留草稿','拖动边界及位置复位','小屏内部滚动固定底栏','只读权限'],
                verified_at=business_iso(business_now())), ensure_ascii=False, indent=2), encoding='utf-8')
            browser.close()
        print('需求到平台每日安排浏览器验收通过')
    finally:
        preview.terminate(); preview.wait(timeout=15); log.close()


if __name__ == '__main__':
    run()
