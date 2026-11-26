"""按部门缺报统计、名单及筛选回归，全部 API 使用模拟数据。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright,expect
base='http://localhost:3000'
compiled=urlopen(base+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h,ref} from VUE;import Statistics from '/src/views/schedule/components/ReportStatistics.vue';createApp({setup(){const department=ref('');window.setDepartment=value=>department.value=value;return()=>h(Statistics,{departmentId:department.value})}}).mount('#app');</script>'''.replace('VUE',json.dumps(vue))
groups=[]
for name,uid,written in [('HR部','hr',True),('IT部','it',False)]:
 person={'id':uid,'name':name+'人员','expected_count':1,'missing_dates':[] if written else ['2026-11-26']}
 groups.append({'name':name,'people_count':1,'people':[person],'expected_count':1,'written_count':int(written),'missing_count':int(not written),'days':[{'date':'2026-11-26','expected_count':1,'written_ids':[uid] if written else [],'missing_ids':[] if written else [uid]}]})
requests=[]
def api(route):
 params=parse_qs(urlsplit(route.request.url).query);requests.append(params)
 selected=groups if not params.get('department_id') else [g for g in groups if g['name']==params['department_id'][0]]
 data={'date_from':'2026-11-26','date_to':'2026-11-26','basis':'测试统计口径','people':[p for g in selected for p in g['people']],'days':[{'date':'2026-11-26','expected_count':len(selected),'written_ids':['hr'] if any(g['name']=='HR部' for g in selected) else [],'missing_ids':['it'] if any(g['name']=='IT部' for g in selected) else []}],'departments':selected,'calendar_sources':[]}
 route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 context=browser.new_context(viewport={'width':1200,'height':900},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 context.route(base+'/department-statistics-check',lambda r:r.fulfill(content_type='text/html',body=html))
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(base+'/department-statistics-check')
 sections=page.locator('.department-statistics');expect(sections).to_have_count(2)
 expect(sections.first.locator('header')).to_contain_text('HR部')
 expect(sections.nth(1).locator('header')).to_contain_text('缺报 1 人次')
 sections.first.get_by_role('button',name='1 人已写',exact=True).click()
 expect(page.locator('.name-list:visible')).to_have_text('HR部人员')
 page.get_by_role('button',name='刷新统计',exact=True).click()
 page.evaluate("window.setDepartment('HR部')")
 expect(sections).to_have_count(1);expect(sections.first.locator('header')).to_contain_text('HR部')
 page.locator('.stat-filter .el-select__wrapper').click();page.get_by_role('option',name='按周',exact=True).click()
 page.wait_for_function("document.querySelector('.stat-filter input') !== null")
 page.evaluate("window.setDepartment('不存在')")
 expect(page.get_by_text('当前筛选范围内暂无人员',exact=True)).to_be_visible()
 assert any(p.get('department_id')==['HR部'] for p in requests)
 assert any(p.get('period')==['week'] for p in requests)
 assert not errors,errors
 print('PASS: department totals, daily names, filtering, weekly mode and empty results')
 browser.close()
