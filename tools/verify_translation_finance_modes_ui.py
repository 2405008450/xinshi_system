"""真实笔译项目表单：客户财务入口、固定收费、已填统计项与税口径；接口模拟。"""
import json,re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    code=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',code).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Page from '/src/views/project/translation/ProjectDetails.vue';import SubOrders from '/src/views/project/translation/SubOrderManagement.vue';import AppForm from '/src/components/common/AppForm.vue';createApp({render:()=>h(RouterView)}).component('AppForm',AppForm).use(createRouter({history:createWebHistory(),routes:[{path:'/project-finance-sub-test/:projectId',component:SubOrders},{path:'/project-finance-new-test',component:Page},{path:'/project-finance-edit-test',component:Page,props:{editorOnly:true,editorProjectId:'p1'}}]})).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    project=dict(id='p1',order_no='TP-TEST',project_name='测试.docx',source_file_name='测试.docx',language_pair='英语→简中',project_status='confirmed',client_id='c1',word_count_matrix={'customer':{'words':100},'company':{'pages':2}},customer_charge_items=[],sub_orders=[],assigned_translators=[],role_assignments=[],file_type_secondary='文档')
    errors=[];writes=[]
    def api(route):
        path=urlparse(route.request.url).path
        if route.request.method in ('POST','PUT','DELETE'):writes.append(path)
        if path=='/api/projects/translation/p1':result=project
        elif path=='/api/projects/translation/next-order-no':result={'orderNo':'TP-NEW'}
        elif path=='/api/projects/languages':result=[dict(id='en',label='英语'),dict(id='zh',label='简中')]
        elif path=='/api/clients/':result=[dict(id='c1',client_name='测试客户',client_short_name='测试',client_code='CL-T')]
        elif path=='/api/customer-translation-rates/c1':result={'ready':True,'items':[],'version':'1'}
        elif path.endswith('/page'):result={'items':[],'total':0}
        elif '/drafts/' in path:result={}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1600,'height':1000})
        context.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['*']))")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(re.compile(r'^http://localhost:3000/project-finance-.*-test(?:/.*)?$'),lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/project-finance-new-test');page.get_by_role('button',name='新增项目',exact=True).click()
        outer=page.locator('.project-editor-dialog:visible');finance=page.locator('.customer-finance-dialog:visible')
        def open_finance():
            search=outer.locator('.dialog-field-search-header input').first;search.fill('');search.fill('客户财务')
            page.locator('.el-autocomplete-suggestion:visible li').filter(has_text='客户财务').first.click()
            outer.get_by_role('button',name='客户财务',exact=True).click()
        expect(outer.get_by_text('客户收费明细',exact=True)).to_have_count(0)
        open_finance();expect(finance.get_by_role('radio',name='按数量',exact=True)).to_be_checked()
        finance.locator('.el-radio').filter(has_text='固定收费').click()
        expect(finance.locator('.language-price-row')).to_have_count(0)
        expect(finance.get_by_text('计算总价（按税口径）',exact=True)).to_have_count(0)
        finance.get_by_role('button',name='保存',exact=True).click();expect(finance).to_contain_text('请填写不含税或含税固定收费')
        finance.get_by_placeholder('请输入不含税固定收费').fill('1000');finance.get_by_placeholder('请输入含税固定收费').fill('1060')
        finance.get_by_role('button',name='保存',exact=True).click();expect(finance).to_have_count(0)
        assert not [path for path in writes if '/projects/translation/' in path],writes
        open_finance();expect(finance.get_by_role('radio',name='固定收费',exact=True)).to_be_checked()
        expect(finance.get_by_placeholder('请输入含税固定收费')).to_have_value(re.compile('^1060'))
        finance.get_by_role('button',name='取消',exact=True).click();expect(finance).to_have_count(0)
        page.goto(BASE+'/project-finance-edit-test');expect(outer).to_be_visible()
        open_finance();expect(finance).to_contain_text('项目已填写 2 项')
        row=finance.locator('.language-price-row').first
        row.locator('.customer-price-fields > label').filter(has_text='计价方式').first.locator('.el-select').click()
        expect(page.get_by_role('option')).to_have_count(2)
        page.get_by_role('option',name='我司统计 · 页数：2',exact=True).click()
        row.get_by_role('spinbutton',name='不含税单价',exact=True).fill('10')
        row.get_by_role('spinbutton',name='含税单价',exact=True).fill('10.6')
        expect(row.locator('.price-preview')).to_contain_text('20.00');expect(row.locator('.price-preview')).to_contain_text('21.20')
        finance.get_by_role('button',name='保存',exact=True).click();expect(finance).to_have_count(0)
        open_finance();expect(finance).to_contain_text('我司统计 · 页数：2')
        expect(finance.get_by_role('spinbutton',name='含税单价',exact=True)).to_have_value(re.compile(r'^10\.6'))
        page.set_viewport_size({'width':560,'height':760})
        expect(finance.get_by_role('button',name='保存',exact=True)).to_be_in_viewport()
        finance.get_by_role('button',name='取消',exact=True).click()
        page.set_viewport_size({'width':1600,'height':1000})
        page.goto(BASE+'/project-finance-sub-test/p1')
        page.get_by_role('button',name='新增子订单',exact=True).click()
        sub=page.locator('.el-dialog:visible').first
        expect(sub.get_by_text('客户收费明细',exact=True)).to_have_count(0)
        sub.get_by_role('button',name='客户财务',exact=True).click()
        expect(finance.get_by_role('radio',name='按数量',exact=True)).to_be_checked()
        finance.locator('.el-radio').filter(has_text='固定收费').click()
        finance.get_by_placeholder('请输入不含税固定收费').fill('0')
        finance.get_by_role('button',name='保存',exact=True).click();expect(finance).to_have_count(0)
        sub.get_by_role('button',name='客户财务',exact=True).click()
        expect(finance.get_by_role('radio',name='固定收费',exact=True)).to_be_checked()
        expect(finance.get_by_placeholder('请输入不含税固定收费')).to_have_value(re.compile(r'^0(?:\.0+)?$'))
        finance.get_by_role('button',name='取消',exact=True).click()
        assert not errors,errors;browser.close()
    print('PASS real project finance button, old section removed, draft fixed price, no quantity calculation, tax amounts, filled-only options, company basis, reopen, mobile footer')

if __name__=='__main__':run()
