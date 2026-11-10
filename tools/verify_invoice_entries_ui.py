"""三个入口共用发票、自动需求与说明框验收；全部业务请求使用模拟接口。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    source=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=15).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',source).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;import Finance from '/src/views/project/translation/CustomerFinance.vue';const app=createApp({render:()=>h(Finance,{clientId:'c1'})});app.use(createRouter({history:createWebHistory(),routes:[{path:'/invoice-entries-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    state={'invoice_status':'unissued','proofs':'','version':'i1'}
    notes={'quotation':'','statement':'','invoice':''};calls=[];errors=[]
    def node():return {'id':'p1','root_id':'p1','order_no':'TP-261110-001','project_name':'发票入口测试','client_id':'c1','client_short_name':'测试客户','project_status':'confirmed','pricing_mode':'fixed','currency':'CNY','adjusted_total':'500','adjusted_total_incl_tax':'530','billing_tax_mode':'incl_tax','effective_billing_tax_mode':'incl_tax','billing_totals':{'CNY':'530'},'totals_excl_tax':{'CNY':'500'},'totals_incl_tax':{'CNY':'530'},'children':[],'prices':[],'word_count_matrix':{},'statement_required':True,'document_notes':dict(notes),'payment_confirmation':{'is_paid':False},'invoice_status':state['invoice_status'],'invoice_required':True}
    def api(route):
        path=urlparse(route.request.url).path
        if route.request.method=='PUT':
            payload=route.request.post_data_json;calls.append((path,payload))
            if path.endswith('/invoice'):state.update(payload);state['version']='i2'
            elif payload.get('document_notes'):notes.update(payload['document_notes'])
        if path.endswith('/invoice'):result={**state,'project_id':'p1','order_id':'p1','order_no':'TP-261110-001','client_name':'测试客户','required':True,'tax_mode':'incl_tax','totals':{'CNY':'530'},'note':notes['invoice'],'previous_payment_version':'pay1','payment_version':'pay1'}
        elif path=='/api/translation-customer-finance/project/p1':result={'item':node(),'version':'v1','reference_prices':{'items':[],'version':'r1'},'payment':{'version':'pay1','payments':[]}}
        elif path.endswith('/page'):result={'items':[node()],'total':1,'client_subtotals':[],'invoice_filter_applied':True}
        elif path.endswith('/p1'):result={'id':'p1','customer_charge_items':[],'payment_confirmation':{'is_paid':False}}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');ctx=browser.new_context(viewport={'width':1700,'height':1000})
        ctx.add_init_script("localStorage.setItem('user_id','invoice-qa');localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write']))")
        ctx.route(re.compile('^http://localhost:3000/api/'),api)
        ctx.route(BASE+'/invoice-entries-test',lambda r:r.fulfill(content_type='text/html',body=html))
        page=ctx.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/invoice-entries-test')
        table=page.locator('.finance-project-table');expect(table).to_contain_text('TP-261110-001')
        actions=table.locator('.el-table__body-wrapper tbody tr').first.locator('td').last
        assert actions.get_by_role('button').all_text_contents()==['价格与付款','对账单','发票','修改记录']
        table.get_by_role('button',name='收起操作栏',exact=True).click();expect(actions.get_by_role('button')).to_have_count(0)
        table.get_by_role('button',name='展开操作栏',exact=True).click()
        # 入口 A：财务操作列。
        actions.get_by_role('button',name='发票',exact=True).click()
        popup=page.locator('.project-invoice-dialog:visible')
        expect(popup.get_by_role('textbox',name='是否需发票',exact=True)).to_have_value('需（含税）')
        initial=popup.bounding_box();header=popup.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+header['width']/2,header['y']+10);page.mouse.down()
        page.mouse.move(header['x']+header['width']/2+50,header['y']+35,steps=8);page.mouse.up()
        moved=popup.bounding_box();assert moved['x']>initial['x']+20
        assert moved['x']>=0 and moved['x']+moved['width']<=1701
        popup.locator('.el-select').click();page.get_by_role('option',name='已开票',exact=True).click()
        popup.get_by_role('textbox',name='发票截图及备注',exact=True).fill('三个入口共用的发票附件备注')
        popup.get_by_role('button',name='保存发票',exact=True).click();expect(popup).not_to_be_visible()
        # 入口 B：发票、查账与追账的发票页签。
        page.get_by_role('button',name='发票、查账与追账',exact=True).click()
        viewer=page.locator('.project-payment-dialog:visible')
        expect(viewer.get_by_role('tab')).to_have_count(3)
        expect(viewer.get_by_role('tab',name='发票',exact=True)).to_have_attribute('aria-selected','true')
        expect(viewer.get_by_role('tab',name='查账',exact=True)).to_be_visible()
        viewer.locator('.el-table').get_by_role('button',name='发票',exact=True).click()
        reopened=popup.bounding_box();assert abs(reopened['x']-initial['x'])<3
        expect(popup.get_by_role('textbox',name='发票截图及备注',exact=True)).to_have_value('三个入口共用的发票附件备注')
        expect(popup.locator('.el-select')).to_contain_text('已开票')
        popup.locator('.el-dialog__footer').get_by_role('button',name='关闭',exact=True).click()
        viewer.locator('.el-dialog__footer').get_by_role('button',name='关闭',exact=True).click()
        # 第一个入口：价格与付款的自动发票需求，三个说明独立填写。
        actions.get_by_role('button',name='价格与付款',exact=True).click()
        editor=page.locator('.customer-finance-dialog:visible').first
        expect(editor.get_by_role('textbox',name='是否需发票',exact=True)).to_have_attribute('readonly','')
        for label,value in [('报价单说明','报价备注'),('对账单说明','账单备注'),('发票说明','开票备注')]:editor.get_by_role('textbox',name=label,exact=True).fill(value)
        editor.locator('.billing-tax-choice label.el-radio-button').filter(has_text=re.compile('^不含税$')).click()
        expect(editor.get_by_role('textbox',name='是否需发票',exact=True)).to_have_value('无需')
        expect(editor.get_by_role('button',name='发票',exact=True)).to_have_count(0)
        editor.locator('.billing-tax-choice label.el-radio-button').filter(has_text=re.compile('^含税$')).click()
        editor.get_by_role('button',name='发票',exact=True).click()
        expect(popup.get_by_role('textbox',name='发票截图及备注',exact=True)).to_have_value('三个入口共用的发票附件备注')
        expect(popup.get_by_role('textbox',name='发票说明',exact=True)).to_have_value('开票备注')
        page.set_viewport_size({'width':760,'height':800})
        popup.locator('.el-dialog__body').evaluate('(node)=>node.scrollTop=node.scrollHeight')
        expect(popup.get_by_role('button',name='保存发票',exact=True)).to_be_in_viewport()
        popup.locator('.el-dialog__footer').get_by_role('button',name='关闭',exact=True).click()
        editor.get_by_role('button',name='保存',exact=True).click();expect(editor).not_to_be_visible()
        assert calls[-1][1]['document_notes']=={'quotation':'报价备注','statement':'账单备注','invoice':'开票备注'}
        assert not errors,errors
        browser.close()
    print('PASS: three shared invoice entries, status/attachment roundtrip, auto tax requirement, three notes, action order/collapse, three tabs and small viewport')

if __name__=='__main__':run()
