import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect

BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/ProjectPaymentDialog.vue',timeout=15).read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,ref,h} from VUE;
import {createRouter,createWebHistory} from ROUTER;
import Finance from '/src/views/project/translation/CustomerFinance.vue';
import Payment from '/src/components/common/ProjectPaymentDialog.vue';
const Root={setup(){const finance=ref(),open=ref(false);window.openFinance=()=>finance.value.openForForm({id:'p1'},{id:'p1'});window.openPayment=()=>open.value=true;window.openNewFinance=()=>{window.newParent={customerChargeItems:[{pricingMode:'fixed',totalExclTax:500,currency:'CNY'}]};return finance.value.openForForm(window.newParent)};return ()=>h('div',[h(Finance,{ref:finance,editorOnly:true}),h(Payment,{modelValue:open.value,'onUpdate:modelValue':v=>open.value=v,initialProjectId:'p1',lockProject:true,onEdit:()=>finance.value.openForForm({id:'p1'},{id:'p1'})})])}};
const app=createApp(Root);app.use(createRouter({history:createWebHistory(),routes:[{path:'/payment-save-sync-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''
workspace=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=15).read().decode()
router=re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)',workspace).group(1)
html=html.replace('from VUE','from '+json.dumps(vue)).replace('from ROUTER','from '+json.dumps(router))
confirmation={'revision':1,'is_paid':False,'payment_option':None,'full_payment_currency':'CNY','proofs':'','payment_account':''}
details=[]
calls=[];errors=[]
def node():
    return {'id':'p1','root_id':'p1','order_no':'TP-261110-001','project_name':'同步测试','prices':[],'children':[],
        'currency':'CNY','pricing_mode':'fixed','adjusted_total':'500','adjusted_total_incl_tax':None,'billing_totals':{'CNY':'500'},
        'totals_excl_tax':{'CNY':'500'},'totals_incl_tax':{},'word_count_matrix':{},'statement_required':True,
        'payment_confirmation':dict(confirmation)}
def api(route):
    global confirmation,details
    path=urlparse(route.request.url).path
    if route.request.method=='PUT':
        data=route.request.post_data_json;calls.append((path,data))
        incoming=data.get('confirmation') or data.get('payment_confirmation')
        if data.get('payment_draft') is not None:
            details=[{**item,'confirmed_by_name':'测试确认人','confirmed_at':'2026-11-10T11:00:00+08:00'} for item in data['payment_draft']]
        if incoming:confirmation={**incoming,'revision':confirmation['revision']+1,'full_match_status':'mismatch' if str(incoming.get('full_payment_amount')) not in ('500','500.0','500.00') else 'matched'}
    if path=='/api/translation-customer-finance/project/p1':result={'item':node(),'payment':{'payments':details,'version':str(confirmation['revision']),'confirmation':dict(confirmation)},'version':str(confirmation['revision']),'reference_prices':{'items':[],'version':'v1'}}
    elif path=='/api/translation-payments/p1':result={'project_id':'p1','order_no':'TP-261110-001','version':str(confirmation['revision']),'payments':details,'confirmation':dict(confirmation)}
    elif path=='/api/translation-payments/p1/totals':result={'items':[{'key':'billing:CNY','label':'计费总价','currency':'CNY','amount':'500.00','taxMode':'excl_tax'}]}
    elif path.endswith('/page'):result={'items':[{**node(),'payment_status':'deposit' if confirmation.get('is_paid') else 'unpaid','payment_actual_total':str(sum(item.get('actual_amount') or 0 for item in details))}],'total':1,'client_subtotals':[],'invoice_filter_applied':True}
    elif path.endswith('/p1'):result={'id':'p1','customer_charge_items':[],'payment_confirmation':dict(confirmation)}
    else:result=[]
    route.fulfill(content_type='application/json',body=json.dumps(result))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge');ctx=browser.new_context(viewport={'width':1600,'height':1000})
    ctx.add_init_script("localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write','finance:write']));localStorage.setItem('user_id','qa')")
    ctx.route(re.compile('^http://localhost:3000/api/'),api)
    ctx.route(BASE+'/payment-save-sync-test',lambda r:r.fulfill(content_type='text/html',body=html))
    page=ctx.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(BASE+'/payment-save-sync-test');page.wait_for_function('typeof window.openFinance==="function"')
    page.evaluate('window.openPayment()')
    payment=page.locator('.project-payment-dialog:visible')
    expect(payment.get_by_role('tab')).to_have_count(3)
    expect(payment.get_by_role('tab',name='付款登记',exact=True)).to_have_count(0)
    expect(payment.get_by_role('tab',name='发票',exact=True)).to_have_attribute('aria-selected','true')
    payment.get_by_role('tab',name='查账',exact=True).click()
    expect(payment).to_contain_text('发票、查账与追账')
    payment.get_by_role('button',name='价格与付款',exact=True).click()
    finance=page.locator('.customer-finance-dialog:visible').first
    save_button=finance.get_by_role('button',name='保存',exact=True)
    expect(save_button).not_to_have_class(re.compile('el-button--primary'))
    page.wait_for_timeout(300)  # 等待弹窗进场完成后读取拖动起点
    initial=finance.bounding_box()
    header=finance.locator('.el-dialog__header').bounding_box()
    page.mouse.move(header['x']+header['width']/2,header['y']+10);page.mouse.down()
    page.mouse.move(header['x']+header['width']/2+50,header['y']+40,steps=8);page.mouse.up()
    moved=finance.bounding_box();assert moved['x']>initial['x']+20
    assert moved['x']>=0 and moved['x']+moved['width']<=1601
    finance.locator('label.el-radio').filter(has_text=re.compile('^已付定金$')).click()
    rows=finance.locator('.project-payment-row')
    expect(save_button).to_have_class(re.compile('el-button--primary'))
    expect(rows).to_have_count(1);expect(rows.first).to_contain_text('付款明细 1')
    expect(rows.first.get_by_role('textbox',name='阶段',exact=True)).to_have_value('定金')
    rows.first.get_by_role('spinbutton',name='预定金额',exact=True).fill('100')
    rows.first.get_by_role('spinbutton',name='实际金额',exact=True).fill('80')
    rows.first.locator('.el-select').click();page.get_by_role('option',name='现金',exact=True).click()
    rows.first.get_by_role('textbox',name='支付截图及备注',exact=True).fill('定金备注')
    finance.get_by_role('button',name='新增付款明细',exact=True).click()
    rows.nth(1).get_by_role('spinbutton',name='实际金额',exact=True).fill('40')
    rows.nth(1).get_by_role('textbox',name='支付截图及备注',exact=True).fill('中期独立备注')
    finance.get_by_role('button',name='保存',exact=True).click()
    expect(finance).not_to_be_visible()
    assert len(calls)==1 and calls[0][0]=='/api/translation-customer-finance/project/p1'
    assert [item['stage_no'] for item in calls[0][1]['payment_draft']]==[1,2]
    assert calls[0][1]['payment_draft'][0]['actual_amount']==80
    assert calls[0][1]['payment_draft'][0]['proofs']=='定金备注'
    assert calls[0][1]['payment_draft'][1]['proofs']=='中期独立备注'
    page.evaluate('window.openPayment()')
    payment.get_by_role('tab',name='查账',exact=True).click()
    expect(payment.locator('.payment-overview .el-table')).to_contain_text('120')
    payment.get_by_role('button',name='价格与付款',exact=True).click()
    expect(rows).to_have_count(2)
    expect(rows.first.get_by_role('spinbutton',name='实际金额',exact=True)).to_have_value('80.00')
    expect(rows.first.get_by_role('textbox',name='支付截图及备注',exact=True)).to_have_value('定金备注')
    expect(rows.nth(1).get_by_role('textbox',name='支付截图及备注',exact=True)).to_have_value('中期独立备注')
    expect(save_button).not_to_have_class(re.compile('el-button--primary'))
    for index in range(2):
        expect(rows.nth(index).get_by_role('textbox',name='期次',exact=True)).to_have_value(str(index+1))
        expect(rows.nth(index).get_by_role('textbox',name='确认人',exact=True)).to_have_value('测试确认人')
        expect(rows.nth(index).get_by_role('textbox',name='确认时间',exact=True)).to_have_value(re.compile('11:00:00'))
    rows.nth(1).locator('.el-select').first.click()
    expect(page.get_by_role('option',name='定金',exact=True)).to_have_count(0)
    page.get_by_role('option',name='尾款',exact=True).click()
    expect(rows.nth(1).get_by_role('textbox',name='期次',exact=True)).to_have_value('2')
    expect(save_button).to_have_class(re.compile('el-button--primary'))
    field_search=finance.get_by_role('textbox',name='搜索项目表单字段',exact=True)
    field_search.fill('付款时')
    page.locator('.project-field-search-popper:visible .project-field-search-option').first.click()
    expect(finance.locator('.is-dialog-field-search-highlight')).to_have_count(1)
    field_search.fill('')
    rows.nth(1).locator('.el-select').first.click();page.get_by_role('option',name='尾款',exact=True).click()
    rows.nth(1).get_by_role('spinbutton').last.fill('420')
    expect(finance).to_contain_text('累计实付金额')
    # 长内容滚动后底部保存仍在视口内，小屏内容不溢出。
    page.set_viewport_size({'width':760,'height':800})
    finance.locator('.el-dialog__body').evaluate('(node)=>node.scrollTop=node.scrollHeight')
    expect(finance.get_by_role('button',name='保存',exact=True)).to_be_in_viewport()
    box=finance.bounding_box();assert box['width']<=760 and box['height']<=800
    finance.get_by_role('button',name='保存',exact=True).click()
    expect(finance).not_to_be_visible();assert len(calls)==2
    assert calls[-1][1]['payment_draft'][1]['stage_type']=='final'
    assert calls[-1][1]['payment_confirmation']['full_payment_amount']==500
    # 新建项目在本地保存付款草稿，不写任何业务接口。
    page.evaluate('window.openNewFinance()')
    finance.locator('label.el-radio').filter(has_text=re.compile('^已付定金$')).click()
    rows.first.get_by_role('spinbutton',name='实际金额',exact=True).fill('60')
    finance.get_by_role('button',name='保存',exact=True).click()
    expect(finance).not_to_be_visible()
    assert page.evaluate('window.newParent.paymentDraft[0].actual_amount')==60
    assert len(calls)==2
    confirmation.update(is_paid=True,payment_option='full',full_payment_amount=500,full_payment_total_key='billing:CNY',
        full_payment_confirmed_by_name='全款确认人',full_payment_confirmed_at='2026-11-10T12:00:00+08:00')
    details=[]
    page.evaluate('window.openFinance()')
    expect(finance.get_by_role('textbox',name='确认人',exact=True)).to_have_value('全款确认人')
    expect(finance.get_by_role('textbox',name='确认时间',exact=True)).to_have_value(re.compile('12:00:00'))
    expect(save_button).not_to_have_class(re.compile('el-button--primary'))
    assert not errors,errors
    browser.close()
print('PASS: payment sequences, save-button states, installment and full confirmation, final total, small viewport and new-project draft; mocked APIs only')
