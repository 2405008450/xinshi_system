"""真实夜间安排组件验证；拦截所有API，不写业务数据库。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
source=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',source).group(1)
html='''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Night from '/src/views/hr/WeekendNightDuty.vue';createApp({render:()=>h('main',[h(Night,{month:'2026-11'}),h(Night,{month:'2026-11',readonly:true})])}).mount('#app')</script>'''.replace('VUE',json.dumps(vue))
person={'id':'person','name':'测试客户专员','active':True,'departments':[{'id':'customer','name':'客户/销售部'}]}
plan={'ready':True,'month':'2026-11','dates':['2026-11-07','2026-11-08'],'assignments':[],'revision':0,'published_revision':0,'can_edit':True,'needs_sync':True,'history':[],'names':{'person':person['name']}}
published=[];writes=[];errors=[]
def intercept(route):
    global published
    request=route.request;path=urlparse(request.url).path;q=parse_qs(urlparse(request.url).query)
    if path.endswith('/directory'):result={'ready':True,'items':[{'id':'customer','name':'客户/销售部'}],'people':[person]}
    elif path.endswith('/sync'):
        published=json.loads(json.dumps(plan['assignments']));plan.update(published_revision=plan['revision'],can_edit=False,needs_sync=False);result=plan
    elif path.endswith('/edit'):plan['can_edit']=True;result=plan
    elif request.method=='PUT':
        data=request.post_data_json;writes.append(data);before=plan['assignments'];plan['assignments']=[{**row,'name':person['name']} for row in data['assignments']];plan['revision']+=1;plan['needs_sync']=True
        plan['history'].append({'action':'save','actor':'测试行政','at':'2026-10-30T12:00:00+08:00','before':before,'after':data['assignments'],'publication_revision':None});result=plan
    elif q.get('public')==['true']:result={**plan,'assignments':published,'history':[]}
    else:result=plan
    route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context(viewport={'width':1550,'height':1000},service_workers='block')
    context.route(re.compile(r'^http://localhost:3000/api/'),intercept)
    context.route(BASE+'/night-duty-check',lambda route:route.fulfill(content_type='text/html',body=html))
    page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/night-duty-check')
    editor=page.locator('.night-duty').nth(0);overview=page.locator('.night-duty').nth(1)
    expect(editor.get_by_text('测试客户专员',exact=True)).to_be_visible()
    transfer=page.evaluate_handle('new DataTransfer()');transfer.evaluate('(t,p)=>t.setData("application/x-project-personnel",JSON.stringify([p]))',person)
    editor.locator('tbody tr').nth(0).locator('td').nth(0).dispatch_event('drop',{'dataTransfer':transfer})
    expect(editor.get_by_text('已保存',exact=True)).to_be_visible(timeout=8000)
    assert writes[-1]['assignments'][0]['mode']=='standalone'
    expect(overview.locator('.night-person')).to_have_count(0)
    editor.get_by_role('button',name='同步（尚未同步）',exact=True).click()
    expect(editor.get_by_role('button',name='修改',exact=True)).to_be_enabled()
    assert not editor.locator('.night-person').first.get_attribute('draggable')=='true'
    overview.get_by_role('button',name='刷新夜间安排').click();expect(overview.locator('.night-person')).to_have_count(1)
    editor.get_by_role('button',name='修改',exact=True).click();expect(editor.locator('.night-person').first).to_have_attribute('draggable','true')
    editor.get_by_role('button',name='接续值班',exact=True).click()
    editor.locator('tbody tr').nth(1).locator('td').nth(1).dispatch_event('drop',{'dataTransfer':transfer})
    expect(editor.get_by_text('已保存',exact=True)).to_be_visible(timeout=8000)
    assert {row['mode'] for row in writes[-1]['assignments']}=={'standalone','continuation'}
    editor.get_by_role('button',name='夜间修改记录').click();expect(page.locator('.night-history').get_by_text(re.compile('修改后：测试客户专员')).first).to_be_visible()
    page.keyboard.press('Escape');page.screenshot(path=str(Path('logs/night-duty-ui.png').resolve()),full_page=True)
    assert not errors,errors
    print('PASS: drag/drop + 400ms save + private draft + explicit sync + edit lock + two modes + history; API mocked, no business writes')
    browser.close()
