"""报告字段跨明细对齐和小屏换行回归；接口全部拦截。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
base='http://localhost:3000'
compiled=urlopen(base+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
items=[]
for i,(project,order,content) in enumerate([('思达','AP-261030-002','会议'),('', 'N/A','邮件+微信+系统沟通'*8),('长项目名称'*30,'AP-261126-001'+'X'*80,'安排+看客户资料'*30)]):
 items.append({'id':str(i),'task_type':'非项目工作','task_name':project,'progress_content':content,'duration_minutes':30,'display_metadata':{'_feedback_key':str(i),'order_no':order,'quantity':1,'quantity_unit':'次','report_types':['非项目工作::邮件+微信+系统沟通等'],**({'parent_item_key':'0'} if i==2 else {})}})
report={'user_name':'对齐测试','report_date':'2026-11-26','saved_at':'2026-11-27T08:00:00+08:00','finalized_at':'2026-11-27T08:00:00+08:00','items':items}
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Snapshot from '/src/views/schedule/components/ReportSnapshot.vue';createApp({render:()=>h(Snapshot,{report:REPORT})}).mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace('REPORT',json.dumps(report,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 context=browser.new_context(service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),lambda r:r.fulfill(content_type='application/json',body='{}'))
 context.route(base+'/report-alignment-check',lambda r:r.fulfill(content_type='text/html',body=html))
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(base+'/report-alignment-check')
 for width in (1800,950,620,390):
  page.set_viewport_size({'width':width,'height':1100})
  expect(page.locator('.report-snapshot > article')).to_have_count(3)
  positions=page.locator('.report-snapshot > article > .el-descriptions').evaluate_all('''tables=>tables.map(table=>Object.fromEntries([...table.querySelectorAll('.el-descriptions__label')].map(label=>[label.textContent.trim(),[label.getBoundingClientRect().x,label.nextElementSibling.getBoundingClientRect().x]])))''')
  for label in ('工作类型','订单号','项目名称','具体任务','工作量','耗时'):
   for axis in (0,1):
    values=[table[label][axis] for table in positions]
    assert max(values)-min(values)<1,(width,label,values)
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),width
 expect(page.locator('.report-snapshot > .el-descriptions')).not_to_contain_text('最近保存时间')
 expect(page.locator('.report-snapshot > .el-descriptions')).to_contain_text('提交时间')
 assert not errors,errors
 print('PASS: identical field boundaries for short/long/child records at desktop and mobile widths; submitted time only')
 browser.close()
