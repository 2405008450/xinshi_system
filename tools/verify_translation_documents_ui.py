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
        context.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write','project_files:read','project_files:write']));localStorage.setItem('form-drafts:translation-project:qa',JSON.stringify({create:{savedAt:new Date().toISOString(),form:{id:'old-project',orderNo:'TP-OLD-001',sourceFileName:'旧草稿.docx',clientShortName:'旧客户',customerReceptionTime:'2026-10-29 11:15',customerDeadlineTime:'2026-10-30 11:00',wordCountMatrix:{company:{documents:3}}}}}))")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/new-project-draft-test',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(18000);errors=[];page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/new-project-draft-test')
        page.get_by_role('button',name='新增项目',exact=True).click();dialog=page.locator('.project-editor-dialog:visible')
        types=dialog.locator('.el-form-item').filter(has=page.locator('label',has_text='客户类型')).locator('.el-select')
        quotation=dialog.locator('[data-field-key="quotationRequired"]')
        statement=dialog.locator('[data-field-key="statementRequired"]')
        types.click();page.get_by_role('option',name='个人客户',exact=True).click()
        expect(quotation.get_by_role('checkbox')).not_to_be_checked();expect(statement.get_by_role('checkbox')).not_to_be_checked()
        types.click();page.get_by_role('option',name='企业客户',exact=True).click()
        expect(quotation.get_by_role('checkbox')).not_to_be_checked();expect(statement.get_by_role('checkbox')).to_be_checked()
        expect(page.locator('.customer-statement-dialog:visible')).to_have_count(0)
        quotation.locator('.el-checkbox').click()
        quote=page.locator('.customer-quotation-dialog:visible');expect(quote).to_be_visible()
        for label,value in [('数量','123.5'),('单价','0.25')]:
            quote.locator('.quotation-line .el-form-item').filter(has=page.locator('label',has_text=label)).get_by_role('spinbutton').fill(value)
        quote.locator('textarea').fill('测试报价条件')
        expect(quote).to_contain_text('30.88 CNY')
        quote.get_by_role('button',name='应用到项目',exact=True).click();expect(quote).not_to_be_visible()
        quotation.get_by_role('button',name='打开报价单',exact=True).click();expect(quote.locator('textarea')).to_have_value('测试报价条件')
        quote.get_by_role('button',name='取消',exact=True).click()
        statement.locator('.el-checkbox').click();statement.locator('.el-checkbox').click()
        window=page.locator('.customer-statement-dialog:visible');expect(window).to_be_visible()
        expect(window).to_contain_text('请先保存项目，再编排对账单')
        window.get_by_role('button',name='关闭',exact=True).click()
        assert not errors,errors
        browser.close()
    print('personal/business defaults, checkbox popups, quotation draft and shared statement window PASS')
if __name__=='__main__':run()
