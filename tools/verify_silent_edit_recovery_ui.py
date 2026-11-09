"""公共编辑窗口：立即关闭恢复、编号更新、多个页签、账号隔离；所有 API 均模拟。"""
import json
import re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE+'/src/components/common/AppForm.vue', timeout=20).read().decode()
    vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
    html = '''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref,reactive} from VUE;
import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';import Center from '/src/components/common/AutoDraftCenter.vue';import {installAutoDrafts} from '/src/utils/autoDrafts.js';
let counter=0;const model=reactive({id:'',orderNo:'',name:'',path:'',notes:''}),visible=ref(false),tab=ref('name');
const open=()=>{Object.assign(model,{id:'',orderNo:'NEW-'+(++counter),name:'',path:'',notes:''});tab.value='name';visible.value=true};
window.testModel=model;
const app=createApp({render:()=>h('div',{},[h(Center),h('button',{onClick:open},'打开'),h(Dialog,{modelValue:visible.value,'onUpdate:modelValue':v=>visible.value=v,title:'新增业务记录',destroyOnClose:true,width:'min(800px, calc(100vw - 32px))'},()=>h(AppForm,{model},()=>[
h('div',{},['name','path','notes'].map(key=>h('button',{type:'button',onClick:()=>tab.value=key},key))),
...['name','path','notes'].map(key=>h('div',{style:{display:tab.value===key?'block':'none'}},[h('label',{},[key,h('input',{'aria-label':key,value:model[key],onInput:e=>model[key]=e.target.value})])]))
]))])});installAutoDrafts(app);app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('from VUE', 'from '+json.dumps(vue))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        page = browser.new_page(viewport={'width':1100,'height':850})
        page.add_init_script("if(!localStorage.getItem('user_id'))localStorage.setItem('user_id','account-a')")
        page.route(BASE+'/silent-edit-test',lambda r:r.fulfill(content_type='text/html',body=html))
        def api(route):
            if route.request.method=='GET': result={'payload':None,'revision':0}
            else: result=[{**item,'revision':item['revision']+1} for item in route.request.post_data_json['drafts']]
            route.fulfill(content_type='application/json',body=json.dumps(result))
        page.route(re.compile(r'^http://localhost:3000/api/'),api)
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/silent-edit-test')
        dialog=page.locator('.el-dialog:visible')
        def open_dialog(): page.get_by_role('button',name='打开',exact=True).click();expect(dialog).to_be_visible()
        def close_dialog(): dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        open_dialog()
        for key,value in [('name','甲的名称'),('path','D:\\甲的路径'),('notes','甲的说明')]:
            dialog.get_by_role('button',name=key,exact=True).click();dialog.get_by_role('textbox',name=key,exact=True).fill(value)
        old_number=page.evaluate('window.testModel.orderNo')
        close_dialog()
        open_dialog()
        expect(dialog.get_by_role('textbox',name='name',exact=True)).to_have_value('甲的名称')
        assert page.evaluate('window.testModel.orderNo')!=old_number
        for key,value in [('path','D:\\甲的路径'),('notes','甲的说明')]:
            dialog.get_by_role('button',name=key,exact=True).click();expect(dialog.get_by_role('textbox',name=key,exact=True)).to_have_value(value)
        close_dialog()
        page.evaluate("window.dispatchEvent(new Event('auth-session-clearing'));localStorage.setItem('user_id','account-b')")
        page.reload();open_dialog()
        expect(dialog.get_by_role('textbox',name='name',exact=True)).to_have_value('')
        dialog.get_by_role('textbox',name='name',exact=True).fill('乙的名称');close_dialog()
        page.evaluate("window.dispatchEvent(new Event('auth-session-clearing'));localStorage.setItem('user_id','account-a')")
        page.reload();open_dialog()
        expect(dialog.get_by_role('textbox',name='name',exact=True)).to_have_value('甲的名称')
        expect(page.locator('.el-message-box,.auto-draft-status')).to_have_count(0)
        assert not errors, errors
        browser.close()
    print('silent restore / immediate close / all tab values / fresh number / two-account isolation PASS')


if __name__=='__main__': run()
