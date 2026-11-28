"""工作报告客户选择、工作量只读表单与项目路径；全部 API 模拟。"""
import json
import re
from urllib.request import urlopen
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import {createRouter,createMemoryHistory} from '/node_modules/.vite/deps/vue-router.js';
import Editor from '/src/views/schedule/components/DailyReportEditor.vue';import Link from '/src/views/schedule/components/ReportItemLink.vue';
import Snapshot from '/src/views/schedule/components/ReportSnapshot.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const initial=[{source_type:'manual',task_type:'项目工作',task_name:'',progress_content:'整理资料',duration_minutes:30,display_metadata:{report_types:['笔译项目'],quantity:1,quantity_unit:'份'}},{source_type:'manual',task_type:'非项目工作',task_name:'',progress_content:'拜访客户',duration_minutes:30,display_metadata:{report_types:['非项目工作::行政工作'],quantity:1,quantity_unit:'次'}}];
const app=createApp({setup(){const editor=ref(),rows=ref(JSON.parse(localStorage.getItem('qa.report')||'null')||initial),saved=ref(null);window.save=()=>{saved.value=editor.value.getRows();localStorage.setItem('qa.report',JSON.stringify(saved.value))};window.readRows=()=>editor.value.getRows();return()=>[h(Editor,{ref:editor,rows:rows.value,editable:true}),h(Link,{row:{display_metadata:{project_id:'p1',order_no:'TP-001',selected_project_type:'笔译项目'}},kind:'project',text:'查看项目路径测试'}),saved.value?h(Snapshot,{report:{items:saved.value}}):null]}});
app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
requests=[]
def api(route):
 url=urlparse(route.request.url);requests.append((route.request.method,url.path,parse_qs(url.query)))
 if url.path.endswith('/project-search'):data={'items':[{'id':'p1','order_no':'TP-001','project_name':'项目测试','project_type':'笔译项目','client_name':'项目客户全称','client_short_name':'项目客户'}],'total':1}
 elif url.path.endswith('/client-options'):data=[{'id':'c2','name':'非项目客户全称'}]
 elif url.path.endswith('/projects/translation/p1'):data={'id':'p1','network_file_path':r'\\mock\项目','order_no':'TP-001','word_count_matrix':{'company':{'chars_no_spaces':5450}}}
 elif url.path.endswith('/project-files/project/p1'):data=[{'storage_path':r'\\mock\原文','translation_path':r'\\mock\译文'}]
 elif '/word-count-matrices/' in url.path:data={'company':{'chars_no_spaces':5450},'customer':{},'translators':[]}
 else:data=[]
 route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))

with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 context=browser.new_context(viewport={'width':1800,'height':1100},service_workers='block')
 context.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_permissions',JSON.stringify(['reports:read','projects:read','project_files:read']));")
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 context.route(BASE+'/report-clients-paths-check',lambda route:route.fulfill(content_type='text/html',body=html))
 page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto(BASE+'/report-clients-paths-check')
 page.get_by_role('button',name='选择项目',exact=True).click()
 page.locator('.report-project-picker:visible').get_by_role('button',name='选定',exact=True).click()
 expect(page.get_by_role('textbox',name='第1行客户名',exact=True)).to_have_value('项目客户全称')
 assert page.get_by_role('textbox',name='第1行客户名',exact=True).get_attribute('readonly') is not None
 selector=page.locator('.report-client-select .el-select__wrapper').last
 selector.click()
 page.get_by_role('option',name='非项目客户全称',exact=True).click()
 data=page.evaluate('window.readRows()')
 assert data[0]['display_metadata']['client_name']=='项目客户全称'
 assert data[1]['display_metadata']['client_id']=='c2' and not data[1]['display_metadata'].get('order_no')
 page.evaluate('window.save()')
 expect(page.locator('.report-snapshot')).to_contain_text('客户名')
 expect(page.locator('.report-snapshot')).to_contain_text('非项目客户全称')
 page.reload()
 expect(page.get_by_role('textbox',name='第1行客户名',exact=True)).to_have_value('项目客户全称')
 expect(page.locator('.report-client-select')).to_contain_text('非项目客户全称')
 page.get_by_role('button',name='查看项目：查看项目路径测试',exact=True).click()
 panel=page.locator('.report-item-detail-popover:visible')
 expect(panel).to_contain_text(r'\\mock\原文')
 expect(panel).to_contain_text(r'\\mock\项目')
 panel.get_by_role('button',name='查看工作量统计表单',exact=True).click()
 matrix=page.locator('.word-count-matrix-popper:visible')
 expect(matrix).to_contain_text('只读查看')
 expect(matrix.locator('input').first).to_be_disabled()
 expect(matrix.get_by_role('button',name='保存',exact=True)).to_have_count(0)
 assert not [method for method,path,_ in requests if method not in ('GET','OPTIONS')],requests
 assert not errors,errors
 assert any(params.get('full_name')==['true'] for _,path,params in requests if path.endswith('/client-options'))
 browser.close()
print('PASS: project client autofill, nonproject client selection, save/reopen, report snapshot, project paths and readonly workload')
