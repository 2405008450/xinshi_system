"""技术汇总→开发任务→报告的完整预填、锁名和确认链路，全部接口拦截。"""
import json,re
from copy import deepcopy
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',urlopen(BASE+'/src/main.js').read().decode()).group(1)
vr=re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)',urlopen(BASE+'/src/router/index.js').read().decode()).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import{createApp,h}from VUE;import{createRouter,createWebHistory,RouterView}from VR;import Panel from '/src/components/chat/TechnicalRequirementsPanel.vue';import Tasks from '/src/views/technology/TechnicalDevelopment.vue';import{technicalDevelopmentAccess}from '/src/utils/technicalDevelopmentAccess.js';import '/src/styles/theme.css';import '/src/styles/common.css';localStorage.setItem('user_id','source-user');Object.assign(technicalDevelopmentAccess,{userId:'source-user',can_enter:true});const router=createRouter({history:createWebHistory(),routes:[{path:'/requirement-ui-check',component:{render:()=>h(Panel,{roomId:'room-a',active:true})}},{path:'/technology-management/development',component:Tasks}]});createApp({render:()=>h(RouterView)}).use(router).mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace('VR',json.dumps(vr))
summary='技术需求汇总原文';revision=1;saved=None;writes=[];errors=[];reports=[]
def source_context():return dict(room_id='room-a',source_name='原始项目名称',source_revision=revision,requirements=summary,task_id=saved['id'] if saved else None,task=saved,default_executor_id='source-user',arranger_id='source-user')
def api(route):
 global summary,revision,saved
 request=route.request;path=urlparse(request.url).path
 if path=='/api/chat/technical/rooms/room-a':
  if request.method=='PUT':summary=request.post_data_json['content'];revision+=1;writes.append((path,request.post_data_json))
  result=dict(enabled=True,room_id='room-a',project_id='project-a',title='技术需求 · 原始项目名称',order_no='AP-TEST',requirements=summary,revision=revision)
 elif path=='/api/technical-development/requirements/room-a':
  if request.method=='POST':
   body=request.post_data_json;writes.append((path,body));assert 'name' not in body
   saved=dict(id='task-a',task_no='DT-261030-001',name='原始项目名称'+(' · '+body['suffix'] if body['suffix'] else ''),parent_id=None,content=body['content'],arranger_id=body['arranger_id'],arranger_name='本人',executor_id=body['executor_id'],executor_name='另一位IT' if body['executor_id']=='other' else '本人',due_at=body['due_at'],progress=0,progress_updated_at=None,adjustment=body['adjustment'],notes=body['notes'],revision=1,created_at='2026-10-30T16:00:00+08:00',updated_at='2026-10-30T16:00:00+08:00',source=dict(room_id='room-a',base_name='原始项目名称',suffix=body['suffix'],source_revision=revision),progress_history=[dict(id='p1',previous_percentage=0,percentage=50,content='当天已完成一半',author_name='本人',created_at='2026-10-30T18:00:00+08:00',reason='')],feedback=[])
   result=saved
  else:result=source_context()
 elif path=='/api/technical-development/tasks':result=dict(enabled=True,items=[saved] if saved else [])
 elif path=='/api/technical-development/people':result=dict(arrangers=[dict(id='source-user',name='本人')],executors=[dict(id='source-user',name='本人'),dict(id='other',name='另一位IT')])
 elif path=='/api/technical-development/tasks/task-a/report':
  if request.method=='POST':reports.append(request.post_data_json);result=dict(report_id='r1',report_date='2026-10-30')
  else:result=dict(report_date='2026-10-30',report_type='开发任务',order_no=saved['task_no'],task_name=saved['name'],progress_content=saved['content'])
 elif path=='/api/technical-development/tasks/task-a':result=saved
 else:result={}
 route.fulfill(content_type='application/json',body=json.dumps(deepcopy(result)))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1600,'height':1000},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 for path in ['/requirement-ui-check','/technology-management/development*']:context.route(BASE+path,lambda route:route.fulfill(content_type='text/html',body=html))
 page=context.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/requirement-ui-check')
 def item(dialog,label):return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label').filter(has_text=re.compile('^'+re.escape(label)+'$')))
 page.get_by_role('button',name='加至工作报告',exact=True).click();expect(page.get_by_text('请先点击“加至开发任务”，编辑并保存开发任务后再加至工作报告',exact=True)).to_be_visible();assert not reports
 page.get_by_role('textbox',name='技术需求汇总',exact=True).fill('修改后的技术需求汇总')
 page.get_by_role('button',name='加至开发任务',exact=True).click();expect(page).to_have_url(re.compile('/technology-management/development\?technicalRoomId=room-a'))
 editor=page.get_by_role('dialog',name='新增技术开发任务',exact=True)
 expect(item(editor,'开发任务').locator('input').first).to_have_value('原始项目名称');expect(item(editor,'开发任务').locator('input').first).to_have_attribute('readonly','')
 expect(item(editor,'具体任务').locator('textarea')).to_have_value('修改后的技术需求汇总')
 expect(item(editor,'执行人')).to_contain_text('本人')
 page.get_by_role('textbox',name='任务名称补充内容',exact=True).fill('质量检查')
 item(editor,'执行人').locator('.el-select').click();page.get_by_role('option',name='本人',exact=True).click();page.get_by_role('option',name='另一位IT',exact=True).click();page.keyboard.press('Escape')
 assert saved is None
 editor.get_by_role('button',name='保存',exact=True).click();expect(editor).not_to_be_visible();assert saved['name']=='原始项目名称 · 质量检查' and saved['executor_id']=='other'
 page.goto(BASE+'/requirement-ui-check');page.get_by_role('button',name='加至工作报告',exact=True).click()
 report=page.get_by_role('dialog',name='加至工作报告',exact=True)
 expect(item(report,'订单号').locator('input')).to_have_value('DT-261030-001');expect(item(report,'项目名称').locator('input')).to_have_value('原始项目名称 · 质量检查');expect(item(report,'具体任务').locator('textarea')).to_have_value('修改后的技术需求汇总')
 report.get_by_role('button',name='原始项目名称 · 质量检查 · 查看各天具体进度',exact=True).click();daily=page.get_by_role('dialog',name='技术任务每日进度',exact=True);expect(daily).to_contain_text('当天已完成一半');daily.get_by_role('button',name='关闭',exact=True).last.click()
 item(report,'项目名称').locator('input').fill('报告可编辑名称');item(report,'具体任务').locator('textarea').fill('报告可编辑具体任务')
 assert not reports
 item(report,'工作量').locator('input').fill('1');item(report,'单位').locator('.el-select').click();page.get_by_role('option',name='项',exact=True).click();item(report,'耗时').locator('.el-select').click();page.get_by_role('option',name='20分钟',exact=True).click()
 report.get_by_role('button',name='确认添加',exact=True).click();expect(report).not_to_be_visible();assert reports[-1]['task_name']=='报告可编辑名称' and reports[-1]['progress_content']=='报告可编辑具体任务'
 page.get_by_role('button',name='加至开发任务',exact=True).click();editor=page.get_by_role('dialog',name='编辑技术开发任务',exact=True);expect(item(editor,'任务编号').locator('input')).to_have_value('DT-261030-001')
 assert not errors,errors
 print(json.dumps(dict(source_saved_before_handoff=True,task_not_created_until_save=True,immutable_project_name_and_suffix=True,default_self_and_it_selection=True,stable_task_number=True,report_blocked_until_task_saved=True,report_prefill_edit_and_confirm=True,daily_progress_link=True,reopen_edits_same_task=True,page_errors=errors)))
 browser.close()
