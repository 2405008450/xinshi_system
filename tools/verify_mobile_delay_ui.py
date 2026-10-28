"""手机端延迟上班与请假可用，打卡禁用；全部业务接口拦截。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode();vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Panel from '/src/views/schedule/components/AttendanceOverview.vue';import AppForm from '/src/components/common/AppForm.vue';const app=createApp({render:()=>h(Panel)});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
writes=[];errors=[]
def api(route):
 request=route.request;path=urlparse(request.url).path
 if path.endswith('/today'):result={'shift':{'label':'早班','periods':['09:00–12:00','13:30–18:30']},'can_check_in':True,'clock_ready':True,'leaves':[]}
 elif path.endswith('/delay-start') and request.method=='POST':writes.append(request.post_data_json);result={'message':'延迟上班申请已保存并通知全体人员'}
 elif path.endswith('/delay-start'):result={'ready':True,'items':[]}
 else:result={'records':[],'people':[],'totals':{},'departments':[],'total':0}
 route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':430,'height':900},is_mobile=True,has_touch=True,user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile Safari',service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/mobile-delay-ui-check',lambda route:route.fulfill(content_type='text/html',body=html));page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/mobile-delay-ui-check')
 expect(page.get_by_role('button',name='上班打卡',exact=True)).to_be_disabled();expect(page.get_by_role('button',name='下班打卡',exact=True)).to_be_disabled()
 page.get_by_role('button',name='延迟上班申请',exact=True).click();dialog=page.get_by_role('dialog',name='延迟上班申请',exact=True);dialog.get_by_role('button',name='提交并通知全体',exact=True).click();expect(dialog.locator('.el-form-item__error')).to_contain_text('请填写申请事由');assert not writes
 dialog.get_by_role('textbox').fill('交通拥堵，申请延迟上班');dialog.get_by_role('button',name='提交并通知全体',exact=True).click();expect(dialog).not_to_be_visible();assert len(writes)==1 and writes[0]['requested_start'].endswith('+08:00')
 page.get_by_role('button',name='请假',exact=True).click();expect(page.get_by_role('dialog',name='请假',exact=True)).to_be_visible()
 assert not errors,errors
 print(json.dumps({'mobile_delay_request':True,'reason_required':True,'timezone_explicit':True,'mobile_leave_available':True,'mobile_clock_disabled':True,'page_errors':errors}))
 browser.close()
