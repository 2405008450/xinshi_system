"""居家申请、年度补录、独立居家加班；真实组件，业务接口拦截。"""
import json,re
from datetime import datetime,timezone,timedelta
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode();vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import Panel from '/src/views/schedule/components/HomeOfficePanel.vue';import AppForm from '/src/components/common/AppForm.vue';const app=createApp({setup(){const admin=ref(false);return()=>h('div',[h('button',{onClick:()=>admin.value=!admin.value},'切换行政视图'),h(Panel,{key:admin.value?'admin':'mine',admin:admin.value})])}});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
manual=11;revision=1;applications=[{'id':'old','requested_date':'2026-10-01','status':'pending','reason':'','created_at':'2026-10-01T09:00:00+08:00'}];qualifications=[];overtime=None;writes=[];errors=[];qualified=True
def overview():
 total=manual+len(applications);month=len(applications)
 return {'ready':True,'hire_date':'2025-01-01','qualified':qualified,'automatic':qualified,'can_apply_qualification':not qualified and not qualifications,'qualification_pending':bool(qualifications),'qualification_hint':'入职已满6个月，自动获得资格' if qualified else '已满3个月，可以提出资格申请（理由必填）','qualification_apply_on':'2025-04-01','automatic_on':'2025-07-01','month_used':month,'quarter_used':month,'half_used':month,'annual_limit':12,'annual_used':total,'manual_usage_ready':True,'manual_used_days':manual,'system_used_days':len(applications),'annual_remaining':max(0,12-total),'quota_available':total<12 and month<2,'limit_message':'年度额度12天已满，不能再申请' if total>=12 else '本月2次已满，不能再申请' if month>=2 else None,'applications':applications,'qualification_requests':qualifications}
def api(route):
 global manual,revision,overtime
 request=route.request;path=urlparse(request.url).path
 if request.method in ('POST','PUT'):writes.append((path,request.post_data_json))
 if path.endswith('/company'):result={'year':2026,'usage_people':[{'user_id':'person','name':'测试员工','manual_used_days':manual,'revision':revision,'system_used_days':len(applications),'annual_used':manual+len(applications),'annual_limit':12,'history':[]}],'applications':applications,'qualification_requests':qualifications}
 elif path.endswith('/usage'):manual=request.post_data_json['used_days'];revision+=1;result={'message':'今年已居家天数已保存并更新本人工作台'}
 elif path.endswith('/qualification'):
  qualifications.append({'id':'q','reason':request.post_data_json['reason'],'status':'pending','created_at':'2026-10-28T09:00:00+08:00'});result={**overview(),'message':'资格申请已通知行政部；审批待开发'}
 elif path.endswith('/apply'):
  applications.append({'id':'new','requested_date':request.post_data_json['requested_date'],'reason':request.post_data_json['reason'],'status':'pending','created_at':'2026-10-28T09:00:00+08:00'});result={**overview(),'message':'申请已通知行政部；审批待开发'}
 elif path.endswith('/today'):result={'can_home_overtime_check_in':overtime is None,'home_overtime_record':overtime,'sessions':[overtime] if overtime else []}
 elif path.endswith('/check-in'):
  overtime={'id':'overtime','segment':2,'check_in':'2026-10-28T19:00:00+08:00','check_out':None,'shift':{'code':'company_home_overtime','label':'公司要求居家加班','overtime_only':True,'home_office_day':True,'periods':[]}};result={'message':'居家加班上班打卡成功','record':overtime}
 elif path.endswith('/check-out'):overtime['check_out']='2026-10-28T21:00:00+08:00';result={'message':'打卡成功','record':overtime}
 else:result=overview()
 route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1500,'height':1000},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/home-office-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
 page=context.new_page();page.clock.set_fixed_time(datetime(2026,10,28,20,tzinfo=timezone(timedelta(hours=8))));page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/home-office-ui-check')
 panel=page.locator('.home-office-panel');expect(panel.get_by_role('button',name='居家办公申请',exact=True)).to_be_disabled();expect(panel).to_contain_text('年度额度12天已满')
 expect(panel.get_by_role('button',name='居家加班',exact=True)).to_be_enabled()
 page.get_by_role('button',name='切换行政视图',exact=True).click();panel.get_by_role('button',name='补录 / 修改',exact=True).click();dialog=page.get_by_role('dialog',name='补录今年已居家天数 · 测试员工',exact=True)
 dialog.get_by_role('spinbutton').fill('0');dialog.get_by_role('button',name='保存补录',exact=True).click();expect(dialog).not_to_be_visible();assert manual==0
 page.get_by_role('button',name='切换行政视图',exact=True).click();expect(panel.get_by_role('button',name='居家办公申请',exact=True)).to_be_enabled();expect(panel).to_contain_text('0天；系统内申请：1天')
 panel.get_by_role('button',name='居家办公申请',exact=True).click();dialog=page.get_by_role('dialog',name='居家办公申请',exact=True);dialog.get_by_role('button',name='提交并通知行政部',exact=True).click();expect(dialog).not_to_be_visible();expect(panel.get_by_role('button',name='居家办公申请',exact=True)).to_be_disabled();assert len(applications)==2
 panel.get_by_role('button',name='居家加班',exact=True).click();dialog=page.get_by_role('dialog',name='居家加班上班打卡',exact=True);expect(dialog).to_contain_text('不占普通居家办公次数');dialog.get_by_role('button',name='打卡',exact=True).click();expect(dialog).not_to_be_visible();assert writes[-1][1]['work_mode']=='company_home_overtime'
 panel.get_by_role('button',name='居家加班下班打卡',exact=True).click();dialog=page.get_by_role('dialog',name='下班打卡确认',exact=True);expect(dialog).to_contain_text('真实、有效的工作时间');expect(dialog).not_to_contain_text('提前到达公司')
 dialog.locator('.el-form-item').filter(has_text='2. 请确认').locator('.el-radio').filter(has_text=re.compile('^是$')).click();dialog.locator('.el-form-item').filter(has_text='是否扣除中间的无效时间').locator('.el-radio').filter(has_text=re.compile('^是$')).click();dialog.get_by_role('spinbutton').fill('20');dialog.get_by_role('textbox').fill('中途处理私人事务');dialog.get_by_role('button',name='打卡',exact=True).click();expect(dialog).not_to_be_visible()
 assert writes[-1][1]['invalid_minutes']==20 and len(applications)==2
 qualified=False;panel.get_by_role('button',name='刷新',exact=True).click();panel.get_by_role('button',name='申请居家办公资格',exact=True).click();dialog=page.get_by_role('dialog',name='申请居家办公资格',exact=True);before=len(writes);dialog.get_by_role('button',name='提交并通知行政部',exact=True).click();expect(dialog.locator('.el-form-item__error')).to_contain_text('请填写申请理由');assert len(writes)==before
 dialog.get_by_role('textbox').fill('希望减少通勤时间');dialog.get_by_role('button',name='提交并通知行政部',exact=True).click();expect(dialog).not_to_be_visible();expect(panel.get_by_role('button',name='申请居家办公资格',exact=True)).to_be_disabled()
 assert not errors,errors
 print(json.dumps({'manual_usage_reflected':True,'annual_and_month_cap_disabled':True,'application_submitted':True,'qualification_reason_required':True,'company_home_overtime_independent':True,'overtime_statement_and_deduction':True,'approval_pending_visible':True,'page_errors':errors}))
 browser.close()
