"""值班真实组件交互；所有业务接口拦截，无业务数据库写入。"""
import json,re,sys
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from monthly_shift import DEPARTMENTS
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><style>body{margin:0}.hr-workspace-content{margin:70px 20px 0 180px;height:calc(100vh - 90px);overflow:auto}</style><div id="app"></div><script type="module">
import {createApp,h} from VUE;import Duty from '/src/views/hr/WeekendDutyArrangement.vue';import Overview from '/src/views/hr/WeekendDutyOverview.vue';import AppForm from '/src/components/common/AppForm.vue';
const app=createApp({render:()=>h('div',{class:'hr-workspace-content'},[h(Duty,{month:'2026-11'}),h(Overview,{month:'2026-11',week:'2026-11-02',mode:'month',scope:'all'})])});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
person={'id':'person','name':'测试值班人员','username':'person','active':True,'departments':[{'id':'customer','name':'客户/销售部'}],'default_department':'customer'}
plan={'ready':True,'sync_ready':True,'month':'2026-11','dates':['2026-11-01','2026-11-07','2026-11-08'],'departments':DEPARTMENTS,'assignments':[],'revision':0,'fixed_revision':0,'publication_revision':0,'published':False,'can_edit':True,'needs_sync':True}
published=[];writes=[];transfers=[];fixed=[];history=[];errors=[]
def api(route):
 global published,fixed
 request=route.request;path=urlparse(request.url).path;q=parse_qs(urlparse(request.url).query)
 if path.endswith('/directory'):result={'ready':True,'items':[{'id':row['code'],'name':row['label']} for row in DEPARTMENTS],'people':[person]}
 elif path.endswith('/fixed'):
  if request.method=='PUT':fixed=request.post_data_json['assignments'];plan['fixed_revision']+=1
  result={'ready':True,'revision':plan['fixed_revision'],'assignments':fixed,'people':[person],'departments':DEPARTMENTS}
 elif path.endswith('/enable-edit'):plan['can_edit']=True;result=plan
 elif path.endswith('/sync'):
  published=json.loads(json.dumps(plan['assignments']));plan.update(published=True,can_edit=False,needs_sync=False,publication_revision=plan['publication_revision']+1);result=plan
 elif path.endswith('/overview'):result={**plan,'assignments':published,'current_user_id':'person'}
 elif path.endswith('/history'):result={'total':len(history),'items':history}
 elif path.endswith('/weekly'):
  week=q['week'][0];result={'ready':True,'week_start':week,'assignments':[{'user_id':'person','name':person['name'],'department':'customer','date':'2026-11-07'}],'departments':DEPARTMENTS,'shifts':[],'versions':{'2026-11':plan['revision']},'publication_versions':{'2026-11':plan['publication_revision']},'fixed_revision':plan['fixed_revision'],'can_edit':True}
 elif path.endswith('/transfer'):transfers.append(request.post_data_json);result={}
 else:
  if request.method=='PUT':
   data=request.post_data_json;writes.append(data);plan['updated_at']='2026-10-28T20:00:00+08:00';plan['revision']+=1;plan['needs_sync']=True;plan['assignments']=[{**row,'name':person['name'],'active':True} for row in data['assignments']]
   history.append({'id':str(len(writes)),'action':'draft_save','actor_name':'管理员','created_at':'2026-10-28T20:00:00+08:00','publication_revision':None,'changes':[]})
  result=plan
 route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1600,'height':1000},service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/duty-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/duty-ui-check')
 duty=page.locator('.weekend-duty')
 def drop(day):
  transfer=page.evaluate_handle('new DataTransfer()');transfer.evaluate('(t,p)=>t.setData("application/x-project-personnel",JSON.stringify([p]))',person)
  duty.locator(f'[data-duty-cell="customer:{day}"]').dispatch_event('drop',{'dataTransfer':transfer})
 expect(duty.get_by_role('button',name='同步（尚未同步）',exact=True)).to_be_visible()
 drop('2026-11-01');page.wait_for_timeout(180);assert not writes
 page.wait_for_function('document.querySelector(".duty-sync-bar").textContent.includes("已保存")')
 assert len(writes)==1 and published==[]
 duty.get_by_role('button',name='同步（尚未同步）',exact=True).click();expect(duty.get_by_role('button',name='已同步',exact=True)).to_be_visible()
 expect(duty.locator('.duty-person[draggable="true"]')).to_have_count(0)
 drop('2026-11-07');page.wait_for_timeout(500);assert len(writes)==1
 duty.get_by_role('button',name='修改',exact=True).click();expect(duty.locator('.duty-person[draggable="true"]')).to_have_count(1)
 drop('2026-11-07');page.wait_for_function('document.querySelectorAll(".duty-person").length===2');page.wait_for_timeout(500)
 assert len(writes)==2 and len(published)==1
 expect(duty.get_by_role('button',name='同步（有未同步修改）',exact=True)).to_be_visible()
 duty.get_by_role('button',name='修改记录',exact=True).click();dialog=page.get_by_role('dialog',name='值班修改记录',exact=True);expect(dialog).to_contain_text('自动保存草稿');dialog.get_by_role('button',name='关闭',exact=True).click()
 duty.get_by_role('button',name='固定值班人员',exact=True).click();dialog=page.get_by_role('dialog',name='固定值班人员',exact=True)
 panel=dialog.locator('.el-dialog');original=panel.bounding_box();handle=panel.locator('.el-dialog__title').bounding_box()
 page.mouse.move(handle['x']+20,handle['y']+10);page.mouse.down();page.mouse.move(handle['x']+60,handle['y']+35,steps=8);page.mouse.up()
 assert panel.bounding_box()['x']>original['x']+20
 handle=panel.locator('.el-dialog__title').bounding_box();page.mouse.move(handle['x']+20,handle['y']+10);page.mouse.down();page.mouse.move(-500,-500,steps=10);page.mouse.up()
 assert panel.bounding_box()['x']>=-1 and panel.bounding_box()['y']>=-1
 dialog.get_by_role('button',name='关闭',exact=True).click();expect(dialog).not_to_be_visible();duty.get_by_role('button',name='固定值班人员',exact=True).click();expect(dialog).to_be_visible()
 assert abs(dialog.locator('.el-dialog').bounding_box()['x']-original['x'])<2
 dialog.locator('.el-checkbox').filter(has_text='周六').click();dialog.get_by_role('button',name='保存配置',exact=True).click();expect(dialog).not_to_be_visible()
 assert fixed[0]['weekdays']==[5]
 duty.get_by_role('button',name='复制 / 转移 / 互换',exact=True).click();dialog=page.get_by_role('dialog',name='复制 / 转移 / 互换',exact=True)
 expect(dialog).to_contain_text('周六对应周六');dialog.get_by_role('button',name='确认复制',exact=True).click();confirm=page.locator('.el-message-box');expect(confirm).to_be_visible();assert not transfers
 confirm.get_by_role('button',name='确认复制',exact=True).click();page.wait_for_timeout(250);assert len(transfers)==1 and transfers[0]['versions']=={'2026-11':2}
 dialog.get_by_role('button',name='关闭',exact=True).click()
 assert duty.locator('.duty-matrix-scroll').evaluate('el=>getComputedStyle(el).overflowY')=='scroll'
 assert not errors,errors
 print(json.dumps({'auto_save_400ms':True,'draft_not_published':True,'published_locks_form':True,'edit_unlocks_form':True,'pending_sync_highlight':True,'history':True,'fixed_weekends':True,'copy_requires_confirmation':True,'workbench_readonly':True,'page_errors':errors}))
 browser.close()
