"""UNC 切换本地路径及待保存子单方向：真实组件、全部 API 隔离模拟。"""
import json
import os
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv('UI_BASE_URL', 'http://localhost:9011')


def run():
    compiled = urlopen(BASE+'/src/views/project/ProjectWorkspace.vue', timeout=30).read().decode()
    def dep(name):
        return json.dumps(re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)', compiled).group(1))
    html = '''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import {createRouter,createWebHistory} from ROUTER;
import Projects from '/src/views/project/translation/ProjectDetails.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const projects=ref();window.form=()=>projects.value.$.setupState.form;
const app=createApp({render:()=>h(Projects,{ref:projects})});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/folder-switch-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE', 'from '+dep('vue')).replace('from ROUTER', 'from '+dep('vue-router'))
    inspections = []
    writes = []
    def api(route):
        path = urlparse(route.request.url).path
        if '/shared-folder/' in path:
            inspections.append(path)
            route.fulfill(status=400, content_type='application/json', body=json.dumps({'detail':'测试 UNC 不可达'}))
            return
        if route.request.method in ('POST','PUT','PATCH','DELETE'):
            writes.append(path)
        if '/business-numbers/reserve' in path:
            data={'token':'00000000-0000-4000-8000-000000000099','number':'TP-261110-999'}
        elif path.endswith('/editor-drafts'):
            data={'payload':None,'revision':0}
        elif path=='/api/projects/languages':
            data=[{'id':str(i),'label':label} for i,label in enumerate(['中文','英语','法语'])]
        elif path.endswith('/page'):
            data={'items':[],'total':0}
        else:
            data=[]
        route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge')
        page=browser.new_page(viewport={'width':1500,'height':1000})
        errors=[]
        page.on('pageerror',lambda err:(errors.append(str(err)),print('PAGE ERROR:',str(err),flush=True)))
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\",\"project_files:read\",\"project_files:write\"]')")
        page.route(re.compile('^'+re.escape(BASE)+r'/api/'),api)
        page.route(BASE+'/folder-switch-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page.goto(BASE+'/folder-switch-test')
        page.get_by_role('button',name='新增项目',exact=True).click()
        dialog=page.locator('.project-editor-dialog:visible')
        expect(dialog).to_be_visible()
        dialog.get_by_role('tab',name='新增母子订单',exact=True).click()
        page.evaluate(r"Object.assign(window.form(),{originalStoragePath:'\\\\old-server\\share\\客户资料',networkFilePath:'\\\\old-server\\share\\客户资料',filePathDraft:{storage_path:'\\\\old-server\\share\\客户资料'},languagePair:'中文→英语',serviceContent:'翻译'})")
        dialog.get_by_role('button',name='读取路径',exact=True).click()
        batch=page.locator('.suborder-batch-create-dialog:visible')
        batch.get_by_role('tab',name='UNC',exact=True).click()
        batch.get_by_placeholder('请输入企业 UNC 共享文件夹路径',exact=True).fill(r'\\old-server\share\客户资料')
        batch.get_by_role('button',name='读取共享文件夹',exact=True).click()
        expect(batch).to_contain_text('测试 UNC 不可达')
        batch.get_by_role('tab',name='本地',exact=True).click()
        page.evaluate("window.showDirectoryPicker=async()=>({name:'客户资料',kind:'directory',async *values(){yield {name:'a.pdf',kind:'file'}}})")
        batch.get_by_role('button',name='选择本地文件夹',exact=True).click()
        root=batch.get_by_placeholder('请粘贴所选根文件夹的完整路径，如 D:\\项目\\客户资料',exact=True)
        expect(root).to_have_value('')
        root.fill(r'D:\本机\客户资料')
        batch.get_by_role('button',name='应用到新增表单',exact=True).click()
        expect(batch).not_to_be_visible()
        for tab in ['项目文件','新增母子订单']:
            dialog.get_by_role('tab',name=tab,exact=True).click()
            page.wait_for_timeout(100)
            assert page.evaluate("[form().originalStoragePath,form().networkFilePath,form().filePathDraft.storage_path]")==[r'D:\本机\客户资料']*3
        dialog.get_by_role('button',name='打开子订单管理（填写字数并汇总）',exact=True).click()
        child=page.locator('.pending-suborder-manager:visible')
        direction=child.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text='翻译方向'))
        expect(direction).to_contain_text('中文→英语')
        direction.locator('.el-tag__close').click()
        direction.locator('input').first.fill('中文 法语')
        page.locator('.language-pair-option__label:visible').filter(has_text='中文→法语').click()
        child.locator('.pending-language-hint').click()
        expect(page.locator('.language-pair-option__label:visible')).to_have_count(0)
        child.get_by_role('button',name='返回母订单',exact=True).click()
        expect(child).not_to_be_visible()
        assert page.evaluate("form().pendingSubOrderDetails['001'].languagePair")=='中文→法语'
        dialog.get_by_role('button',name='打开子订单管理（填写字数并汇总）',exact=True).click()
        expect(direction).to_contain_text('中文→法语')
        expect(child.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text='原文路径')).locator('input')).to_have_value(r'D:\本机\客户资料\a.pdf')
        page.set_viewport_size({'width':800,'height':700})
        expect(child.get_by_role('button',name='返回母订单',exact=True)).to_be_in_viewport()
        child.get_by_role('button',name='返回母订单',exact=True).click()
        assert len(inspections)==1,inspections
        assert not [path for path in writes if '/business-numbers/' not in path and '/editor-drafts' not in path],writes
        assert not errors,errors
        browser.close()
    print('PASS: UNC→本地 / 母单与项目文件及子单路径一致 / 不重读 UNC / 子单方向复制、修改、重开保留 / 小屏固定操作栏；API 全部模拟')


if __name__=='__main__':
    run()
