"""子客户全称选填：五个真实表单入口，仅校验字段，全部接口模拟。"""
import json,os,re
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect

BASE=os.environ.get('UI_BASE_URL','http://localhost:3000')
CLIENT='00000000-0000-4000-8000-000000000010'
SUB='00000000-0000-4000-8000-000000000011'
PROJECT='00000000-0000-4000-8000-000000000012'


def run():
    source=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    def dep(name):return re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',source).group(1)
    html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;import T from '/src/views/project/translation/ProjectDetails.vue';import C from '/src/views/client/Clients.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const view=new URLSearchParams(location.search).get('view');const app=createApp({render:()=>h(view==='client'?C:T,{ref:vm=>window.vm=vm})});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/optional-subclient-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    writes=[]
    def api(route):
        path=urlparse(route.request.url).path
        if route.request.method!='GET' and any(part in path for part in ('/clients/','/projects/','/sub-orders')):writes.append(path)
        if path.endswith('/page'):result={'items':[],'total':0}
        elif path.endswith('/editor-drafts'):result={'payload':None,'revision':0}
        elif path.endswith('/business-numbers/reserve'):result={'token':str(uuid4()),'number':'TP-261110-999'}
        elif path==f'/api/projects/translation/{PROJECT}':result={'id':PROJECT,'order_no':'TP-261110-999','project_name':'项目.docx','source_file_name':'项目.docx'}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1450,'height':1000})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"*\"]')")
        page.route(re.compile(re.escape(BASE)+r'/api/'),api)
        page.route(BASE+'/optional-subclient-test*',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/optional-subclient-test?view=translation')
        page.get_by_role('button',name='新增项目',exact=True).click()
        dialog=page.locator('.project-editor-dialog:visible')
        for tab in ['新增母订单','新增母子订单']:
            dialog.get_by_role('tab',name=tab,exact=True).click()
            page.evaluate("()=>Object.assign(window.vm.$.setupState.form,{subClientShortName:'仅填子客户简称',subClientName:''})")
            field=dialog.locator('[data-field-key="subClientName"]:visible')
            expect(field).not_to_have_class(re.compile(r'\bis-required\b'))
            expect(field.locator('input')).to_have_attribute('placeholder',re.compile('选填'))
            assert page.evaluate("async()=>{const s=window.vm.$.setupState;try{await s.formRef.validateField('subClientName');return true}catch{return false}}")
            expect(field.locator('.el-form-item__error')).to_have_count(0)
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.evaluate('(row)=>window.vm.$.setupState.handleEdit(row,false)',{'id':PROJECT,'orderNo':'TP-261110-999','projectName':'项目.docx','sourceFileName':'项目.docx'})
        expect(dialog).to_be_visible()
        page.evaluate("()=>Object.assign(window.vm.$.setupState.form,{subClientShortName:'编辑时仅填简称',subClientName:''})")
        expect(dialog.locator('[data-field-key="subClientName"]:visible')).not_to_have_class(re.compile(r'\bis-required\b'))
        assert page.evaluate("async()=>{try{await window.vm.$.setupState.formRef.validateField('subClientName');return true}catch{return false}}")
        page.goto(BASE+'/optional-subclient-test?view=client')
        parent={'id':CLIENT,'client_short_name':'母客户','client_name':'母客户全称'}
        for editing in (False,True):
            if editing:
                page.evaluate('(data)=>window.vm.$.setupState.handleEditSub(data.child,data.parent)',{'child':{'id':SUB,'client_name':'','client_short_name':'子客户','sub_client_code':'SC-001'},'parent':parent})
            else:page.evaluate('(parent)=>window.vm.$.setupState.handleAddSubForParent(parent)',parent)
            sub=page.locator('.el-dialog:visible').last
            field=sub.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=re.compile('^客户全称$')))
            expect(field).not_to_have_class(re.compile(r'\bis-required\b'))
            expect(field.locator('input')).to_have_value('')
            assert page.evaluate("async()=>{try{await window.vm.$.setupState.subFormRef.validateField('client_name');return true}catch{return false}}")
            sub.get_by_role('button',name='关闭窗口',exact=True).click();expect(sub).not_to_be_visible()
        assert not writes,writes
        assert not errors,errors
        browser.close()
    print('translation create mother / combined mother-child / edit mother / create child client / edit child client: optional marker and blank validation PASS; no business writes')


if __name__=='__main__':run()
