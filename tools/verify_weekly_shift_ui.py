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
html=f'''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
import {{createApp,h,ref}} from {json.dumps(vue)};import Management from '/src/views/hr/MonthlyShiftManagement.vue';import Mine from '/src/views/schedule/components/MyMonthlyShift.vue';import AppForm from '/src/components/common/AppForm.vue';const app=createApp({{setup(){{const mine=ref(false);return()=>h('div',[h('button',{{onClick:()=>mine.value=!mine.value}},'切换个人排班'),mine.value?h(Mine):h(Management)])}}}});app.component('AppForm',AppForm);app.mount('#app');</script>'''
people=[{'id':key,'name':name,'username':key,'active':True,'departments':[{'id':'customer','name':'客户/销售部'}]} for key,name in [('person','界面测试人员'),('other','其他排班人员'),('new','待安排人员')]]
plans={};posts=[];writes=[];errors=[];reads=[]
def plan(week):
 from datetime import date
 return plans.setdefault(week,{'ready':True,'week_start':week,'week_end':(date.fromisoformat(week)+timedelta(days=6)).isoformat(),'revision':1,'assignments':[{'user_id':key,'name':name,'department':'customer','shift':'early' if week=='2026-10-26' else 'late','active':True} for key,name in [('person','界面测试人员'),('other','其他排班人员')]],'shifts':SHIFTS,'departments':DEPARTMENTS})
def api(route):
 request=route.request;path=urlparse(request.url).path;q=parse_qs(urlparse(request.url).query);week=q.get('week',['2026-10-26'])[0];reads.append((path,week))
 if path.endswith('/directory'):result={'ready':True,'items':[{'id':row['code'],'name':row['label']} for row in DEPARTMENTS],'people':people}
 elif path.endswith('/weekly/transfer'):
  data=request.post_data_json;posts.append(data);a,b=plan(data['source_week']),plan(data['target_week']);old=list(a['assignments'])
  if data['operation']!='copy':a['assignments']=list(b['assignments']) if data['operation']=='swap' else [];a['revision']+=1
  b['assignments']=old;b['revision']+=1;result={'source':a,'target':b}
 elif path.endswith('/weekly/mine'):
  result={**plan(week),'assignment':next((row for row in plan(week)['assignments'] if row['user_id']=='person'),None)};result.pop('assignments')
 elif path.endswith('/weekly') and request.method=='PUT':
  data=request.post_data_json;writes.append(week);result=plan(week);result['revision']+=1;result['assignments']=[{**row,'name':next(p['name'] for p in people if p['id']==row['user_id']),'active':True} for row in data['assignments']]
 elif path.endswith('/weekly') or path.endswith('/weekly/overview'):result=plan(week)
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
 expect(page.get_by_role('heading',name='2026-10-26 至 2026-11-01 班次安排')).to_be_visible()
 expect(page.locator('[draggable="true"]')).to_have_count(0)
 drop(page.locator('[data-cell="customer:early"]'),'application/x-project-personnel',[{'id':'new'}]);assert not writes
 page.get_by_role('button',name='快捷安排（展开）').click();page.get_by_role('button',name='本月安排',exact=True).click()
 expect(page.locator('.month-week-table tbody tr')).to_have_count(5)
 expect(page.get_by_role('button',name='调整本周',exact=True)).to_have_count(0)
 actions=page.locator('.shift-title-actions button');assert actions.nth(0).inner_text()=='增加/编辑班次' and actions.nth(1).inner_text()=='固定班次人员'
 page.get_by_role('button',name='增加/编辑班次',exact=True).click()
 dialog=page.get_by_role('dialog',name='增加/编辑班次',exact=True);panel=dialog.locator('.el-dialog')
 expect(dialog.get_by_role('combobox',name='编辑月份',exact=True)).to_have_value('2026-11')
 expect(dialog.locator('[data-editor-week]')).to_have_count(6)
 expect(dialog.locator('[data-editor-week].is-active')).to_have_count(1)
 first=dialog.locator('[data-editor-week="2026-10-26"]');expect(first).to_contain_text('跨月周')
 expect(first.locator('.monthly-matrix')).to_be_visible()
 original_other=json.dumps(plan('2026-11-02'),sort_keys=True)
 drop(first.locator('[data-cell="customer:late"]'),'application/x-project-personnel',[{'id':'new'}])
 expect(first.locator('[data-cell="customer:late"]')).to_contain_text('待安排人员')
 assert writes==['2026-10-26'] and json.dumps(plan('2026-11-02'),sort_keys=True)==original_other
 drop(first.locator('[data-cell="customer:late"]'),'application/x-shift-plan',{'period':'2026-10-19','user_ids':['person']});assert len(writes)==1
 # 按周编辑只展示本周，不批量改其他周。
 dialog.locator('.el-radio-button').filter(has_text='按周编辑').click();expect(dialog.locator('[data-editor-week]')).to_have_count(1)
 expect(dialog.get_by_role('combobox',name='编辑周',exact=True)).to_have_value('2026-10-26')
 dialog.locator('.el-radio-button').filter(has_text='按月分周编辑').click()
 month_input=dialog.get_by_role('combobox',name='编辑月份',exact=True);month_input.fill('2026-10');month_input.press('Enter')
 expect(dialog.locator('[data-editor-week]')).to_have_count(5);expect(dialog.locator('[data-editor-week="2026-10-26"]')).to_contain_text('跨月周')
 # 搜索自动收集表单字段，并可定位隐藏标签页。
 search=dialog.get_by_role('textbox',name='搜索项目表单字段');search.fill('目标周')
 expect(page.locator('.project-field-search-popper:visible')).to_contain_text('目标周')
 page.locator('.project-field-search-popper:visible li').filter(has_text='目标周').first.click()
 expect(dialog.get_by_role('combobox',name='目标周',exact=True)).to_be_visible()
 expect(dialog.get_by_role('button',name='确认复制',exact=True)).to_be_enabled()
 source_snapshot=json.dumps(plan('2026-10-26'),sort_keys=True)
 dialog.get_by_role('button',name='确认复制',exact=True).click();confirm=page.locator('.el-message-box');expect(confirm).to_contain_text('保留来源周');confirm.get_by_role('button',name='取消',exact=True).click();assert not posts
 dialog.get_by_role('button',name='确认复制',exact=True).click();confirm.get_by_role('button',name='确认复制',exact=True).click();expect(dialog.get_by_role('button',name='确认复制',exact=True)).to_be_enabled();assert posts[-1]['operation']=='copy';assert json.dumps(plan('2026-10-26'),sort_keys=True)==source_snapshot
 for title,action in [('两周互换','swap'),('转移到另一周','move')]:
  dialog.locator('.el-radio-button').filter(has_text=title).click();label='确认互换' if action=='swap' else '确认转移';dialog.get_by_role('button',name=label,exact=True).click();confirm.get_by_role('button',name=label,exact=True).click();expect(dialog.get_by_role('button',name='完成',exact=True)).to_be_enabled();assert posts[-1]['operation']==action
 expect(dialog).to_be_visible()
 # 内容独立滚动，底部按钮保持在视口；可拖动、限制边界并复位。
 dialog.get_by_role('tab',name='班次编辑',exact=True).click();first=dialog.locator('[data-editor-week="2026-10-26"]')
 if 'is-active' not in first.get_attribute('class'):first.locator('.el-collapse-item__header').click()
 body=dialog.locator('.el-dialog__body');body.evaluate('(el)=>{el.scrollTop=el.scrollHeight}');expect(dialog.get_by_role('button',name='完成',exact=True)).to_be_in_viewport()
 page.wait_for_timeout(350);before=panel.bounding_box();header=dialog.locator('.el-dialog__header').bounding_box();page.mouse.move(header['x']+250,header['y']+15);page.mouse.down();page.mouse.move(header['x']+285,header['y']+65,steps=8);page.mouse.up();page.wait_for_timeout(100);after=panel.bounding_box();assert abs(after['y']-before['y'])>20
 page.mouse.move(after['x']+250,after['y']+30);page.mouse.down();page.mouse.move(-1000,-1000,steps=8);page.mouse.up();bounds=panel.bounding_box();assert bounds['x']>=0 and bounds['y']>=0
 dialog.get_by_role('button',name='完成',exact=True).click();expect(dialog).not_to_be_visible();page.get_by_role('button',name='增加/编辑班次',exact=True).click();expect(dialog).to_be_visible();page.wait_for_timeout(350);assert abs(panel.bounding_box()['x']-before['x'])<3
 page.set_viewport_size({'width':390,'height':844});expect(dialog.get_by_role('button',name='完成',exact=True)).to_be_in_viewport();bounds=panel.bounding_box();assert bounds['width']<=390 and bounds['height']<=844
 dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible();page.set_viewport_size({'width':1600,'height':1000})
 # 工作台默认全部，切换本人和月视图均只读。
 page.get_by_role('button',name='切换个人排班',exact=True).click();expect(page.locator('.my-monthly-shift')).to_contain_text('当前查看全部人员')
 expect(page.locator('.my-monthly-shift [draggable="true"]')).to_have_count(0)
 assert any(path.endswith('/weekly/overview') for path,week in reads)
 page.locator('.my-monthly-shift .el-radio-button').filter(has_text='仅看自己').click();expect(page.locator('.my-monthly-shift')).to_contain_text('当前查看本人')
 page.get_by_role('button',name='快捷安排（展开）').click();page.get_by_role('button',name='本月安排',exact=True).click();expect(page.locator('.my-month-weeks>.el-card')).to_have_count(5)
 page.locator('.my-monthly-shift .el-radio-button').filter(has_text='全部人员').click();expect(page.locator('.month-week-table tbody tr')).to_have_count(5)
 assert len(writes)==1 and not errors,errors
 print(json.dumps({'readonly_page':True,'next_month_default':True,'independent_week_edits':True,'cross_month_shared_week':True,'copy_source_unchanged':True,'copy_move_swap_confirmed':True,'field_search_hidden_tab':True,'dialog_drag_scroll_reset_mobile':True,'workbench_default_all_and_personal':True,'page_errors':errors}))
 browser.close()
