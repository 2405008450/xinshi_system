"""真实财务窗口对账单页签、客户税口径、账户及印章替换；业务请求全部模拟。"""
import json,re,sys
from base64 import b64decode
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from customer_statements import default_stamp
BASE='http://localhost:3000'

def run():
    code=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',code).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h,ref} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Finance from '/src/views/project/translation/CustomerFinance.vue';import ClientFinance from '/src/components/common/CustomerFinancePanel.vue';import AppForm from '/src/components/common/AppForm.vue';const Harness={setup(){const editor=ref();const parent={id:'p1',clientId:'c1',languagePair:'英语→简中'};const target={id:'p1',orderNo:'TP-261101-001',projectName:'测试.docx',languagePair:'英语→简中',wordCountMatrix:{customer:{words:1234}},customerChargeItems:[{pricingMode:'metric',unitPriceExclTax:100,unitPriceInclTax:106,unitSize:1000,quantityBasis:'customer_auto:words',billingMonth:'2026-11',currency:'CNY'}]};return()=>h('div',[h(ClientFinance,{clientId:'c1',canWrite:true}),h('button',{onClick:()=>editor.value.openForForm(target,parent)},'打开项目财务'),h(Finance,{ref:editor,editorOnly:true})])}};createApp({render:()=>h(RouterView)}).component('AppForm',AppForm).use(createRouter({history:createWebHistory(),routes:[{path:'/customer-statement-ui-test',component:Harness}]})).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    stamp=default_stamp();settings=dict(bank_name='',account_name='',account_number='',stamp_image=None,default_stamp=stamp,revision=0)
    preference=dict(tax_included=False,revision=0);calls=[];errors=[]
    def api(route):
        nonlocal settings,preference
        request=route.request;parsed=urlparse(request.url);path=parsed.path;query=parse_qs(parsed.query);calls.append((path,query))
        if path=='/api/customer-statement-settings':
            if request.method=='PUT':settings={**request.post_data_json,'default_stamp':stamp,'revision':settings['revision']+1}
            result=settings
        elif path.endswith('/statement-preference'):
            if request.method=='PUT':preference={**request.post_data_json,'revision':preference['revision']+1}
            result=preference
        elif path=='/api/translation-statements/preview':
            scope=query['scope'][0];count=1 if scope=='project' else 2;included=preference['tax_included'];unit=106 if included else 100;subtotal='130.80' if included else '123.40'
            result=dict(company='广州信实翻译服务公司',client_name='测试客户',month=query['month'][0],tax_included=included,
                rows=[dict(received_date='2026-10-31',project_name=f'项目{i+1}.docx',language_pair='英语→简中',quantity='1234',basis='客户统计 · 字数（每1000计价）',unit_price=str(unit),unit_label='含税' if included else '不含税',currency='CNY',subtotal=subtotal,remarks='测试备注') for i in range(count)],
                totals={'CNY':'261.60' if included and count==2 else '246.80' if count==2 else subtotal},pending=[],settings=settings,stamp_image=settings['stamp_image'] or stamp,statement_version='a'*64)
        elif path=='/api/translation-statements/excel':route.fulfill(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',body=b'fake-excel-download');return
        elif path=='/api/customer-translation-rates/c1':result={'items':[],'version':'1'}
        elif path.endswith('/rate-differences'):result={'items':[],'total':0}
        elif path.endswith('/page'):result={'items':[],'total':0}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1600,'height':1100},accept_downloads=True)
        context.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['*']));window.print=()=>{window.top.__statementPrinted=true}")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/customer-statement-ui-test',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/customer-statement-ui-test');check=page.get_by_role('checkbox',name='单价含税',exact=True)
        expect(check).not_to_be_checked();check.locator('..').click();expect(check).to_be_checked();assert preference['tax_included']
        page.get_by_role('button',name='打开项目财务',exact=True).click();dialog=page.locator('.customer-finance-dialog:visible')
        expect(dialog.get_by_role('tab',name='收费设置',exact=True)).to_have_attribute('aria-selected','true')
        search=dialog.locator('.dialog-field-search-header input').first;search.fill('对账单')
        page.locator('.el-autocomplete-suggestion:visible li').filter(has_text='对账单').first.click()
        expect(dialog.get_by_role('tab',name='对账单',exact=True)).to_have_attribute('aria-selected','true')
        expect(dialog.get_by_role('button',name='保存',exact=True)).to_have_count(0)
        dialog.get_by_role('button',name='生成对账单',exact=True).click();paper=dialog.locator('.statement-paper');expect(paper).to_contain_text('广州信实翻译服务公司')
        expect(paper.locator('tbody tr')).to_have_count(1);expect(paper).to_contain_text('（含税）');expect(paper).to_contain_text('CNY 130.80')
        dialog.locator('.el-radio').filter(has_text='该客户整月项目').click();expect(paper).to_have_count(0)
        dialog.get_by_role('button',name='生成对账单',exact=True).click();expect(paper.locator('tbody tr')).to_have_count(2);expect(paper).to_contain_text('261.60')
        dialog.get_by_role('button',name='对账单设置',exact=True).click();config=page.locator('.statement-settings-dialog:visible')
        config.get_by_placeholder('填写开户行').fill('测试银行广州分行');config.get_by_placeholder('填写收款账户名').fill('测试收款公司');config.get_by_placeholder('填写收款账号').fill('001234567890')
        config.locator('input[type=file]').set_input_files({'name':'stamp.png','mimeType':'image/png','buffer':b64decode(stamp.split(',')[1])})
        expect(config.locator('.stamp-preview')).to_have_attribute('src',re.compile('^data:image/png;base64,'))
        page.set_viewport_size({'width':560,'height':760});expect(config.get_by_role('button',name='保存设置',exact=True)).to_be_in_viewport()
        config.get_by_role('button',name='保存设置',exact=True).click();expect(config).to_have_count(0);assert settings['account_number']=='001234567890' and settings['stamp_image']
        page.set_viewport_size({'width':1600,'height':1100});dialog.get_by_role('button',name='生成对账单',exact=True).click();expect(paper).to_contain_text('测试银行广州分行')
        expect(paper).to_contain_text('账号：001234567890')
        image=paper.locator('.statement-stamp');expect(image).to_be_visible();assert image.evaluate('(n)=>getComputedStyle(n).position')=='absolute'
        image_box=image.bounding_box();total_box=paper.locator('tfoot').bounding_box();assert image_box['y']<total_box['y']+total_box['height'] and image_box['y']+image_box['height']>total_box['y']
        paper.screenshot(path='tmp/customer-statement-preview.png')
        with page.expect_download() as download:
            dialog.get_by_role('button',name='下载Excel',exact=True).click()
        assert download.value.suggested_filename.endswith('.xlsx')
        dialog.get_by_role('button',name='打印 / 另存PDF',exact=True).click();page.wait_for_function('window.__statementPrinted===true')
        assert any(path.endswith('/preview') and query.get('scope')==['customer'] and query.get('month')==['2026-11'] for path,query in calls)
        assert not errors,errors;browser.close()
    print('PASS pricing/statement tabs, customer tax preference, project/month scopes, exact month, company header, fields/totals, bank settings, stamp upload/overlay, Excel download, print document, mobile footer')

if __name__=='__main__':run()
