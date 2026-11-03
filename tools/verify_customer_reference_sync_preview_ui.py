"""客户参考价空缺/差异、最新版本、取消与再次确认；接口模拟。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=20).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Workspace from '/src/views/project/ProjectWorkspace.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';const app=createApp({render:()=>h(RouterView)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/reference-sync-preview-test',component:Workspace,props:{module:'translation'}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    price={'id':'charge1','language_pair':'中→英','amount':'.2','currency':'CNY','unit_size':1,'metric':'customer_auto'}
    root={'id':'p1','root_id':'p1','client_id':'c1','client_short_name':'客户简称','order_no':'TP-261029-010','project_name':'测试.docx','language_pair':'中→英','children':[],'prices':[price],'billing_month':'2026-10','word_count_matrix':{'customer':{'foreign_words':100}},'totals':{'CNY':'20.00'},'adjusted_totals':{'CNY':'20.00'}}
    library={'ready':True,'items':[],'version':'latest-v2','client':{'name':'客户管理中的客户全称','short_name':'客户简称','code':'CL-TEST-001'}};writes=[];errors=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/translation-customer-finance/page':result={'items':[root],'total':1,'client_subtotals':[]}
        elif path=='/api/translation-customer-finance/project/p1':
            if route.request.method=='PUT':writes.append(route.request.post_data_json)
            result={'item':root,'version':'project-v1','reference_prices':{'ready':True,'items':[],'version':'stale-v1'}}
        elif path=='/api/customer-translation-rates/c1':result=library
        elif path=='/api/projects/languages':result=[{'id':'en','label':'英'},{'id':'zh','label':'中'}]
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1500,'height':1000})
        context.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write','clients:write']))")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/reference-sync-preview-test*',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/reference-sync-preview-test?section=customer-finance')
        page.locator('.finance-manager-dialog:visible').get_by_role('button',name='确定',exact=True).click();page.get_by_role('button',name='编辑收费',exact=True).click()
        editor=page.locator('.customer-finance-dialog:visible');button=editor.get_by_role('button',name='保存并同步单价至客户信息…',exact=True);preview=page.locator('.customer-rate-sync-preview:visible')
        button.click();expect(preview).to_contain_text('尚无该语种方向的参考价');expect(preview).to_contain_text('客户管理中的客户全称');expect(preview).to_contain_text('CL-TEST-001');assert not writes
        preview.get_by_role('button',name='取消',exact=True).click();assert not writes
        library['items']=[{**price,'id':'rate1','amount':'.1','updated_at':'2026-11-02T10:00:00+08:00'}]
        button.click();expect(preview).to_contain_text('单价不同，将更新该参考价');expect(preview).to_contain_text('CNY .1 / 1');expect(preview).to_contain_text('CNY 0.2 / 1');preview.get_by_role('button',name='关闭窗口',exact=True).click();assert not writes
        library['items'][0]['amount']='.15';library['version']='latest-v3'
        button.click();expect(preview).to_contain_text('CNY .15 / 1');preview.get_by_role('button',name='确认保存并同步',exact=True).click();expect(editor).not_to_be_visible()
        assert len(writes)==1 and writes[0]['library_version']=='latest-v3' and writes[0]['update_library'] is True and writes[0]['sync_confirmed'] is True
        assert not errors,errors;browser.close()
    print('missing direction warning, customer identity, price comparison, cancel without writes and explicit latest-version confirmation PASS')


if __name__=='__main__':run()
