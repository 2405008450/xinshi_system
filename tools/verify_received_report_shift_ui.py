import json,re
from urllib.request import urlopen
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright,expect
base='http://localhost:3000'
compiled=urlopen(base+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Reports from '/src/views/schedule/components/ReceivedWorkReports.vue';const app=createApp({render:()=>h(Reports)});window.unmount=()=>app.unmount();app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
report={'id':'report','department_name':'IT部','user_name':'班次测试','report_date':'2026-11-22','status':'finalized','items':[{'task_type':'非项目工作','task_name':name,'duration_minutes':minutes} for name,minutes in [('任务甲',30),('任务乙',45)]],'duration_minutes':75,'idle_minutes':15,'shift':{'label':'早班','periods':['09:00–12:00','13:30–18:30']}}
for item,subtype in zip(report['items'],['邮件+微信+系统沟通等','行政工作']):item['display_metadata']={'report_types':['非项目工作::'+subtype]}
report['clock_in']='2026-11-22T08:05:00+08:00'
report['clock_available']=True
report['clock_sessions']=[{'check_in':'2026-11-22T08:05:00+08:00','check_out':'2026-11-22T12:00:00+08:00'},{'check_in':'2026-11-22T13:30:00+08:00','check_out':'2026-11-23T00:15:00+08:00'},{'check_in':'2026-11-23T00:30:00+08:00','check_out':None}]
def api(route):
 path=route.request.url.split('?')[0]
 data={}
 if path.endswith('/received'):data={'items':[report,{**report,'id':'unassigned','department_name':'HR部','user_name':'未安排测试','shift':None,'clock_in':None}],'total':2}
 elif path.endswith('/review-directory'):data={'people':[],'departments':[]}
 elif '/received/' in path:data=report
 route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 context=browser.new_context(viewport={'width':1800,'height':1000},service_workers='block')
 context.add_init_script("Date.now=()=>Date.parse(localStorage.getItem('test.now')||'2026-11-27T12:00:00+08:00')")
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 context.route(base+'/report-shift-check',lambda r:r.fulfill(content_type='text/html',body=html))
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 try:
  with page.expect_response(lambda response:urlsplit(response.url).path.endswith('/daily-reports/received'),timeout=10000) as initial:
   page.goto(base+'/report-shift-check')
 except Exception:
  print('PAGE_ERRORS',errors,flush=True)
  raise
 initial.value.json()
 initial_params=parse_qs(urlsplit(initial.value.url).query)
 assert initial_params['date_from']==['2026-11-26'] and initial_params['date_to']==['2026-11-26']
 presets=[('今日','2026-11-27','2026-11-27'),('前日','2026-11-25','2026-11-25'),('大前天','2026-11-24','2026-11-24'),('上周','2026-11-16','2026-11-22'),('上个月','2026-10-01','2026-10-31'),('全部日期',None,None),('昨日','2026-11-26','2026-11-26')]
 for label,start,end in presets:
  with page.expect_response(lambda response:urlsplit(response.url).path.endswith('/daily-reports/received')) as changed:
   page.locator('.report-date-shortcuts').get_by_role('button',name=label,exact=True).click()
  changed.value.json();params=parse_qs(urlsplit(changed.value.url).query)
  assert params.get('date_from')==([start] if start else None) and params.get('date_to')==([end] if end else None),(label,params)
  assert params['page']==['1']
  expect(page.locator('.report-date-shortcuts').get_by_role('button',name=label,exact=True)).to_have_class(re.compile('el-button--primary'))
 with page.expect_response(lambda response:urlsplit(response.url).path.endswith('/daily-reports/received')) as reset:
  page.get_by_role('button',name='重置',exact=True).click()
 reset.value.json()
 assert parse_qs(urlsplit(reset.value.url).query)['date_from']==['2026-11-26']
 groups=page.locator('.report-department-group')
 expect(groups).to_have_count(2)
 expect(groups.nth(0).locator('.department-group-heading')).to_contain_text('IT部')
 expect(groups.nth(1).locator('.department-group-heading')).to_contain_text('HR部')
 expect(groups.nth(0).locator('.el-table__header-wrapper')).to_contain_text('班次')
 expect(groups.nth(0).locator('.el-table__header-wrapper')).not_to_contain_text('最近保存时间')
 expect(groups.nth(0).locator('.el-table__header-wrapper')).to_contain_text('提交时间')
 expect(groups.nth(0).locator('.el-table__body-wrapper')).to_contain_text('早班')
 headers=groups.nth(0).locator('.el-table__header-wrapper th').all_text_contents()
 assert headers.index('上班时间')+1==headers.index('提交时间'),headers
 expect(groups.nth(0).locator('.el-table__body-wrapper')).to_contain_text('2026/11/22 08:05:00')
 expect(groups.nth(1).locator('.el-table__body-wrapper')).to_contain_text('未打卡')
 expect(groups.nth(1).locator('.el-table__body-wrapper')).to_contain_text('未安排')
 for group in (groups.nth(0),groups.nth(1)):group.locator('.el-table__body-wrapper .el-checkbox').first.click()
 expect(page.get_by_role('button',name='打开所选报告（2）',exact=True)).to_be_enabled()
 expect(page.get_by_role('button',name='查看详情',exact=True)).to_have_count(0)
 page.get_by_role('button',name='打开报告窗口',exact=True).first.click()
 expect(page.get_by_role('dialog')).to_be_visible()
 summary=page.locator('.report-snapshot > .el-descriptions')
 expect(summary).to_contain_text('班次')
 expect(summary).to_contain_text('早班 · 09:00–12:00 / 13:30–18:30')
 expect(summary).to_contain_text('总计时间')
 expect(summary).to_contain_text('1小时15分钟')
 expect(summary).to_contain_text('上班打卡时间')
 expect(summary).to_contain_text('2026/11/22 08:05:00')
 expect(summary).to_contain_text('下班打卡时间')
 expect(summary).to_contain_text('2026/11/23 00:15:00')
 expect(summary).to_contain_text('未下班打卡')
 page.locator('.snapshot-filter input[type="text"]').fill('任务甲')
 expect(page.locator('.report-snapshot article:visible')).to_have_count(1)
 expect(summary).to_contain_text('1小时15分钟')
 page.get_by_role('button',name='按任务类型排序',exact=True).click()
 type_summary=page.locator('.report-type-summary')
 expect(type_summary).to_contain_text('累计 1小时15分钟')
 expect(type_summary.locator('.report-type-group')).to_have_count(1)
 expect(type_summary.locator('.report-type-group > header')).to_contain_text('非项目工作')
 expect(type_summary.locator('.report-type-subgroup')).to_have_count(2)
 expect(type_summary).to_contain_text('子类：邮件+微信+系统沟通等')
 expect(type_summary).to_contain_text('子类：行政工作')
 expect(type_summary).to_contain_text('任务甲');expect(type_summary).to_contain_text('任务乙')
 expect(type_summary).to_contain_text('30分钟');expect(type_summary).to_contain_text('45分钟')
 expect(summary).to_contain_text('1小时15分钟')
 page.get_by_role('button',name='恢复原顺序',exact=True).click();expect(type_summary).not_to_be_visible()
 for instant,expected_day in [('2026-11-27T17:59:59+08:00','2026-11-26'),('2026-11-27T18:00:00+08:00','2026-11-27'),('2026-11-28T00:00:00+08:00','2026-11-27')]:
  page.evaluate('(instant)=>localStorage.setItem("test.now",instant)',instant)
  with page.expect_response(lambda response:urlsplit(response.url).path.endswith('/daily-reports/received')) as reopened:
   page.reload()
  assert parse_qs(urlsplit(reopened.value.url).query)['date_from']==[expected_day]
 page.evaluate('window.unmount()')
 assert not errors,errors
 print('PASS: shift column, unassigned fallback, report window and unmount')
 browser.close()
