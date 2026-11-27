"""报告沟通接收范围及动态必填字段回归，业务 API 全部拦截。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
base='http://localhost:3000'
compiled=urlopen(base+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
router_module=re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)',urlopen(base+'/src/views/schedule/components/ReceivedWorkReports.vue').read().decode()).group(1)
rid='11111111-1111-4111-8111-111111111111';key='22222222-2222-4222-8222-222222222222'
person='33333333-3333-4333-8333-333333333333';department='44444444-4444-4444-8444-444444444444'
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Panel from '/src/views/schedule/components/ReportFeedbackPanel.vue';import AppForm from '/src/components/common/AppForm.vue';const app=createApp({render:()=>h(Panel,{reportId:RID,allowNew:true,workItems:[{id:KEY,task_name:'测试项目',progress_content:'测试工作项'}]})});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace('RID',json.dumps(rid)).replace('KEY',json.dumps(key))
writes=[];messages=[]
def api(route):
 path=route.request.url.split('?')[0]
 if path.endswith('/recipients'):data={'ready':True,'people':[{'id':person,'name':'同事甲','username':'alice'}],'departments':[{'id':department,'name':'HR部'}]}
 elif route.request.method=='POST':
  value=route.request.post_data_json;writes.append(value)
  messages.append({'id':str(len(messages)),'item_key':key,'item_snapshot':{'task_name':'测试项目'},'author_name':'发送人','content':value['content'],'created_at':'2026-11-27T10:00:00+08:00'});data=messages[-1]
 elif path.endswith('/feedback-inbox'):data={'ready':True,'items':[{'report_id':rid,'user_name':'测试作者','report_date':'2026-11-26'}],'total':1}
 elif path.endswith('/received'):data={'items':[],'total':0}
 elif path.endswith('/review-directory'):data={'people':[],'departments':[]}
 else:data={'ready':True,'items':messages,'report':{'report_id':rid,'user_name':'测试作者','report_date':'2026-11-26'}}
 route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 context=browser.new_context(viewport={'width':1100,'height':1000},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 context.route(base+'/feedback-recipients-check',lambda r:r.fulfill(content_type='text/html',body=html))
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(base+'/feedback-recipients-check')
 def mode(label):
  page.locator('.report-feedback .el-select').nth(1).locator('.el-select__wrapper').click()
  page.get_by_role('option',name=label,exact=True).click()
 def send(text):
  page.get_by_placeholder('围绕此项工作沟通，可多次来回回复').fill(text)
  page.get_by_role('button',name=re.compile('^发送(反馈|回复)$')).click()
 mode('指定人员（可多选）');send('定向反馈')
 expect(page.get_by_text('请选择接收人员',exact=True)).to_be_visible();assert not writes
 page.locator('.report-feedback .el-select').nth(2).locator('.el-select__wrapper').click();page.get_by_role('option',name='同事甲（alice）',exact=True).click()
 page.locator('.subject').click();send('定向反馈')
 expect(page.locator('.messages')).to_contain_text('定向反馈')
 assert writes[-1]['recipient_mode']=='people' and writes[-1]['recipient_ids']==[person]
 mode('按部门选择')
 page.locator('.report-feedback .el-select').nth(2).locator('.el-select__wrapper').click();page.get_by_role('option',name='HR部',exact=True).click()
 page.locator('.subject').click();send('部门反馈')
 expect(page.locator('.messages')).to_contain_text('部门反馈');assert writes[-1]['department_ids']==[department]
 mode('所有人');send('全员反馈')
 expect(page.locator('.messages')).to_contain_text('全员反馈');assert writes[-1]['recipient_mode']=='all' and not writes[-1]['recipient_ids'] and not writes[-1]['department_ids']
 linked='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createMemoryHistory} from '/node_modules/.vite/deps/vue-router.js';import Reports from '/src/views/schedule/components/ReceivedWorkReports.vue';import AppForm from '/src/components/common/AppForm.vue';const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]});await router.push({path:'/',query:{reportFeedbackId:RID}});const app=createApp({render:()=>h(Reports)});app.use(router);app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace('RID',json.dumps(rid))
 linked=linked.replace('/node_modules/.vite/deps/vue-router.js',router_module)
 context.route(base+'/feedback-link-check',lambda r:r.fulfill(content_type='text/html',body=linked))
 page.goto(base+'/feedback-link-check')
 expect(page.get_by_role('dialog',name='测试作者 · 2026-11-26 工作报告沟通',exact=True)).to_be_visible()
 expect(page.locator('.messages')).to_contain_text('全员反馈')
 assert not errors,errors
 print('PASS: people/department/all scopes, empty recipient validation, hidden fields do not block submission')
 browser.close()
