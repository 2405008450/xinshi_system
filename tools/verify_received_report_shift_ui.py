import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
base='http://localhost:3000'
compiled=urlopen(base+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Reports from '/src/views/schedule/components/ReceivedWorkReports.vue';const app=createApp({render:()=>h(Reports)});window.unmount=()=>app.unmount();app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
report={'id':'report','user_name':'班次测试','report_date':'2026-11-22','status':'finalized','items':[],'duration_minutes':30,'shift':{'label':'早班','periods':['09:00–12:00','13:30–18:30']}}
def api(route):
 path=route.request.url.split('?')[0]
 data={}
 if path.endswith('/received'):data={'items':[report,{**report,'id':'unassigned','user_name':'未安排测试','shift':None}],'total':2}
 elif path.endswith('/review-directory'):data={'people':[],'departments':[]}
 elif '/received/' in path:data=report
 route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 context=browser.new_context(viewport={'width':1800,'height':1000},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 context.route(base+'/report-shift-check',lambda r:r.fulfill(content_type='text/html',body=html))
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(base+'/report-shift-check')
 expect(page.locator('.el-table__header-wrapper')).to_contain_text('班次')
 expect(page.locator('.el-table__body-wrapper')).to_contain_text('早班')
 expect(page.locator('.el-table__body-wrapper')).to_contain_text('未安排')
 expect(page.get_by_role('button',name='查看详情',exact=True)).to_have_count(0)
 page.get_by_role('button',name='打开报告窗口',exact=True).first.click()
 expect(page.get_by_role('dialog')).to_be_visible()
 page.evaluate('window.unmount()')
 assert not errors,errors
 print('PASS: shift column, unassigned fallback, report window and unmount')
 browser.close()
