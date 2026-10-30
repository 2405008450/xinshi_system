"""工作台手动打卡、确认表单及折叠；所有业务请求拦截。"""
import json,re,sys
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from monthly_shift import SHIFTS,DEPARTMENTS
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import Mine from '/src/views/schedule/components/MyMonthlyShift.vue';import Attendance from '/src/views/schedule/components/AttendanceOverview.vue';import AppForm from '/src/components/common/AppForm.vue';
const app=createApp({setup(){const admin=ref(false);return()=>h('div',[h('button',{onClick:()=>admin.value=!admin.value},'切换公司考勤'),admin.value?h(Attendance,{admin:true}):h(Mine)])}});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
shift={**SHIFTS[1],'fixed':True};sessions=[];writes=[];reads=[];errors=[]
def api(route):
 global sessions
 request=route.request;path=urlparse(request.url).path;reads.append(path)
 if path.endswith('/today'):
  opened=next((row for row in sessions if not row['check_out']),None);count=2 if shift['code']=='customer_remote' else 1
  result={'day':'2026-10-28','shift':shift,'record':opened or (sessions[-1] if sessions else None),'sessions':sessions,'segment_count':count,'can_check_in':not opened and len(sessions)<count,'next_segment':min(len(sessions),1),'clock_ready':True,'leaves':[]}
 elif path.endswith('/check-in'):
  data=request.post_data_json;writes.append((path,data));record={'id':f'record-{len(sessions)}','day':'2026-10-28','segment':data['segment'],'check_in':'2026-10-28T08:00:00+08:00','check_out':None,'shift':shift};sessions.append(record);result={'message':'上班打卡成功','record':record}
 elif path.endswith('/check-out'):
  data=request.post_data_json;writes.append((path,data));record=next(row for row in sessions if row['id']==data['record_id']);record['check_out']='2026-10-28T18:30:00+08:00';result={'message':'打卡成功','record':record}
 elif path.endswith('/mine') or path.endswith('/report'):
  result={'start':'2026-10-26','end':'2026-11-01','records':[{'user_id':'self','name':'本人','day':'2026-10-28','shift':shift,'check_in':'2026-10-28T08:00:00+08:00','check_out':'2026-10-28T18:30:00+08:00','raw_overtime_minutes':60,'overtime_minutes':25,'violation_count':1,'sessions':[{'id':'report-session','segment':0,'raw_overtime_minutes':60,'breakfast_deduction_minutes':15,'dinner_deduction_minutes':20,'overtime_minutes':25,'deduction_details':[{'reason':'早餐前打卡，早餐抵扣并记违纪一次','minutes':15,'kind':'deduction'}]}]}],'total':1,'totals':{'overtime_minutes':25,'violation_count':1},'people':[],'departments':[],'monthly_balances':[{'user_id':'self','name':'本人','month':'2026-10','raw_minutes':60,'deduction_minutes':35,'overtime_minutes':25}]}
 elif path.endswith('/overview') and '/weekly/' in path:result={'ready':True,'week_start':'2026-10-26','week_end':'2026-11-01','assignments':[],'shifts':SHIFTS,'departments':DEPARTMENTS}
 elif path.endswith('/overview'):result={'ready':True,'month':'2026-10','assignments':[],'dates':[],'departments':DEPARTMENTS,'current_user_id':'self'}
 else:result={'ready':True,'items':[],'assignments':[],'total':0}
 route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1500,'height':1000},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/attendance-clock-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/attendance-clock-ui-check')
 clock=page.locator('.attendance-heading').filter(has_text='打卡与请假')
 def button(name):return clock.get_by_role('button',name=name,exact=True)
 expect(page.locator('.el-collapse-item.is-active')).to_have_count(1)
 page.get_by_role('button',name='全部规则说明',exact=True).first.click();rules=page.locator('.attendance-rules-content:visible');expect(rules).to_contain_text('再过3个月');expect(rules).to_contain_text('早餐');expect(rules).to_contain_text('晚餐');expect(rules).to_contain_text('无效时间');expect(rules).to_contain_text('最多10天');page.get_by_role('button',name='全部规则说明',exact=True).first.click()
 expect(button('上班打卡')).to_be_enabled();assert button('上班打卡').bounding_box()['x']<button('下班打卡').bounding_box()['x']
 for title in ['打卡与请假','考勤与加班统计','班次安排','值班安排']:
  header=page.locator('.el-collapse-item__header').filter(has_text=re.compile('^'+title+'$'));expect(header).to_have_count(1)
 header=page.locator('.el-collapse-item__header').filter(has_text=re.compile('^打卡与请假$'));header.click();expect(button('上班打卡')).not_to_be_visible();header.click()
 button('上班打卡').click();dialog=page.get_by_role('dialog',name='上班打卡',exact=True);expect(dialog).to_contain_text('上班打卡须在早餐后完成');assert not writes
 panel=dialog.locator('.el-dialog');original=panel.bounding_box();handle=panel.locator('.el-dialog__title').bounding_box()
 page.mouse.move(handle['x']+20,handle['y']+10);page.mouse.down();page.mouse.move(handle['x']+60,handle['y']+35,steps=8);page.mouse.up();assert panel.bounding_box()['x']>original['x']+20
 handle=panel.locator('.el-dialog__title').bounding_box();page.mouse.move(handle['x']+20,handle['y']+10);page.mouse.down();page.mouse.move(-500,-500,steps=8);page.mouse.up();assert panel.bounding_box()['x']>=-1 and panel.bounding_box()['y']>=-1
 dialog.get_by_role('button',name='取消',exact=True).click();expect(dialog).not_to_be_visible();assert not writes
 button('上班打卡').click();dialog.get_by_role('button',name='打卡',exact=True).click();expect(dialog).not_to_be_visible();assert len(writes)==1
 button('下班打卡').click();dialog=page.get_by_role('dialog',name='下班打卡确认',exact=True);dialog.get_by_role('button',name='打卡',exact=True).click();expect(dialog.locator('.el-form-item__error')).to_have_count(2);assert len(writes)==1
 def choose(prefix,text):dialog.locator('.el-form-item').filter(has_text=prefix).locator('.el-radio').filter(has_text=re.compile('^'+re.escape(text)+'$')).click()
 choose('1. 请确认','否，提前时间不计加班');choose('2. 请确认','否');expect(dialog).to_contain_text('记违纪一次');expect(dialog).to_contain_text('固定班次每天扣除一次20分钟')
 dialog.get_by_role('button',name='打卡',exact=True).click();expect(dialog).not_to_be_visible();assert writes[-1][1]['early_work_confirmed'] is False and writes[-1][1]['breakfast_after_eating'] is False
 page.locator('.el-collapse-item__header').filter(has_text=re.compile('^考勤与加班统计$')).click()
 page.get_by_role('button',name='查看详情',exact=True).click();detail=page.locator('.attendance-detail');expect(detail).to_contain_text('原额 1小时 − 早餐 15分钟 − 晚餐 20分钟');expect(detail).to_contain_text('违纪次数')
 page.locator('.attendance-heading').filter(has_text='我的考勤统计').locator('h3').click()
 shift={**SHIFTS[3],'fixed':True};sessions=[];button('刷新').click();button('上班打卡（第1段）').click();page.get_by_role('dialog',name='上班打卡',exact=True).get_by_role('button',name='打卡',exact=True).click()
 page.set_viewport_size({'width':740,'height':600})
 button('下班打卡').click();dialog=page.get_by_role('dialog',name='下班打卡确认',exact=True);expect(dialog).not_to_contain_text('有无进食晚餐');choose('1. 请确认','是，提前时间计加班');choose('2. 请确认','是');choose('是否扣除中间的无效时间','是')
 footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']>=0 and footer['y']+footer['height']<=600
 dialog.get_by_role('spinbutton').fill('12');dialog.get_by_role('textbox').fill('处理个人事务');dialog.get_by_role('button',name='打卡',exact=True).click();expect(dialog).not_to_be_visible()
 assert writes[-1][1]['invalid_minutes']==12 and writes[-1][1]['invalid_reason']=='处理个人事务'
 expect(button('上班打卡（第2段）')).to_be_enabled();assert '/api/attendance/report' not in reads
 page.get_by_role('button',name='切换公司考勤',exact=True).click();expect(page.get_by_role('button',name='上班打卡',exact=True)).to_have_count(0)
 assert '/api/attendance/report' in reads and not errors,errors
 print(json.dumps({'manual_breakfast_notice':True,'check_in_left_of_check_out':True,'explicit_yes_no_validation':True,'fixed_dinner_explanation':True,'breakfast_violation_and_deduction_visible':True,'remote_second_segment':True,'invalid_minutes_and_reason':True,'collapsible_sections':4,'personal_and_company_separate':True,'page_errors':errors}))
 browser.close()
