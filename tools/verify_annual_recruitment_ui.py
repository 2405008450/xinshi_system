"""年假调整与招聘需求交互；所有业务请求拦截，不写业务数据库。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
router_source=urlopen(BASE+'/src/components/common/RouteSectionNavigation.vue').read().decode()
router_module=re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)',router_source).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h,ref} from VUE;import {createRouter,createMemoryHistory,RouterView} from ROUTER;import HR from '/src/views/hr/HRManagement.vue';import Recruitment from '/src/views/hr/RecruitmentManagement.vue';import Annual from '/src/views/schedule/components/AnnualLeavePanel.vue';import Attendance from '/src/views/schedule/components/AttendanceOverview.vue';import AppForm from '/src/components/common/AppForm.vue';localStorage.setItem('user_id','annual-recruitment-check');localStorage.setItem('user_permissions',JSON.stringify(['system:users:read','system:organization:write']));localStorage.setItem('hr_management_user_id','annual-recruitment-check');localStorage.setItem('hr_management_allowed','1');const router=createRouter({history:createMemoryHistory(),routes:[{path:'/hr-management',component:HR,children:[{path:':section',component:Recruitment}]}]});const app=createApp({setup(){const mode=ref('recruitment');const admin=ref(true);return()=>h('div',[h('button',{onClick:()=>mode.value='annual'},'测试年假'),h('button',{onClick:()=>{admin.value=false;mode.value='annual'}},'测试个人年假'),h('button',{onClick:()=>mode.value='attendance'},'测试规则区域'),mode.value==='recruitment'?h(RouterView):mode.value==='annual'?h(Annual,{admin:admin.value,key:String(admin.value)}):h(Attendance)])}});app.use(router);app.component('AppForm',AppForm);router.push('/hr-management/recruitment').then(()=>app.mount('#app'));</script>'''.replace('VUE',json.dumps(vue)).replace('ROUTER',json.dumps(router_module))
rows=[];writes=[];queries=[];errors=[];wage=False;annual_id='11111111-1111-1111-1111-111111111111'


def annual_data():
    key=f'application:{annual_id}'
    before={'2026':{'entries':[{'source_key':key,'annual_minutes':480,'wage_minutes':0}]}}
    after={'2026':{'entries':[{'source_key':key,'annual_minutes':0,'wage_minutes':480}]}}
    history=[{'id':'audit-1','actor_name':'行政人员','created_at':'2026-10-29T11:00:00+08:00','before_mode':'auto','after_mode':'wage','reason':'经确认改为扣工资','before_snapshot':before,'after_snapshot':after}] if wage else []
    return {'people':[{'user_id':'self','name':'本人','username':'self','ready':True,'annual_leave_days':1,'used_days':0 if wage else 1,'reserved_days':0,'remaining_days':1 if wage else 0,'wage_minutes':480 if wage else 0,'makeup_required_minutes':0,'entries':[{'entry_id':'leave:1:2026-10-29','source_key':key,'source_kind':'application','source_id':annual_id,'day':'2026-10-29','minutes':480,'day_minutes':480,'annual_minutes':0 if wage else 480,'annual_days':0 if wage else 1,'wage_minutes':480 if wage else 0,'makeup_required_minutes':0,'mode':'wage' if wage else 'auto','revision':1 if wage else 0,'reason':'个人事由','history':history}]}]}


def api(route):
    global rows,wage
    request=route.request;url=urlparse(request.url);path=url.path;params=parse_qs(url.query)
    if path.endswith('/office-management/cities'):result={'items':[{'id':'gz','city':'广州','name':'广州办公室'},{'id':'sz','city':'深圳','name':'深圳南山办公室'}]}
    elif path.endswith('/annual-leave/settlement'):
        writes.append((path,request.post_data_json));wage=True;result={'message':'抵扣方式已保存，调整记录可查看'}
    elif '/annual-leave' in path:result=annual_data()
    elif '/hr-recruitment/requirements' in path:
        if request.method=='POST':
            body=request.post_data_json;writes.append((path,body));row={**body,'id':'requirement-1','demand_no':'RT-261029-001','revision':1,'created_at':'2026-10-29T10:00:00+08:00','updated_at':'2026-10-29T10:00:00+08:00'};rows.append(row);result=row
        elif request.method=='PUT':
            body=request.post_data_json;writes.append((path,body));rows[0]={**rows[0],**body,'revision':2};result=rows[0]
        elif request.method=='DELETE':rows=[];result={'message':'已删除'}
        else:
            queries.append(params);terms=params.get('keyword',[''])[0].split();selected=[row for row in rows if all(term.lower() in ' '.join(str(value) for value in row.values()).lower() for term in terms)];result={'items':selected,'total':len(selected)}
    elif path.endswith('/today'):result={'can_check_in':False,'leaves':[]}
    else:result={'records':[],'people':[],'totals':{},'total':0,'leaves':[],'departments':[]}
    route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))


with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1550,'height':1000},service_workers='block')
    context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/annual-recruitment-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/annual-recruitment-ui-check')
    nav=page.locator('[aria-label="人事管理二级导航"]')
    expect(nav).to_contain_text('招聘管理');assert nav.inner_text().index('招聘管理')<nav.inner_text().index('入职管理')
    page.get_by_role('button',name='新增招聘需求',exact=True).click();dialog=page.get_by_role('dialog',name='新增招聘需求',exact=True)
    panel=dialog.locator('.el-dialog');original=panel.bounding_box();handle=dialog.locator('.dialog-field-search-header__title').bounding_box()
    page.mouse.move(handle['x']+12,handle['y']+10);page.mouse.down();page.mouse.move(handle['x']+72,handle['y']+40,steps=8);page.mouse.up();assert panel.bounding_box()['x']>original['x']+20
    handle=dialog.locator('.dialog-field-search-header__title').bounding_box();page.mouse.move(handle['x']+12,handle['y']+10);page.mouse.down();page.mouse.move(-500,-500,steps=8);page.mouse.up();assert panel.bounding_box()['x']>=-1 and panel.bounding_box()['y']>=-1
    dialog.get_by_role('button',name='取消',exact=True).click();page.get_by_role('button',name='新增招聘需求',exact=True).click();assert abs(panel.bounding_box()['x']-original['x'])<2
    dialog.get_by_role('button',name='保存招聘需求',exact=True).click();expect(dialog.locator('.el-form-item__error')).to_have_count(3)
    def field(label):return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label').filter(has_text=re.compile('^'+label+'$')))
    field('招聘城市').locator('.el-select').click();page.get_by_role('option',name='广州',exact=True).click()
    field('计划到岗日期').locator('input').fill('2026年11月15日');field('计划到岗日期').locator('input').press('Enter');field('计划到岗日期').locator('input').press('Tab');field('招聘岗位').locator('input').fill('英语翻译');field('招聘原因').locator('textarea').fill('项目新增');field('招聘人数').locator('input').fill('3');field('具体需求').locator('textarea').fill('熟悉医学翻译\n需要审校经验')
    assert field('具体需求').bounding_box()['width']>field('招聘岗位').bounding_box()['width']*1.8
    dialog.get_by_role('button',name='展开具体需求编辑',exact=True).click();expect(field('具体需求').locator('textarea')).to_have_attribute('rows','12')
    page.set_viewport_size({'width':700,'height':600});footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=600
    dialog.get_by_role('button',name='保存招聘需求',exact=True).click();expect(dialog).not_to_be_visible();assert writes[-1][1]['planned_onboarding_date']=='2026-11-15' and writes[-1][1]['headcount']==3 and writes[-1][1]['recruitment_city']=='广州'
    page.set_viewport_size({'width':1550,'height':1000});expect(page.locator('.el-table')).to_contain_text('RT-261029-001')
    page.get_by_role('button',name='展开具体需求 RT-261029-001',exact=True).click();expect(page.locator('.requirement-detail:visible')).to_contain_text('需要审校经验')
    page.locator('.requirement-header').click();page.get_by_role('button',name='编辑',exact=True).click();dialog=page.get_by_role('dialog',name='编辑招聘需求',exact=True)
    expect(field('计划到岗日期').locator('input')).to_have_value('2026年11月15日')
    expect(field('招聘岗位').locator('input')).to_have_value('英语翻译');expect(field('需求编号').locator('input')).to_have_attribute('readonly','')
    dialog.locator('.dialog-field-search-header__search input').fill('具体需');page.locator('.project-field-search-popper:visible .project-field-search-option').filter(has_text='具体需求').click();expect(field('具体需求').locator('textarea')).to_be_focused()
    field('招聘岗位').locator('input').fill('高级英语翻译');dialog.get_by_role('button',name='保存招聘需求',exact=True).click();expect(dialog).not_to_be_visible()
    search=page.get_by_role('textbox',name='招聘需求搜索',exact=True);search.fill('高级 医学');page.wait_for_timeout(550);expect(page.locator('.el-table')).to_contain_text('高级英语翻译');assert queries[-1]['keyword']==['高级 医学']
    search.fill('');page.wait_for_timeout(100)
    page.get_by_role('button',name='删除管理',exact=True).click();expect(page.get_by_role('button',name='编辑',exact=True)).to_have_count(0)
    page.locator('.el-table__body-wrapper .el-checkbox').first.click();page.get_by_role('button',name='删除所选（1）',exact=True).click();page.get_by_role('button',name='确定删除',exact=True).click();expect(page.locator('.el-table')).not_to_contain_text('RT-261029-001')
    page.get_by_role('button',name='测试年假',exact=True).click();expect(page.get_by_role('button',name='调整抵扣',exact=True)).to_be_enabled()
    page.get_by_role('button',name='调整抵扣',exact=True).click();dialog=page.get_by_role('dialog',name='调整请假抵扣方式',exact=True)
    annual_panel=dialog.locator('.el-dialog');original=annual_panel.bounding_box();handle=dialog.locator('.el-dialog__title').bounding_box();page.mouse.move(handle['x']+12,handle['y']+10);page.mouse.down();page.mouse.move(handle['x']+62,handle['y']+30,steps=8);page.mouse.up();assert annual_panel.bounding_box()['x']>original['x']+20
    dialog.get_by_role('button',name='取消',exact=True).click();page.get_by_role('button',name='调整抵扣',exact=True).click();assert abs(annual_panel.bounding_box()['x']-original['x'])<2
    dialog.get_by_role('button',name='保存调整并留记录',exact=True).click();expect(dialog.locator('.el-form-item__error')).to_contain_text('请填写调整原因')
    dialog.locator('textarea').fill('经确认改为扣工资');page.set_viewport_size({'width':700,'height':500});footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=500
    dialog.get_by_role('button',name='保存调整并留记录',exact=True).click();expect(dialog).not_to_be_visible();assert writes[-1][1]['mode']=='wage'
    page.set_viewport_size({'width':1550,'height':1000});page.get_by_role('button',name='调整记录（1）',exact=True).click();detail=page.locator('.annual-detail:visible');expect(detail).to_contain_text('行政人员');expect(detail).to_contain_text('经确认改为扣工资');expect(detail).to_contain_text('8小时 → 0分钟')
    page.get_by_role('button',name='测试个人年假',exact=True).click();expect(page.get_by_role('button',name='调整抵扣',exact=True)).to_have_count(0);expect(page.get_by_role('button',name='调整记录（1）',exact=True)).to_be_visible()
    page.get_by_role('button',name='测试规则区域',exact=True).click();page.get_by_role('button',name='全部规则说明',exact=True).first.click();rules=page.locator('.attendance-rules-content:visible');expect(rules).to_contain_text('请假与年假抵扣');expect(rules).to_contain_text('班次与值班安排');expect(rules).to_contain_text('法定假居家/加班（待开发）')
    page.locator('.attendance-overview').locator('.attendance-heading').first.click();header=page.locator('.el-collapse-item__header').filter(has_text=re.compile('^法定假居家/加班（待开发）$'));header.click();expect(page.locator('.attendance-overview')).to_contain_text('此处预留相关安排')
    assert not errors,errors
    print(json.dumps({'recruitment_nav_order':True,'number_readonly':True,'double_width_details_expand':True,'crud_search_delete_management':True,'annual_wage_adjustment_and_history':True,'personal_readonly':True,'rules_and_statutory_area':True,'fixed_footer_small_screen':True,'page_errors':errors}))
    browser.close()
