"""四类实际表单默认值及公共原因校验/记录小窗；所有接口均隔离模拟。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE + '/src/views/project/ProjectWorkspace.vue').read().decode()
    dependency = lambda name: re.search(r'from ["\']([^"\']*/' + name + r'\.js[^"\']*)', compiled).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {createApp,h,reactive,ref} from VUE;
    import {createRouter,createWebHistory,RouterView} from ROUTER;
    import Translation from '/src/views/project/translation/ProjectDetails.vue';
    import Interpretation from '/src/views/project/interpretation/InterpretationProjectDetails.vue';
    import Recruitment from '/src/views/project/RecruitmentProjects.vue';
    import Annotation from '/src/views/project/AnnotationProjects.vue';
    import AppForm from '/src/components/common/AppForm.vue';
    import Dialog from '/src/components/common/DraggableFormDialog.vue';
    import Field from '/src/components/common/ProjectClientManagerField.vue';
    const Harness={setup(){const form=reactive({clientManagerId:'owner',clientManagerChangeReason:''}),control=ref(),id=ref('');return()=>h(AppForm,{ref:control,model:form},()=>[h(Field,{modelValue:form.clientManagerId,'onUpdate:modelValue':v=>form.clientManagerId=v,reason:form.clientManagerChangeReason,'onUpdate:reason':v=>form.clientManagerChangeReason=v,baselineId:'owner',projectType:'translation',projectId:id.value}),h('button',{onClick:async()=>{if(await control.value.validate().catch(()=>false)){window.saved={...form};id.value='project1'}}},'测试保存')])}};
    const router=createRouter({history:createWebHistory(),routes:Object.entries({translation:Translation,interpretation:Interpretation,recruitment:Recruitment,annotation:Annotation,harness:Harness}).map(([name,component])=>({path:'/client-manager-test/'+name,component}))});
    const app=createApp({render:()=>h(RouterView)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(router);app.mount('#app');</script>'''.replace('from VUE', 'from ' + json.dumps(dependency('vue'))).replace('from ROUTER', 'from ' + json.dumps(dependency('vue-router')))
    errors = []

    def api(route):
        path = urlparse(route.request.url).path
        if path == '/api/users/options':
            result = [{'id': 'owner', 'display_name': '填写人'}, {'id': 'other', 'display_name': '接任经理'}]
        elif path == '/api/users/':
            result = [{'id': 'owner', 'full_name': '填写人', 'is_active': True}, {'id': 'other', 'full_name': '接任经理', 'is_active': True}]
        elif path.endswith('/manager-options'):
            result = [{'id': 'owner', 'full_name': '填写人', 'is_active': True}, {'id': 'other', 'full_name': '接任经理', 'is_active': True}]
        elif path.endswith('/history'):
            result = {'total': 1, 'items': [{'id': 'event1', 'previous_manager_name': '填写人', 'new_manager_name': '接任经理', 'actor_name': '填写人', 'reason': '客户交接', 'changed_at': '2026-10-29T10:00:00+08:00'}]}
        elif path.endswith('/page'):
            result = {'total': 0, 'items': []}
        elif path.endswith('/openapi.json'):
            result = {'paths': {}, 'components': {'schemas': {}}}
        elif 'next-order-no' in path:
            result = {'order_no': 'TP-TEST-001'}
        else:
            result = []
        route.fulfill(content_type='application/json', body=json.dumps(result, ensure_ascii=False))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 1000}, service_workers='block')
        context.add_init_script("localStorage.setItem('user_id','owner');localStorage.setItem('user_full_name','填写人');localStorage.setItem('user_name','owner');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write']));")
        context.route(re.compile(r'^http://localhost:3000/api/'), api)
        context.route(re.compile(r'^http://localhost:3000/client-manager-test/'), lambda route: route.fulfill(content_type='text/html', body=html))
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        for kind, label in [('translation', '新增项目'), ('interpretation', '新增口译项目'), ('recruitment', '新增招聘项目'), ('annotation', '新增标注项目')]:
            page.goto(BASE + '/client-manager-test/' + kind)
            page.get_by_role('button', name=label, exact=True).click()
            dialog = page.locator('.el-dialog:visible').first
            manager = dialog.locator('.el-form-item').filter(has=page.locator('label', has_text=re.compile('^客户经理$'))).first
            # 笔译客户页签按需显示；通过字段定位打开实际所在分区。
            if kind == 'translation' and not manager.is_visible():
                dialog.get_by_role('tab', name=re.compile('基础|客户')).first.click()
            expect(manager).to_contain_text('填写人', timeout=15000)
            print(kind + ': current writer selected')
        page.goto(BASE + '/client-manager-test/harness')
        page.locator('.el-select').click()
        page.get_by_role('option', name='接任经理', exact=True).click()
        page.get_by_role('button', name='测试保存').click()
        expect(page.get_by_text('请填写客户经理调整原因', exact=True)).to_be_visible()
        assert page.evaluate('window.saved === undefined')
        page.locator('textarea').fill('客户交接')
        page.get_by_role('button', name='测试保存').click()
        page.wait_for_function("window.saved?.clientManagerChangeReason === '客户交接'")
        page.get_by_role('button', name='查看调整记录').click()
        popup = page.locator('.project-manager-history:visible')
        expect(popup).to_contain_text('接任经理')
        expect(popup).to_contain_text('客户交接')
        expect(popup).to_contain_text('填写人')
        expect(popup).to_contain_text('2026/10/29')
        assert not errors, errors
        browser.close()
    print('client manager defaults, required reason and history: PASS')


if __name__ == '__main__':
    run()
