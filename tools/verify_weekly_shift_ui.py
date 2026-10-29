"""周班次转移、互换确认与月视图回归；真实组件，业务接口全部拦截，不写业务数据库。"""
import json,re,sys
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from datetime import datetime,timezone,timedelta
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from monthly_shift import SHIFTS,DEPARTMENTS
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html=f'''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><style>*{{box-sizing:border-box}}html,body,#app{{margin:0;width:100%;height:100%;overflow:hidden}}#app{{width:100vw;height:100vh}}.test-shell{{height:100%;display:grid;grid-template-columns:200px minmax(0,1fr)}}.main-content{{min-width:0;overflow:auto;padding:12px;box-sizing:border-box}}.test-nav{{height:48px;display:flex;align-items:center;background:#f1f5f9;margin-bottom:8px}}@media(max-width:600px){{.test-shell{{grid-template-columns:50px minmax(0,1fr)}}}}</style><div id="app"></div><script type="module">
import {{createApp,h,ref}} from {json.dumps(vue)};import Management from '/src/views/hr/MonthlyShiftManagement.vue';import Mine from '/src/views/schedule/components/MyMonthlyShift.vue';import AppForm from '/src/components/common/AppForm.vue';import {{applyUiZoom}} from '/src/composables/useUiZoom.js';const app=createApp({{setup(){{const mine=ref(false);return()=>h('div',{{class:'test-shell'}},[h('aside','侧栏'),h('main',{{class:'main-content'}},[h('nav',{{class:'test-nav'}},'排班管理 / 考勤管理'),h('div',{{class:'hr-workspace-content'}},[h('button',{{onClick:()=>mine.value=!mine.value}},'切换个人排班'),mine.value?h(Mine):h(Management)])])])}}}});app.component('AppForm',AppForm);app.mount('#app');window.__setTestZoom=applyUiZoom;applyUiZoom(0.8);</script>'''
people=[{'id':key,'name':name,'username':key,'active':True,'departments':[{'id':'customer','name':'客户/销售部'}]} for key,name in [('person','界面测试人员'),('other','其他排班人员'),('new','待安排人员')]]
plans={};publications={};audits={};posts=[];writes=[];errors=[];reads=[];fail_next=False
def plan(week):
 from datetime import date
 return plans.setdefault(week,{'ready':True,'week_start':week,'week_end':(date.fromisoformat(week)+timedelta(days=6)).isoformat(),'revision':1,'sync_ready':True,'can_edit':True,'published':False,'needs_sync':True,'publication_revision':0,'fixed_revision':0,'assignments':[{'user_id':key,'name':name,'department':'customer','shift':'early' if week=='2026-10-26' else 'late','active':True} for key,name in [('person','界面测试人员'),('other','其他排班人员')]],'shifts':SHIFTS,'departments':DEPARTMENTS})
def api(route):
 global fail_next
 request=route.request;path=urlparse(request.url).path;q=parse_qs(urlparse(request.url).query);week=q.get('week',['2026-10-26'])[0];reads.append((path,week))
 if fail_next and path.endswith('/weekly'):
  fail_next=False;route.fulfill(status=502,content_type='application/json',body=json.dumps({'detail':'上游服务暂时不可用，请稍后重试'}));return
 if path.endswith('/fixed'):result={'ready':True,'revision':0,'assignments':[],'people':[{**person,'default_department':'customer'} for person in people],'shifts':SHIFTS,'departments':DEPARTMENTS}
 elif path.endswith('/directory'):result={'ready':True,'items':[{'id':row['code'],'name':row['label']} for row in DEPARTMENTS],'people':people}
 elif path.endswith('/weekly/history'):result={'total':len([row for row in audits.get(week,[]) if q.get('public',['true'])[0]=='false' or row.get('publication_revision')]),'items':[row for row in audits.get(week,[]) if q.get('public',['true'])[0]=='false' or row.get('publication_revision')]}
 elif path.endswith('/weekly/sync'):
  result=plan(week);result['publication_revision']+=1;result['published']=True;result['can_edit']=False;result['needs_sync']=False;result['published_at']='2026-10-28T19:00:00+08:00';publications[week]=json.loads(json.dumps(result))
  for row in audits.get(week,[]):row['publication_revision']=result['publication_revision']
 elif path.endswith('/weekly/enable-edit'):result=plan(week);result['can_edit']=True
 elif path.endswith('/weekly/transfer'):
  data=request.post_data_json;posts.append(data);a,b=plan(data['source_week']),plan(data['target_week']);old=list(a['assignments'])
  if data['operation']!='copy':a['assignments']=list(b['assignments']) if data['operation']=='swap' else [];a['revision']+=1
  b['assignments']=old;b['revision']+=1;result={'source':a,'target':b}
 elif path.endswith('/weekly/mine'):
  published=publications.get(week,{**plan(week),'assignments':[],'published':False});result={**published,'assignment':next((row for row in published['assignments'] if row['user_id']=='person'),None)};result.pop('assignments')
 elif path.endswith('/weekly') and request.method=='PUT':
  data=request.post_data_json;writes.append(week);result=plan(week);result['revision']+=1;result['needs_sync']=True;audits.setdefault(week,[]).append({'id':str(len(writes)),'action':'draft_save','revision':result['revision'],'publication_revision':None,'actor_name':'测试管理员','created_at':'2026-10-28T19:00:00+08:00','changes':[]});result['assignments']=[{**row,'name':next(p['name'] for p in people if p['id']==row['user_id']),'active':True} for row in data['assignments']]
 elif path.endswith('/weekly/overview'):result=publications.get(week,{**plan(week),'assignments':[],'published':False})
 elif path.endswith('/weekly'):result=plan(week)
 else:result={'ready':True,'items':[],'assignments':[],'revision':0}
 route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 context=browser.new_context(viewport={'width':1600,'height':1000},timezone_id='America/Los_Angeles',service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 context.route(BASE+'/weekly-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
 page=context.new_page();page.clock.set_fixed_time(datetime(2026,10,28,18,tzinfo=timezone(timedelta(hours=8))))
 page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/weekly-ui-check')
 def drop(target,kind,data):
  transfer=page.evaluate_handle('new DataTransfer()');transfer.evaluate('(t,p)=>t.setData(p.kind,JSON.stringify(p.data))',{'kind':kind,'data':data});target.dispatch_event('drop',{'dataTransfer':transfer})
 management=page.locator('.monthly-shift-management')
 expect(page.locator('vite-error-overlay')).to_have_count(0)
 expect(management.locator('.shift-period-main .el-radio-button').filter(has_text='进行排班')).to_have_class(re.compile('is-active'))
 expect(management.get_by_role('radio',name='按周编辑',exact=True)).to_be_checked()
 management.locator('.el-radio-button').filter(has_text='按月分周编辑').click()
 expect(management.locator('[data-editor-week]')).to_have_count(5)
 expect(management.locator('[data-editor-week].is-active')).to_have_count(1)
 current=management.locator('[data-editor-week="2026-10-26"]');expect(current).to_contain_text('跨月周')
 expect(current.locator('.monthly-matrix')).to_be_visible()
 other_before=json.dumps(plan('2026-10-19'),sort_keys=True)
 drop(current.locator('[data-cell="customer:early"]'),'application/x-project-personnel',[{'id':'new'}])
 drop(current.locator('[data-cell="customer:late"]'),'application/x-shift-plan',{'period':'2026-10-26','user_ids':['new']})
 expect(current.locator('[data-cell="customer:late"]')).to_contain_text('待安排人员')
 assert writes==['2026-10-26'] and json.dumps(plan('2026-10-19'),sort_keys=True)==other_before
 assert not publications
 expect(current.get_by_role('button',name='同步（尚未同步）',exact=True)).to_have_class(re.compile('needs-sync'))
 current.get_by_role('button',name='同步（尚未同步）',exact=True).click();expect(current.get_by_role('button',name='已同步',exact=True)).to_be_visible()
 expect(current.locator('.monthly-person[draggable="true"]')).to_have_count(0)
 current.get_by_role('button',name='修改',exact=True).click();expect(current.locator('.monthly-person[draggable="true"]')).to_have_count(3)
 assert current.locator('.monthly-matrix-scroll').evaluate('el=>getComputedStyle(el).overflowY')=='scroll'
 assert current.locator('.arrangement-personnel').evaluate('el=>getComputedStyle(el).overflowY')=='scroll'
 sizes=current.evaluate('el=>[el.querySelector(".el-collapse-item__title"),el.querySelector(".personnel-heading strong"),el.querySelector(".monthly-matrix")].map(item=>getComputedStyle(item).fontSize)');assert len(set(sizes))==1,sizes
 drop(current.locator('[data-cell="customer:late"]'),'application/x-shift-plan',{'period':'2026-10-19','user_ids':['person']});assert len(writes)==1
 # 月份总览仍只读，进行排班恢复分周编辑；跨月周使用同一数据。
 management.locator('.shift-period-main .el-radio-button').filter(has_text='每月安排').click()
 expect(management.locator('.month-week-table tbody tr')).to_have_count(5);expect(management.locator('[draggable="true"]')).to_have_count(0)
 expect(management.locator('.planning-period-form')).to_have_count(0)
 management.locator('.shift-period-main .el-radio-button').filter(has_text='进行排班').click()
 month_input=management.get_by_role('combobox',name='编辑月份',exact=True);month_input.fill('2026-11');month_input.press('Enter')
 expect(management.locator('[data-editor-week]')).to_have_count(6)
 current=management.locator('[data-editor-week="2026-10-26"]');expect(current).to_contain_text('待安排人员')
 expect(management.locator('[data-editor-week].is-active')).to_have_count(1)
 management.locator('.planning-period-form .el-radio-button').filter(has_text='按周编辑').click()
 expect(management.locator('[data-editor-week]')).to_have_count(1)
 expect(management.get_by_role('combobox',name='编辑周',exact=True)).to_have_value('2026-10-26')
 page.get_by_role('button',name='快速查看（展开）').click();page.get_by_role('button',name='上周安排',exact=True).click()
 expect(management.locator('[data-editor-week="2026-10-19"]')).to_be_visible()
 page.get_by_role('button',name='本周安排',exact=True).click();expect(management.locator('[data-editor-week="2026-10-26"]')).to_be_visible()
 assert not page.get_by_role('button',name='增加/编辑班次',exact=True).count()
 # 操作窗口只剩来源、目标与复制转移互换，不含班次矩阵或编辑方式。
 def open_operations():
  page.evaluate('document.body.scrollLeft=0;document.body.scrollTop=0;document.querySelector(".main-content").scrollTop=0')
  button=page.locator('.shift-title-actions').get_by_role('button',name='复制 / 转移 / 互换',exact=True).bounding_box();page.mouse.click(button['x']+button['width']/2,button['y']+button['height']/2)
 fail_next=True;open_operations()
 dialog=page.get_by_role('dialog',name='复制 / 转移 / 互换',exact=True);panel=dialog.locator('.el-dialog')
 expect(dialog.get_by_role('button',name='重新加载安排',exact=True)).to_be_visible();dialog.get_by_role('button',name='重新加载安排',exact=True).click()
 expect(dialog.get_by_role('button',name='确认复制',exact=True)).to_be_enabled()
 expect(dialog.locator('.monthly-matrix')).to_have_count(0)
 expect(dialog.get_by_role('tab',name='班次编辑',exact=True)).to_have_count(0)
 expect(dialog.get_by_text('编辑方式',exact=True)).to_have_count(0)
 expect(dialog.get_by_role('combobox',name='来源周',exact=True)).to_have_value('2026-10-26')
 def assert_region():
  actual=panel.bounding_box();expected=page.locator('.hr-workspace-content').evaluate('el=>{const r=el.getBoundingClientRect(),m=el.closest(".main-content").getBoundingClientRect(),left=Math.max(0,r.left,m.left),top=Math.max(0,r.top,m.top);return {x:left,y:top,width:Math.min(innerWidth,r.right,m.right)-left,height:Math.min(innerHeight,m.bottom)-top}}')
  assert all(abs(actual[key]-expected[key])<1.1 for key in actual),(actual,expected)
  return actual
 page.wait_for_timeout(350);bounds=assert_region();assert bounds['x']>0 and bounds['y']>0
 header=dialog.locator('.el-dialog__header').bounding_box();page.mouse.move(header['x']+350,header['y']+25);page.mouse.down();page.mouse.move(header['x']+420,header['y']+70,steps=5);page.mouse.up();assert_region()
 page.evaluate('window.__setTestZoom(1.25)');page.wait_for_timeout(200);assert_region();page.evaluate('window.__setTestZoom(0.8)');page.wait_for_timeout(200);assert_region()
 search=dialog.get_by_role('textbox',name='搜索项目表单字段');search.fill('目标周');expect(page.locator('.project-field-search-popper:visible')).to_contain_text('目标周');page.locator('.project-field-search-popper:visible li').filter(has_text='目标周').first.click()
 source_snapshot=json.dumps(plan('2026-10-26'),sort_keys=True)
 dialog.get_by_role('button',name='确认复制',exact=True).click();confirm=page.locator('.el-message-box');expect(confirm).to_contain_text('保留来源周');confirm.get_by_role('button',name='取消',exact=True).click();assert not posts
 dialog.get_by_role('button',name='确认复制',exact=True).click();confirm.get_by_role('button',name='确认复制',exact=True).click();expect(dialog.get_by_role('button',name='关闭',exact=True)).to_be_enabled();assert posts[-1]['operation']=='copy' and json.dumps(plan('2026-10-26'),sort_keys=True)==source_snapshot
 for title,action in [('两周互换','swap'),('转移到另一周','move')]:
  dialog.locator('.el-radio-button').filter(has_text=title).click()
  unlocks=dialog.get_by_role('button').filter(has_text='开启修改')
  if unlocks.count():unlocks.first.click()
  label='确认互换' if action=='swap' else '确认转移';dialog.get_by_role('button',name=label,exact=True).click();confirm.get_by_role('button',name=label,exact=True).click();expect(dialog.get_by_role('button',name='关闭',exact=True)).to_be_enabled();assert posts[-1]['operation']==action
 expect(dialog).to_be_visible()
 page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(150);assert_region();expect(dialog.get_by_role('button',name='关闭',exact=True)).to_be_in_viewport()
 dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible();page.set_viewport_size({'width':1600,'height':1000})
 # 工作台保持全部/本人只读，不受恢复主页面编辑影响。
 page.get_by_role('button',name='切换个人排班',exact=True).click();expect(page.locator('.my-monthly-shift')).to_contain_text('当前查看全部人员')
 expect(page.locator('.my-monthly-shift [draggable="true"]')).to_have_count(0)
 page.locator('.my-monthly-shift .el-radio-button').filter(has_text='仅看自己').click();expect(page.locator('.my-monthly-shift')).to_contain_text('当前查看本人')
 page.get_by_role('button',name='快速查看（展开）').click();page.get_by_role('button',name='本月安排',exact=True).click();expect(page.locator('.my-month-weeks>.el-card')).to_have_count(5)
 page.locator('.my-monthly-shift .el-radio-button').filter(has_text='全部人员').click();expect(page.locator('.month-week-table tbody tr')).to_have_count(5)
 page.get_by_role('button',name='切换个人排班',exact=True).click()
 page.get_by_role('button',name='固定班次人员',exact=True).click();fixed=page.get_by_role('dialog',name='固定班次人员',exact=True)
 fixed.get_by_role('combobox',name='界面测试人员固定部门',exact=True).locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")]').click();page.get_by_role('option',name='IT部门',exact=True).click()
 fixed.get_by_role('combobox',name='界面测试人员固定班次',exact=True).locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")]').click();page.get_by_role('option',name='晚班',exact=True).click()
 page.wait_for_timeout(500)
 saved_fixed=page.evaluate("JSON.parse(localStorage.getItem('form-drafts:fixed-shift-config:anonymous'))")
 assert saved_fixed['configuration:0']['form']['settings']['person']['department']=='it'
 fixed.get_by_role('button',name='取消',exact=True).click();expect(fixed).not_to_be_visible();page.get_by_role('button',name='固定班次人员',exact=True).click()
 page.locator('.el-message-box').get_by_role('button',name='恢复草稿',exact=True).click()
 expect(fixed.get_by_role('combobox',name='界面测试人员固定部门',exact=True).locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")]')).to_contain_text('IT部门')
 expect(fixed.get_by_role('combobox',name='界面测试人员固定班次',exact=True).locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")]')).to_contain_text('晚班')
 assert len(writes)==1 and not errors,errors
 print(json.dumps({'main_page_editable':True,'renamed_planning_entry':True,'independent_week_save':True,'foldable_month_weeks':True,'cross_month_shared_week':True,'month_overview_readonly':True,'operations_only_dialog':True,'copy_move_swap_confirmed':True,'content_region_scaled_and_mobile':True,'workbench_still_readonly':True,'fixed_config_dependent_fields_recovered':True,'page_errors':errors}))
 browser.close()
