"""客户姓名录入回归；全部业务接口拦截，不读取或写入真实客户。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE + '/src/views/project/ProjectWorkspace.vue', timeout=30).read().decode()
    dep = lambda name: re.search(r'from ["\']([^"\']*/' + name + r'\.js[^"\']*)', compiled).group(1)
    cases = [
        ('project/translation/ProjectDetails', '新增项目', 'clientName', 'clientShortName'),
        ('project/interpretation/InterpretationProjectDetails', '新增口译项目', 'clientFullName', 'clientShortName'),
        ('project/AnnotationProjects', '新增标注项目', 'clientFullName', 'clientShortName'),
        ('project/RecruitmentProjects', '新增招聘项目', 'clientName', 'clientShortName'),
        ('client/Clients', '新增客户', 'client_name', 'client_short_name'),
        ('client/Consultations', '新增咨询', 'client_name', 'client_short_name'),
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        for path, button, full_prop, short_prop in cases:
            context = browser.new_context(viewport={'width': 1500, 'height': 1000})
            context.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\",\"clients:read\",\"clients:write\",\"consultations:read\",\"consultations:write\"]')")
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            def api(route):
                endpoint = urlparse(route.request.url).path
                result = {'items': [], 'total': 0} if endpoint.endswith('/page') else []
                if endpoint.endswith('/next-order-no'): result = {'order_no': 'TP-261107-999'}
                if endpoint.endswith('/count'): result = 0
                if endpoint.endswith('/editor-drafts'): result = {'payload': None, 'revision': 0}
                route.fulfill(content_type='application/json', body=json.dumps(result))
            page.route(re.compile(r'^http://localhost:3000/api/'), api)
            html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;
import Editor from EDITOR;import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const app=createApp({render:()=>h(RouterView)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/client-name-test',component:Editor}]}));app.mount('#app');</script>'''
            html = html.replace('from VUE', 'from '+json.dumps(dep('vue'))).replace('from ROUTER', 'from '+json.dumps(dep('vue-router'))).replace('from EDITOR', 'from '+json.dumps('/src/views/'+path+'.vue'))
            page.route('**/client-name-test', lambda route: route.fulfill(content_type='text/html', body=html))
            page.goto(BASE+'/client-name-test')
            try: page.get_by_role('button', name=button, exact=True).click(timeout=15000)
            except Exception:
                print(path, errors, page.locator('body').inner_text()[:1500], flush=True)
                raise
            dialog = page.locator('.el-dialog:visible').last
            full = dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=re.compile('^客户全称$'))).filter(visible=True).first
            expect(full).to_have_class(re.compile('is-required'))
            field = full.locator('input').first
            field.fill('   ');field.press('Tab')
            expect(full.locator('.el-form-item__error')).to_contain_text('客户全称')
            field.fill('广州信实翻译服务有限公司');field.press('Tab')
            expect(full.locator('.el-form-item__error')).to_have_count(0)
            short = dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=re.compile('^客户简称$'))).filter(visible=True).first
            expect(short.locator('.client-name-guidance')).to_contain_text('行政区划＋字号＋行业表述')
            expect(short.locator('.client-name-guidance')).to_contain_text('广州信实翻译服务有限公司 → 广州信实翻译')
            short.locator('input').first.fill('广州信实翻译');short.locator('input').first.press('Tab')
            expect(field).to_have_value('广州信实翻译服务有限公司')
            assert not errors, (path, errors)
            print(path, 'PASS')
            context.close()
        browser.close()


if __name__ == '__main__': run()
