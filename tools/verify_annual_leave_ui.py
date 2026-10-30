"""人员入职字段、年假规则与表单预览；业务接口全部拦截。"""
import json,re,sys
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse
from datetime import date,datetime,timezone,timedelta
from playwright.sync_api import sync_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from employee_employment import values
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode();vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
import {createApp,h} from VUE;import Users from '/src/views/system/Users.vue';import AppForm from '/src/components/common/AppForm.vue';localStorage.setItem('user_roles',JSON.stringify(['admin']));localStorage.setItem('user_id','annual-ui-user');const app=createApp({render:()=>h(Users)});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
rows=[{'id':'person','username':'person','full_name':'年假测试人员','email':None,'department':'IT部','is_active':True,'hire_date':None,'annual_leave_days':None}];writes=[];errors=[]
def api(route):
 request=route.request;path=urlparse(request.url).path
 if path.endswith('/users/page'):result={'items':rows,'total':len(rows)}
 elif path.endswith('/users/person') and request.method=='PUT':
  data=request.post_data_json;writes.append(data);rows[0].update(data);rows[0].update(values(date.fromisoformat(data['hire_date']) if data.get('hire_date') else None,date(2026,10,28)));result=rows[0]
 elif path.endswith('/users/') and request.method=='POST':
  data=request.post_data_json;writes.append(data);result={**data,'id':'new-person'}
 elif path.endswith('/user-roles/'):result=[]
 elif path.endswith('/departments/organization'):result={'ready':True,'membershipReady':True,'canManage':True,'items':[],'people':[]}
 else:result={'ready':True,'items':[],'people':[],'total':0}
 route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False,default=str))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1450,'height':1000},timezone_id='America/Los_Angeles',service_workers='block')
 context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/annual-leave-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
 page=context.new_page();page.clock.set_fixed_time(datetime(2026,10,28,20,tzinfo=timezone(timedelta(hours=8))));page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/annual-leave-ui-check')
 expect(page.locator('.el-table__body')).to_contain_text('待填写入职时间')
 page.get_by_role('button',name='年假规则',exact=True).click();rules=page.locator('.attendance-rules-content');expect(rules).to_contain_text('每满一个入职周年，再过3个月');expect(rules).to_contain_text('额度最多10天');expect(rules).to_contain_text('6月30日及之前入职');expect(rules).to_contain_text('次年1月1日先获得1天（只发放一次）');page.locator('.header-title').click()
 page.get_by_role('button',name='编辑',exact=True).click();dialog=page.get_by_role('dialog',name='编辑用户',exact=True)
 field=dialog.locator('.el-form-item').filter(has_text=re.compile('^入职时间'));field.get_by_role('combobox').fill('2025年06月30日');field.get_by_role('combobox').press('Enter');dialog.locator('.el-dialog__header').click(position={'x':20,'y':10})
 expect(dialog.locator('.el-form-item').filter(has_text='当前年假额度').get_by_role('textbox')).to_have_value('2天')
 expect(dialog).to_contain_text('2027年9月30日')
 search=dialog.locator('.dialog-field-search-header__search input');search.fill('入职');page.locator('.project-field-search-option').filter(has_text='入职时间').click();expect(field.get_by_role('combobox')).to_be_focused()
 dialog.get_by_role('button',name='确定',exact=True).click();expect(dialog).not_to_be_visible();assert writes[-1]['hire_date']=='2025-06-30'
 expect(page.locator('.el-table__body')).to_contain_text('2025年6月30日');expect(page.locator('.el-table__body')).to_contain_text('2天')
 page.get_by_role('button',name='新增用户',exact=True).click();dialog=page.get_by_role('dialog',name='新增用户',exact=True);expect(dialog.locator('.el-form-item').filter(has_text='当前年假额度').get_by_role('textbox')).to_have_value('待填写入职时间')
 expect(dialog.locator('.el-form-item').filter(has_text=re.compile('^入职时间')).get_by_role('combobox')).to_have_value('')
 hire=dialog.locator('.el-form-item').filter(has_text=re.compile('^入职时间')).get_by_role('combobox');hire.fill('2026年09月09日');hire.press('Enter');dialog.locator('.el-dialog__header').click(position={'x':20,'y':10})
 expect(dialog.locator('.el-form-item').filter(has_text='当前年假额度').get_by_role('textbox')).to_have_value('0天');expect(dialog).to_contain_text('2027年1月1日')
 page.set_viewport_size({'width':600,'height':600});footer=dialog.locator('.el-dialog__footer');expect(footer).to_be_visible();bounds=footer.bounding_box();assert bounds['y']+bounds['height']<=600
 body=dialog.locator('.el-dialog__body');body.evaluate('el=>el.scrollTop=el.scrollHeight');expect(footer).to_be_visible()
 dialog.get_by_role('button',name='取消',exact=True).click();expect(dialog).not_to_be_visible();assert len(writes)==1 and not errors,errors
 print(json.dumps({'hire_date_saved_and_displayed':True,'anniversary_plus_three_months':True,'readonly_preview':True,'next_increase_visible':True,'rules_visible':True,'new_form_reset':True,'small_screen_fixed_footer':True,'page_errors':errors}))
 browser.close()
