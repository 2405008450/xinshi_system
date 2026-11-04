"""口译系统语言对、参考价无数量及口译/标注项目单价引入；接口全部模拟。"""
import json,re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    code=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode();vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',code).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp} from VUE;import Panel from '/src/components/common/CustomerFinancePanel.vue';import AppForm from '/src/components/common/AppForm.vue';createApp(Panel,{clientId:'c1',canWrite:true}).component('AppForm',AppForm).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
    oral=dict(ready=True,revision=1,payload=dict(rates=[dict(direction='英语 ↔ 简中',amount='100',tax_prices={'unit_price_excl_tax':'100','unit_price_incl_tax':'106'},currency='CNY',unit='天',quantity='4',hours='8',includes_lunch=False)],has_overtime=False,overtime=None,adjusted_totals=[],explanation=''))
    saved=[];syncs=[];annotation=[];errors=[]
    project_oral=[dict(direction='英语 ↔ 简中',amount='300',tax_prices={'unit_price_excl_tax':'300','unit_price_incl_tax':'318'},currency='CNY',unit='天',quantity='5',hours='8',includes_lunch=False)]
    project_annotation=[dict(project_type='audio_annotation',amount='2.123456',tax_prices={'unit_price_excl_tax':'2.123456','unit_price_incl_tax':'2.250863'},currency='CNY',unit='minute')]
    def api(route):
        path=urlparse(route.request.url).path;method=route.request.method
        if path=='/api/projects/languages':result=[dict(id='en',label='英语'),dict(id='zh',label='简中')]
        elif path=='/api/interpretation-customer-finance/client/c1':
            if method=='PUT':
                body=route.request.post_data_json;saved.append(body);oral['revision']+=1;oral['payload']={k:v for k,v in body.items() if k in oral['payload']}
            result=oral
        elif '/history' in path:result={'items':[],'total':0}
        elif path=='/api/clients/c1/annotation-rates':result={'items':annotation}
        elif path.endswith('/differences'):
            module=path.split('/')[3];source=project_oral if module=='interpretation' else project_annotation
            match=any(x['module']==module for x in syncs)
            row=dict(project_id='p1',order_id='rate1',order_no='PROJECT-001',project_name='项目单价来源',project_rates=source,customer_rates=[],version='p-v1',customer_version='c-v1')
            result={'ready':True,'items':[] if match else [row],'total':0 if match else 1}
        elif path.endswith('/sync'):
            module=path.split('/')[3];body=route.request.post_data_json;syncs.append(dict(module=module,body=body))
            if module=='interpretation':oral['revision']+=1;oral['payload']['rates']=[dict(project_oral[0],quantity='1')]
            else:annotation.append(dict(project_annotation[0],id='imported',revision=1))
            result={'success':True}
        else:result={'ready':True,'items':[],'total':0,'version':'1'}
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1500,'height':1000})
        context.add_init_script("localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['clients:read','clients:write','projects:read','projects:write']))")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/client-price-import-test',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/client-price-import-test')
        page.get_by_role('tab',name='口译',exact=True).click();page.get_by_role('button',name='口译参考价及调整记录',exact=True).click()
        editor=page.locator('.interpretation-finance-dialog:visible')
        expect(editor.locator('.el-form-item__label').filter(has_text=re.compile('^数量$'))).to_have_count(0)
        editor.locator('.language-pair-select [role=combobox]').click();page.locator('.language-pair-option__label:visible').filter(has_text=re.compile('^简中→英语$')).click()
        expect(editor.get_by_role('button',name='查看项目已登记单价',exact=True)).to_be_disabled()
        editor.get_by_role('button',name='保存',exact=True).click()
        expect(editor.get_by_role('button',name='查看项目已登记单价',exact=True)).to_be_enabled()
        assert saved[-1]['rates'][0]['direction']=='简中 ↔ 英语'
        editor.get_by_role('button',name='查看项目已登记单价',exact=True).click()
        dialog=page.locator('.customer-rate-differences-dialog:visible')
        expect(dialog).to_contain_text('300')
        dialog.get_by_role('button',name='此订单单价 → 客户',exact=True).click()
        page.locator('.el-message-box:visible').get_by_role('button',name='取消',exact=True).click();assert not syncs
        dialog.get_by_role('button',name='此订单单价 → 客户',exact=True).click()
        page.locator('.el-message-box:visible').get_by_role('button',name='确认同步',exact=True).click()
        expect(dialog.locator('.el-table__body-wrapper tbody tr')).to_have_count(0)
        dialog.get_by_role('button',name='关闭',exact=True).click()
        expect(editor.locator('.rate-row').get_by_role('spinbutton').first).to_have_value(re.compile(r'^300'))
        editor.get_by_role('button',name='关闭',exact=True).click();expect(editor).to_have_count(0)
        page.get_by_role('tab',name='标注',exact=True).click();page.get_by_role('button',name='查看项目已登记单价',exact=True).click()
        expect(dialog).to_contain_text('音频标注');expect(dialog).to_contain_text('分钟')
        expect(dialog.get_by_role('button',name='客户单价 → 此订单',exact=True)).to_have_count(0)
        dialog.get_by_role('button',name='此订单单价 → 客户',exact=True).click();page.locator('.el-message-box:visible').get_by_role('button',name='确认同步',exact=True).click()
        expect(dialog.locator('.el-table__body-wrapper tbody tr')).to_have_count(0)
        dialog.get_by_role('button',name='关闭',exact=True).click()
        expect(page.locator('.customer-annotation-rates')).to_contain_text('2.123456')
        assert len(syncs)==2 and all(x['body']['confirmed'] for x in syncs)
        assert project_oral[0]['quantity']=='5' and project_annotation[0]['amount']=='2.123456'
        assert not errors,errors;browser.close()
    print('PASS reference quantity hidden, system language pair, unsaved protection, oral and annotation source previews, cancel, explicit imports, source preservation')

if __name__=='__main__':run()
