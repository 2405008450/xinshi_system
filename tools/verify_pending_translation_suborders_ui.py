"""未保存母单的子订单管理：真实组件，接口全部模拟。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive} from VUE;
import Pending from '/src/views/project/translation/components/PendingSubOrderManager.vue';
import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const form=reactive({orderNo:'TP-261108-999',sourceFileName:'母项目',initialSubOrderNamesText:'a.pdf\\nb.docx',languagePair:'中文→英语；中文→法语',serviceContent:'翻译',customerRequirementProfessional:'母专业要求',customerRequirementSpecial:'母特殊要求',remarks:'母说明',projectStatus:'confirmed',fileTypeSecondary:'合同',pendingSubOrderDetails:{}});
const state=reactive({visible:false});window.testOpen=()=>state.visible=true;window.testForm=form;
const app=createApp({render:()=>h(Pending,{modelValue:state.visible,form,'onUpdate:modelValue':v=>state.visible=v,onConfirmed:()=>window.result=JSON.parse(JSON.stringify(form.pendingSubOrderDetails))})});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1500,'height':950})
        page.route(BASE+'/pending-suborder-test',lambda route:route.fulfill(content_type='text/html',body=html))
        writes=[]
        def api(route):
            if route.request.method in ('POST','PUT','PATCH','DELETE'):writes.append(route.request.url)
            route.fulfill(content_type='application/json',body='[]')
        page.route(re.compile(r'^http://localhost:3000/api/'),api)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/pending-suborder-test');page.wait_for_function('typeof window.testOpen === "function"');page.evaluate('window.testOpen()')
        dialog=page.locator('.pending-suborder-manager:visible');expect(dialog).to_be_visible()
        grid=dialog.locator('.suborder-statistics-grid')
        expect(grid.locator('tbody tr')).to_have_count(6)
        dialog.get_by_role('button',name='汇总至母订单并确认',exact=True).click()
        expect(dialog).to_be_visible()
        for index,value in [(1,'10'),(2,'20'),(4,'30'),(5,'40')]:grid.locator(f'input[data-row="{index}"][data-col="0"]').fill(value)
        dialog.get_by_role('button',name='返回母订单',exact=True).click();expect(dialog).not_to_be_visible()
        page.evaluate('window.testOpen()');expect(dialog).to_be_visible()
        expect(grid.locator('input[data-row="1"][data-col="0"]')).to_have_value('10')
        dialog.get_by_role('button',name='汇总至母订单并确认',exact=True).click()
        expect(dialog).not_to_be_visible()
        result=page.evaluate('window.result')
        assert result['001.001']['wordCountMatrix']['company']['words']==10,result
        assert result['002.002']['wordCountMatrix']['company']['words']==40,result
        assert page.evaluate('window.testForm.wordCountMatrix.company.words')==100
        assert page.evaluate('window.testForm.wordCountMatrixSource')=='suborder_aggregate'
        assert not writes,writes
        assert not errors,errors
        browser.close()
    print('pending multi-file / multi-direction tree / mandatory leaf statistics / local draft reopen / confirmed details / no server writes PASS')


if __name__=='__main__':run()
