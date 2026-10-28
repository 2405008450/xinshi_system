"""中午加班声明、项目选择、标记、筛选及保存范围；接口全部拦截。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode();vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
normal={'source_type':'manual','task_type':'非项目工作','task_name':'普通工作','progress_content':'行政整理','duration_minutes':30,'display_metadata':{'report_types':['非项目工作::行政工作'],'quantity':1,'quantity_unit':'次'}}
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import Editor from '/src/views/schedule/components/DailyReportEditor.vue';import AppForm from '/src/components/common/AppForm.vue';const app=createApp({setup(){const editor=ref();window.__saved=null;return()=>h('div',[h('button',{onClick:async()=>{try{await editor.value.validate();window.__saved=editor.value.getRows()}catch{}}},'验证保存'),h(Editor,{ref:editor,rows:ROWS,editable:true})])}});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace('ROWS',json.dumps([normal],ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1800,'height':1000},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),lambda route:route.fulfill(content_type='application/json',body=json.dumps({'items':[{'id':'project','order_no':'TP-002','project_name':'午间测试项目','project_type':'translation'}],'total':1},ensure_ascii=False)))
 context.route(BASE+'/lunch-report-ui-check',lambda route:route.fulfill(content_type='text/html',body=html));page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/lunch-report-ui-check')
 tools=page.locator('.lunch-report-tools');tools.locator('.el-radio').filter(has_text=re.compile('^有$')).click();expect(tools).to_contain_text('没有顺延下午上班时间');expect(tools.get_by_role('button',name='新增中午加班行',exact=True)).to_be_disabled()
 tools.locator('.el-checkbox').click();tools.get_by_role('button',name='新增中午加班行',exact=True).click();row=page.locator('.report-grid tbody tr').nth(1);expect(row).to_contain_text('中午加班')
 row.locator('.el-cascader__search-input').fill('笔译项目');page.locator('.el-cascader__suggestion-item').filter(has_text='笔译项目').click()
 picker=page.get_by_role('dialog',name='笔译项目 · 搜索选择项目',exact=True);expect(picker).to_be_visible();picker.get_by_role('textbox',name='搜索报告关联项目').fill('午间 测试');picker.get_by_role('button',name='选定',exact=True).click();expect(picker).not_to_be_visible();expect(row.locator('td').nth(2).get_by_role('textbox')).to_have_value('TP-002')
 row.locator('td').nth(4).locator('input,textarea').first.fill('午间校对项目');row.get_by_role('textbox',name='第2行工作量',exact=True).fill('1')
 row.locator('td').nth(6).locator('.el-select__wrapper').click();page.get_by_role('option',name='页',exact=True).click()
 start=row.locator('input[aria-label="第2行午间开始"]');end=row.locator('input[aria-label="第2行午间结束"]');start.fill('12:00');start.press('Enter');end.fill('13:00');end.press('Enter');tools.get_by_text('是否有中午加班？',exact=True).click()
 page.get_by_role('button',name='验证保存',exact=True).click();page.wait_for_function('window.__saved!==null');saved=page.evaluate('window.__saved');assert len(saved)==2 and saved[1]['duration_minutes']==60 and saved[1]['display_metadata']['lunch_overtime_confirmed'] is True
 page.get_by_role('textbox',name='工作报告项目筛选',exact=True).fill('午间 测试');expect(page.locator('.report-grid tbody tr:visible')).to_have_count(1)
 page.get_by_role('button',name='验证保存',exact=True).click();assert len(page.evaluate('window.__saved'))==2
 page.locator('.report-project-filter .el-checkbox').click();expect(page.locator('.report-grid tbody tr:visible')).to_have_count(1)
 assert not errors,errors
 print(json.dumps({'declaration_required_before_add':True,'project_search_selection':True,'lunch_badge':True,'time_matches_duration':True,'project_filter':True,'filter_does_not_drop_saved_rows':True,'page_errors':errors}))
 browser.close()
