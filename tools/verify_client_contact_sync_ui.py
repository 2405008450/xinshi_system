"""客户管理维护多联系人、项目选择联系人与个人默认；全部接口模拟。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import expect,sync_playwright

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import {createRouter,createWebHistory} from ROUTER;import Clients from '/src/views/client/Clients.vue';import Projects from '/src/views/project/translation/ProjectDetails.vue';import Finance from '/src/views/project/translation/CustomerFinance.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const mode=ref('clients');const app=createApp({render:()=>h('div',{},[h('button',{onClick:()=>mode.value=mode.value==='clients'?'projects':mode.value==='projects'?'finance':'clients'},'切换模块'),h(mode.value==='clients'?Clients:mode.value==='projects'?Projects:Finance)])});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/contact-sync-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    client={'id':'c1','client_code':'CL-TEST','client_name':'广州测试有限公司','client_short_name':'广州测试','customer_type':'企业客户','client_manager':'张先生','manager_contact':'13800000000','contact_names':['张先生','李女士'],'sub_clients':[],'updated_at':'2026-11-07T12:00:00+08:00'}
    writes=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/clients/c1':
            if route.request.method=='PUT':writes.append(route.request.post_data_json);client.update(route.request.post_data_json)
            result=client
        elif path=='/api/clients/page':result={'items':[client],'total':1}
        elif path in ['/api/clients/','/api/clients/options']:result=[client]
        elif path=='/api/client-contact-people':result={'contact_names':client['contact_names']}
        elif path=='/api/translation-customer-finance/page':result={'items':[{'id':'p1','client_id':'c1','client_short_name':'广州测试','client_manager':'测试经理','order_no':'TP-261107-999','project_name':'测试.docx','project_status':'confirmed','language_pair':'中英','children':[],'prices':[],'word_count_matrix':{'company':{'words':1}}}],'total':1,'client_subtotals':[]}
        elif path.startswith('/api/translation-statement-workspaces/c1'):result={'client_id':'c1','client_name':'广州测试','documents':[],'payload':{'tasks':{}},'months':[],'pending':[],'available_months':[],'revision':0,'capabilities':{}}
        elif path.endswith('/statement-preference'):result={'statement_default':'required','revision':0}
        elif path.endswith('/page'):result={'items':[],'total':0}
        elif path=='/api/business-numbers/reserve':result={'token':'00000000-0000-4000-8000-000000000099','number':'TP-261107-999'}
        elif path.startswith('/api/business-numbers/'):result={'ok':True}
        elif path.endswith('/editor-drafts'):result={'payload':None,'revision':0}
        elif path.endswith('/sub_clients'):result=[]
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1500,'height':1000})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\",\"clients:read\",\"clients:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(BASE+'/contact-sync-test',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
        page.goto(BASE+'/contact-sync-test');page.get_by_role('button',name='编辑',exact=True).first.click()
        dialog=page.locator('.el-dialog:visible');expect(dialog.get_by_role('textbox',name='客户联系人1',exact=True)).to_have_value('张先生');expect(dialog.get_by_role('textbox',name='客户联系人2',exact=True)).to_have_value('李女士')
        dialog.get_by_role('button',name='添加客户联系人',exact=True).click();dialog.get_by_role('button',name='确定',exact=True).click();expect(dialog.get_by_role('textbox',name='客户联系人3',exact=True)).to_be_focused();assert not writes
        dialog.get_by_role('textbox',name='客户联系人3',exact=True).fill('赵先生')
        dialog.get_by_role('button',name='确定',exact=True).click();expect(dialog).not_to_be_visible();assert writes[0]['contact_names']==['张先生','李女士','赵先生'],writes
        page.get_by_role('button',name='切换模块',exact=True).click();page.get_by_role('button',name='新增项目',exact=True).click()
        dialog=page.locator('.project-editor-dialog:visible')
        short=dialog.locator('[data-field-key="clientShortName"] input');short.fill('广州测试')
        page.locator('.el-autocomplete-suggestion:visible').get_by_text('广州测试',exact=True).click()
        contact=dialog.locator('[data-field-key="contactName"]');expect(contact).to_have_class(re.compile('is-required'))
        contact.locator('input').click();choices=page.locator('.el-autocomplete-suggestion:visible').filter(has_text='赵先生')
        expect(choices).to_contain_text('赵先生');choices.get_by_text('赵先生',exact=True).click();expect(contact.locator('input')).to_have_value('赵先生')
        expect(dialog.locator('.el-form-item__label',has_text='客户经理联系方式')).to_have_count(0)
        contact.locator('input').fill('新增项目联系人');expect(contact.locator('input')).to_have_value('新增项目联系人')
        # 选择个人客户类型时按简称自动填写联系人。
        type_item=dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=re.compile('^客户类型$')))
        type_item.locator('.el-select').click();page.get_by_role('option',name='个人客户',exact=True).click()
        expect(contact.locator('input')).to_have_value('广州测试')
        dialog.get_by_role('button',name='价格与付款',exact=True).first.click()
        finance_dialog=page.locator('.customer-finance-dialog:visible')
        statement_choice=finance_dialog.locator('[data-field-key="statementRequired"] .el-checkbox')
        for _ in range(2):
            statement_choice.click();expect(page.locator('.customer-statement-dialog:visible')).to_have_count(0)
        finance_dialog.locator('[data-field-key="quotationRequired"] .el-checkbox').click();expect(page.locator('.el-dialog:visible')).to_have_count(2)
        finance_dialog.get_by_role('button',name='打开对账单',exact=True).click()
        statement=page.locator('.customer-statement-dialog:visible')
        expect(statement.locator('.statement-client-context')).to_have_text('广州测试 · 2026-11')
        expect(statement.locator('.statement-workspace')).to_be_visible()
        statement.get_by_role('button',name='关闭',exact=True).click();expect(statement).not_to_be_visible()
        finance_dialog.locator('.el-dialog__footer').get_by_role('button',name='取消',exact=True).click();page.get_by_role('button',name='放弃修改',exact=True).click();expect(finance_dialog).not_to_be_visible()
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='切换模块',exact=True).click()
        expect(page.locator('.customer-finance').first).to_be_visible()
        picker=page.locator('.finance-manager-dialog:visible')
        if picker.count():picker.get_by_role('button',name='取消',exact=True).click()
        page.locator('.finance-search').get_by_role('button',name='查询',exact=True).click()
        expect(page.locator('.finance-project-table')).to_contain_text('TP-261107-999')
        expand=page.get_by_role('button',name='展开操作栏',exact=True)
        if expand.count():expand.click()
        page.locator('.el-table__body').get_by_role('button',name='对账单',exact=True).first.click()
        expect(statement.locator('.statement-client-context')).to_have_text('广州测试 · 2026-11')
        expect(statement.locator('.statement-workspace')).to_be_visible()
        assert not errors,errors
        browser.close()
    print('client multi-contact editor / saved options in project / required field / personal automatic name / checkbox no popup / same row statement workspace PASS')


if __name__=='__main__':run()
