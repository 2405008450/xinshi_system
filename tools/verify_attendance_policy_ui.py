"""补班/调休/年终奖界面验收；拦截全部业务 API，不写业务数据库。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect

BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h,ref} from VUE;import Panel from '/src/views/schedule/components/AttendanceOverview.vue';import AppForm from '/src/components/common/AppForm.vue';const app=createApp({setup(){const admin=ref(false);return()=>h('div',[h('button',{onClick:()=>admin.value=!admin.value},'切换公司'),h(Panel,{admin:admin.value,key:String(admin.value)})])}});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
reads=[];writes=[];errors=[]
event={'id':'late:clock-2','clock_id':'clock-2','day':'2026-10-26','ordinal':2,'minutes':20,'bonus_linked':True,'spans':[{'start_at':'2026-10-26T09:10:00+08:00','end_at':'2026-10-26T09:30:00+08:00','minutes':20}]}
balance={'user_id':'self','name':'本人','ready':True,'hire_date':'2026-10-01','counted_months':1,'duty_days':3,'average_days':3,'eligible':True,'available_minutes':840,'extra_minutes':960,'makeup_remaining_minutes':0,'reserved_minutes':0,'duties':[{'id':'duty:1','day':'2026-10-17','home':True,'minutes':480,'extra':True,'uses':[{'kind':'makeup','minutes':120,'source_id':'leave:1'}]}],'obligations':[{'id':'leave:1','day':'2026-10-12','source':'application','reason':'个人事由','minutes':120,'makeup_minutes':120,'remaining_minutes':0,'makeup_links':[{'duty_id':'duty:1','day':'2026-10-17','minutes':120}]}],'requests':[]}
policy={'balances':[balance],'monthly_policy':[{'name':'本人','month':'2026-10','overtime_minutes':600,'late_count':2,'free_count':1,'linked_count':1,'late_leave_minutes':40,'provisional':True,'events':[event]}]}


def api(route):
    request=route.request;path=urlparse(request.url).path;reads.append(path)
    if path.endswith('/comp-time'):
        writes.append(request.post_data_json);result={'message':'调休申请已保存并预留额度；审批待开发，尚未批准'}
    elif '/policy' in path:result=policy
    elif path.endswith('/today'):result={'can_check_in':False,'leaves':[]}
    else:result={'records':[],'people':[],'total':0,'leaves':[{'source':'lateness','source_label':'迟到折算请假','minutes':20,'reason':'迟到累计请假','start_at':'2026-10-26T09:10:00+08:00','end_at':'2026-10-26T09:30:00+08:00'}],'totals':{'leave_minutes':20,'late_leave_minutes':20,'requested_leave_minutes':0},'departments':[]}
    route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))


with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context(viewport={'width':1440,'height':900},service_workers='block')
    context.route(re.compile(r'^http://localhost:3000/api/'),api)
    context.route(BASE+'/attendance-policy-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/attendance-policy-ui-check')
    header=page.locator('.el-collapse-item__header').filter(has_text=re.compile('^补班、调休与年终奖$'))
    expect(header).to_have_attribute('aria-expanded','false')
    assert not any('/policy' in path for path in reads)
    header.click();expect(page.get_by_role('button',name='申请调休',exact=True)).to_be_enabled()
    page.get_by_role('button',name='查看详情',exact=True).first.click()
    detail=page.locator('.policy-detail').filter(has_text='补班与调休详情')
    expect(detail).to_contain_text('每次请假及补班');expect(detail).to_contain_text('2026-10-17');expect(detail).to_contain_text('个人事由')
    page.get_by_role('tab',name='补班与调休',exact=True).click()
    page.get_by_role('button',name='申请调休',exact=True).click()
    dialog=page.get_by_role('dialog',name='调休申请',exact=True)
    dialog.get_by_role('button',name='提交待审批',exact=True).click();expect(dialog.locator('.el-form-item__error')).to_have_count(3);assert not writes
    # 拖动、边界、关闭及重新打开复位。
    panel=dialog.locator('.el-dialog');original=panel.bounding_box();handle=panel.locator('.el-dialog__title').bounding_box()
    page.mouse.move(handle['x']+20,handle['y']+10);page.mouse.down();page.mouse.move(handle['x']+80,handle['y']+40,steps=8);page.mouse.up();assert panel.bounding_box()['x']>original['x']+20
    handle=panel.locator('.el-dialog__title').bounding_box();page.mouse.move(handle['x']+20,handle['y']+10);page.mouse.down();page.mouse.move(-500,-500,steps=8);page.mouse.up();assert panel.bounding_box()['x']>=-1 and panel.bounding_box()['y']>=-1
    dialog.get_by_role('button',name='取消',exact=True).click();page.get_by_role('button',name='申请调休',exact=True).click()
    assert abs(panel.bounding_box()['x']-original['x'])<2
    items=dialog.locator('.el-form-item')
    for index,value in [(0,'2026-10-30 09:00:00'),(1,'2026-10-30 10:00:00')]:
        control=items.nth(index).locator('input');control.fill(value);control.press('Enter');control.press('Tab')
    items.nth(2).locator('textarea').fill('值班后调休')
    page.set_viewport_size({'width':700,'height':500})
    footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']>=0 and footer['y']+footer['height']<=500
    dialog.get_by_role('button',name='提交待审批',exact=True).click();expect(dialog).not_to_be_visible()
    assert len(writes)==1 and writes[0]['start_at'].endswith('+08:00') and writes[0]['reason']=='值班后调休'
    page.set_viewport_size({'width':1440,'height':900})
    page.get_by_role('tab',name='年终奖挂钩（待开发）',exact=True).click()
    page.get_by_role('button',name='查看详情',exact=True).last.click();bonus=page.locator('.policy-detail').filter(has_text='年终奖挂钩来源')
    expect(bonus).to_contain_text('clock-2');expect(bonus).to_contain_text('第2次');expect(bonus).to_contain_text('年终奖挂钩（待开发）')
    page.get_by_role('tab',name='节假日值班（待开发）',exact=True).click();expect(page.get_by_role('alert').filter(has_text='100元/天补贴＋调休')).to_be_visible()
    page.get_by_role('button',name='切换公司',exact=True).click();page.locator('.el-collapse-item__header').filter(has_text=re.compile('^补班、调休与年终奖$')).click()
    expect(page.get_by_role('columnheader',name='人员',exact=True).first).to_be_visible()
    assert '/api/attendance/policy/company' in reads and not errors,errors
    print(json.dumps({'lazy_personal_section':True,'makeup_sources':True,'late_bonus_sources':True,'holiday_pending_rules':True,'comp_validation_timezone':True,'dialog_drag_reset_fixed_footer':True,'company_scope':True,'page_errors':errors}))
    browser.close()
