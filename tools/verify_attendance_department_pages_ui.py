"""考勤各列表分页、部门分组与完整累计回归；业务 API 全部拦截。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright,expect
base='http://localhost:3000'
compiled=urlopen(base+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
people=[{'user_id':f'p{i:02}','name':f'人员{i:02}','username':f'u{i:02}','department':'HR部' if i<13 else 'IT部','late_count':0,'late_minutes':0,'overtime_minutes':60,'leave_minutes':0,'annual_leave_days':1,'ready':True,'entries':[]} for i in range(26)]
names={p['user_id']:p['department'] for p in people}
records=[{**p,'day':'2026-11-26','check_in':'2026-11-26T09:00:00+08:00','check_out':'2026-11-26T18:30:00+08:00','shift':{'label':'早班','periods':['09:00–12:00','13:30–18:30']},'leaves':[],'sessions':[]} for p in people]
leaves=[{**p,'id':p['user_id'],'source':'application','source_label':'申请请假','start_at':'2026-11-26T10:00:00+08:00','end_at':'2026-11-26T10:30:00+08:00','minutes':30,'reason':'测试请假'} for p in people]
balances=[{**p,'month':'2026-11','raw_minutes':90,'deduction_minutes':30,'overtime_minutes':60} for p in people]
requests=[]
def api(route):
 path=urlsplit(route.request.url).path;params=parse_qs(urlsplit(route.request.url).query)
 if path.endswith('/attendance/report'):
  requests.append(params);size=int(params.get('limit',['50'])[0]);page=int(params.get('page',['1'])[0]);selected=people
  keyword=params.get('keyword',[''])[0]
  if keyword:selected=[p for p in selected if keyword in p['name']]
  ids={p['user_id'] for p in selected};rows=[r for r in records if r['user_id'] in ids]
  data={'start':'2026-11-23','end':'2026-11-29','totals':{'overtime_minutes':len(selected)*60},'people':selected,'records':rows[(page-1)*size:page*size],'total':len(rows),'leaves':[r for r in leaves if r['user_id'] in ids],'monthly_balances':[r for r in balances if r['user_id'] in ids],'monthly_policy':[],'departments':[{'id':'hr','name':'HR部'},{'id':'it','name':'IT部'}],'department_names':names}
 elif path.endswith('/clock-corrections'):data={'items':[{**p,'day':'2026-11-26','kind':'in','status':'confirmed','history':[]} for p in people],'adjustments':[{**p,'day':'2026-11-26','history':[]} for p in people]}
 elif path.endswith('/annual-leave/company'):data={'year':2026,'people':[{**p,'entries':[dict(leaves[i],source_key=p['user_id'],day='2026-11-26',history=[])]} for i,p in enumerate(people)]}
 elif path.endswith('/policy/company'):data={'year':2026,'balances':[{**p,'duties':[],'obligations':[],'requests':[]} for p in people],'monthly_policy':[{**p,'month':'2026-11','events':[]} for p in people]}
 elif path.endswith('/home-office/company'):data={'year':2026,'usage_people':[{**p,'annual_limit':12,'annual_used':0,'system_used_days':0,'history':[]} for p in people],'company_overtime':records,'applications':[{**p,'status':'pending','requested_date':'2026-11-26','history':[]} for p in people],'qualification_requests':[{**p,'status':'pending'} for p in people]}
 else:data={}
 route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Overview from '/src/views/schedule/components/AttendanceOverview.vue';import AppForm from '/src/components/common/AppForm.vue';const app=createApp({render:()=>h(Overview,{admin:true})});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 context=browser.new_context(viewport={'width':1800,'height':1100},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 context.route(base+'/attendance-pagination-check',lambda r:r.fulfill(content_type='text/html',body=html))
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(base+'/attendance-pagination-check')
 summary=page.get_by_role('tabpanel',name='人员累计',exact=True).locator('.department-paged-list')
 expect(summary.locator('.el-table__body-wrapper tbody tr')).to_have_count(20)
 expect(summary.locator('.department-paged-list__heading')).to_have_count(2)
 def size(container,label,count):
  container.locator('.el-pagination .el-select__wrapper').click();page.get_by_role('option',name=re.compile('^'+str(label)+r'\D')).click()
  expect(container.locator('.el-table__body-wrapper tbody tr')).to_have_count(count)
 size(summary,10,10)
 summary.get_by_role('button',name='Go to next page',exact=True).click()
 expect(summary).to_contain_text('人员10')
 size(summary,50,26)
 expect(page.locator('.attendance-totals')).to_contain_text('26小时')
 page.get_by_role('tab',name='每日明细',exact=True).click()
 daily=page.get_by_role('tabpanel',name='每日明细',exact=True).locator('.department-paged-list')
 expect(daily.locator('.el-table__body-wrapper tbody tr')).to_have_count(20)
 size(daily,10,10);assert requests[-1]['limit']==['10']
 daily.get_by_role('button',name='Go to next page',exact=True).click()
 expect(daily).to_contain_text('人员10')
 assert requests[-1]['page']==['2']
 expect(page.locator('.attendance-totals')).to_contain_text('26小时')
 page.get_by_role('tab',name='请假明细',exact=True).click()
 leave=page.get_by_role('tabpanel',name='请假明细',exact=True).locator('.department-paged-list');size(leave,50,26)
 search=page.get_by_role('textbox',name='考勤人员搜索',exact=True);search.fill('人员01')
 expect(leave.locator('.el-table__body-wrapper tbody tr')).to_have_count(1)
 assert requests[-1]['page']==['1']
 search.fill('');expect(leave.locator('.el-table__body-wrapper tbody tr')).to_have_count(26)
 for title,count in [('补卡与跨日记录',2),('补班、调休与年终奖',1),('请假与年假',2),('居家办公申请',4)]:
  page.get_by_role('button',name=title,exact=True).click()
  scope=page.locator('.el-collapse-item').filter(has=page.get_by_role('button',name=title,exact=True)).locator('.el-collapse-item__content').first
  expect(scope.locator('.department-paged-list:visible')).to_have_count(count)
  expect(scope.locator('.department-paged-list:visible').first.locator('.el-table__body-wrapper tbody tr')).to_have_count(20)
 assert not errors,errors
 print('PASS: 10/20/50 paging, department grouping, independent lists, server limits, search reset and unpaginated totals')
 browser.close()
