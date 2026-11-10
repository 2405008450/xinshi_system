"""独立付款核对筛选交互验证；所有业务接口均为模拟数据。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect

BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/components/common/ProjectPaymentDialog.vue',timeout=15).read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,ref,h} from VUE;import Payment from '/src/components/common/ProjectPaymentDialog.vue';createApp({setup(){const open=ref(false);return ()=>h('div',[h('button',{onClick:()=>open.value=true},'Open'),h(Payment,{modelValue:open.value,'onUpdate:modelValue':v=>open.value=v,query:{billing_month:'2020-01'}})])}}).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
    queries=[];errors=[];old_backend=False
    def api(route):
        parsed=urlparse(route.request.url)
        if parsed.path.endswith('/translation-customer-finance/page'):
            q=parse_qs(parsed.query);queries.append(q)
            mismatch=q.get('payment_amount_mismatch')==['true'] and not old_backend
            result={'items':[{'id':'p1','order_no':'TP-MISMATCH' if mismatch else 'TP-UNPAID','payment_status':'full' if mismatch else 'unpaid',
                'payment_amount_mismatch':mismatch,'payment_actual_total':'280' if mismatch else '0','billing_totals':{'CNY':'300'},'children':[{'id':'child','order_no':'CHILD'}]}],
                'total':21 if mismatch else 1,'invoice_filter_applied':True}
            if mismatch:result['payment_amount_mismatch_filter_applied']=True
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');ctx=browser.new_context(viewport={'width':1600,'height':1000})
        ctx.add_init_script("localStorage.setItem('user_permissions',JSON.stringify(['projects:read']))")
        ctx.route(re.compile('^http://localhost:3000/api/'),api)
        ctx.route(BASE+'/payment-mismatch-test',lambda r:r.fulfill(content_type='text/html',body=html))
        page=ctx.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/payment-mismatch-test');page.get_by_role('button',name='Open',exact=True).click()
        page.get_by_role('tab',name='查账',exact=True).click()
        client=page.get_by_role('textbox',name='客户',exact=True);client.fill('其他客户')
        page.locator('.payment-filter-bar .el-select').click()
        page.get_by_role('option',name='未付款',exact=True).click()
        label=page.locator('label.el-checkbox').filter(has_text='仅看已付全款且金额不匹配的项目')
        label.click()
        table=page.locator('.payment-overview .el-table')
        expect(table).to_contain_text('TP-MISMATCH');expect(table).not_to_contain_text('TP-UNPAID');expect(table).not_to_contain_text('CHILD')
        expect(client).to_be_disabled();expect(page.get_by_role('button',name='查询',exact=True)).to_be_disabled()
        assert not any(key in queries[-1] for key in ('billing_month','billing_months','client','payment_status')),queries[-1]
        page.locator('.payment-overview .el-pager li').filter(has_text=re.compile('^2$')).click()
        page.wait_for_timeout(300)
        assert queries[-1]['skip']==['20'] and queries[-1]['payment_amount_mismatch']==['true']
        assert not any(key in queries[-1] for key in ('billing_month','billing_months','client','payment_status'))
        label.click();expect(client).to_be_enabled();expect(table).to_contain_text('TP-UNPAID')
        assert queries[-1]['billing_months']==['2020-01'] and queries[-1]['client']==['其他客户'] and queries[-1]['payment_status']==['unpaid']
        old_backend=True;label.click()
        expect(table).not_to_contain_text('TP-UNPAID');expect(table).not_to_contain_text('TP-MISMATCH')
        expect(page.locator('.el-alert--error')).to_contain_text('后端未正确执行')
        assert not errors,errors
        browser.close()
    print('PASS: independent filters, full-only results, pagination, restore, no child rows and stale-backend guard')

if __name__=='__main__':run()
