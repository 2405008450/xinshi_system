"""价格与付款弹窗单据位置、保存/取消和两个单据入口；业务接口全部模拟。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref,reactive} from VUE;import {createRouter,createWebHistory} from ROUTER;import Finance from '/src/views/project/translation/CustomerFinance.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const root=window.testRoot=reactive({id:'',orderNo:'TP-261107-999',projectName:'测试.docx',clientId:'c1',clientShortName:'广州测试',clientName:'广州测试有限公司',clientManager:'测试经理',languagePair:'中→英',statementRequired:true,quotationRequired:false,quotationDraft:{clientName:'广州测试有限公司',items:[{description:'原报价内容',languagePair:'中→英',quantity:2,unit:'字',unitPrice:'0.5',currency:'CNY'}],notes:'原报价说明'},wordCountMatrix:{},customerChargeItems:[]});const finance=ref();const app=createApp({render:()=>h('main',{},[h('button',{onClick:()=>finance.value.openForForm(root,root)},'打开测试财务'),h(Finance,{ref:finance,editorOnly:true,onDocumentRequirementsSaved:value=>window.lastDocumentChange=value})])});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/price-payment-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    writes=[]
    def api(route):
        path=route.request.url.split('/api',1)[1].split('?')[0]
        if route.request.method in ('POST','PUT','PATCH'):writes.append(path)
        if path=='/translation-customer-finance/page':data={'items':[],'total':0,'client_subtotals':[]}
        elif path.startswith('/translation-statement-workspaces/c1'):data={'client_id':'c1','client_name':'广州测试','documents':[],'payload':{'tasks':{}},'months':[],'pending':[],'available_months':[],'revision':0,'capabilities':{}}
        elif path.endswith('/statement-preference'):data={'statement_default':'required','revision':0}
        elif path.startswith('/customer-translation-rates/'):data={'items':[],'version':''}
        else:data=[]
        route.fulfill(content_type='application/json',body=json.dumps(data))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1500,'height':1000})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\",\"clients:read\",\"clients:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(BASE+'/price-payment-test',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/price-payment-test')
        page.get_by_role('button',name='打开测试财务',exact=True).click();dialog=page.locator('.customer-finance-dialog:visible')
        expect(dialog).to_contain_text('价格与付款 · TP-261107-999');expect(dialog.get_by_role('heading',name='计价方式与单据',exact=True)).to_be_visible()
        quote=dialog.locator('[data-field-key="quotationRequired"]');statement=dialog.locator('[data-field-key="statementRequired"]')
        bill=dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=re.compile('^账单月份$')))
        assert quote.bounding_box()['y']<bill.bounding_box()['y'] and statement.bounding_box()['y']<bill.bounding_box()['y']
        quote.locator('.el-checkbox').click();statement.locator('.el-checkbox').click()
        expect(page.locator('.customer-quotation-dialog:visible')).to_have_count(0);expect(page.locator('.customer-statement-dialog:visible')).to_have_count(0)
        quote.get_by_role('button',name='打开报价单',exact=True).click();quotation=page.locator('.customer-quotation-dialog:visible')
        expect(quotation.get_by_role('textbox',name='客户名称',exact=True)).to_have_value('广州测试有限公司')
        expect(quotation.get_by_role('spinbutton',name='单价',exact=True)).to_have_value('0.5000')
        quotation.get_by_role('button',name='应用到项目',exact=True).click();expect(quotation).not_to_be_visible()
        statement.get_by_role('button',name='打开对账单',exact=True).click();workspace=page.locator('.customer-statement-dialog:visible')
        expect(workspace.locator('.statement-client-context')).to_have_text('广州测试 · 2026-11');workspace.get_by_role('button',name='关闭',exact=True).click();expect(workspace).not_to_be_visible()
        dialog.get_by_text('固定收费',exact=True).first.click();dialog.get_by_placeholder('请输入不含税固定收费',exact=True).fill('100');dialog.get_by_placeholder('请输入不含税固定收费',exact=True).press('Tab')
        dialog.locator('.el-dialog__footer').get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible()
        values=page.evaluate('JSON.parse(JSON.stringify(testRoot))');assert values['quotationRequired'] is True and values['statementRequired'] is False and values['statementRequiredExplicit'] is True,values
        assert values['quotationDraft']['items'][0]['unit_price']==0.5 and 'unitPrice' not in values['quotationDraft']['items'][0]
        assert page.evaluate('lastDocumentChange.quotationDraftChanged') is True
        page.get_by_role('button',name='打开测试财务',exact=True).click();expect(quote.locator('input')).to_be_checked();expect(statement.locator('input')).not_to_be_checked()
        statement.locator('.el-checkbox').click();dialog.locator('.el-dialog__footer').get_by_role('button',name='取消',exact=True).click();page.get_by_role('button',name='放弃修改',exact=True).click();expect(dialog).not_to_be_visible()
        assert page.evaluate('testRoot.statementRequired') is False
        assert not writes,writes
        assert not errors,errors;browser.close()
    print('price/payment titles / invoice fields above month / checkbox no popup / same quotation and statement / local save+cancel PASS')
if __name__=='__main__':run()
