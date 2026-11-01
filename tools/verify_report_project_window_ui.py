"""工作报告“进入项目”弹出复用表单，保留未保存报告；所有接口模拟。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode()
    dep = lambda name: re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)', compiled).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {createApp,h,ref} from VUE;
    import {createRouter,createWebHistory,RouterView} from ROUTER;
    import Link from '/src/views/schedule/components/ReportItemLink.vue';
    import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
    const row={task_name:'报告原任务',display_metadata:{order_no:'TP-WINDOW-TEST',project_id:'project1',selected_project_type:'笔译项目'}};
    const Report={setup(){const draft=ref('');return()=>h('main',[h('h1','工作报告'),h('textarea',{id:'report-draft',value:draft.value,onInput:e=>draft.value=e.target.value}),h(Link,{row,kind:'project',text:'TP-WINDOW-TEST'})])}};
    const router=createRouter({history:createWebHistory(),routes:[{path:'/report-project-window-test',component:Report}]});
    const app=createApp({render:()=>h(RouterView)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(router);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    errors = []; requests = []
    project = {'id':'project1','order_no':'TP-WINDOW-TEST','project_name':'完整项目.docx','source_file_name':'完整项目.docx','project_status':'confirmed','sub_orders':[]}

    def api(route):
        path = urlparse(route.request.url).path; requests.append(path)
        if path == '/api/projects/translation/project1': result = project
        elif path.endswith('/short-notes'): result = {'items':[],'total':0}
        elif '/word-count-matrices/' in path: result = {'company':{},'customer':{},'translators':[]}
        else: result = []
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge',headless=True)
        context = browser.new_context(viewport={'width':1600,'height':1000},service_workers='block')
        context.add_init_script("if(!localStorage.getItem('user_roles')){localStorage.setItem('user_id','window-qa');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write','project_files:read']))}")
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/report-project-window-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page = context.new_page(); page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/report-project-window-test')
        page.locator('#report-draft').fill('尚未保存的报告内容')
        for index in range(2):
            page.get_by_role('button',name='查看项目：TP-WINDOW-TEST',exact=True).click()
            page.locator('.report-item-detail-popover:visible').get_by_role('button',name='进入项目',exact=True).click()
            dialog = page.locator('.project-editor-dialog:visible')
            expect(dialog).to_contain_text('项目详情')
            expect(dialog.locator('[data-field-key="sourceFileName"] input')).to_have_value('完整项目.docx')
            for tab in ['基础信息','进度跟踪','子订单','项目文件']:
                dialog.get_by_role('tab',name=tab,exact=True).click()
                expect(dialog.get_by_role('button',name='保存',exact=True)).to_be_visible()
            expect(dialog.get_by_role('button',name='简单需求',exact=True)).to_be_visible()
            assert page.url == BASE+'/report-project-window-test'
            assert '/api/projects/translation/page' not in requests
            box=dialog.bounding_box()
            if index==0:
                initial=(box['x'],box['y'])
                page.mouse.move(box['x']+350,box['y']+16);page.mouse.down();page.mouse.move(box['x']+470,box['y']+66,steps=10);page.mouse.up()
                moved=dialog.bounding_box();assert moved['x']>box['x']+20
                page.mouse.move(moved['x']+350,moved['y']+16);page.mouse.down();page.mouse.move(5000,5000,steps=10);page.mouse.up()
                limited=dialog.bounding_box();assert limited['x']>=0 and limited['y']>=0 and limited['x']+limited['width']<=1601 and limited['y']+limited['height']<=1001
            else:
                assert abs(box['x']-initial[0])<2 and abs(box['y']-initial[1])<2
            dialog.get_by_role('button',name='取消',exact=True).click()
            expect(page.locator('.translation-editor-only')).to_have_count(0)
            expect(page.locator('#report-draft')).to_have_value('尚未保存的报告内容')
        page.evaluate("localStorage.setItem('user_roles','[]');localStorage.setItem('user_permissions',JSON.stringify(['projects:read','project_files:read']))")
        page.reload()
        page.get_by_role('button',name='查看项目：TP-WINDOW-TEST',exact=True).click()
        page.locator('.report-item-detail-popover:visible').get_by_role('button',name='进入项目',exact=True).click()
        dialog=page.locator('.project-editor-dialog:visible')
        expect(dialog.locator('[data-field-key="sourceFileName"] input')).to_be_disabled()
        expect(dialog.get_by_role('button',name='保存',exact=True)).to_have_count(0)
        page.screenshot(path='scratch/report-project-window.png')
        assert not errors, errors
        browser.close()
    print('report enter-project: full modal, four tabs, report preserved, no navigation/list query, drag/bounds/reset and readonly PASS')


if __name__=='__main__':
    run()
