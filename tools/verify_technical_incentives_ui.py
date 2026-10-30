"""完成日期、金额弹窗及KPI抵消验收；所有业务接口拦截。"""
import json,re
from copy import deepcopy
from decimal import Decimal
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',urlopen(BASE+'/src/main.js').read().decode()).group(1)
vr=re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)',urlopen(BASE+'/src/router/index.js').read().decode()).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import{createApp,h}from VUE;import{createRouter,createWebHistory,RouterView}from VR;import Tasks from '/src/views/technology/TechnicalDevelopment.vue';import KPI from '/src/views/hr/KPI.vue';import '/src/styles/theme.css';import '/src/styles/common.css';localStorage.setItem('user_id','incentives-ui');const router=createRouter({history:createWebHistory(),routes:[{path:'/completion-ui-check',component:Tasks},{path:'/kpi-ui-check',component:KPI}]});createApp({render:()=>h(RouterView)}).use(router).mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace('VR',json.dumps(vr))
STAMP='2026-10-30T15:00:00+08:00'
rows=[dict(id=key,task_no=f'DT-261030-00{i}',name=name,parent_id=None,content='任务',arranger_id='u1',arranger_name='开发员甲',executor_id=person,executor_name='开发员甲' if person=='u1' else '开发员乙',due_at='2026-10-30T12:00:00+08:00',progress=100,progress_updated_at=STAMP,adjustment='',notes='',revision=1,created_at=STAMP,updated_at=STAMP,completion_enabled=True,completed_on=None,on_time=None,completion_revision=0,incentive=None) for i,(key,name,person) in enumerate([('a','奖励任务','u1'),('b','抵消任务','u1'),('c','另一人抵消任务','u2')],1)]
histories={row['id']:dict(changes=[],ledger_history=[]) for row in rows};writes=[];errors=[]
def completion(row):return dict(task_id=row['id'],task_no=row['task_no'],task_name=row['name'],due_on='2026-10-30',task_revision=1,**{key:row[key] for key in ['completed_on','on_time','completion_revision','incentive']},**histories[row['id']])
def api(route):
 request=route.request;path=urlparse(request.url).path
 if path=='/api/technical-development/tasks':result=dict(enabled=True,items=rows)
 elif path=='/api/technical-development/people':result=dict(arrangers=[dict(id='u1',name='开发员甲')],executors=[dict(id='u1',name='开发员甲'),dict(id='u2',name='开发员乙')])
 elif path=='/api/technical-development/incentives':
  people={}
  for row in rows:
   if not row['completion_revision']:continue
   p=people.setdefault(row['executor_id'],dict(executor_id=row['executor_id'],executor_name=row['executor_name'],reward_total=Decimal(0),deduction_total=Decimal(0),pending=0));entry=row['incentive']
   if entry:p['reward_total' if entry['kind']=='reward' else 'deduction_total']+=Decimal(entry['amount'])
   elif row['on_time'] is not None:p['pending']+=1
  totals={key:Decimal(0) for key in ['reward_total','deduction_total','offset_total','net_reward','net_deduction']};totals['pending']=0
  for p in people.values():
   p['offset_total']=min(p['reward_total'],p['deduction_total']);p['net_reward']=p['reward_total']-p['offset_total'];p['net_deduction']=p['deduction_total']-p['offset_total']
   for key in totals:totals[key]+=p[key]
  money=lambda v:{key:f'{n:.2f}' if isinstance(n,Decimal) else n for key,n in v.items()}
  result=dict(enabled=True,people=[money(p) for p in people.values()],totals=money(totals),tasks=[dict(task_id=r['id'],task_no=r['task_no'],task_name=r['name'],executor_name=r['executor_name'],due_on='2026-10-30',completed_on=r['completed_on'],on_time=r['on_time'],incentive=r['incentive']) for r in rows if r['completion_revision']])
 elif path.startswith('/api/technical-development/tasks/'):
  row=next(r for r in rows if r['id']==path.split('/')[4]);history=histories[row['id']]
  if request.method!='GET':
   body=request.post_data_json;writes.append((path,body))
   if path.endswith('/completion'):
    previous=row['completed_on'];row['completed_on']=body['completed_on'];row['on_time']=body['completed_on']<='2026-10-30' if body['completed_on'] else None;row['completion_revision']+=1;row['incentive']=None
    for entry in history['ledger_history']:entry['effective']=False
    history['changes'].insert(0,dict(id=f'd{len(writes)}',previous_date=previous,completed_on=row['completed_on'],previous_due_on='2026-10-30',due_on='2026-10-30',reason=body['reason'],author_name='开发员甲',author_username='developer',created_at=STAMP))
   else:
    for entry in history['ledger_history']:entry['effective']=False
    entry=dict(id=f'm{len(writes)}',amount=f"{Decimal(body['amount']):.2f}",kind='reward' if row['on_time'] else 'deduction',executor_name=row['executor_name'],author_name='开发员甲',author_username='developer',reason=body['reason'],created_at=STAMP,effective=True);row['incentive']=entry;history['ledger_history'].insert(0,entry)
  result=completion(row)
 else:result={}
 route.fulfill(content_type='application/json',body=json.dumps(deepcopy(result)))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1700,'height':1000},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 for path in ['/completion-ui-check','/kpi-ui-check']:context.route(BASE+path,lambda route:route.fulfill(content_type='text/html',body=html))
 page=context.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/completion-ui-check')
 def table_row(name):return page.locator('.el-table__body tr').filter(has=page.locator('.task-name span').filter(has_text=re.compile('^'+re.escape(name)+'$')))
 def field(dialog,label):return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label').filter(has_text=re.compile('^'+re.escape(label)+'$')))
 def choose(name,day,amount,title):
  row=table_row(name);date=row.locator('.el-date-editor input');date.fill(day);date.press('Enter');date.press('Tab')
  dialog=page.get_by_role('dialog',name='调整完成日期',exact=True);expect(dialog).to_be_visible();dialog.get_by_role('button',name='保存完成日期',exact=True).click()
  dialog=page.get_by_role('dialog',name=title,exact=True);expect(dialog).to_be_visible();field(dialog,'金额').locator('input').fill(amount);dialog.get_by_role('button',name='确认金额',exact=True).click();expect(dialog).not_to_be_visible();page.wait_for_timeout(250)
 choose('奖励任务','2026-10-30','100','给予奖励');choose('抵消任务','2026-10-31','60','抵消奖金');choose('另一人抵消任务','2026-10-31','80','抵消奖金')
 page.goto(BASE+'/kpi-ui-check');expect(page.get_by_text('开发部门奖励',exact=True)).to_be_visible();assert page.get_by_role('button',name='新增KPI',exact=True).count()==0
 summary=page.locator('.el-descriptions');expect(summary).to_contain_text('100.00');expect(summary).to_contain_text('140.00');expect(summary).to_contain_text('60.00');expect(summary).to_contain_text('40.00');expect(summary).to_contain_text('80.00')
 page.goto(BASE+'/completion-ui-check');row=table_row('奖励任务');date=row.locator('.el-date-editor input');date.fill('2026-10-31');date.press('Enter');date.press('Tab')
 dialog=page.get_by_role('dialog',name='调整完成日期',exact=True);dialog.get_by_role('button',name='保存完成日期',exact=True).click();expect(dialog.locator('.el-form-item__error')).to_contain_text('调整完成日期必须填写原因')
 field(dialog,'调整原因').locator('textarea').fill('核对实际完成日期');dialog.get_by_role('button',name='保存完成日期',exact=True).click();dialog=page.get_by_role('dialog',name='抵消奖金',exact=True);expect(dialog).to_be_visible();dialog.get_by_role('button',name='取消',exact=True).click();expect(dialog).not_to_be_visible();page.wait_for_timeout(250)
 row=table_row('奖励任务');expect(row).to_contain_text('待登记金额');row.get_by_role('button',name='调整记录',exact=True).click();history=page.get_by_role('dialog',name='完成日期与奖励调整记录',exact=True);expect(history).to_contain_text('核对实际完成日期');expect(history).to_contain_text('历史记录，不计入当前统计');expect(history).to_contain_text('developer')
 assert not errors,errors
 print(json.dumps(dict(automatic_reward_and_deduction_dialogs=True,amounts_recorded=True,per_executor_offsets=True,kpi_replaced=True,date_reason_required=True,date_and_money_history=True,old_amount_excluded=True,page_errors=errors)))
 browser.close()
