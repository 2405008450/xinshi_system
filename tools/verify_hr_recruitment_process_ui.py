"""招聘过程、两轮面试和入职意愿弹窗；所有业务 API 拦截。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode();vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Recruitment from '/src/views/hr/RecruitmentManagement.vue';import AppForm from '/src/components/common/AppForm.vue';localStorage.setItem('user_id','process-ui-check');const app=createApp({render:()=>h(Recruitment)});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue))
demand={'id':'11111111-1111-1111-1111-111111111111','demand_no':'RT-261029-001','request_date':'2026-10-29','recruitment_city':'广州','position':'翻译','reason':'扩招','headcount':2,'details':'医学翻译','revision':1}
rows=[];writes=[];reads=[];errors=[]


def serialize(row):return {**row,'demand_no':demand['demand_no'],'recruitment_city':demand['recruitment_city'],'position':demand['position'],'actual_onboarded':None,'created_at':'2026-10-29T10:00:00+08:00','updated_at':'2026-10-29T10:00:00+08:00'}
def api(route):
    global rows
    request=route.request;url=urlparse(request.url);path=url.path;params=parse_qs(url.query);reads.append((path,params))
    if path.endswith('/requirements'):result={'items':[demand],'total':1}
    elif path=='/api/hr-recruitment/process' and request.method=='POST':
        body=request.post_data_json;writes.append((path,body));row={**body,'id':'22222222-2222-2222-2222-222222222222','revision':1};rows.append(row);result=serialize(row)
    elif path.startswith('/api/hr-recruitment/process/') and request.method=='PUT':
        body=request.post_data_json;writes.append((path,body));rows[0]={**rows[0],**body,'revision':rows[0]['revision']+1};result=serialize(rows[0])
    elif path.startswith('/api/hr-recruitment/process/') and request.method=='DELETE':rows=[];result={'message':'已删除'}
    elif path.endswith('/process'):result={'items':[serialize(row) for row in rows],'total':len(rows)}
    else:result={'ready':True,'items':[],'people':[],'total':0}
    route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))


with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1550,'height':1000},service_workers='block')
    context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/recruitment-process-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
    page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/recruitment-process-ui-check')
    header=page.locator('.el-collapse-item__header').filter(has_text=re.compile('^招聘过程$'));header.click()
    process=page.locator('.el-collapse-item').filter(has=page.locator('.el-collapse-item__header').filter(has_text=re.compile('^招聘过程$')))
    process.get_by_role('button',name='新增招聘过程',exact=True).click();main=page.get_by_role('dialog',name='新增招聘过程',exact=True)
    main.get_by_role('button',name='保存招聘过程',exact=True).click();expect(main.locator('.el-form-item__error')).to_have_count(2)
    def item(dialog,label):return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label').filter(has_text=re.compile('^'+re.escape(label)+'$')))
    item(main,'招聘需求').locator('.el-select').click();page.get_by_role('option',name=re.compile('RT-261029-001')).click()
    expect(item(main,'招聘城市').locator('input')).to_have_value('广州');expect(item(main,'招聘岗位').locator('input')).to_have_value('翻译')
    main.get_by_role('button',name='填写应聘人及面试情况',exact=True).click();candidate=page.get_by_role('dialog',name='应聘人及面试情况',exact=True)
    panel=candidate.locator('.el-dialog');original=panel.bounding_box();handle=candidate.locator('.dialog-field-search-header__title').bounding_box();page.mouse.move(handle['x']+12,handle['y']+10);page.mouse.down();page.mouse.move(handle['x']+62,handle['y']+30,steps=8);page.mouse.up();assert panel.bounding_box()['x']>original['x']+20
    candidate.get_by_role('button',name='取消',exact=True).click();main.get_by_role('button',name='填写应聘人及面试情况',exact=True).click();assert abs(panel.bounding_box()['x']-original['x'])<2
    item(candidate,'应聘人姓名').locator('input').fill('候选甲')
    item(candidate,'是否一面').locator('.el-radio').filter(has_text=re.compile('^是$')).click();candidate.get_by_role('button',name='确认应聘人与面试',exact=True).click();expect(candidate.locator('.el-form-item__error')).to_have_count(2)
    def fill_time(label,value):
        control=item(candidate,label).locator('input');control.fill(value);control.press('Enter');control.press('Tab')
    fill_time('一面时间','2026年10月29日 09:00');item(candidate,'一面结果').locator('textarea').fill('一面通过，医学经验合适')
    item(candidate,'是否二面').locator('.el-radio').filter(has_text=re.compile('^是$')).click();fill_time('二面时间','2026年10月30日 10:00');item(candidate,'二面结果').locator('textarea').fill('二面通过')
    search=candidate.locator('.dialog-field-search-header__search input');search.fill('二面结果');page.locator('.project-field-search-option').filter(has_text='二面结果').click();expect(item(candidate,'二面结果').locator('textarea')).to_be_focused()
    page.set_viewport_size({'width':700,'height':560});candidate.locator('.el-dialog__body').evaluate('el=>el.scrollTop=el.scrollHeight');footer=candidate.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=560
    candidate.get_by_role('button',name='确认应聘人与面试',exact=True).click();expect(candidate).not_to_be_visible();page.set_viewport_size({'width':1550,'height':1000})
    item(main,'入职意愿').locator('.el-select').click();page.get_by_role('option',name='候选人放弃',exact=True).click();will=page.get_by_role('dialog',name='填写放弃原因',exact=True)
    will.get_by_role('button',name='确认入职意愿',exact=True).click();expect(will.locator('.el-form-item__error')).to_contain_text('请填写放弃原因');will.locator('textarea').fill('候选人因地点原因放弃');will.get_by_role('button',name='确认入职意愿',exact=True).click();expect(will).not_to_be_visible()
    main.get_by_role('button',name='保存招聘过程',exact=True).click();expect(main).not_to_be_visible();assert writes[-1][1]['willingness']=='candidate_withdrew' and writes[-1][1]['first_interview_at'].endswith('+08:00') and 'actual_onboarded' not in writes[-1][1]
    process.get_by_role('button',name='编辑',exact=True).click();main=page.get_by_role('dialog',name='编辑招聘过程',exact=True)
    item(main,'入职意愿').locator('.el-select').click();page.get_by_role('option',name='信实放弃',exact=True).click();will=page.get_by_role('dialog',name='填写放弃原因',exact=True);expect(will).to_contain_text('信实放弃原因');will.locator('textarea').fill('岗位暂停');will.get_by_role('button',name='确认入职意愿',exact=True).click()
    item(main,'入职意愿').locator('.el-select').click();page.get_by_role('option',name='是',exact=True).click();will=page.get_by_role('dialog',name='填写入职时间',exact=True)
    will.get_by_role('button',name='确认入职意愿',exact=True).click();expect(will.locator('.el-form-item__error')).to_contain_text('请填写入职时间');will.locator('input').fill('2026年11月05日');will.locator('input').press('Enter');will.locator('input').press('Tab');will.get_by_role('button',name='确认入职意愿',exact=True).click();expect(will).not_to_be_visible()
    expect(item(main,'入职时间').locator('input')).to_have_value('2026-11-05');expect(item(main,'是否入职').locator('input')).to_be_disabled();main.get_by_role('button',name='保存招聘过程',exact=True).click();expect(main).not_to_be_visible();assert writes[-1][1]['willingness']=='yes' and writes[-1][1]['onboarding_date']=='2026-11-05' and writes[-1][1]['willingness_reason']==''
    process.get_by_role('button',name='候选甲',exact=True).click();candidate=page.get_by_role('dialog',name='应聘人及面试情况',exact=True);item(candidate,'一面结果').locator('textarea').fill('一面结果更新');candidate.get_by_role('button',name='保存应聘人与面试',exact=True).click();expect(candidate).not_to_be_visible();assert writes[-1][1]['first_result']=='一面结果更新'
    demand.update(recruitment_city='深圳',position='译审');process.get_by_role('button',name='刷新过程',exact=True).click();expect(process.locator('.el-table__body')).to_contain_text('深圳');expect(process.locator('.el-table__body')).to_contain_text('译审')
    process.get_by_role('button',name='查看详情',exact=True).click();detail=page.locator('.process-detail:visible');expect(detail).to_contain_text('二面通过');expect(detail).to_contain_text('2026-11-05');process.get_by_role('button',name='查看详情',exact=True).click()
    process.get_by_role('button',name='删除管理',exact=True).click();process.locator('.el-table__body-wrapper .el-checkbox').first.click();process.get_by_role('button',name='删除所选（1）',exact=True).click();page.get_by_role('button',name='确定删除',exact=True).click();expect(process.locator('.el-table__body')).not_to_contain_text('候选甲')
    assert not errors,errors
    print(json.dumps({'requirement_city_job_linked':True,'two_interviews_and_conditional_results':True,'withdrawal_reason_required':True,'yes_sets_onboarding_date':True,'actual_onboarding_reserved':True,'applicant_click_popup_edit':True,'live_source_update':True,'delete_management':True,'nested_dialog_field_search_and_footer':True,'page_errors':errors}))
    browser.close()
