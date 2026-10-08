"""调试机隔离前端验收：模拟业务接口，不向业务数据库写入记录。"""
import json
import re
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
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('仅允许在本机 E:\\xinshi_system 执行模拟接口验收')
    if not (ROOT / 'frontend' / 'dist' / 'index.html').is_file():
        raise SystemExit('请先执行前端 npm run build')
    out = ROOT / '.tmp' / 'child-order-ui'
    out.mkdir(parents=True, exist_ok=True)
    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '12423', '--strictPort'], cwd=ROOT / 'frontend', stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
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
    parent['direction_summary'] = dict(automatic_enabled=True,direction_count=7,
        missing_directions=[item['display'] for item in parent['language_items'][1:]],
        extra_directions=[],invalid_child_order_nos=[])
    children = []
    for index in range(2):
        children.append({**parent, 'id': str(uuid4()), 'order_no': f'{parent["order_no"]}-S{index+1:03d}', 'project_name': f'英语标注批次{index+1}', 'parent_project_id': PID, 'parent_order_no': parent['order_no'], 'parent_project_name': parent['project_name'], 'child_sequence_no': index+1, 'child_count': 0, 'child_status_counts': {}, 'language_items':[dict(parent['language_items'][0])], 'direction_summary':None})
    errors, creates, scopes, saves = [], [], [], []
    session = dict(id=UID, username='qa', full_name='验收经理', roles=['admin'], permissions=['projects:read','projects:write','projects:order_no:write'])
    membership_requests, context_project_ids, detail_reads, pending_memberships = [], [], [], []
    mock_state = dict(hold_membership=False, fail_membership=False)

    def finish_membership(route, child, payload):
        child['arrangement_included'] = payload['included']
        child['arrangement_membership_note'] = payload.get('membership_note')
        child['arrangement_membership_updated_at'] = NOW
        route.fulfill(json=dict(included=payload['included'], membership_note=child['arrangement_membership_note'], updated_at=NOW))

    def api(route):
        request = route.request
        url = urlparse(request.url)
        path = url.path.removeprefix('/api')
        query = parse_qs(url.query)
        result, status = [], 200
        if path == '/auth/session':
            result = session
        elif path.startswith('/annotation-ops/project-arrangements/projects/') and path.endswith('/membership'):
            project_id = path.split('/')[-2]
            payload = request.post_data_json
            membership_requests.append(dict(project_id=project_id, payload=payload))
            child = next(child for child in children if child['id'] == project_id)
            if mock_state['fail_membership']:
                result, status = dict(detail='模拟安排更新失败'), 500
            elif mock_state['hold_membership']:
                pending_memberships.append((route, child, payload))
                return
            else:
                finish_membership(route, child, payload)
                return
        elif path == '/annotation-ops/project-arrangements/context':
            ids = query.get('project_id', [])
            context_project_ids.extend(ids)
            result = dict(projects=[{**child, 'tasks':[dict(id='qa-task', execution_date='2026-10-08', task_type_id='qa-type', assignee_id=UID, task_content='子订单安排验收', updated_at=NOW)]} for child in children if child['id'] in ids], task_types=[dict(id='qa-type', name='标注', is_active=True)], assignees=[dict(id=UID, display_name='验收经理', priority_group='project_manager')])
        elif path == '/resource-requests/source-statuses':
            result = {children[1]['id']: 'confirmed'}
        elif path == '/resource-requests/source-request':
            result = None
        elif path == '/resource-requests/source-prefill':
            child = next(child for child in children if child['id'] == query['source_project_id'][0])
            result = dict(source_project_id=child['id'], order_no=child['order_no'], project_name=child['project_name'], items=[])
        elif path.startswith('/project-chat/annotation/'):
            result = dict(items=[], has_more=False) if path.endswith(('/timeline', '/refresh')) else dict(members=[], eligible_users=[], following=False)
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
        elif path == f'/projects/annotation/{PID}' and request.method == 'PUT':
            payload=request.post_data_json; saves.append(payload)
            directions={ (item['source_language_id'],item.get('target_language_id')) for child in children
                if len(child['language_items'])==1 for item in child['language_items'] }
            added=0
            for item in parent['language_items']:
                if (item['source_language_id'],item.get('target_language_id')) in directions:
                    continue
                number=len(children)+1
                children.append({**parent,'id':str(uuid4()),'order_no':f'{parent["order_no"]}-S{number:03d}',
                    'parent_project_id':PID,'parent_order_no':parent['order_no'],'child_sequence_no':number,
                    'language_items':[dict(item)],'child_count':0,'child_status_counts':{},'direction_summary':None})
                added+=1
            parent['child_count']=len(children); parent['auto_created_child_count']=added
            parent['direction_summary']['missing_directions']=[]
            result=parent
        elif path.startswith('/projects/annotation/') and path.rsplit('/',1)[-1] in [PID, *(child['id'] for child in children)]:
            detail_reads.append(path.rsplit('/',1)[-1])
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
        elif path.endswith('/page'):
            result = dict(items=[], total=0)
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
            assert len(selection) == 7 and 'customerPriceSummary' not in selection and 'orderNo' not in selection, selection
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings = page.locator('.table-column-settings-popover:visible')
            expect(settings.get_by_role('checkbox', name='订单号', exact=True)).to_have_count(0)
            settings.locator('.el-checkbox').filter(has_text='客户经理').click()
            page.mouse.click(300, 160)
            page.reload()
            expect(page.get_by_role('button', name='新增标注项目', exact=True)).to_be_visible()
            assert 'clientManagerName' in page.evaluate("JSON.parse(localStorage.getItem('table-columns:annotation-details-v6:qa'))")
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings.get_by_role('button', name='恢复默认', exact=True).click()
            page.mouse.click(300, 160)
            expect(settings).not_to_be_visible()
            # 历史隐藏订单号和全部取消业务字段，都必须保留详情入口。
            page.evaluate("localStorage.setItem('table-columns:annotation-details-v6:qa', JSON.stringify(['projectName']))")
            page.reload()
            expect(page.locator('.annotation-table .order-no-link')).to_have_text(parent['order_no'])
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings.locator('.el-checkbox').filter(has_text='项目名称').click()
            page.mouse.click(300, 160)
            page.reload()
            expect(page.locator('.annotation-table .order-no-link')).to_have_text(parent['order_no'])
            assert page.evaluate("JSON.parse(localStorage.getItem('table-columns:annotation-details-v6:qa'))") == []
            session['username'] = 'qa-other'
            page.reload()
            expect(page.locator('.annotation-table .order-no-link')).to_have_text(parent['order_no'])
            page.get_by_role('button', name='字段设置', exact=True).click()
            expect(settings.locator('.el-checkbox.is-checked')).to_have_count(7)
            page.mouse.click(300, 160)
            session['username'] = 'qa'
            page.reload()
            expect(page.get_by_role('button', name='字段设置', exact=True)).to_be_visible()
            assert page.evaluate("JSON.parse(localStorage.getItem('table-columns:annotation-details-v6:qa'))") == []
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings.get_by_role('button', name='恢复默认', exact=True).click()
            page.mouse.click(300, 160)
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
            expect(table.get_by_role('button', name='查看详情', exact=True)).to_have_count(0)
            order.click()
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
            expect(page.locator('.sub-order-panel:visible')).to_have_count(0)
            page.get_by_role('button', name='删除管理', exact=True).click()
            row.get_by_role('button', name='展开子订单', exact=True).click()
            readonly_panel = page.locator('.sub-order-panel:visible').first
            expect(readonly_panel.get_by_role('button', name='批量新增子订单', exact=True)).to_have_count(0)
            expect(readonly_panel.get_by_role('button', name='更多操作', exact=True)).to_have_count(0)
            expect(readonly_panel.get_by_role('button', name='编辑', exact=True)).to_have_count(0)
            row.get_by_role('button', name='收起子订单', exact=True).click()
            page.get_by_role('button', name='退出', exact=True).click()
            row.get_by_role('button', name='展开子订单', exact=True).click()
            panel = page.locator('.sub-order-panel:visible').first
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
            expect(editor.get_by_role('button',name='添加语言项',exact=True)).to_be_disabled()
            expect(editor.get_by_text('子订单必须且只能绑定一个语种或语言方向。',exact=True)).to_be_visible()
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
            expect(editor.locator('.sub-order-panel')).to_be_visible()
            editor.locator('.project-field-search input').fill('具体任务')
            page.locator('.project-field-search-option').filter(has_text='具体任务').first.click()
            expect(editor.get_by_role('tab', name='订单信息', exact=True)).to_have_attribute('aria-selected', 'true')
            expect(editor.locator('.el-form-item').filter(has=page.locator('label', has_text='具体任务')).first).to_be_visible()
            expect(editor.get_by_text('一个方向不自动生成子订单；两个及以上方向保存后自动补齐对应子订单，已有子订单不会覆盖。',exact=True)).to_be_visible()
            page.screenshot(path=str(out/'automatic-direction-form.png'),full_page=True)
            editor.get_by_role('button',name='保存',exact=True).click()
            expect(editor).not_to_be_visible()
            assert len(saves)==1 and len(saves[0]['language_items'])==7
            expect(page.get_by_text('标注项目已更新，自动生成 6 个子订单',exact=True)).to_be_visible()
            expect(page.locator('.annotation-table .order-cell-secondary').first).to_contain_text(f'子订单 {len(children)}')
            page.locator('.annotation-table .order-no-link').first.click()
            expect(page.locator('.annotation-detail-popover:visible').get_by_text('方向对应完整',exact=True)).to_be_visible()
            page.wait_for_function("() => [...document.querySelectorAll('.annotation-detail-popover')].some(el => el.getClientRects().length && Number(getComputedStyle(el).opacity) > 0.99 && el.getBoundingClientRect().top >= 0)")
            page.screenshot(path=str(out/'automatic-direction-detail.png'),full_page=True)
            page.mouse.click(300,160)
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

            def open_panel(in_editor=False):
                if in_editor:
                    page.goto(BASE + f'/annotation-details?projectId={PID}&openEditor=1')
                    expect(editor).to_be_visible()
                    editor.get_by_role('tab', name='子订单', exact=True).click()
                    current_panel = editor.locator('.sub-order-panel')
                else:
                    page.goto(BASE + '/annotation-details')
                    page.locator('.annotation-index-cell .table-expand-button').first.click()
                    current_panel = page.locator('.sub-order-panel:visible').first
                expect(current_panel).to_be_visible()
                child_row = current_panel.locator('tr.el-table__row').first
                expect(child_row.locator('.child-order-no-link')).to_have_text(children[0]['order_no'])
                expect(current_panel.get_by_role('button', name='查看详情', exact=True)).to_have_count(0)
                expect(current_panel.get_by_role('button', name='编辑', exact=True)).to_have_count(0)
                return current_panel, child_row

            def more_menu(child_row):
                child_row.get_by_role('button', name='更多操作', exact=True).click()
                menu = page.locator('.el-dropdown-menu:visible')
                expect(menu).to_be_visible()
                menu.evaluate("async element => { await Promise.all(element.closest('.el-popper').getAnimations().map(animation => animation.finished.catch(() => {}))) }")
                return menu

            def stable_dialog(dialog):
                # 等待入场和拖动阴影动画结束，防止把动画位移误判为拖拽。
                dialog.evaluate("""async element => {
                    const animations = []
                    for (let current = element; current; current = current.parentElement) animations.push(...current.getAnimations())
                    await Promise.all(animations.map(animation => animation.finished.catch(() => {})))
                    await new Promise(requestAnimationFrame)
                }""")

            def dismiss_menu(child_row):
                child_row.get_by_role('button', name='更多操作', exact=True).click()
                expect(page.locator('.el-dropdown-menu:visible')).to_have_count(0)

            page.set_viewport_size({'width':1440,'height':1000})
            current_panel, child_row = open_panel()
            print('开始验收子订单详情、菜单、安排状态和嵌套弹窗', flush=True)
            child_row.locator('.child-order-no-link').click()
            detail_popover = page.locator('.annotation-detail-popover:visible')
            expect(detail_popover.locator('.el-descriptions').get_by_text(children[0]['order_no'], exact=True)).to_be_visible()
            assert children[0]['id'] in detail_reads
            page.mouse.click(300, 160)
            expect(detail_popover).not_to_be_visible()
            menu = more_menu(child_row)
            for label in ['编辑', '发起需求', '沟通', '试标/试采管理', '进入项目账号表', '加入安排']:
                expect(menu.get_by_role('menuitem', name=label, exact=True)).to_be_visible()
            page.screenshot(path=str(out / 'child-order-actions.png'), full_page=True)
            mock_state['hold_membership'] = True
            menu.get_by_role('menuitem', name='加入安排', exact=True).click()
            message_box = page.locator('.el-message-box:visible')
            message_box.locator('textarea').fill('优先安排当前子订单')
            message_box.get_by_role('button', name='加入安排', exact=True).click()
            menu = more_menu(child_row)
            expect(menu.get_by_role('menuitem', name='加入安排', exact=True)).to_have_attribute('aria-disabled', 'true')
            assert len(pending_memberships) == 1
            dismiss_menu(child_row)
            mock_state['hold_membership'] = False
            finish_membership(*pending_memberships.pop())
            expect(page.get_by_text('已加入项目安排', exact=True)).to_be_visible()
            assert membership_requests[-1]['project_id'] == children[0]['id']
            assert membership_requests[-1]['payload']['membership_note'] == '优先安排当前子订单'
            menu = more_menu(child_row)
            expect(menu.get_by_role('menuitem', name='加入安排', exact=True)).to_have_count(0)
            expect(menu.get_by_role('menuitem', name='安排', exact=True)).to_be_visible()
            menu.get_by_role('menuitem', name='移出安排', exact=True).click()
            message_box.get_by_role('button', name='移出安排', exact=True).click()
            expect(page.get_by_text('已移出项目安排', exact=True)).to_be_visible()
            mock_state['fail_membership'] = True
            more_menu(child_row).get_by_role('menuitem', name='加入安排', exact=True).click()
            message_box.locator('textarea').fill('模拟失败')
            message_box.get_by_role('button', name='加入安排', exact=True).click()
            expect(page.get_by_text('模拟安排更新失败', exact=True)).to_be_visible()
            mock_state['fail_membership'] = False
            menu = more_menu(child_row)
            expect(menu.get_by_role('menuitem', name='加入安排', exact=True)).not_to_have_attribute('aria-disabled', 'true')
            dismiss_menu(child_row)

            # 母订单编辑窗口中的菜单和详情必须位于遮罩上方；安排窗口保留父窗口。
            children[0]['arrangement_included'] = True
            page.set_viewport_size({'width':1440,'height':1000})
            current_panel, child_row = open_panel(True)
            child_row.locator('.child-order-no-link').click()
            expect(detail_popover.locator('.el-descriptions').get_by_text(children[0]['order_no'], exact=True)).to_be_visible()
            editor.get_by_role('tab', name='子订单', exact=True).click()
            menu = more_menu(child_row)
            menu.get_by_role('menuitem', name='安排', exact=True).click()
            arrangement = page.locator('.annotation-arrangement-quick-dialog:visible')
            expect(arrangement).to_be_visible()
            expect(arrangement.locator('.quick-dialog-heading')).to_contain_text(children[0]['order_no'])
            expect(arrangement.locator('.quick-task-content textarea')).to_have_value('子订单安排验收')
            stable_dialog(arrangement)
            assert context_project_ids[-1] == children[0]['id']
            expect(editor).to_be_visible()
            before = arrangement.bounding_box()
            handle = arrangement.locator('.dialog-field-search-header__title').bounding_box()
            drag_x, drag_y = handle['x']+handle['width']/2, handle['y']+handle['height']/2
            page.mouse.move(drag_x, drag_y)
            page.mouse.down(); page.mouse.move(drag_x+75, drag_y+23, steps=6); page.mouse.up()
            stable_dialog(arrangement)
            assert abs(arrangement.bounding_box()['x'] - before['x']) > 20
            handle = arrangement.locator('.dialog-field-search-header__title').bounding_box()
            page.mouse.move(handle['x']+handle['width']/2, handle['y']+handle['height']/2)
            page.mouse.down(); page.mouse.move(3000, 2000, steps=8); page.mouse.up()
            stable_dialog(arrangement)
            bounded = arrangement.bounding_box()
            assert bounded['x'] >= -1 and bounded['y'] >= -1 and bounded['x']+bounded['width'] <= 1441 and bounded['y']+bounded['height'] <= 1001
            page.screenshot(path=str(out / 'child-order-nested-arrangement.png'), full_page=True)
            arrangement.locator('.el-dialog__headerbtn').click()
            expect(arrangement).not_to_be_visible()
            more_menu(child_row).get_by_role('menuitem', name='安排', exact=True).click()
            expect(arrangement).to_be_visible()
            stable_dialog(arrangement)
            assert abs(arrangement.bounding_box()['x'] - before['x']) < 3
            arrangement.locator('.quick-task-content textarea').focus()
            expect(arrangement.locator('.quick-task-content textarea')).to_be_focused()
            arrangement.locator('.el-dialog__headerbtn').click()
            expect(arrangement).not_to_be_visible()
            editor.get_by_role('button', name='取消', exact=True).click()
            expect(editor).not_to_be_visible()

            # 每个跳转均核对当前子订单，而非母订单；编辑页签中的跳转关闭母订单窗口。
            for in_editor in [False, True]:
                for label, section in [('发起需求', 'request'), ('试标/试采管理', 'trials'), ('进入项目账号表', 'accounts'), ('编辑', 'edit'), ('沟通', 'chat')]:
                    current_panel, child_row = open_panel(in_editor)
                    more_menu(child_row).get_by_role('menuitem', name=label, exact=True).click()
                    if section == 'request':
                        expect(page).to_have_url(re.compile(r'/resource-requests\?.*sourceProjectId=' + children[0]['id']))
                    elif section == 'edit':
                        expect(page).to_have_url(re.compile(r'/annotation-child-orders\?.*projectId=' + children[0]['id']))
                        expect(editor).to_be_visible()
                        expect(editor.locator('.el-dialog__header')).to_contain_text(children[0]['order_no'])
                    elif section == 'chat':
                        expect(page.locator('.project-chat-window__subtitle').filter(has_text=children[0]['order_no'])).to_be_visible()
                    else:
                        expect(page).to_have_url(re.compile(r'/annotation-details\?.*section=' + section + r'.*projectId=' + children[0]['id']))
                    if in_editor and section != 'edit':
                        expect(editor).not_to_be_visible()

            # 已发需求的子订单沿用主列表文案；普通只读账号只保留可读操作。
            current_panel, child_row = open_panel()
            second_child_row = current_panel.locator('tr.el-table__row').nth(1)
            expect(more_menu(second_child_row).get_by_role('menuitem', name='需求已发送', exact=True)).to_be_visible()
            dismiss_menu(second_child_row)
            page.goto(BASE + '/annotation-child-orders')
            expect(page.locator('.annotation-table .order-no-link').first).to_have_text(children[0]['order_no'])
            expect(page.get_by_role('button', name='查看详情', exact=True)).to_have_count(0)
            page.get_by_role('button', name='字段设置', exact=True).click()
            expect(settings.get_by_role('checkbox', name='订单号', exact=True)).to_have_count(0)
            page.mouse.click(300, 160)
            page.locator('.annotation-table .order-no-link').first.click()
            expect(detail_popover.locator('.el-descriptions').get_by_text(children[0]['order_no'], exact=True)).to_be_visible()
            session.update(username='qa-readonly', roles=['项目助理'], permissions=['projects:read'])
            current_panel, child_row = open_panel()
            expect(child_row.get_by_role('button', name='编辑', exact=True)).to_have_count(0)
            menu = more_menu(child_row)
            expect(menu.get_by_role('menuitem', name='编辑', exact=True)).to_have_count(0)
            expect(menu.get_by_role('menuitem')).to_have_count(2)
            expect(menu.get_by_role('menuitem', name='沟通', exact=True)).to_be_visible()
            expect(menu.get_by_role('menuitem', name='试标/试采管理', exact=True)).to_be_visible()
            dismiss_menu(child_row)
            page.set_viewport_size({'width':600, 'height':740})
            child_row.locator('.child-order-no-link').click()
            expect(detail_popover.locator('.el-descriptions').get_by_text(children[0]['order_no'], exact=True)).to_be_visible()
            detail_popover.evaluate("async element => { await Promise.all(element.getAnimations().map(animation => animation.finished.catch(() => {}))) }")
            small_box = detail_popover.bounding_box()
            page.screenshot(path=str(out / 'child-order-detail-small.png'), full_page=True)
            assert 0 <= small_box['x'] and small_box['x']+small_box['width'] <= 601 and small_box['width'] <= 569, small_box
            content = detail_popover.locator('.annotation-project-detail__content')
            content.evaluate('(element) => element.scrollTop=element.scrollHeight')
            assert content.evaluate('(element) => element.scrollTop') > 0
            page.screenshot(path=str(out / 'child-order-detail-small.png'), full_page=True)
            page.set_viewport_size({'width':1440, 'height':1000})
            session.update(username='qa', roles=['admin'], permissions=['projects:read','projects:write','projects:order_no:write'])
            parent['child_count'] = 0
            page.goto(BASE + '/annotation-details')
            expect(page.locator('.annotation-table .order-no-link')).to_have_text(parent['order_no'])
            expect(page.locator('.annotation-index-cell .table-expand-button')).to_have_count(0)
            assert not errors, errors
            (out/'result.json').write_text(json.dumps(dict(passed=True,list_row_height=list_row_height,language_count=7,layout_viewports=[1920,1440,1024,768],column_settings_verified=True,child_actions_verified=True,readonly_verified=True,membership_requests=membership_requests,batch_rows=2,scopes=sorted(set(scopes)),errors=errors),ensure_ascii=False,indent=2),encoding='utf-8')
            browser.close()
            print('UI 验收通过：订单号详情入口、固定订单号及字段配置隔离、子订单菜单与正确跳转、安排状态及失败保护、只读权限、删除模式、嵌套拖拽与复位、小屏详情滚动、母子订单原有流程')
    finally:
        process.terminate(); process.wait(timeout=10); log.close()


if __name__=='__main__': run()
