"""新增项目始终空白、不提示草稿及母订单文件名例外；全部接口模拟。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=20).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Workspace from '/src/views/project/ProjectWorkspace.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';const app=createApp({render:()=>h(RouterView)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/new-project-draft-test',component:Workspace,props:{module:'translation'}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/projects/translation/page':result={'items':[],'total':0}
        elif path.endswith('/next-order-no'):result={'order_no':'TP-261102-999'}
        elif path=='/api/editor-drafts':result={'payload':None,'revision':0}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1500,'height':1000})
        context.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write']));localStorage.setItem('form-drafts:translation-project:qa',JSON.stringify({create:{savedAt:new Date().toISOString(),form:{id:'old-project',orderNo:'TP-OLD-001',sourceFileName:'旧草稿.docx',clientShortName:'旧客户',customerReceptionTime:'2026-10-29 11:15',customerDeadlineTime:'2026-10-30 11:00',wordCountMatrix:{company:{documents:3}}}}}))")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/new-project-draft-test',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(18000);errors=[];page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/new-project-draft-test')
        page.get_by_role('button',name='新增项目',exact=True).click();dialog=page.locator('.project-editor-dialog:visible')
        expect(dialog.get_by_role('button',name='恢复草稿',exact=True)).to_have_count(0)
        name=dialog.locator('[data-field-key="sourceFileName"] input.el-input__inner')
        expect(name).to_have_value('');expect(dialog.locator('[data-field-key="clientShortName"] input.el-input__inner')).to_have_value('')
        name.fill('本次未保存.docx')
        parent_mode=dialog.locator('.el-checkbox').filter(has_text='同时创建子订单（母订单名称可不带扩展名）');expect(parent_mode).to_be_visible()
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='新增项目',exact=True).click();expect(name).to_have_value('');expect(dialog.locator('[data-field-key="clientShortName"] input.el-input__inner')).to_have_value('');expect(dialog.get_by_role('button',name='恢复草稿',exact=True)).to_have_count(0)
        parent_mode.click();name.fill('母订单名称')
        children=dialog.locator('.el-form-item').filter(has_text='子订单文件名称').locator('textarea');children.fill('文件甲.docx\n文件乙.pdf');children.press('Tab')
        expect(dialog.locator('[data-field-key="sourceFileName"] .el-form-item__error')).to_have_count(0)
        assert not errors,errors;browser.close()
    print('new form always blank, no draft prompt, close/reopen clears values and parent naming UI PASS')


if __name__=='__main__':run()
