"""办公室工位、人数跳转和人员城市同步；业务 API 全部拦截。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode();vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
compiled_org=urlopen(BASE+'/src/views/system/Organization.vue').read().decode();router_module=re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)',compiled_org).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createMemoryHistory,RouterView} from ROUTER;import Organization from '/src/views/system/Organization.vue';import AppForm from '/src/components/common/AppForm.vue';localStorage.setItem('user_roles',JSON.stringify(['admin']));localStorage.setItem('user_id','office-ui-check-user');const router=createRouter({history:createMemoryHistory(),routes:[{path:'/users',component:Organization}]});const app=createApp({render:()=>h(RouterView)});app.component('AppForm',AppForm);app.use(router);router.push('/users?tab=offices').then(()=>app.mount('#app'));</script>'''.replace('VUE',json.dumps(vue)).replace('ROUTER',json.dumps(router_module))
offices=[{'id':'gz','city':'广州','name':'广州办公室','seats':None,'revision':1},{'id':'sz','city':'深圳','name':'深圳南山办公室','seats':None,'revision':1},{'id':'sh','city':'上海','name':'上海办公室','seats':None,'revision':1}]
people=[{'id':'p1','username':'staff1','full_name':'广州人员','email':None,'department':'IT部','is_active':True,'office_city_id':'gz'},{'id':'p2','username':'staff2','full_name':'停用人员','email':None,'department':'IT部','is_active':False,'office_city_id':'gz'},{'id':'p3','username':'staff3','full_name':'未分城市','email':None,'department':'IT部','is_active':True,'office_city_id':None}]
queries=[];writes=[];errors=[]


def api(route):
    request=route.request;url=urlparse(request.url);path=url.path;params=parse_qs(url.query)
    if path=='/api/office-management' and request.method=='POST':
        body=request.post_data_json;writes.append((path,body));offices.append({**body,'id':'hz','revision':1});result={'message':'办公室设置已保存'}
    elif path.startswith('/api/office-management/') and request.method=='PUT':
        body=request.post_data_json;writes.append((path,body));row=next(row for row in offices if row['id']==path.rsplit('/',1)[1]);row.update(body);row['revision']+=1;result={'message':'办公室设置已保存'}
    elif path=='/api/office-management':
        items=[{**office,'actual_people':sum(person['office_city_id']==office['id'] and person['is_active'] for person in people),'registered_people':sum(person['office_city_id']==office['id'] for person in people)} for office in offices];result={'ready':True,'items':items,'unassigned_people':sum(not person['office_city_id'] and person['is_active'] for person in people)}
    elif path.endswith('/users/page'):
        queries.append(params);selected=[person for person in people if (not params.get('office_city_id') or person['office_city_id']==params['office_city_id'][0]) and (params.get('active_only')!=['true'] or person['is_active'])]
        result={'items':[{**person,'city':next((office['city'] for office in offices if office['id']==person['office_city_id']),None)} for person in selected],'total':len(selected)}
    elif path.startswith('/api/users/') and request.method=='PUT':
        body=request.post_data_json;writes.append((path,body));person=next(person for person in people if person['id']==path.rsplit('/',1)[1]);person.update(body);result=person
    elif path.endswith('/user-roles/') or path.endswith('/roles/'):result=[]
    elif path.endswith('/daily-reports/access-context'):result={'can_configure':True}
    else:result={'ready':True,'membershipReady':True,'canManage':True,'items':[],'people':[],'total':0}
    route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))


with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1450,'height':1000},service_workers='block')
    context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/office-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
    page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/office-ui-check')
    expect(page.get_by_role('tab',name='办公室管理',exact=True)).to_have_attribute('aria-selected','true')
    def card(name):return page.locator('.office-grid>.el-card').filter(has=page.locator('.office-card-heading>strong').filter(has_text=re.compile('^'+name+'$')))
    expect(card('广州办公室')).to_contain_text('登记人员 2 人');expect(page.get_by_role('button',name='查看广州办公室人员',exact=True)).to_have_text('1 人')
    page.get_by_role('button',name='设置广州办公室',exact=True).click();dialog=page.get_by_role('dialog',name='编辑办公室设置',exact=True);dialog.get_by_role('spinbutton').fill('24');dialog.get_by_role('button',name='保存办公室设置',exact=True).click();expect(dialog).not_to_be_visible();expect(card('广州办公室').locator('.office-capacity>strong')).to_have_text('24')
    page.get_by_role('button',name='增加其他城市办公室',exact=True).click();dialog=page.get_by_role('dialog',name='增加城市办公室',exact=True)
    panel=dialog.locator('.el-dialog');original=panel.bounding_box();handle=dialog.locator('.el-dialog__title').bounding_box();page.mouse.move(handle['x']+12,handle['y']+10);page.mouse.down();page.mouse.move(handle['x']+62,handle['y']+35,steps=8);page.mouse.up();assert panel.bounding_box()['x']>original['x']+20
    handle=dialog.locator('.el-dialog__title').bounding_box();page.mouse.move(handle['x']+12,handle['y']+10);page.mouse.down();page.mouse.move(-500,-500,steps=8);page.mouse.up();assert panel.bounding_box()['x']>=-1 and panel.bounding_box()['y']>=-1
    dialog.get_by_role('button',name='取消',exact=True).click();page.get_by_role('button',name='增加其他城市办公室',exact=True).click();assert abs(panel.bounding_box()['x']-original['x'])<2
    dialog.get_by_role('button',name='保存办公室设置',exact=True).click();expect(dialog.locator('.el-form-item__error')).to_have_count(2)
    dialog.locator('.el-form-item').filter(has_text=re.compile('^城市')).locator('input').fill('杭州');dialog.locator('.el-form-item').filter(has_text=re.compile('^办公室名称')).locator('input').fill('杭州办公室');dialog.get_by_role('spinbutton').fill('10')
    page.set_viewport_size({'width':700,'height':500});footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=500
    dialog.get_by_role('button',name='保存办公室设置',exact=True).click();expect(dialog).not_to_be_visible();page.set_viewport_size({'width':1450,'height':1000});expect(card('杭州办公室')).to_be_visible()
    page.get_by_role('button',name='查看广州办公室人员',exact=True).click();expect(page.locator('.office-people-filter')).to_contain_text('广州办公室 · 在用人员');assert queries[-1]['office_city_id']==['gz'] and queries[-1]['active_only']==['true']
    expect(page.locator('.users-card:visible .el-table__body:visible')).to_contain_text('广州人员');expect(page.locator('.users-card:visible .el-table__body:visible')).not_to_contain_text('停用人员')
    page.get_by_role('button',name='编辑',exact=True).click();dialog=page.get_by_role('dialog',name='编辑用户',exact=True)
    labels=dialog.locator('.el-form-item__label').all_text_contents();assert labels.index('城市')==labels.index('姓名')+1
    city=dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label').filter(has_text=re.compile('^城市$')))
    city.locator('.el-select').click();page.get_by_role('option',name='杭州',exact=True).click();dialog.get_by_role('button',name='确定',exact=True).click();expect(dialog).not_to_be_visible();assert writes[-1][1]['office_city_id']=='hz'
    page.get_by_role('tab',name='办公室管理',exact=True).click();expect(page.get_by_role('button',name='查看杭州办公室人员',exact=True)).to_have_text('1 人');expect(page.get_by_role('button',name='查看广州办公室人员',exact=True)).to_have_text('0 人')
    page.get_by_role('button',name='查看杭州办公室人员',exact=True).click();expect(page.locator('.office-people-filter')).to_contain_text('杭州办公室');expect(page.locator('.users-card:visible .el-table__body:visible')).to_contain_text('杭州')
    page.get_by_role('button',name='清除办公室筛选',exact=True).click();expect(page.locator('.office-people-filter')).not_to_be_visible();assert 'office_city_id' not in queries[-1]
    page.get_by_role('button',name='新增用户',exact=True).click();dialog=page.get_by_role('dialog',name='新增用户',exact=True);city=dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label').filter(has_text=re.compile('^城市$')));expect(city.locator('.el-select__placeholder')).to_contain_text('选择办公室城市')
    search=dialog.locator('.dialog-field-search-header__search input');search.fill('城市');page.locator('.project-field-search-option').filter(has_text='城市').click();expect(city.locator('.el-select__wrapper')).to_be_focused();dialog.get_by_role('button',name='取消',exact=True).click()
    assert not errors,errors
    print(json.dumps({'default_offices':True,'capacity_saved':True,'new_city_synced_to_person_form':True,'active_counts_and_people_link':True,'city_after_name':True,'counts_updated_after_person_city_change':True,'city_form_reset_and_search':True,'drag_reset_small_screen_footer':True,'page_errors':errors}))
    browser.close()
