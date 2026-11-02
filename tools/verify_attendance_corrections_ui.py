"""补卡提交、行政确认全程记录、跨日字段及居家小时选项；全部API拦截。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode();vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h,ref} from VUE;import Panel from '/src/views/schedule/components/ClockCorrections.vue';import Home from '/src/views/schedule/components/HomeOfficePanel.vue';import Clock from '/src/views/schedule/components/AttendanceClockDialog.vue';import AppForm from '/src/components/common/AppForm.vue';const app=createApp({setup(){const admin=ref(false),home=ref(false),showClock=ref(false);return()=>h('div',[h('button',{onClick:()=>admin.value=!admin.value},'切换行政'),h('button',{onClick:()=>home.value=!home.value},'检查居家'),h('button',{onClick:()=>showClock.value=true},'检查跨日签退'),home.value?h(Home):h(Panel,{admin:admin.value,key:String(admin.value)}),h(Clock,{modelValue:showClock.value,'onUpdate:modelValue':v=>showClock.value=v,mode:'out',record:{id:'clock-1',check_in:'2026-10-28T09:00:00+08:00',shift:{code:'early',label:'早班',periods:['09:00–12:00','13:30–18:30']},requires_cross_day_reason:true}})])}});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
rows=[];writes=[];errors=[]
def home_data():return {'ready':True,'qualified':True,'quota_available':True,'qualification_hint':'已获得资格','allowed_minutes':[120,240,480],'month_hours':0,'two_hour_count':0,'partial_hours':0,'annual_limit':12,'annual_remaining':12,'manual_used_days':0,'applications':[],'qualification_requests':[]}
def api(route):
 path=urlparse(route.request.url).path;body=route.request.post_data_json if route.request.method in ('POST','PUT') else None
 if path=='/api/attendance/clock-corrections' and body:
  writes.append((path,body));rows.append({**body,'declarations':{key:body.get(key) for key in ('early_work_confirmed','breakfast_after_eating','dinner_eaten','deduct_invalid_time','invalid_minutes','invalid_reason','next_start')},'id':'request-1','name':'测试人员','status':'pending','created_at':'2026-10-30T10:00:00+08:00','history':[{'action':'submitted','actor_name':'测试人员','at':'2026-10-30T10:00:00+08:00'}]});result={'message':'已提交'}
 elif path=='/api/attendance/clock-corrections/request-1' and route.request.method=='PUT':
  writes.append((path,body));before={key:value for key,value in rows[0].items() if key!='history'};rows[0].update(body);rows[0]['history'].append({'action':'updated','actor_name':'测试人员','at':'2026-10-30T10:30:00+08:00','before_request':before,'request':body});result={'message':'已修改'}
 elif path.endswith('/confirm'):
  writes.append((path,body));rows[0]['status']='confirmed';rows[0]['history'].append({'action':'confirmed','actor_name':'行政人员','at':'2026-10-30T11:00:00+08:00','before':{},'after':{'check_in':rows[0]['requested_at']}});result={'message':'已确认'}
 elif path=='/api/attendance/clock-corrections':result={'items':rows,'clock_records':[{'id':'clock-1','day':'2026-10-28','segment':0,'check_in':'2026-10-28T09:00:00+08:00','check_out':None,'shift':{'code':'early','label':'早班'}}],'adjustments':[]}
 elif path=='/api/attendance/home-office/apply':writes.append((path,body));result={'message':'已提交',**home_data()}
 elif path=='/api/attendance/home-office':result=home_data()
 else:result={'ready':True,'items':[]}
 route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1400,'height':1000},service_workers='block');context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/correction-ui-check',lambda route:route.fulfill(content_type='text/html',body=html));page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/correction-ui-check')
 def item(dialog,label):return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label').filter(has_text=re.compile('^'+re.escape(label)+'$')))
 def filldate(dialog,label,text):
  control=item(dialog,label).locator('input');control.fill(text);control.press('Enter');control.press('Tab')
 def choice(dialog,label,text):item(dialog,label).locator('.el-radio').filter(has_text=re.compile('^'+text+'$')).click()
 page.get_by_role('button',name='补上班打卡',exact=True).click();dialog=page.get_by_role('dialog',name='补上班打卡',exact=True)
 dialog.get_by_role('button',name='提交并通知行政部',exact=True).click();expect(dialog.locator('.el-form-item__error')).to_have_count(4);assert not writes
 filldate(dialog,'考勤日期（原上班日期）','2026-10-28');filldate(dialog,'实际应补上班时间','2026年10月28日 09:00:00');item(dialog,'向行政部说明原因').locator('textarea').fill('忘记打卡，请确认');expect(item(dialog,'证据截图及说明（非必填）').locator('input[type=file]')).to_have_count(1)
 choice(dialog,'提前到达的时间是否确实已在工作','否');choice(dialog,'是否在早餐后打卡','是')
 page.set_viewport_size({'width':700,'height':550});footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=550
 dialog.get_by_role('button',name='提交并通知行政部',exact=True).click();expect(dialog).not_to_be_visible();assert writes[-1][1]['requested_at']=='2026-10-28T09:00:00+08:00';expect(page.locator('.clock-corrections')).to_contain_text('待行政确认')
 page.set_viewport_size({'width':1400,'height':1000})
 page.get_by_role('button',name='修改',exact=True).click();dialog=page.get_by_role('dialog',name='修改补上班打卡',exact=True)
 expect(item(dialog,'向行政部说明原因').locator('textarea')).to_have_value('忘记打卡，请确认')
 expect(item(dialog,'实际应补上班时间').locator('input')).to_have_value('2026年10月28日 09:00:00')
 dialog.evaluate('(el)=>Promise.all(el.getAnimations({subtree:true}).map(a=>a.finished))');original=dialog.locator('.el-dialog').bounding_box();header=dialog.locator('.dialog-field-search-header__title').bounding_box()
 page.mouse.move(header['x']+20,header['y']+10);page.mouse.down();page.mouse.move(header['x']+150,header['y']+60,steps=10);page.mouse.up()
 moved=dialog.locator('.el-dialog').bounding_box();assert moved['x']>original['x']+50
 header=dialog.locator('.dialog-field-search-header__title').bounding_box();page.mouse.move(header['x']+20,header['y']+10);page.mouse.down();page.mouse.move(-1000,-1000);page.mouse.up();bounded=dialog.locator('.el-dialog').bounding_box();assert bounded['x']>=-1 and bounded['y']>=-1
 dialog.get_by_role('button',name='关闭').click();expect(dialog).not_to_be_visible()
 page.get_by_role('button',name='修改',exact=True).click();dialog=page.get_by_role('dialog',name='修改补上班打卡',exact=True)
 dialog.evaluate('(el)=>Promise.all(el.getAnimations({subtree:true}).map(a=>a.finished))');reopened=dialog.locator('.el-dialog').bounding_box();assert abs(reopened['x']-original['x'])<2 and abs(reopened['y']-original['y'])<2
 item(dialog,'向行政部说明原因').locator('textarea').fill('修改为实际到岗时间')
 filldate(dialog,'实际应补上班时间','2026年10月28日 09:10:00')
 page.set_viewport_size({'width':700,'height':550});content=dialog.locator('.el-dialog__body');content.evaluate('(node)=>node.scrollTop=node.scrollHeight');footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=550
 dialog.get_by_role('button',name='保存修改并通知行政部',exact=True).click();expect(dialog).not_to_be_visible()
 assert writes[-1][1]['expected_history_length']==1 and writes[-1][1]['requested_at']=='2026-10-28T09:10:00+08:00'
 expect(page.locator('.clock-corrections')).to_contain_text('修改为实际到岗时间')
 page.get_by_role('button',name='查看记录',exact=True).click();expect(page.locator('.correction-detail:visible')).to_contain_text('修改申请');expect(page.locator('.correction-detail:visible')).to_contain_text('忘记打卡，请确认');page.get_by_role('button',name='查看记录',exact=True).click()
 page.set_viewport_size({'width':1400,'height':1000});page.get_by_role('button',name='切换行政',exact=True).click();page.get_by_role('button',name='确认补卡',exact=True).click();page.locator('.el-message-box').get_by_role('button',name='确认补卡',exact=True).click();expect(page.locator('.clock-corrections')).to_contain_text('已确认')
 page.get_by_role('button',name='查看记录',exact=True).click();detail=page.locator('.correction-detail:visible');expect(detail).to_contain_text('提交申请');expect(detail).to_contain_text('行政确认');expect(detail).to_contain_text('修改后');page.get_by_role('button',name='查看记录',exact=True).click()
 page.get_by_role('button',name='切换行政',exact=True).click();page.get_by_role('button',name='补下班打卡',exact=True).click();dialog=page.get_by_role('dialog',name='补下班打卡',exact=True);dialog.get_by_role('button',name='提交并通知行政部',exact=True).click();expect(dialog.locator('.el-form-item__error').filter(has_text='请填写下次或第二天上班时间')).to_have_count(1);dialog.get_by_role('button',name='取消',exact=True).click()
 page.get_by_role('button',name='检查跨日签退',exact=True).click();dialog=page.get_by_role('dialog',name='下班打卡确认',exact=True);expect(dialog).to_contain_text('第二天/第二次上班时间');dialog.get_by_role('button',name='打卡',exact=True).click();expect(dialog.locator('.el-form-item__error').filter(has_text='请说明跨日/跨组签退原因')).to_have_count(1);dialog.get_by_role('button',name='取消',exact=True).click()
 page.get_by_role('button',name='检查居家',exact=True).click();page.get_by_role('button',name='居家办公申请',exact=True).click();dialog=page.get_by_role('dialog',name='居家办公申请',exact=True);choice(dialog,'申请时长','2小时');dialog.get_by_role('button',name='提交并通知行政部',exact=True).click();expect(dialog).not_to_be_visible();assert writes[-1][1]['minutes']==120
 assert not errors,errors
 print(json.dumps({'correction_required_fields':True,'optional_screenshot_editor':True,'admin_confirmation_history':True,'checkout_next_start_required':True,'cross_day_reason_required':True,'home_hour_choice':True,'fixed_footer':True,'edit_prefill_save_history':True,'drag_bounds_reset_close':True,'page_errors':errors}))
 browser.close()
