"""客户部人员多选、取消/确认、ID传参、列表与小计联调；模拟接口。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=20).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Workspace from '/src/views/project/ProjectWorkspace.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';const app=createApp({render:()=>h(RouterView)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/finance-manager-test',component:Workspace,props:{module:'translation'}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    people=[{'id':'11111111-1111-4111-8111-111111111111','name':'甲经理','username':'manager_a','active':True},{'id':'22222222-2222-4222-8222-222222222222','name':'乙经理','username':'manager_b','active':True}]
    queries=[];errors=[]
    def api(route):
        parsed=urlparse(route.request.url)
        if parsed.path=='/api/translation-customer-finance/manager-options':result={'items':people}
        elif parsed.path=='/api/translation-customer-finance/page':
            q=parse_qs(parsed.query);queries.append(q)
            ids=q.get('manager_ids') or (['self'] if q.get('only_mine')==['true'] else ['self',*[p['id'] for p in people]])
            names={'self':'本人',people[0]['id']:'甲',people[1]['id']:'乙'}
            result={'items':[{'id':id,'root_id':id,'order_no':'TP-'+names[id],'project_name':'测试.docx','prices':[],'children':[],'totals':{'CNY':'10'},'adjusted_totals':{'CNY':'10'}} for id in ids], 'total':len(ids),'client_subtotals':[{'client_id':'c1','client_name':'筛选客户','project_count':len(ids),'totals':{'CNY':str(10*len(ids))},'adjusted_totals':{'CNY':str(10*len(ids))}}]}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        b=p.chromium.launch(channel='msedge');context=b.new_context(viewport={'width':1500,'height':950})
        context.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_full_name','本人测试');localStorage.setItem('user_permissions',JSON.stringify(['projects:read']))")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/finance-manager-test*',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/finance-manager-test?section=customer-finance')
        popup=page.locator('.finance-manager-dialog:visible').filter(has_text='客户经理筛选');expect(popup).to_be_visible();assert queries[0]['only_mine']==['true']
        popup.locator('label.el-radio').filter(has_text=re.compile('^指定客户经理$')).click();select=popup.locator('.el-select');select.click()
        expect(page.get_by_role('option',name='甲经理（manager_a）',exact=True)).to_be_visible();page.get_by_role('option',name='乙经理（manager_b）',exact=True).click();expect(popup).to_be_visible()
        popup.get_by_role('button',name='确定',exact=True).click()
        table=page.locator('.customer-finance .el-card__body > .el-table').first;expect(table).to_contain_text('TP-乙');expect(table).not_to_contain_text('TP-本人')
        assert queries[-1]['manager_ids']==[people[1]['id']] and queries[-1]['only_mine']==['false'] and 'client_manager' not in queries[-1]
        page.get_by_role('button',name=re.compile('指定（1人）')).click();expect(popup).to_be_visible();select.click();page.get_by_role('option',name='甲经理（manager_a）',exact=True).click();popup.get_by_text('客户经理筛选',exact=True).click();count=len(queries);popup.get_by_role('button',name='取消',exact=True).click();assert len(queries)==count
        page.get_by_role('button',name=re.compile('指定（1人）')).click();expect(popup.locator('.el-tag')).to_have_count(1);select.click();page.get_by_role('option',name='甲经理（manager_a）',exact=True).click();popup.get_by_text('客户经理筛选',exact=True).click();popup.get_by_role('button',name='确定',exact=True).click()
        expect(table).to_contain_text('TP-甲');expect(table).to_contain_text('TP-乙');assert set(queries[-1]['manager_ids'])=={p['id'] for p in people};expect(page.locator('.client-subtotals')).to_contain_text('CNY 20.00')
        page.get_by_role('button',name='重置',exact=True).click();expect(table).to_contain_text('TP-本人');expect(table).not_to_contain_text('TP-甲');assert queries[-1]['only_mine']==['true'] and 'manager_ids' not in queries[-1]
        page.get_by_role('button',name=re.compile('本人（')).click()
        popup.locator('label.el-radio').filter(has_text='不指定人（全部订单）').click();popup.get_by_role('button',name='确定',exact=True).click()
        expect(table).to_contain_text('TP-甲');expect(table).to_contain_text('TP-乙');expect(table).to_contain_text('TP-本人')
        assert queries[-1]['only_mine']==['false'] and 'manager_ids' not in queries[-1]
        page.get_by_role('button',name='不指定人（全部订单）',exact=True).click()
        popup.locator('label.el-radio').filter(has_text=re.compile('^指定客户经理$')).click();select.click();page.get_by_role('option',name='乙经理（manager_b）',exact=True).click()
        expect(popup).to_be_visible();popup.get_by_role('button',name='确定',exact=True).click();expect(table).to_contain_text('TP-乙');expect(table).not_to_contain_text('TP-本人')
        page.get_by_role('button',name=re.compile('指定（1人）')).click();popup.locator('.el-tag__close').click();popup.get_by_role('button',name='确定',exact=True).click()
        expect(table).to_contain_text('TP-本人');expect(table).to_contain_text('TP-甲');assert queries[-1]['only_mine']==['false'] and 'manager_ids' not in queries[-1]
        page.get_by_role('tab',name='笔译须知',exact=True).click()
        page.get_by_role('tab',name='财务管理（客户）',exact=True).click()
        expect(table).to_contain_text('TP-本人');expect(table).not_to_contain_text('TP-甲');expect(table).not_to_contain_text('TP-乙')
        expect(page.get_by_role('button',name='本人（本人测试）',exact=True)).to_be_visible()
        assert queries[-1]['only_mine']==['true'] and 'manager_ids' not in queries[-1]
        assert not errors,errors;b.close()
    print('customer department options, multi-ID filtering, draft cancel/confirm, matching subtotal, and reset-to-self PASS')


if __name__=='__main__':run()
