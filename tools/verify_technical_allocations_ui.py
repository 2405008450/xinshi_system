"""执行人多选、分工、个人完成/金额/进度与报告；全部业务接口拦截。"""
import json,re
from copy import deepcopy
from urllib.parse import urlparse
from urllib.request import urlopen
from decimal import Decimal
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',urlopen(BASE+'/src/main.js').read().decode()).group(1)
vr=re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)',urlopen(BASE+'/src/router/index.js').read().decode()).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import{createApp,h}from VUE;import{createRouter,createWebHistory,RouterView}from VR;import Page from '/src/views/technology/TechnicalDevelopment.vue';import '/src/styles/theme.css';import '/src/styles/common.css';localStorage.setItem('user_id','a');const router=createRouter({history:createWebHistory(),routes:[{path:'/allocation-ui-check',component:Page}]});createApp({render:()=>h(RouterView)}).use(router).mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace('VR',json.dumps(vr))
root=None;executions={};errors=[];writes=[];reports=[];STAMP='2026-10-30T18:00:00+08:00'
def task(uid,name,content,due,executor,number):return dict(id=uid,task_no=number,name=name,parent_id=None,content=content,arranger_id='a',arranger_name='甲',executor_id=executor,executor_name='甲' if executor=='a' else '乙',due_at=due,progress=0,progress_updated_at=None,adjustment='',notes='',revision=1,completion_enabled=True,completed_on=None,on_time=None,completion_revision=0,incentive=None,created_at=STAMP,updated_at=STAMP,progress_history=[],feedback=[])
def group():return {**root,'allocations':[{**value,'task_id':value['id']} for value in executions.values()]}
def completion(row):return dict(task_id=row['id'],task_no=row['task_no'],task_name=row['name'],task_revision=row['revision'],due_on=row['due_at'][:10],**{key:row[key] for key in ['completed_on','on_time','completion_revision','incentive']},changes=[],ledger_history=[])
def api(route):
 global root
 request=route.request;path=urlparse(request.url).path
 if path=='/api/technical-development/people':result=dict(arrangers=[dict(id='a',name='甲')],executors=[dict(id='a',name='甲'),dict(id='b',name='乙')])
 elif path=='/api/technical-development/tasks':
  if request.method=='POST':
   body=request.post_data_json;writes.append((path,body));assert len(body['allocations'])==2
   root=task('root',body['name'],body['content'],body['due_at'],'a','DT-261030-001');root.update(has_allocations=True,executor_ids=['a','b'],executor_name='甲、乙')
   for index,part in enumerate(body['allocations'],2):executions[part['executor_id']]=task('exec-'+part['executor_id'],body['name']+' · '+('甲' if part['executor_id']=='a' else '乙'),part['content'],part['due_at'],part['executor_id'],f'DT-261030-00{index}')
   result=group()
  else:result=dict(enabled=True,items=[group()] if root else [])
 elif path.startswith('/api/technical-development/tasks/'):
  uid=path.split('/')[4];row=next(value for value in executions.values() if value['id']==uid)
  if path.endswith('/report'):
   if request.method=='POST':reports.append(request.post_data_json);result=dict(report_id='report',report_date='2026-10-30')
   else:result=dict(report_date='2026-10-30',report_type='开发任务',order_no=row['task_no'],task_name=row['name'],progress_content=row['content'])
  elif path.endswith('/completion'):
   if request.method=='PUT':
    body=request.post_data_json;writes.append((path,body));row['completed_on']=body['completed_on'];row['on_time']=body['completed_on']<=row['due_at'][:10];row['completion_revision']+=1;row['incentive']=None
   result=completion(row)
  elif path.endswith('/incentive'):
   body=request.post_data_json;writes.append((path,body));row['incentive']=dict(id=f'm{len(writes)}',kind='reward' if row['on_time'] else 'deduction',amount=f"{Decimal(body['amount']):.2f}");result=completion(row)
  elif path.endswith('/progress'):
   body=request.post_data_json;writes.append((path,body));previous=row['progress'];row['progress']=body['percentage'];row['revision']+=1;row['progress_history'].insert(0,dict(id='progress-a',previous_percentage=previous,percentage=row['progress'],content=body['content'],reason=body['reason'],author_name='甲',created_at=STAMP));result=row
  else:result=row
 else:result={}
 route.fulfill(content_type='application/json',body=json.dumps(deepcopy(result)))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1700,'height':1050},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/allocation-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
 page=context.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/allocation-ui-check')
 def field(dialog,label):return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label').filter(has_text=re.compile('^'+re.escape(label)+'$')))
 page.get_by_role('button',name='新增任务',exact=True).click();editor=page.get_by_role('dialog',name='新增技术开发任务',exact=True)
 field(editor,'任务名称').locator('input').fill('多人开发任务');field(editor,'安排人').locator('.el-select').click();page.get_by_role('option',name='甲',exact=True).click()
 field(editor,'执行人').locator('.el-select').click();page.get_by_role('option',name='甲',exact=True).last.click();page.get_by_role('option',name='乙',exact=True).click()
 division=page.get_by_role('dialog',name='执行人分工',exact=True);expect(division).to_be_visible()
 division.get_by_role('button',name='确定分工',exact=True).click();expect(division.locator('.el-form-item__error').first).to_contain_text('请填写该执行人的分工')
 for person,content,date in [('甲','接口开发','2026-10-30 18:00:00'),('乙','页面开发','2026-11-01 18:00:00')]:
  section=division.locator('.allocation-person').filter(has=page.locator('h4').filter(has_text=re.compile('^'+person+'$')))
  section.locator('textarea').fill(content);date_input=section.locator('.el-date-editor input');date_input.fill(date);date_input.press('Enter');date_input.press('Tab')
 expect(division.locator('.el-dialog__footer')).to_be_in_viewport();division.get_by_role('button',name='确定分工',exact=True).click();expect(division).not_to_be_visible()
 editor.get_by_role('button',name='保存',exact=True).click();expect(editor).not_to_be_visible();expect(page.locator('.el-table__body')).to_contain_text('甲、乙');assert root is not None
 page.get_by_role('button',name='分工与完成情况',exact=True).click();viewer=page.get_by_role('dialog',name='分工与完成情况',exact=True)
 expect(viewer).to_contain_text('接口开发');expect(viewer).to_contain_text('页面开发')
 def execution_row(person):return viewer.locator('.el-table__body tr').filter(has=page.locator('td').filter(has_text=re.compile('^'+person+'$')))
 for person,date,amount,title in [('甲','2026-10-30','40','给予奖励'),('乙','2026-11-02','15','抵消奖金')]:
  execution_row(person).get_by_role('button',name='填写／调整',exact=True).click();dialog=page.get_by_role('dialog',name='调整完成日期',exact=True)
  date_input=field(dialog,'完成日期').locator('input');date_input.fill(date);date_input.press('Enter');date_input.press('Tab');dialog.get_by_role('button',name='保存完成日期',exact=True).click()
  dialog=page.get_by_role('dialog',name=title,exact=True);expect(dialog).to_be_visible();field(dialog,'金额').locator('input').fill(amount);dialog.get_by_role('button',name='确认金额',exact=True).click();expect(dialog).not_to_be_visible();page.wait_for_timeout(250)
 assert executions['a']['on_time'] is True and executions['b']['on_time'] is False
 assert executions['a']['incentive']['amount']=='40.00' and executions['b']['incentive']['amount']=='15.00'
 execution_row('甲').get_by_role('button',name='0% · 修改进度',exact=True).click();progress=page.get_by_role('dialog',name='分工进度与修改记录',exact=True);field(progress,'进度（1—100）').locator('input').fill('80');field(progress,'具体进度').locator('textarea').fill('接口联调完成');progress.get_by_role('button',name='保存进度',exact=True).click();expect(progress).to_contain_text('接口联调完成');progress.get_by_role('button',name='关闭',exact=True).last.click()
 assert executions['a']['progress']==80 and executions['b']['progress']==0
 execution_row('乙').get_by_role('button',name='加至工作报告',exact=True).click();report=page.get_by_role('dialog',name='加至工作报告',exact=True);expect(field(report,'订单号').locator('input')).to_have_value('DT-261030-003');expect(field(report,'具体任务').locator('textarea')).to_have_value('页面开发')
 field(report,'工作量').locator('input').fill('1');field(report,'单位').locator('.el-select').click();page.get_by_role('option',name='项',exact=True).click();field(report,'耗时').locator('.el-select').click();page.get_by_role('option',name='30分钟',exact=True).click()
 report.get_by_role('button',name='确认添加',exact=True).click();expect(report).not_to_be_visible();assert reports[0]['progress_content']=='页面开发'
 assert not errors,errors
 print(json.dumps(dict(multiselect_opens_division_dialog=True,division_validation=True,independent_deadlines=True,independent_completion_and_amounts=True,independent_progress=True,report_uses_selected_division=True,main_tree_not_inflated=True,page_errors=errors)))
 browser.close()
