import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode();vue=re.search(r'from [\"\']([^\"\']*/vue\.js[^\"\']*)',compiled).group(1)
html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import Batch from '/src/views/project/translation/components/SubOrderBatchCreateDialog.vue';import AppForm from '/src/components/common/AppForm.vue';
const visible=ref(false);const app=createApp({render:()=>h('div',{},[h('button',{onClick:()=>visible.value=true},'打开'),h(Batch,{modelValue:visible.value,'onUpdate:modelValue':v=>visible.value=v,initialMode:'localfiles',project:{orderNo:'TP-261108-999',originalStoragePath:'D:\\\\已登记\\\\客户资料'}})])});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1400,'height':950});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.route(re.compile(r'^http://localhost:3000/api/'),lambda r:r.fulfill(content_type='application/json',body='[]'))
 page.route(BASE+'/root-path-test',lambda r:r.fulfill(content_type='text/html',body=html));page.goto(BASE+'/root-path-test')
 page.evaluate("window.showDirectoryPicker=async()=>({name:'客户资料',kind:'directory',async *values(){yield {name:'a.pdf',kind:'file'}}})")
 page.get_by_role('button',name='打开',exact=True).click();dialog=page.locator('.suborder-batch-create-dialog:visible');expect(dialog).to_be_visible()
 select=dialog.get_by_role('button',name='选择本地文件夹',exact=True);select.click()
 field=dialog.get_by_placeholder('请粘贴所选根文件夹的完整路径，如 D:\\项目\\客户资料',exact=True)
 expect(field).to_have_value('D:\\已登记\\客户资料');field.fill('E:\\人工修改\\客户资料');select.click();expect(field).to_have_value('E:\\人工修改\\客户资料')
 comparison=dialog.locator('.folder-root-comparison:visible')
 field.fill('E:\\人工修改\\旧资料')
 expect(comparison).to_contain_text('所选名称：客户资料')
 expect(comparison).to_contain_text('路径末尾：旧资料')
 expect(dialog.get_by_role('button',name='应用到新增表单',exact=True)).to_be_disabled()
 field.fill('"E:\\人工修改\\客户资料"')
 expect(dialog.get_by_role('button',name='应用到新增表单',exact=True)).to_be_enabled()
 page.evaluate("window.xinshiDesktop={chooseTranslationFolder:async()=>({rootPath:'G:\\\\真实目录\\\\客户资料',entries:[{relativePath:'客户资料',files:['a.pdf']}]})}")
 select.click();expect(field).to_have_value('G:\\真实目录\\客户资料');field.fill('G:\\修改后\\客户资料');expect(field).to_have_value('G:\\修改后\\客户资料')
 expect(comparison).to_contain_text('G:\\真实目录\\客户资料')
 expect(comparison).to_contain_text('G:\\修改后\\客户资料')
 comparison.get_by_role('button',name='使用所选完整路径').click()
 expect(field).to_have_value('G:\\真实目录\\客户资料')
 page.evaluate("delete window.xinshiDesktop;window.showDirectoryPicker=async()=>({name:'另一个文件夹',kind:'directory',async *values(){yield {name:'b.pdf',kind:'file'}}})")
 select.click();expect(field).to_have_value('');expect(dialog).to_contain_text('浏览器未提供完整路径')
 assert not errors,errors
 browser.close()
print('registered-path autofill / editable override / native absolute path / per-computer browser fallback / no guessed path PASS')
