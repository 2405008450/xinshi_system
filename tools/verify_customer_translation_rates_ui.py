"""真实客户信息与项目财务：多语种单价、默认口径、双向人工同步；全部接口模拟。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=20).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Workspace from '/src/views/project/ProjectWorkspace.vue';import Clients from '/src/views/client/Clients.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';const app=createApp({render:()=>h(RouterView)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/rates-project-test',component:Workspace,props:{module:'translation'}},{path:'/rates-client-test',component:Clients}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    reference=[dict(id='ref1',language_pair='英语→简中',amount='.1',currency='CNY',metric='foreign_words',unit_size=1,revision=1),dict(id='ref2',language_pair='简中→英语',amount='.2',currency='CNY',metric='characters_no_spaces',unit_size=1,revision=1)]
    root=dict(id='p1',root_id='p1',client_id='c1',order_no='TP-PRICE-001',project_name='测试.docx',language_pair='英语→简中；简中→英语',children=[],prices=[],currency='CNY',metric='characters_no_spaces',unit_size=1,amount=None,word_count_matrix={'customer':{'characters_no_spaces':100,'foreign_words':20,'words':50,'cjk_chars_korean_words':60}},totals={},adjusted_totals={},incomplete=True)
    client=dict(id='c1',client_name='语种测试公司',client_short_name='语种测试',client_code='CL-RATE',sub_clients=[])
    project_writes=[];client_writes=[];queries=[];errors=[];price_events=[];client_events=[]
    def api(route):
        parsed=urlparse(route.request.url);path=parsed.path
        if path=='/api/projects/languages':result=[{'id':str(i),'label':name,'is_active':True} for i,name in enumerate(['英语','简中','日语'])]
        elif path=='/api/translation-customer-finance/page':queries.append(parse_qs(parsed.query));result={'items':[root],'total':1,'client_subtotals':[{'client_id':'c1','client_name':'语种测试','project_count':1,'totals':root['totals'],'adjusted_totals':root['adjusted_totals']}]}
        elif path=='/api/translation-customer-finance/project/p1':
            if route.request.method=='PUT':
                before=json.loads(json.dumps(root))
                body=route.request.post_data_json;project_writes.append(body);root['prices']=[{**item,'id':item.get('id') or 'charge'+str(i)} for i,item in enumerate(body['prices'])]
                value=sum(float(row['amount'])*root['word_count_matrix']['customer'][row['metric']]/float(row['unit_size']) for row in root['prices']);root.update(totals={'CNY':str(value)},adjusted_totals={'CNY':str(value)},incomplete=False)
                if body['update_library']:
                    for i,row in enumerate(body['prices']):reference[i].update(amount=row['amount'],revision=reference[i]['revision']+1)
                root['adjusted_total']=body.get('adjusted_total');root['adjusted_totals']={'CNY':str(body.get('adjusted_total') if body.get('adjusted_total') is not None else value)}
                price_events.insert(0,{'id':'e1:p1','actor_name':'测试人员','created_at':'2026-11-02T18:00:00+08:00','order_no':root['order_no'],'project_name':root['project_name'],'before':before,'after':json.loads(json.dumps(root))})
            result={'item':root,'version':'tree1','reference_prices':{'ready':True,'version':'lib1','items':reference}}
        elif path=='/api/customer-translation-rates/c1':
            if route.request.method=='PUT':
                before=json.loads(json.dumps(reference))
                body=route.request.post_data_json;client_writes.append(body);reference[:]=[{**item,'id':item.get('id') or 'ref'+str(i),'revision':2} for i,item in enumerate(body['items'])]
                client_events.insert(0,{'id':'ce1','actor_name':'客户编辑人','created_at':'2026-11-02T18:00:00+08:00','origin':'client','before':before,'after':json.loads(json.dumps(reference))})
            result={'ready':True,'version':'lib1','items':reference}
        elif path=='/api/translation-customer-finance/project/p1/history':result={'ready':True,'items':price_events,'total':len(price_events)}
        elif path.endswith('/history'):result={'items':client_events,'total':len(client_events)}
        elif path=='/api/clients/page':result={'items':[client],'total':1}
        elif path=='/api/clients/c1':result=client
        elif '/drafts/' in path:result={}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1550,'height':1000},service_workers='block')
        context.add_init_script("localStorage.setItem('user_id','rates-test');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write','clients:read','clients:write']))")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/rates-*-test*',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/rates-project-test?section=customer-finance')
        search=page.locator('.finance-search');expect(search.get_by_placeholder('全部月份')).to_be_visible();expect(search.get_by_role('button',name=re.compile('本人'))).to_be_visible();expect(page.get_by_placeholder('客户全称或简称')).not_to_be_visible()
        manager_popup=page.locator('.app-window-popover:visible').filter(has_text='客户经理筛选');expect(manager_popup).to_be_visible();assert queries[0]['only_mine']==['true']
        manager_popup.locator('label.el-radio').filter(has_text=re.compile('^全部客户经理$')).click();manager_popup.get_by_role('button',name='确定',exact=True).click();page.wait_for_timeout(250);assert queries[-1]['only_mine']==['false']
        search.get_by_role('button',name=re.compile('高级筛选')).click();expect(page.get_by_placeholder('客户全称或简称')).to_be_visible();page.get_by_placeholder('客户全称或简称').fill('测试');page.wait_for_timeout(550);assert queries[-1]['client']==['测试'];page.locator('.finance-heading').click()
        page.get_by_role('button',name='编辑收费',exact=True).click();dialog=page.locator('.customer-finance-dialog:visible');expect(dialog.locator('.language-price-row')).to_have_count(2)
        first=dialog.locator('.language-price-row').first;second=dialog.locator('.language-price-row').nth(1)
        expect(first).to_contain_text('外文字数');expect(second).to_contain_text('字符数不计空格')
        first.get_by_role('spinbutton',name='单价',exact=True).fill('.3');dialog.get_by_role('spinbutton',name='调整后总价',exact=True).fill('42.2');dialog.locator('.el-checkbox').filter(has_text='同时将本次语种单价').click();dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible()
        assert len(project_writes[-1]['prices'])==2 and project_writes[-1]['update_library'] is True
        expect(page.locator('.client-subtotals')).to_contain_text('CNY 26.00')
        page.get_by_role('button',name='修改记录',exact=True).first.click();record_dialog=page.locator('.el-dialog:visible').filter(has_text='财务修改记录');expect(record_dialog).to_contain_text('测试人员');record_dialog.locator('.el-collapse-item__header').first.click();expect(record_dialog).to_contain_text('42.20');expect(record_dialog).to_contain_text('未手动调整');record_dialog.get_by_role('button',name='关闭窗口',exact=True).click()
        page.goto(BASE+'/rates-client-test');page.get_by_role('button',name='编辑',exact=True).first.click();client_dialog=page.locator('.client-form-dialog:visible');client_dialog.get_by_role('button',name='客户语种单价',exact=True).click();ref_dialog=page.locator('.customer-reference-dialog:visible');expect(ref_dialog.locator('.language-price-row')).to_have_count(2)
        ref_dialog.locator('.language-price-row').first.get_by_role('spinbutton',name='单价',exact=True).fill('.4');ref_dialog.get_by_role('button',name='保存参考价',exact=True).click();page.wait_for_timeout(300);assert float(client_writes[-1]['items'][0]['amount'])==.4
        ref_dialog.get_by_text('参考价修改记录（1）',exact=True).click();expect(ref_dialog).to_contain_text('客户编辑人')
        page.wait_for_function('!document.querySelector(".customer-reference-dialog.dialog-fade-enter-active")');initial=ref_dialog.bounding_box();header=ref_dialog.locator('.el-dialog__header').bounding_box();page.mouse.move(header['x']+12,header['y']+12);page.mouse.down();page.mouse.move(header['x']+50,header['y']+40,steps=8);page.mouse.up();moved=ref_dialog.bounding_box();assert abs(initial['x']-moved['x'])+abs(initial['y']-moved['y'])>15
        ref_dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(ref_dialog).not_to_be_visible();expect(client_dialog).to_be_visible()
        client_dialog.get_by_role('button',name='客户语种单价',exact=True).click();expect(ref_dialog).to_be_visible();page.wait_for_function('!document.querySelector(".customer-reference-dialog.dialog-fade-enter-active")');assert abs(ref_dialog.bounding_box()['x']-initial['x'])<5
        page.set_viewport_size({'width':600,'height':800});expect(ref_dialog.get_by_role('button',name='保存参考价',exact=True)).to_be_in_viewport();ref_dialog.locator('.el-dialog__body').evaluate('(el)=>el.scrollTop=el.scrollHeight');expect(ref_dialog.get_by_role('button',name='保存参考价',exact=True)).to_be_in_viewport();ref_dialog.get_by_role('button',name='关闭窗口',exact=True).click();page.set_viewport_size({'width':1550,'height':1000})
        page.goto(BASE+'/rates-project-test?section=customer-finance');page.get_by_role('button',name='编辑收费',exact=True).click();expect(dialog.locator('.language-price-row').first.get_by_role('spinbutton',name='单价',exact=True)).to_have_value(re.compile(r'^0\.30*$'))
        dialog.get_by_role('button',name='采用最新客户参考价',exact=True).click();expect(dialog.locator('.language-price-row').first.get_by_role('spinbutton',name='单价',exact=True)).to_have_value(re.compile(r'^0\.40*$'))
        dialog.get_by_role('button',name='新增单价（含语种方向）',exact=True).click();expect(dialog.locator('.language-price-row')).to_have_count(3)
        added=dialog.locator('.language-price-row').last;added.locator('.language-pair-select [role=combobox]').click();page.locator('.language-pair-option__label:visible').filter(has_text=re.compile('^日语→简中$')).click();expect(added).to_contain_text('外文字数')
        added.locator('.language-pair-select [role=combobox]').click();page.locator('.language-pair-option__label:visible').filter(has_text=re.compile('^简中→日语$')).click();expect(added).to_contain_text('字符数不计空格')
        added.get_by_role('button',name='移除单价',exact=True).click();expect(dialog.locator('.language-price-row')).to_have_count(2)
        assert not errors,errors;browser.close()
    print('finance filter placement, shared language directions, multi-rates, direction defaults, project-to-client sync, actual client-info editor, snapshot preservation and manual latest adoption PASS')


if __name__=='__main__':run()
