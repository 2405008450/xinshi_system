import json,re
from urllib.request import urlopen
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode()
vue=re.search(r'from [\"\']([^\"\']*/vue\.js[^\"\']*)',compiled).group(1)
html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import Batch from '/src/views/project/translation/components/SubOrderBatchCreateDialog.vue';import AppForm from '/src/components/common/AppForm.vue';
const visible=ref(false),mode=ref('quantity');const app=createApp({render:()=>h('div',{},[...['quantity','unc','filenames'].map(value=>h('button',{onClick:()=>{mode.value=value;visible.value=true}},value)),h(Batch,{modelValue:visible.value,'onUpdate:modelValue':v=>visible.value=v,initialMode:mode.value,project:{orderNo:'TP-261108-999',projectName:'测试.docx'}})])});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
with sync_playwright() as p:
 b=p.chromium.launch(channel='msedge');page=b.new_page(viewport={'width':1400,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 def api(route):
  path=route.request.url
  if '/import-list/parse' in path:
   assert 'multipart/form-data; boundary=' in route.request.headers['content-type']
   data={'kind':'workbook','sheets':[{'name':'清单','rows':[['文件名','路径'],['a.pdf','D:\\项目\\资料']]}]}
  elif '/import-list/preview' in path:
   data={'kind':'tree','root_path':'D:\\项目','entries':[{'relative_path':'项目','files':[]},{'relative_path':'项目/资料','files':['a.pdf']}],'warnings':[],'empty_folders':[],'order_count':2}
  else:data=[]
  route.fulfill(content_type='application/json',body=json.dumps(data))
 page.route(re.compile(r'^http://localhost:3000/api/'),api)
 page.route(BASE+'/workflow-test',lambda r:r.fulfill(content_type='text/html',body=html))
 page.goto(BASE+'/workflow-test');page.get_by_role('button',name='quantity',exact=True).click();dialog=page.locator('.suborder-batch-create-dialog:visible')
 expect(dialog).to_contain_text('按数量批量新增');expect(dialog.get_by_role('tab')).to_have_count(0);expect(dialog).to_contain_text('生成数量');dialog.get_by_role('button',name='取消',exact=True).click()
 page.get_by_role('button',name='unc',exact=True).click();expect(dialog.get_by_role('tab')).to_have_count(2);expect(dialog.get_by_role('tab',name='UNC',exact=True)).to_be_visible();dialog.get_by_role('tab',name='本地',exact=True).click();expect(dialog.get_by_role('button',name='选择本地文件夹',exact=True)).to_be_visible();dialog.get_by_role('button',name='取消',exact=True).click()
 page.get_by_role('button',name='filenames',exact=True).click();expect(dialog.get_by_role('tab')).to_have_count(0);expect(dialog).to_contain_text('复制/文件导入')
 dialog.locator('.suborder-list-import input[type=file]').first.set_input_files({'name':'清单.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':b'fake-mocked'})
 expect(dialog).to_contain_text('工作表');expect(dialog).to_contain_text('a.pdf');dialog.get_by_role('button',name='分析文件与路径层级',exact=True).click();expect(dialog.get_by_role('button',name='确认导入 2 单',exact=True)).to_be_enabled();expect(dialog).to_contain_text('1级子订单')
 dialog.get_by_placeholder('例如 D:\\客户资料；相对路径清单需填写完整根路径',exact=True).fill('D:\\其他');expect(dialog.get_by_role('button',name='确认导入 0 单',exact=True)).to_be_disabled()
 assert not errors,errors
 b.close()
print('quantity / UNC-local tabs / copy-file workbook / multipart / hierarchy preview / invalidation PASS')
