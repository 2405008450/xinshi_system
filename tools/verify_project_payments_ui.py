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
        controls=dialog.locator('.project-finance-controls')
        left=controls.locator('.project-finance-actions');right=controls.locator('.project-client-documents')
        assert left.bounding_box()['x']<right.bounding_box()['x']
        payment_button=left.get_by_role('button',name='付款情况',exact=True);payment_button.click()
        payment=page.locator('.project-payment-dialog:visible');expect(payment).to_be_visible()
        initial=payment.bounding_box();header=payment.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+220,header['y']+15);page.mouse.down();page.mouse.move(header['x']+320,header['y']+55);page.mouse.up()
        assert abs(payment.bounding_box()['x']-initial['x'])>10
        payment.get_by_role('button',name='关闭窗口',exact=True).click();expect(payment).not_to_be_visible()
        payment_button.click();expect(payment).to_be_visible();assert abs(payment.bounding_box()['x']-initial['x'])<2
        payment.get_by_role('button',name='新增付款明细',exact=True).click()
        for label,value in [('预定金额','100'),('实际金额','40')]:
            payment.locator('.project-payment-row .el-form-item').filter(has=page.locator('label',has_text=label)).get_by_role('spinbutton').fill(value)
        payment.locator('.project-payment-row .el-form-item').filter(has=page.locator('label',has_text='付款方式')).locator('input').fill('银行转账')
        expect(payment).to_contain_text('部分付款')
        payment.get_by_role('button',name='应用到项目',exact=True).click();expect(payment).not_to_be_visible()
        payment_button.click();expect(payment).to_contain_text('40.00')
        expect(payment.locator('.project-payment-row .el-form-item').filter(has=page.locator('label',has_text='付款方式')).locator('input')).to_have_value('银行转账')
        actual=payment.locator('.project-payment-row .el-form-item').filter(has=page.locator('label',has_text='实际金额')).get_by_role('spinbutton')
        actual.fill('50');payment.get_by_role('button',name='关闭窗口',exact=True).click()
        page.get_by_role('button',name='继续编辑',exact=True).click();expect(payment).to_be_visible()
        actual.fill('40')
        payment.get_by_role('button',name='取消',exact=True).click()
        page.set_viewport_size({'width':700,'height':900})
        assert controls.evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length===1")
        assert not errors,errors;browser.close()
    print('tidy two-column layout, payment popup, dragging/reset, draft persistence and narrow layout PASS')
if __name__=='__main__':run()
