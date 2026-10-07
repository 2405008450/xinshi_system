"""调试机隔离前端验收：模拟业务接口，不向业务数据库写入记录。"""
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:12423'
PID, CID, UID, LID, LID2 = [str(uuid4()) for _ in range(5)]
FIELD_ID = str(uuid4())
NOW = '2026-10-06T08:00:00'


def run():
    if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5' or 'xinshi_validation' not in str(ROOT):
        raise SystemExit('仅允许在局域网调试机隔离验证目录执行')
    out = ROOT / '.tmp' / 'child-order-ui'
    out.mkdir(parents=True, exist_ok=True)
    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/frontend-dist', '--host', '127.0.0.1', '--port', '12423', '--strictPort'], cwd=ROOT / 'frontend', stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    parent = dict(id=PID, order_no='AP-QA-CHILD', project_name='多语种标注母订单', project_types=['text_annotation'], task_description='公共标注要求', client_id=CID, client_short_name='验收客户', client_full_name='验收客户全称', client_code='QA-CLIENT', contact_name='母订单联系人', customer_order_no='CUSTOMER-QA', client_manager_id=UID, client_manager_name='验收经理', project_status='trial_preparation', priority='medium', status_effective_on=NOW, task_dispatched_at=NOW, task_submitted_at=None, updated_at=NOW, created_at=NOW, language_items=[dict(id=str(uuid4()), source_language_id=LID, source_language_label='英语', display='英语', sequence_no=1)], language_items_display='英语', price_items=[], assignees=[], custom_values={}, role_assignments=[dict(role_code='project_manager', role_name='项目经理', assignee_id=UID, assignee_name='验收经理', assignment_type='direct')], parent_project_id=None, child_count=2, child_status_counts={'trial_preparation': 2})
    # 长编号和七个语种用于复现列表逐字换行、行高失控的问题。
    parent['order_no'] = 'AP-260929-003'
    for sequence, label in enumerate(['南非荷兰语', '冰岛语', '阿尔巴尼亚语', '爱尔兰语', '宿务语', '加泰罗尼亚语'], 2):
        parent['language_items'].append(dict(id=str(uuid4()), source_language_id=str(uuid4()), source_language_label=label, display=label, sequence_no=sequence))
    parent['language_items_display'] = '；'.join(item['display'] for item in parent['language_items'])
    parent['custom_values'] = {FIELD_ID: '母订单字段值'}
    parent['task_submitted_at'] = '2026-12-01T18:00:00'
    parent['language_items'][0]['target_language_id'] = LID2
    parent['language_items'][0]['display'] = '英语 → 日语'
    children = []
    for index in range(2):
        children.append({**parent, 'id': str(uuid4()), 'order_no': f'{parent["order_no"]}-S{index+1:03d}', 'project_name': f'英语标注批次{index+1}', 'parent_project_id': PID, 'parent_order_no': parent['order_no'], 'parent_project_name': parent['project_name'], 'child_sequence_no': index+1, 'child_count': 0, 'child_status_counts': {}})
    errors, creates, scopes = [], [], []

    def api(route):
        request = route.request
        url = urlparse(request.url)
        path = url.path.removeprefix('/api')
        query = parse_qs(url.query)
        result, status = [], 200
        if path == '/auth/session':
            result = dict(id=UID, username='qa', full_name='验收经理', roles=['admin'], permissions=['projects:read','projects:write','projects:order_no:write'])
        elif path in ['/projects/annotation/page', '/projects/annotation/']:
            scope = query.get('order_scope', ['all'])[0]; scopes.append(scope)
            rows = children if scope == 'child' else [parent] if scope == 'parent' else [parent, *children]
            result = dict(items=rows, total=len(rows)) if path.endswith('page') else rows
        elif path.endswith('/children/batch') or (path.endswith('/children') and request.method == 'POST'):
            payload = request.post_data_json
            items = payload['items'] if 'items' in payload else [payload]
            creates.append(dict(key=request.headers.get('x-idempotency-key'), items=items))
            added = []
            for item in items:
                number = len(children) + 1
                language = '日语' if item['language_items'][0]['source_language_id'] == LID2 else '英语'
                child = {**parent, **item, 'id': str(uuid4()), 'order_no': f'{parent["order_no"]}-S{number:03d}', 'parent_project_id': PID, 'parent_order_no': parent['order_no'], 'parent_project_name': parent['project_name'], 'child_sequence_no': number, 'child_count': 0, 'child_status_counts': {}, 'language_items_display': language}
                children.append(child); added.append(child)
            parent['child_count'] = len(children); parent['child_status_counts'] = {'trial_preparation': len(children)}
            result = added if 'items' in payload else added[0]; status = 201
        elif path.endswith('/children'):
            result = dict(items=children[:10], total=len(children))
        elif path.startswith('/projects/annotation/') and path.rsplit('/',1)[-1] in [PID, *(child['id'] for child in children)]:
            result = parent if path.endswith(PID) else next(child for child in children if path.endswith(child['id']))
        elif path == '/projects/languages':
            result = [dict(id=LID,label='英语'),dict(id=LID2,label='日语')]
        elif path == '/annotation-ops/custom-fields' and query.get('table_code') == ['project']:
            result = [dict(id=FIELD_ID, table_code='project', field_key='qa_required', field_label='验收必填字段', data_type='text', is_required=True, is_active=True, options=[])]
        elif path.rstrip('/') == '/users' or 'role-candidates' in path:
            result = [dict(id=UID, username='qa', full_name='验收经理', is_active=True)]
        elif path.rstrip('/') == '/clients':
            result = [dict(id=CID, client_short_name='验收客户', client_name='验收客户全称', client_code='QA-CLIENT')]
        elif path.endswith('/language-reserves/lookup'):
            result = dict(items=[])
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        route.fulfill(status=status, json=result)

    try:
        for _ in range(40):
            try: urlopen(BASE, timeout=1).close(); break
            except Exception: time.sleep(.25)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel='msedge')
            context = browser.new_context(viewport={'width':1440,'height':1000})
            context.route('**/api/**', api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            context.add_init_script("if (!localStorage.getItem('table-columns:annotation-details-v6:qa')) localStorage.setItem('table-columns:annotation-details-v6:qa', JSON.stringify(['orderNo','projectName','projectTypes','clientManagerName','projectManagerName','taskDescription','projectStatus','priority','clientShortName','languageItemsDisplay','potentialDemand','customerPriceSummary','taskDispatchedAt','taskSubmittedAt']))")
            page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(BASE + '/annotation-details')
            expect(page.get_by_role('button', name='新增标注项目', exact=True)).to_be_visible()
            selection = page.evaluate("JSON.parse(localStorage.getItem('table-columns:annotation-details-v6:qa'))")
            assert len(selection) == 8 and 'customerPriceSummary' not in selection, selection
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings = page.locator('.table-column-settings-popover:visible')
            settings.locator('.el-checkbox').filter(has_text='客户经理').click()
            page.mouse.click(300, 160)
            page.reload()
            expect(page.get_by_role('button', name='新增标注项目', exact=True)).to_be_visible()
            assert 'clientManagerName' in page.evaluate("JSON.parse(localStorage.getItem('table-columns:annotation-details-v6:qa'))")
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings.get_by_role('button', name='恢复默认', exact=True).click()
            page.mouse.click(300, 160)
            expect(settings).not_to_be_visible()
            table = page.locator('.annotation-table')
            row = table.locator('.el-table__body-wrapper tr.el-table__row').first
            order = row.locator('.order-no-link')
            expect(order).to_have_text(parent['order_no'])
            assert order.evaluate('(element) => getComputedStyle(element).whiteSpace') == 'nowrap'
            list_row_height = row.bounding_box()['height']
            assert order.bounding_box()['height'] < 25
            assert row.bounding_box()['height'] < 80, row.bounding_box()
            summary = row.locator('.annotation-language-summary')
            expect(summary).to_contain_text('+6')
            table.locator('.el-table__body-wrapper .el-scrollbar__wrap').evaluate('(element)=>element.scrollLeft=element.scrollWidth')
            summary.click()
            languages = page.locator('.annotation-languages-popover:visible')
            expect(languages.get_by_text('加泰罗尼亚语', exact=True)).to_be_visible()
            languages.get_by_text('加泰罗尼亚语', exact=True).click()
            expect(page.locator('.annotation-language-reserve-popover:visible')).to_be_visible()
            page.keyboard.press('Escape'); page.mouse.click(300, 160)
            row.get_by_role('button', name='查看详情', exact=True).click()
            expect(page.locator('.annotation-detail-popover:visible').last).to_be_visible()
            page.mouse.click(300, 160)
            row.get_by_role('button', name='项目资料', exact=True).click()
            expect(page.locator('.annotation-material-popover:visible')).to_be_visible()
            page.mouse.click(300, 160)
            expect(page.locator('.annotation-material-popover:visible')).not_to_be_visible()
            page.set_viewport_size({'width':1920,'height':1000})
            table.locator('.el-table__body-wrapper .el-scrollbar__wrap').evaluate('(element)=>element.scrollLeft=0')
            page.screenshot(path=str(out / 'annotation-list-desktop.png'), full_page=True)
            for width in [1024, 768]:
                page.set_viewport_size({'width':width,'height':900})
                assert row.bounding_box()['height'] < 80
                assert order.bounding_box()['height'] < 25
                page.screenshot(path=str(out / f'annotation-list-{width}.png'), full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            expand = row.get_by_role('button', name='展开子订单', exact=True)
            assert expand.locator('xpath=ancestor::div[contains(@class,"annotation-index-cell")]').count() == 1
            assert row.locator('.annotation-expand-column').bounding_box()['width'] <= 2
            expand.focus(); expand.press('Enter')
            expect(row.get_by_role('button', name='收起子订单', exact=True)).to_have_attribute('aria-expanded', 'true')
            row.get_by_role('button', name='收起子订单', exact=True).press('Space')
            expect(page.locator('.child-order-panel:visible')).to_have_count(0)
            page.get_by_role('button', name='删除管理', exact=True).click()
            row.get_by_role('button', name='展开子订单', exact=True).click()
            readonly_panel = page.locator('.child-order-panel:visible').first
            expect(readonly_panel.get_by_role('button', name='批量新增子订单', exact=True)).to_have_count(0)
            row.get_by_role('button', name='收起子订单', exact=True).click()
            page.get_by_role('button', name='退出', exact=True).click()
            row.get_by_role('button', name='展开子订单', exact=True).click()
            panel = page.locator('.child-order-panel:visible').first
            expect(panel.get_by_text('英语标注批次1', exact=True)).to_be_visible()
            assert 'parent' in scopes
            panel.get_by_role('button', name='分拆子订单', exact=True).click()
            split_dialog = page.locator('.annotation-child-create-dialog:visible')
            expect(split_dialog.locator('.child-preview-row')).to_have_count(7)
            first_split = split_dialog.locator('.child-preview-row').first
            expect(first_split.locator('textarea').first).to_have_value(parent['task_description'])
            expect(first_split.locator('.el-form-item').filter(has=page.locator('label', has_text='任务名称')).locator('input')).to_have_value(parent['project_name'])
            expect(first_split.locator('.el-form-item').filter(has=page.locator('label', has_text='目标语种')).locator('.el-select__placeholder')).to_contain_text('日语')
            inherited = first_split.locator('.el-form-item').filter(has=page.locator('label', has_text='验收必填字段'))
            expect(inherited.locator('textarea')).to_have_value('母订单字段值')
            page.screenshot(path=str(out / 'split-copy-preview.png'), full_page=True)
            split_dialog.locator('.el-dialog__headerbtn').click()
            expect(split_dialog).not_to_be_visible()
            panel.get_by_role('button', name='批量新增子订单', exact=True).click()
            dialog = page.locator('.annotation-child-create-dialog:visible')
            expect(dialog).to_be_visible()
            expect(dialog.get_by_text('子订单 1', exact=True)).to_be_visible()
            # 默认语种一行；继续追加同语种批次，确认可创建多个任务。
            dialog.get_by_role('button', name='添加任务行', exact=True).click()
            language_select = dialog.locator('.child-preview-row').nth(1).locator('.el-form-item').filter(has=page.locator('label', has_text='语种')).first.locator('.el-select')
            language_select.click(); page.locator('.el-select-dropdown:visible').get_by_text('英语', exact=True).click()
            for row in dialog.locator('.child-preview-row').all():
                field = row.locator('.el-form-item').filter(has=page.locator('label', has_text='验收必填字段'))
                field.locator('textarea').fill('子订单独立值')
            before = dialog.bounding_box()
            header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x']+15, header['y']+12); page.mouse.down(); page.mouse.move(header['x']+80, header['y']+40,steps=6); page.mouse.up()
            after = dialog.bounding_box(); assert abs(after['x']-before['x']) > 20
            page.mouse.move(after['x']+15,after['y']+12); page.mouse.down(); page.mouse.move(3000,2000,steps=8); page.mouse.up()
            bounded=dialog.bounding_box(); assert bounded['x']>=-1 and bounded['y']>=-1 and bounded['x']+bounded['width']<=1441 and bounded['y']+bounded['height']<=1001
            dialog.locator('.el-dialog__body').evaluate('(element)=>element.scrollTop=element.scrollHeight')
            expect(dialog.get_by_role('button',name='确认创建',exact=True)).to_be_visible()
            dialog.get_by_role('button',name='确认创建',exact=True).click()
            expect(dialog).not_to_be_visible(timeout=10000)
            assert len(creates)==1 and len(creates[0]['items'])==2 and creates[0]['key']
            assert all(item['custom_values'][FIELD_ID] == '子订单独立值' for item in creates[0]['items'])
            panel.get_by_role('button',name='新增子订单',exact=True).click()
            expect(dialog).to_be_visible(); reopened=dialog.bounding_box(); assert abs(reopened['x']-before['x'])<3
            dialog.locator('.el-dialog__headerbtn').click(); expect(dialog).not_to_be_visible()
            page.goto(BASE+f'/annotation-child-orders?parentProjectId={PID}&projectId={children[0]["id"]}&openEditor=1')
            editor=page.locator('.annotation-editor-dialog:visible')
            expect(editor).to_be_visible(); expect(editor.get_by_text('所属母订单：',exact=False)).to_be_visible()
            for label in ['联系人','客户单号/项目标识']:
                field=editor.locator('.el-form-item').filter(has=page.locator('label',has_text=label)).first
                assert field.locator('input:not([readonly])').count() == 1, label
            assert editor.locator('.el-form-item').filter(has=page.locator('label',has_text='客户经理')).first.locator('.el-select.is-disabled').count() == 0
            assert editor.get_by_role('button',name='修改订单号',exact=True).count()==0
            assert editor.get_by_role('tab',name='子订单',exact=True).count()==0
            editor.locator('.el-dialog__body').evaluate('(element)=>element.scrollTop=element.scrollHeight')
            expect(editor.get_by_role('button',name='保存',exact=True)).to_be_visible()
            editor.get_by_role('button',name='取消',exact=True).click()
            expect(editor).not_to_be_visible()
            assert 'child' in scopes
            page.goto(BASE+f'/annotation-details?projectId={PID}&openEditor=1')
            expect(editor).to_be_visible(); editor.get_by_role('tab',name='子订单',exact=True).click()
            expect(editor.locator('.child-order-panel')).to_be_visible()
            editor.locator('.project-field-search input').fill('具体任务')
            page.locator('.project-field-search-option').filter(has_text='具体任务').first.click()
            expect(editor.get_by_role('tab', name='订单信息', exact=True)).to_have_attribute('aria-selected', 'true')
            expect(editor.locator('.el-form-item').filter(has=page.locator('label', has_text='具体任务')).first).to_be_visible()
            editor.get_by_role('button',name='取消',exact=True).click()
            expect(editor).not_to_be_visible()
            page.set_viewport_size({'width':600,'height':740})
            page.get_by_role('button',name='新增标注项目',exact=True).click()
            expect(editor).to_be_visible()
            page.wait_for_function("() => { const element = [...document.querySelectorAll('.annotation-editor-dialog')].find(item => item.getClientRects().length); if (!element) return false; const box = element.getBoundingClientRect(); return box.width <= 568.5 && box.height <= 666.5; }")
            box=editor.bounding_box(); assert box['width']<=568.5 and box['height']<=666.5
            editor.get_by_role('button',name='保存',exact=True).click()
            expect(editor.locator('.el-form-item.is-error').first).to_be_visible()
            expect(editor.get_by_role('button',name='取消',exact=True)).to_be_visible()
            page.screenshot(path=str(out/'child-orders-small.png'), full_page=True)
            editor.get_by_role('button',name='取消',exact=True).click()
            expect(editor).not_to_be_visible()
            parent['child_count'] = 0
            page.goto(BASE + '/annotation-details')
            expect(page.locator('.annotation-table .order-no-link')).to_have_text(parent['order_no'])
            expect(page.locator('.annotation-index-cell .table-expand-button')).to_have_count(0)
            assert not errors, errors
            (out/'result.json').write_text(json.dumps(dict(passed=True,list_row_height=list_row_height,language_count=7,layout_viewports=[1920,1440,1024,768],column_settings_verified=True,batch_rows=2,scopes=sorted(set(scopes)),errors=errors),ensure_ascii=False,indent=2),encoding='utf-8')
            browser.close()
            print('UI 验收通过：紧凑行高、多语种及储备小窗、资料详情、字段配置迁移与持久化、展开、批量预览、同语种多批次、分拆全部方向、业务信息继承、独立管理与客户字段编辑、母订单页签、拖拽边界与复位、小屏校验及固定操作栏')
    finally:
        process.terminate(); process.wait(timeout=10); log.close()


if __name__=='__main__': run()
