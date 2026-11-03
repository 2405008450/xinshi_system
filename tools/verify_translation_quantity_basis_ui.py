"""七种计价口径、唯一客户统计、计算总价及同月同步预览/确认；接口模拟。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=20).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Workspace from '/src/views/project/ProjectWorkspace.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';const app=createApp({render:()=>h(RouterView)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/quantity-basis-test',component:Workspace,props:{module:'translation'}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    root=dict(id='p1',root_id='p1',client_id='c1',order_no='TP-BASIS-001',project_name='测试.docx',language_pair='中→英',children=[],prices=[],billing_month='2026-11',currency='CNY',metric='characters_no_spaces',unit_size=1,adjusted_total=None,word_count_matrix={'customer':{'foreign_words':100},'company':{'characters_no_spaces':180,'words':200,'cjk_chars_korean_words':220,'foreign_words':240}},totals={},adjusted_totals={},incomplete=True)
    root['word_count_matrix']['company'].update(documents=3,pages=8)
    writes=[];applies=[];errors=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/projects/languages':result=[{'id':'en','label':'英'},{'id':'zh','label':'中'}]
        elif path=='/api/translation-customer-finance/page':result={'items':[root],'total':1,'client_subtotals':[]}
        elif path=='/api/translation-customer-finance/project/p1':
            if route.request.method=='PUT':
                body=route.request.post_data_json;writes.append(body);root['prices']=[{**row,'id':'charge'+str(i)} for i,row in enumerate(body['prices'])]
            result={'item':root,'version':'v1','reference_prices':{'ready':True,'items':[],'version':'lib1'}}
        elif path.endswith('/sync-orders/preview'):
            result={'token':'preview-token','client_name':'同客户测试','billing_month':'2026-11','targets':[{'order_id':'t'+str(i),'order_no':number,'project_name':'匹配测试.docx','language_pair':'中→英','before':[{'amount':'.8','currency':'CNY','unit_size':1,'metric':'customer_auto','language_pair':'中→英'}],'prices':root['prices']} for i,number in enumerate(['TP-TARGET-001','TP-TARGET-001.001','TP-TARGET-001.001.001'])]}
        elif path.endswith('/sync-orders/apply'):applies.append(route.request.post_data_json);result={'updated_orders':3}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        b=p.chromium.launch(channel='msedge');context=b.new_context(viewport={'width':1500,'height':1000})
        context.add_init_script("localStorage.setItem('user_id','basis-test');localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write']))")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/quantity-basis-test*',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/quantity-basis-test?section=customer-finance')
        popup=page.locator('.finance-manager-dialog:visible').filter(has_text='客户经理筛选');expect(popup).to_be_visible();popup.get_by_role('button',name='确定',exact=True).click()
        page.get_by_role('button',name='编辑收费',exact=True).click();dialog=page.locator('.customer-finance-dialog:visible');price=dialog.locator('.language-price-row').first;price.get_by_role('spinbutton',name='单价',exact=True).fill('.2');dialog.get_by_text('项目名称',exact=True).click()
        computed=dialog.locator('.el-form-item').filter(has_text='计算得出的总价').locator('input');expect(computed).to_have_value('CNY 20.00')
        price.locator('.customer-price-fields .el-select').nth(1).click();options=page.get_by_role('option');expected=['客户统计','我司统计（字符数（不计空格））','我司统计（字数）','我司统计（中朝）','我司统计（外文）','我司统计（份数）','我司统计（页数）'];expect(options).to_have_text(expected)
        page.get_by_role('option',name='我司统计（字数）',exact=True).click();expect(computed).to_have_value('CNY 40.00')
        for label,total in [('我司统计（份数）','CNY 0.60'),('我司统计（页数）','CNY 1.60')]:
            price.locator('.customer-price-fields .el-select').nth(1).click();page.get_by_role('option',name=label,exact=True).click();expect(computed).to_have_value(total)
        price.locator('.customer-price-fields .el-select').nth(1).click();page.get_by_role('option',name='客户统计',exact=True).click();expect(computed).to_have_value('CNY 20.00')
        expect(dialog.get_by_role('button',name='同步到同客户同月同语种方向订单…',exact=True)).to_be_disabled();dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible();assert writes[-1]['prices'][0]['metric']=='customer_auto'
        page.set_viewport_size({'width':900,'height':620})
        page.get_by_role('button',name='编辑收费',exact=True).click();dialog.get_by_role('button',name='同步到同客户同月同语种方向订单…',exact=True).click();sync_dialog=page.locator('.same-month-price-dialog:visible');expect(sync_dialog).to_contain_text('TP-TARGET-001.001.001')
        page.wait_for_timeout(350)
        initial=sync_dialog.bounding_box();header=sync_dialog.locator('.el-dialog__header').bounding_box();page.mouse.move(header['x']+header['width']*.55,header['y']+18);page.mouse.down();page.mouse.move(2000,2000,steps=12);page.mouse.up();moved=sync_dialog.bounding_box();assert moved['y']!=initial['y'];assert 0<=moved['x'] and moved['x']+moved['width']<=901 and 0<=moved['y'] and moved['y']+moved['height']<=621
        expect(sync_dialog.get_by_role('button',name='关闭窗口',exact=True)).to_be_visible();footer=sync_dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=621
        sync_dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(sync_dialog).not_to_be_visible();assert not applies
        dialog.get_by_role('button',name='同步到同客户同月同语种方向订单…',exact=True).click();expect(sync_dialog).to_contain_text('TP-TARGET-001.001.001');page.wait_for_timeout(350);assert abs(sync_dialog.bounding_box()['y']-initial['y'])<2,(initial,sync_dialog.bounding_box())
        sync_dialog.get_by_role('button',name='确认同步 3 个订单',exact=True).click();expect(sync_dialog).not_to_be_visible();assert applies[-1]['token']=='preview-token' and applies[-1]['billing_month']=='2026-11';page.set_viewport_size({'width':1500,'height':1000})
        root['word_count_matrix']['customer']['words']=150
        page.get_by_role('button',name='编辑收费',exact=True).click();expect(dialog).to_contain_text('客户统计有多栏，请选择')
        select=dialog.locator('.el-form-item').filter(has_text='客户统计口径（多栏时必须选择）').locator('.el-select');select.click();page.get_by_role('option',name='字数：150',exact=True).click();expect(computed).to_have_value('CNY 30.00');dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible();assert writes[-1]['prices'][0]['metric']=='customer_auto:words'
        assert not errors,errors;b.close()
    print('seven quantity bases, company documents/pages totals, customer unique/ambiguous handling and same-month preview/cancel/apply PASS')


if __name__=='__main__':run()
