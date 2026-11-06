"""客户管理真实 Vue 页面交互回归，所有业务接口模拟，不写业务数据库。"""
import json
import re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'

def run():
    compiled = urlopen(BASE + '/src/views/project/ProjectWorkspace.vue', timeout=20).read().decode()
    dep = lambda name: re.search(r'from ["\']([^"\']*/' + name + r'\.js[^"\']*)', compiled).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp} from VUE;import Clients from '/src/views/client/Clients.vue';import AppForm from '/src/components/common/AppForm.vue';createApp(Clients).component('AppForm',AppForm).mount('#app');</script>'''.replace('from VUE', 'from ' + json.dumps(dep('vue')))
    client = dict(id='c1', client_name='回归客户', client_short_name='回归', client_code='CL-TEST', client_manager='负责人', client_status='active', cooperation_info='原合作信息', sub_clients=[])
    client.update(operator_name='钟楚翘', operator_source='consultation_capture_backfill', operator_consultation_code='EQ-261105-001')
    writes, errors, project_requests = [], [], []
    project_groups = [dict(module=module, label=label, items=[dict(id=module, order_no=module+'-001', project_name=label+'样例', project_status='in_progress')]) for module, label in [('translation','笔译项目'), ('annotation','标注项目')]]
    project_groups[0]['items'] = [dict(id=f'p-{i}', order_no=f'TP-{i:03}', project_name=f'笔译项目样例{i}', project_status='in_progress') for i in range(1, 26)]
    def api(route):
        path = urlparse(route.request.url).path
        if path == '/api/clients/page': result = {'items':[client], 'total':1}
        elif path == '/api/clients/c1/projects':
            project_requests.append(path); result = {'groups':project_groups}
        elif path == '/api/clients/c1':
            if route.request.method == 'PUT':
                writes.append(route.request.post_data_json); client.update(writes[-1])
            result = client
        elif path == '/api/clients/':
            writes.append(route.request.post_data_json); result = {**client, **writes[-1]}
        elif 'rate-differences' in path: result = {'items':[], 'total':0, 'ready':True}
        elif 'translation-customer-finance/page' in path: result = {'items':[], 'total':0, 'client_subtotals':[]}
        elif '/drafts/' in path: result = {}
        else: result = {'items':[], 'total':0, 'ready':True, 'version':'1'}
        route.fulfill(content_type='application/json', body=json.dumps(result, ensure_ascii=False))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        context = browser.new_context(viewport={'width':1440,'height':900}, service_workers='block')
        context.add_init_script("localStorage.setItem('user_id','client-ui-test');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['projects:read','clients:read','clients:write']))")
        context.route(re.compile(r'^http://localhost:3000/api/'), api)
        context.route(BASE + '/client-management-ui-test', lambda r:r.fulfill(content_type='text/html', body=html))
        page = context.new_page(); page.set_default_timeout(12000)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(BASE + '/client-management-ui-test')
        expect(page.locator('.card-header')).to_contain_text('客户管理')
        page.get_by_role('button', name='编辑', exact=True).click()
        dialog = page.locator('.client-form-dialog:visible')
        for name in ['基本信息','财务信息','合作信息','合作项目']:
            expect(dialog.get_by_role('tab', name=name, exact=True)).to_be_visible()
        expect(dialog.get_by_role('tab', name='基本信息', exact=True)).to_have_attribute('aria-selected','true')
        operator = dialog.locator('[data-dialog-field-search-label="操作人"]')
        expect(operator.locator('input')).to_have_value('钟楚翘')
        expect(operator.locator('input')).to_have_attribute('readonly', '')
        expect(operator).to_contain_text('EQ-261105-001')
        dialog.get_by_role('tab', name='合作信息', exact=True).click()
        expect(dialog.get_by_placeholder('请输入客户合作信息')).to_have_value('原合作信息')
        dialog.get_by_placeholder('请输入客户合作信息').fill('新的合作信息\n第二行')
        # 字段搜索自动展开非当前标签页。
        search = dialog.get_by_placeholder('搜索客户字段，如客户负责人')
        search.fill('负责人')
        page.locator('.el-autocomplete-suggestion:visible li').filter(has_text='客户负责人').first.click()
        expect(dialog.get_by_role('tab', name='基本信息', exact=True)).to_have_attribute('aria-selected','true')
        # 非基本信息页提交时，必填校验仍定位基本页并聚焦。
        manager = dialog.locator('.el-form-item').filter(has=page.locator('label').filter(has_text=re.compile('^客户负责人$'))).locator('input')
        manager.fill('')
        dialog.get_by_role('tab', name='合作信息', exact=True).click()
        dialog.get_by_role('button', name='确定', exact=True).click()
        expect(dialog.get_by_role('tab', name='基本信息', exact=True)).to_have_attribute('aria-selected','true')
        expect(manager).to_be_focused(); manager.fill('负责人')
        dialog.get_by_role('tab', name='合作项目', exact=True).click()
        expect(dialog.locator('.project-group')).to_have_count(2)
        expect(dialog.locator('.cooperation-projects')).to_contain_text('笔译项目样例')
        expect(dialog.locator('.cooperation-projects')).not_to_contain_text('招聘项目')
        translation = dialog.locator('.project-group').first
        annotation = dialog.locator('.project-group').nth(1)
        expect(translation.locator('.el-table__body-wrapper tbody tr')).to_have_count(10)
        translation.locator('.el-pager li').filter(has_text=re.compile('^2$')).click()
        expect(translation.locator('.el-table__body-wrapper tbody tr').first).to_contain_text('TP-011')
        expect(annotation.locator('.el-table__body-wrapper tbody tr')).to_have_count(1)
        translation.locator('.el-pagination__sizes .el-select').click()
        page.get_by_role('option', name=re.compile('^20')).click()
        expect(translation.locator('.el-table__body-wrapper tbody tr')).to_have_count(20)
        expect(translation.locator('.el-table__body-wrapper tbody tr').first).to_contain_text('TP-001')
        dialog.get_by_role('tab', name='财务信息', exact=True).click()
        expect(dialog.get_by_role('tab', name='笔译', exact=True)).to_be_visible()
        expect(dialog.locator('form form')).to_have_count(0)
        expect(dialog.get_by_text('财务管理（客户）', exact=True)).to_have_count(0)
        # 长表单仅正文滚动，底部操作始终可见。
        dialog.get_by_role('tab', name='基本信息', exact=True).click()
        dialog.locator('.el-dialog__body').evaluate('(el)=>el.scrollTop=el.scrollHeight')
        expect(dialog.get_by_role('button', name='确定', exact=True)).to_be_in_viewport()
        # 拖动、边界、关闭与再次打开复位。
        before = dialog.bounding_box(); header = dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+45,header['y']+25); page.mouse.down(); page.mouse.move(header['x']+125,header['y']+95,steps=6); page.mouse.up()
        after = dialog.bounding_box(); assert abs(after['x']-before['x'])>30
        page.mouse.move(after['x']+45,after['y']+25); page.mouse.down(); page.mouse.move(1800,1100,steps=6); page.mouse.up()
        bounded = dialog.bounding_box(); assert bounded['x'] >= -1 and bounded['x']+bounded['width'] <= 1441
        dialog.get_by_role('button', name='确定', exact=True).click()
        expect(dialog).to_have_count(0)
        assert writes[-1]['cooperation_info'] == '新的合作信息\n第二行'
        assert not any(key.startswith('operator_') for key in writes[-1])
        page.get_by_role('button', name='编辑', exact=True).click()
        expect(dialog.get_by_role('tab', name='基本信息', exact=True)).to_have_attribute('aria-selected','true')
        page.wait_for_timeout(400)
        reopened = dialog.bounding_box(); assert abs(reopened['x']-before['x']) < 2 and abs(reopened['y']-before['y']) < 2
        dialog.get_by_role('button', name='关闭窗口', exact=True).click(); expect(dialog).to_have_count(0)
        page.get_by_role('button', name='新增客户', exact=True).click()
        expect(dialog.locator('[data-dialog-field-search-label="操作人"] input')).to_have_attribute('placeholder', '保存后自动生成')
        expect(dialog.get_by_role('tab', name='基本信息', exact=True)).to_have_attribute('aria-selected','true')
        dialog.get_by_role('tab', name='合作信息', exact=True).click()
        expect(dialog.get_by_placeholder('请输入客户合作信息')).to_have_value('')
        dialog.get_by_role('tab', name='合作项目', exact=True).click()
        expect(dialog).to_contain_text('请先保存客户')
        page.set_viewport_size({'width':540,'height':740})
        expect(dialog.get_by_role('button', name='确定', exact=True)).to_be_in_viewport()
        bounds = dialog.bounding_box(); assert bounds['width'] <= 508.5
        assert not errors, errors
        browser.close()
    print('PASS pagination 10/20, independent groups, removed finance region, tabs, field search, validation focus, finance, project groups, save, reset, drag, viewport bounds, fixed footer, mobile')

if __name__ == '__main__': run()
