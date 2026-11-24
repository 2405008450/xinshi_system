"""工作报告草稿、刷新恢复、手动项目选择与正式提交回归；业务 API 全部拦截。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h} from VUE;import Panel from '/src/views/schedule/components/DailyReportPanel.vue';import AppForm from '/src/components/common/AppForm.vue';localStorage.setItem('user_id','draft-test');const app=createApp({render:()=>h(Panel,{reportDate:'2026-11-24'})});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
server={'payload':None,'revision':0,'updated_at':None};writes=[];formal=[];fail=False
def api(route):
 global server
 path=route.request.url.split('/api')[-1].split('?')[0]
 data={}
 if path=='/daily-reports/preview':data={'report_date':'2026-11-24','status':'draft','items':[]}
 elif path=='/daily-reports/editor-context':data={'user_name':'测试','departments':[]}
 elif path=='/editor-drafts':data=server
 elif path=='/editor-drafts/batch':
  if fail:return route.fulfill(status=503,content_type='application/json',body='{"detail":"测试网络失败"}')
  data=[]
  for entry in route.request.post_data_json['drafts']:
   writes.append(entry);server={**entry,'revision':server['revision']+1,'updated_at':'2026-11-24T20:00:00+08:00'};data.append(server)
 elif path.endswith('/finalize'):
  payload=route.request.post_data_json;formal.append(payload)
  data={**payload,'id':'confirmed-report','report_date':'2026-11-24','status':'finalized','edit_draft_revision':server['revision']+1}
 elif 'report-project' in path or 'project-options' in path:data={'items':[{'id':'project','order_no':'TP-002','project_name':'测试项目','project_type':'translation'}],'total':1}
 route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 context=browser.new_context(viewport={'width':1800,'height':1050},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 context.route(BASE+'/report-draft-fix-check',lambda r:r.fulfill(content_type='text/html',body=html))
 page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(BASE+'/report-draft-fix-check');page.get_by_role('button',name='新增一行',exact=True).click()
 task=page.locator('.report-grid tbody tr').first.locator('td').nth(4).locator('textarea').first
 task.fill('尚未选择类型的草稿内容')
 saved=page.evaluate("JSON.parse(localStorage.getItem('daily-report-form-draft:draft-test:2026-11-24'))")
 assert saved['items'][0]['progress_content']=='尚未选择类型的草稿内容'
 page.reload();expect(page.locator('.report-grid tbody tr')).to_have_count(1)
 task=page.locator('.report-grid tbody tr').first.locator('td').nth(4).locator('textarea').first
 expect(task).to_have_value('尚未选择类型的草稿内容')
 page.get_by_role('button',name='新增一行',exact=True).click()
 page.get_by_role('button',name='保存草稿',exact=True).click()
 expect(page.locator('.report-submit-notice')).to_contain_text('草稿已保存')
 assert len(server['payload']['items'])==2 and not formal
 page.evaluate("localStorage.removeItem('daily-report-form-draft:draft-test:2026-11-24')")
 page.reload();expect(page.locator('.report-grid tbody tr')).to_have_count(2)
 row=page.locator('.report-grid tbody tr').first
 expect(row.locator('td').nth(4).locator('textarea').first).to_have_value('尚未选择类型的草稿内容')
 # 模拟 Element Plus 在刷新 options 时的内部 emit，不得改类型或弹窗。
 page.locator('.el-cascader').first.evaluate("el=>el.__vueParentComponent.emit('update:modelValue',['笔译项目'])")
 expect(page.get_by_role('dialog',name='笔译项目 · 搜索选择项目',exact=True)).not_to_be_visible()
 assert page.evaluate("JSON.parse(localStorage.getItem('daily-report-form-draft:draft-test:2026-11-24')).items[0].display_metadata.report_types")==[]
 row.locator('.el-cascader__search-input').fill('笔译项目')
 page.locator('.el-cascader__suggestion-item').filter(has_text=re.compile('^笔译项目$')).click()
 expect(row.get_by_role('button',name='选择项目',exact=True)).to_be_visible()
 expect(page.get_by_role('dialog',name='笔译项目 · 搜索选择项目',exact=True)).not_to_be_visible()
 row.get_by_role('button',name='选择项目',exact=True).click()
 expect(page.get_by_role('dialog',name='笔译项目 · 搜索选择项目',exact=True)).to_be_visible()
 page.get_by_role('dialog',name='笔译项目 · 搜索选择项目',exact=True).get_by_role('button',name='取消',exact=True).click()
 fail=True
 row.locator('td').nth(4).locator('textarea').first.fill('断网后也保留的新内容')
 page.get_by_role('button',name='保存草稿',exact=True).click()
 expect(page.locator('.report-submit-notice')).to_contain_text('本机已备份')
 page.reload()
 expect(page.locator('.report-grid tbody tr').first.locator('td').nth(4).locator('textarea').first).to_have_value('断网后也保留的新内容')
 assert not errors,errors
 assert not formal
 context.close();fail=False;server={'payload':None,'revision':0,'updated_at':None}
 context=browser.new_context(viewport={'width':1800,'height':1050},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 context.route(BASE+'/report-draft-fix-check',lambda r:r.fulfill(content_type='text/html',body=html))
 complete={'report_date':'2026-11-24','items':[{'source_type':'manual','task_type':'非项目工作','task_name':'','progress_content':'完整工作内容','duration_minutes':30,'display_metadata':{'report_types':['非项目工作::行政工作'],'quantity':1,'quantity_unit':'次'}}],'idle_minutes':0,'idle_declaration_confirmed':True,'_savedAt':1795528241069,'_baseRevision':0}
 context.add_init_script("localStorage.setItem('daily-report-form-draft:draft-test:2026-11-24',"+json.dumps(json.dumps(complete,ensure_ascii=False))+ ")")
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(BASE+'/report-draft-fix-check');expect(page.locator('.report-grid tbody tr')).to_have_count(1)
 page.get_by_role('button',name='新增一行',exact=True).click()
 page.get_by_role('button',name='确认报告',exact=True).click()
 expect(page.locator('.el-message-box')).to_contain_text('报告日期：2026-11-24')
 page.locator('.el-message-box').get_by_role('button',name=re.compile('^(确定|OK)$')).click()
 expect(page.locator('.report-submit-notice')).to_contain_text('已保存并发送')
 expect(page.locator('.report-submit-notice')).to_contain_text('报告日期：2026-11-24')
 assert len(formal)==1 and len(formal[0]['items'])==1
 assert formal[0]['items'][0]['progress_content']=='完整工作内容'
 snapshot_html=html.replace('/DailyReportPanel.vue','/ReportSnapshot.vue').replace("{reportDate:'2026-11-24'}","{report:{report_date:'2026-11-22',saved_at:'2026-11-25T09:15:00+08:00',finalized_at:'2026-11-25T09:16:00+08:00',items:[]}}")
 context.route(BASE+'/report-timestamp-ui-check',lambda r:r.fulfill(content_type='text/html',body=snapshot_html))
 page.goto(BASE+'/report-timestamp-ui-check')
 descriptions=page.locator('.report-snapshot > .el-descriptions')
 expect(descriptions).to_contain_text('报告日期')
 expect(descriptions).to_contain_text('2026-11-22')
 expect(descriptions).to_contain_text('最近保存时间')
 expect(descriptions).to_contain_text('2026/11/25 09:15:00')
 expect(descriptions).to_contain_text('提交时间')
 expect(descriptions).to_contain_text('2026/11/25 09:16:00')
 assert not errors,errors
 print(json.dumps({'immediate_backup':True,'local_refresh_restore':True,'incomplete_cloud_save':True,'cloud_restore':True,'new_blank_row_preserved':True,'synthetic_type_ignored':True,'explicit_picker_only':True,'offline_restore':True,'formal_submission_ignores_only_untouched_blank_rows':True,'page_errors':errors}))
 browser.close()
