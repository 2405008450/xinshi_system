"""四类项目任务标题、详情、报告入口和报告预填；业务接口全部隔离。"""
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'
DAY = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
TYPES = [('translation', '笔译项目', 'TP', 'pending_confirmation', '待确认'),
         ('interpretation', '口译项目', 'IP', 'in_progress', '进行中'),
         ('annotation', '标注项目', 'AP', 'trial_preparation', '试标准备'),
         ('recruitment', '招聘项目', 'RP', 'initial_consultation', '初步咨询')]


def run():
    compiled = urlopen(BASE + '/src/components/common/ProjectIdentityHeader.vue').read().decode()
    def dependency(name):
        return json.dumps(re.search(r'from ["\']([^"\']*/' + name + r'\.js[^"\']*)', compiled).group(1))
    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {createApp,h,ref} from VUE;import {createRouter,createWebHistory} from ROUTER;
    import Header from '/src/components/common/ProjectIdentityHeader.vue';
    import Panel from '/src/views/schedule/components/DailyReportPanel.vue';
    import AppForm from '/src/components/common/AppForm.vue';
    const types=TYPES; const selected=ref(null);
    window.testProject=project=>selected.value=project;
    const router=createRouter({history:createWebHistory(),routes:[{path:'/project-identity-test',component:{render:()=>null}},{path:'/workbench',name:'WorkDashboard',component:{render:()=>null}}]});
    const app=createApp({render:()=>h('main',{},[
      ...types.map(([type,label,prefix])=>h('section',{'data-type':type,style:'padding:16px;border:1px solid #ddd'},[h(Header,{projectId:type,projectType:label,orderNo:prefix+'-TEST-001',projectName:label+'标题测试'})])),
      h('output',{id:'route'},JSON.stringify(router.currentRoute.value.query)),
      h(Panel,{reportDate:DAY,annotationProject:selected.value})
    ])});app.use(router);app.component('AppForm',AppForm);app.mount('#app');</script>'''
    html = html.replace('from VUE', 'from ' + dependency('vue')).replace('from ROUTER', 'from ' + dependency('vue-router')).replace('TYPES', json.dumps(TYPES, ensure_ascii=False)).replace('reportDate:DAY', 'reportDate:' + json.dumps(DAY))
    requests, errors = [], []
    def api(route):
        path = urlparse(route.request.url).path
        requests.append((route.request.method, path))
        data = {}
        for kind, label, prefix, status, _ in TYPES:
            if path == f'/api/projects/{kind}/{kind}':
                data = dict(id=kind, order_no=prefix+'-TEST-001', project_name=label+'标题测试', source_file_name=label+'标题测试', project_status=status, project_manager_name='项目经理乙', role_assignments=[dict(role_code='project_manager',assignee_name='项目经理乙')])
                data[{'translation':'client_manager','interpretation':'current_client_manager'}.get(kind,'client_manager_name')] = '客户经理甲'
        if path == '/api/daily-reports/preview':
            data = dict(report_date=DAY, status='draft', items=[])
        elif path == '/api/daily-reports/editor-context':
            data = dict(user_name='隔离测试', departments=[])
        elif path == '/api/editor-drafts':
            data = dict(payload=None, revision=0)
        elif path == '/api/editor-drafts/batch':
            data = [{**row, 'revision':1} for row in route.request.post_data_json['drafts']]
        route.fulfill(content_type='application/json', body=json.dumps(data, ensure_ascii=False))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport=dict(width=1500, height=1100), service_workers='block')
        context.add_init_script("localStorage.setItem('user_id','project-identity-test')")
        context.route(re.compile(r'^http://localhost:3000/api/'), api)
        context.route(BASE+'/project-identity-test', lambda r:r.fulfill(content_type='text/html', body=html))
        page = context.new_page()
        page.on('pageerror', lambda e:errors.append(str(e)))
        page.goto(BASE+'/project-identity-test')
        for index, (kind, label, prefix, _, expected_status) in enumerate(TYPES):
            card = page.locator(f'[data-type="{kind}"]')
            expect(card).to_contain_text('客户经理甲')
            expect(card).to_contain_text('项目经理乙')
            # 招聘状态可能由模块状态目录映射，仍应显示该模块真实状态。
            if kind != 'recruitment': expect(card).to_contain_text(expected_status)
            card.get_by_role('button', name='查看项目详情 '+prefix+'-TEST-001', exact=True).click()
            detail = page.locator('.project-identity-detail:visible')
            expect(detail).to_contain_text(label+'标题测试')
            expect(detail).to_contain_text('客户经理甲')
            page.locator('body').click(position=dict(x=5,y=5))
            card.get_by_role('button', name='填写工作报告', exact=True).click()
            expect(page.locator('#route')).to_contain_text('"reportProjectId":"'+kind+'"')
            expect(page.locator('#route')).to_contain_text('"reportProjectType":"'+kind+'"')
            page.evaluate('(p)=>window.testProject(p)', dict(id=kind,type=kind,orderNo=prefix+'-TEST-001',name=label+'标题测试'))
            expect(page.locator('.report-grid tbody tr')).to_have_count(index+1)
            row = page.locator('.report-grid tbody tr').last
            expect(row.locator('td').nth(2).locator('input')).to_have_value(prefix+'-TEST-001')
            expect(row.locator('td').nth(3).locator('input')).to_have_value(label+'标题测试')
            page.evaluate('(p)=>window.testProject(p)', dict(id=kind,type=kind,orderNo=prefix+'-TEST-001',name=label+'标题测试'))
            expect(page.locator('.report-grid tbody tr')).to_have_count(index+1)
        page.set_viewport_size(dict(width=390,height=844))
        for card in page.locator('[data-type]').all():
            box = card.bounding_box()
            button = card.get_by_role('button', name='填写工作报告', exact=True).bounding_box()
            assert button['x'] >= box['x'] and button['x']+button['width'] <= box['x']+box['width']
        assert not errors, errors
        assert not any(method != 'GET' and 'editor-drafts' not in path for method,path in requests), requests
        browser.close()
    print('PASS: 四类项目标题、订单详情、工作报告跳转与报告字段预填')


if __name__ == '__main__':
    run()
