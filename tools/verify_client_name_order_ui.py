"""客户简称顺序和全称回填：真实表单，全部 API 模拟，不保存客户或项目。"""
import json,re,os
from urllib.parse import urlparse,parse_qs
from urllib.request import urlopen
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect

BASE=os.environ.get('UI_BASE_URL','http://localhost:3000')
CLIENT='00000000-0000-4000-8000-000000000010'
SUB='00000000-0000-4000-8000-000000000011'
LIB={'id':CLIENT,'client_code':'CL-TEST-001','client_short_name':'测试客户','client_name':'测试客户有限公司','customer_type':'企业客户','contact_people':[],
     'sub_clients':[{'id':SUB,'parent_client_id':CLIENT,'sub_client_code':'SC-TEST-001','client_short_name':'华南分公司','client_name':'测试客户华南分公司'}]}


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    def dep(name):return re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;import C from '/src/views/client/Clients.vue';import Q from '/src/views/client/Consultations.vue';import V from '/src/views/client/ClientContacts.vue';import S from '/src/views/client/SubsidiaryClients.vue';import T from '/src/views/project/translation/ProjectDetails.vue';import I from '/src/views/project/interpretation/InterpretationProjectDetails.vue';import A from '/src/views/project/AnnotationProjects.vue';import R from '/src/views/project/RecruitmentProjects.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const view=new URLSearchParams(location.search).get('view');const app=createApp({render:()=>h({client:C,consultation:Q,visit:V,subsidiary:S,translation:T,interpretation:I,annotation:A,recruitment:R}[view],{ref:vm=>window.testVm=vm})});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/client-name-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    mutations=[]
    def api(route):
        path=urlparse(route.request.url).path;query=parse_qs(urlparse(route.request.url).query)
        if route.request.method in ('POST','PUT','PATCH','DELETE') and not any(value in path for value in ('editor-drafts','business-numbers','work-reports')):mutations.append(path)
        if path=='/api/clients/':
            keyword=query.get('client_short_name',[''])[0]
            result=[LIB] if not keyword or all(term.lower() in LIB['client_short_name'].lower() for term in keyword.split()) else []
        elif path==f'/api/clients/{CLIENT}':result=LIB
        elif path.endswith('/page'):result={'items':[],'total':0}
        elif path.endswith('/count'):result=0
        elif path.endswith('/editor-drafts'):result={'payload':None,'revision':0}
        elif path.endswith('/editor-drafts/batch'):result=[]
        elif path.endswith('/business-numbers/reserve'):result={'token':str(uuid4()),'number':'CL-261110-999'}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1500,'height':1000})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"*\"]')")
        page.route(re.compile(re.escape(BASE)+r'/api/'),api)
        page.route(BASE+'/client-name-test*',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        def item(dialog,label):return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=re.compile('^'+label+'$'))).first
        def check(dialog,short='客户简称',full='客户全称',short_value='测试客户',full_value='测试客户有限公司'):
            short_item,full_item=item(dialog,short),item(dialog,full)
            assert short_item.evaluate('(el,other)=>!!(el.compareDocumentPosition(other)&Node.DOCUMENT_POSITION_FOLLOWING)',full_item.element_handle())
            field=short_item.locator('input').first
            field.fill(short_value)
            option=page.locator('.el-autocomplete-suggestion:visible li').filter(has_text=short_value).first
            expect(option).to_be_visible(timeout=8000);option.click()
            expect(full_item.locator('input').first).to_have_value(full_value)
            expect(field).to_have_value(short_value)
        for view,button in [('client','新增客户'),('consultation','新增咨询'),('visit','新增回访记录'),('subsidiary','新增子公司客户'),('translation','新增项目'),('interpretation','新增口译项目'),('annotation','新增标注项目'),('recruitment','新增招聘项目')]:
            page.goto(BASE+'/client-name-test?view='+view)
            page.get_by_role('button',name=button,exact=True).click()
            dialog=page.locator('.el-dialog:visible').first
            expect(dialog).to_be_visible()
            check(dialog)
            if view=='consultation':
                page.evaluate("()=>window.testVm.$.setupState.form.consultation_type='simple'")
                check(dialog)
            if view=='translation':
                page.evaluate("()=>Object.assign(window.testVm.$.setupState.form,{subClientId:'00000000-0000-4000-8000-000000000011',subClientShortName:'华南分公司',subClientName:'待更新全称'})")
                check(dialog,'子客户','子客户全称','华南分公司','测试客户华南分公司')
                dialog.get_by_role('tab',name='新增母子订单',exact=True).click();check(dialog)
            if view=='client':
                # 同一管理页面的子客户新增/编辑窗口，限定在当前母客户内联想。
                dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
                page.evaluate('(parent)=>window.testVm.$.setupState.handleAddSubForParent(parent)',LIB)
                sub_dialog=page.locator('.el-dialog:visible').last
                check(sub_dialog,short_value='华南分公司',full_value='测试客户华南分公司')
            assert not errors,(view,errors)
        assert not mutations,mutations
        browser.close()
    print('client / child client / consultation normal-simple / visit / subsidiary / translation mother-child / interpretation / annotation / recruitment: order and fullname autofill PASS; no business writes')


if __name__=='__main__':run()
