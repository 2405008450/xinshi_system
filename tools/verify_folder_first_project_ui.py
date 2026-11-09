"""新增项目可先导入目录，原母单基础必填仍可后补；全部接口模拟。"""
import json,re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;import Projects from '/src/views/project/translation/ProjectDetails.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';const app=createApp({render:()=>h(Projects)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/folder-first-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    root={'id':'p-new','order_no':'TP-261107-981','project_name':'客户资料','source_file_name':'客户资料','project_status':'pending_confirmation','network_file_path':r'D:\客户资料','folder_root':True,'updated_at':'2026-11-07T23:00:00+08:00'}
    child={'id':'s-new','parent_project_id':'p-new','sub_order_no':'TP-261107-981.001','sub_project_name':'文档.docx','status':'pending_confirmation'}
    imports=[];other_writes=[]
    def api(route):
        path=urlparse(route.request.url).path;method=route.request.method
        if path.endswith('/business-numbers/reserve'):
            kind=route.request.post_data_json['kind'];data={'token':'00000000-0000-4000-8000-000000000099','number':root['order_no'] if kind=='translation' else root['order_no']+'.002'}
        elif '/business-numbers/' in path:data={'ok':True}
        elif path.endswith('/project-status-sync/snapshot'):data={'items':[]}
        elif path.endswith('/editor-drafts'):data={'payload':None,'revision':0}
        elif path=='/api/sub-orders/folders/import':
            imports.append(route.request.post_data_json)
            data={'project_id':root['id'],'order_no':root['order_no'],'project_name':root['project_name'],'network_file_path':root['network_file_path'],'created_root':True,'created_count':1,'skipped_count':0,'created':[child],'skipped':[]}
        elif path=='/api/projects/translation/p-new':data={**root,'sub_orders':[child]}
        elif path=='/api/sub-orders/project/p-new':data=[child]
        elif path.endswith('/page'):data={'items':[root] if imports else [],'total':1 if imports else 0}
        else:
            if method in ['POST','PUT','PATCH']:other_writes.append((path,route.request.post_data_json))
            data=[]
        route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1550,'height':1100})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(BASE+'/folder-first-test',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda err:errors.append(str(err)));page.goto(BASE+'/folder-first-test')
        page.get_by_role('button',name='新增项目',exact=True).click()
        editor=page.locator('.project-editor-dialog:visible')
        editor.locator('[data-field-key="clientName"] input').fill('稍后补充的客户全称')
        basic_labels=editor.locator('.el-form-item__label').all_text_contents()
        editor.get_by_role('tab',name='新增母子订单',exact=True).click()
        expect(editor.locator('[data-field-key="clientName"] input')).to_have_value('稍后补充的客户全称')
        assert editor.locator('.el-form-item__label').all_text_contents()==basic_labels
        editor.locator('[data-field-key="clientName"] input').fill('合并界面填写的客户')
        editor.get_by_role('tab',name='新增母订单',exact=True).click()
        expect(editor.locator('[data-field-key="clientName"] input')).to_have_value('合并界面填写的客户')
        editor.get_by_role('tab',name='新增母子订单',exact=True).click()
        editor.get_by_role('button',name='读取路径',exact=True).click()
        batch=page.locator('.suborder-batch-create-dialog:visible')
        batch.get_by_role('tab',name='本地',exact=True).click()
        page.evaluate("""()=>{window.showDirectoryPicker=async()=>({name:'客户资料',kind:'directory',async *values(){yield {name:'文档.docx',kind:'file'}}})}""")
        batch.get_by_role('button',name='选择本地文件夹',exact=True).click()
        batch.get_by_placeholder('请粘贴所选根文件夹的完整路径，如 D:\\项目\\客户资料',exact=True).fill(r'D:\客户资料')
        batch.get_by_role('button',name='按目录导入 1 单',exact=True).click()
        expect(batch).not_to_be_visible()
        expect(editor).to_contain_text('编辑项目详情')
        expect(editor.get_by_role('tab',name='新增母子订单',exact=True)).to_have_attribute('aria-selected','true')
        assert len(imports)==1 and imports[0]['parent_project_id'] is None and imports[0]['order_no']=='TP-261107-981',imports
        assert not [item for item in other_writes if not item[0].startswith('/api/editor-drafts')],other_writes
        editor.get_by_role('tab',name='基础信息',exact=True).click()
        expect(editor.locator('[data-field-key="clientName"] input')).to_have_value('合并界面填写的客户')
        expect(editor.locator('[data-field-key="sourceFileName"] input')).to_have_value('客户资料')
        assert not errors,errors;browser.close()
    print('new editor / directory import before validation / reserved mother number / pending root / same editor / existing basic input retained PASS')
if __name__=='__main__':run()
