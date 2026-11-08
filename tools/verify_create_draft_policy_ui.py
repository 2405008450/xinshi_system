"""验证新增草稿禁用策略：即使误调用 beginDraft('create')，也不恢复或保存。"""
import json
import re
from urllib.request import urlopen
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE+'/src/components/common/AppForm.vue', timeout=20).read().decode()
    vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
    html = '''<!doctype html><meta charset="utf-8"><div id="app"></div><script type="module">
import {createApp,h,reactive,ref} from VUE;
import AppForm from '/src/components/common/AppForm.vue';
import Input from '/src/components/common/ScreenshotInput.vue';
import {useFormDraft} from '/src/composables/useFormDraft.js';
import {installAutoDrafts} from '/src/utils/autoDrafts.js';
const app=createApp({setup(){
 const form=reactive({id:'',name:''}),mode=ref('create');
 const {beginDraft,pauseDraft}=useFormDraft({namespace:'create-policy',form,createDefault:()=>({id:'',name:''}),createDrafts:false});
 async function create(){pauseDraft();mode.value='create';Object.assign(form,{id:'',name:''});await beginDraft('create')}
 async function edit(){pauseDraft();mode.value='edit';Object.assign(form,{id:'r1',name:''});await beginDraft('edit:r1')}
 return()=>h('div',{'data-auto-draft':mode.value==='create'?'off':undefined},[
  h(AppForm,{model:form},()=>h(Input,{modelValue:form.name,'onUpdate:modelValue':value=>form.name=value,'aria-label':'测试名称'})),
  h('button',{onClick:create},'新增'),h('button',{onClick:edit},'编辑')]);
}});installAutoDrafts(app);app.mount('#app');</script>'''.replace('from VUE', 'from '+json.dumps(vue))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge')
        context=browser.new_context()
        context.add_init_script("""localStorage.setItem('user_id','qa');localStorage.setItem('form-drafts:create-policy:qa',JSON.stringify({create:{savedAt:new Date().toISOString(),form:{id:'old',name:'之前新增的内容'}},'edit:r1':{savedAt:new Date().toISOString(),form:{id:'r1',name:'编辑草稿仍可恢复'}}}));""")
        calls=[]
        def api(route):
            parsed=urlparse(route.request.url)
            calls.append((route.request.method,parsed.path,parse_qs(parsed.query)))
            route.fulfill(content_type='application/json',body='{"payload":null,"revision":0}')
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/create-policy-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/create-policy-test')
        name=page.get_by_role('textbox',name='测试名称')
        page.get_by_role('button',name='新增',exact=True).click();expect(name).to_have_value('')
        name.fill('本次未保存');page.wait_for_timeout(600)
        assert page.evaluate("JSON.parse(localStorage.getItem('form-drafts:create-policy:qa')).create.form.name")=='之前新增的内容'
        page.get_by_role('button',name='新增',exact=True).click();expect(name).to_have_value('')
        page.get_by_role('button',name='编辑',exact=True).click();expect(name).to_have_value('编辑草稿仍可恢复')
        page.wait_for_timeout(300)
        assert any(query.get('key')==['edit:r1'] for _,_,query in calls)
        assert not any(query.get('key')==['create'] for _,_,query in calls)
        page.get_by_role('button',name='新增',exact=True).click();expect(name).to_have_value('')
        assert not errors,errors
        browser.close()
    print('create restoration/writes blocked; explicit create calls safe; edit drafts preserved PASS')


if __name__=='__main__':
    run()
