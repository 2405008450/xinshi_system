"""项目安排筛选、字段持久化、凌晨确认及紧凑布局；所有接口隔离。"""
import json,re
from datetime import datetime,timezone,timedelta
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html=f'''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
    import {{createApp,h}} from {json.dumps(dep('vue'))};import {{createRouter,createWebHistory,RouterView}} from {json.dumps(dep('vue-router'))};
    import Details from '/src/views/project/translation/ProjectDetails.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
    const router=createRouter({{history:createWebHistory(),routes:[{{path:'/arrangement-filter-test',component:Details,props:{{arrangement:true}}}}]}});
    const app=createApp({{render:()=>h(RouterView)}});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(router);app.mount('#app');</script>'''
    calls=[];errors=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/projects/translation/page':
            params=parse_qs(urlparse(route.request.url).query)
            filters=json.loads(params.get('field_filters',['{}'])[0]);calls.append(filters)
            result={'total':1,'items':[{'id':'project-1','order_no':'TP-TEST-001','project_name':'测试项目','source_file_name':'测试项目','project_status':'confirmed','client_short_name':'客户简称','language_pair':'中→英','customer_reception_time':'2026-10-20T10:00:00+08:00','customer_deadline_time':'2026-10-25T18:00:00+08:00','assigned_translators':[]}]}
        elif path=='/api/departments/organization':result={'items':[],'people':[],'canManage':True,'ready':True,'membershipReady':True}
        elif path=='/api/project-arrangements/directory':result={'ready':True}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1700,'height':1000},service_workers='block',timezone_id='America/Los_Angeles')
        context.add_init_script("if(!localStorage.getItem('user_id'))localStorage.setItem('user_id','filters-qa');if(!localStorage.getItem('default-fields-seeded')){localStorage.setItem('table-columns:translation-arrangements-v1:filters-qa',JSON.stringify(['orderNo','sourceFileName','clientShortName','projectStatus','languagePair','translatorReturnTime']));localStorage.setItem('default-fields-seeded','1')}localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write']));localStorage.setItem('user_roles',JSON.stringify(['超级管理员']))")
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/arrangement-filter-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.clock.set_fixed_time(datetime(2026,10,25,6,30,tzinfo=timezone(timedelta(hours=8))))
        page.goto(BASE+'/arrangement-filter-test')
        expect(page.locator('.arrangement-project')).to_have_count(1)
        assert calls[-1]['excluded_project_status']['value']==['pending_confirmation','sent_to_client','feedback_sent_to_client','paused','cancelled']
        expect(page.locator('.el-card__header')).to_have_count(0)
        expect(page.locator('.arrangement-toolbar')).to_be_visible()
        page.get_by_role('button',name='排除已安排',exact=True).click()
        page.wait_for_function("document.querySelector('.arrangement-project')!==null")
        expect(page.get_by_role('button',name='排除已安排',exact=True)).to_have_class(re.compile('el-button--primary'))
        arranged=page.get_by_role('button',name='排除已安排',exact=True)
        expect(arranged).to_have_attribute('aria-pressed','true')
        arranged.click();expect(arranged).to_have_attribute('aria-pressed','false')
        arranged.click();expect(arranged).to_have_class(re.compile('is-active-filter'))
        page.get_by_role('button',name=re.compile('排除状态')).click()
        exclusion=page.locator('.arrangement-filter-popover:visible').filter(has_text='勾选的项目状态')
        exclusion.get_by_role('checkbox',name='待确认',exact=True).locator('xpath=ancestor::label').click()
        exclusion.get_by_role('button',name='取消全部',exact=True).click()
        expect(exclusion.get_by_role('checkbox',checked=True)).to_have_count(0)
        exclusion.get_by_role('button',name='恢复默认',exact=True).click()
        expect(exclusion.get_by_role('checkbox',checked=True)).to_have_count(5)
        page.locator('.arrangement-toolbar>strong').click()
        previous=len(calls)
        page.get_by_role('button',name='今天回稿',exact=True).click()
        box=page.locator('.el-message-box')
        expect(box).to_contain_text('现在已是凌晨，请确认是否是“今天”')
        box.get_by_role('button',name='取消',exact=True).click()
        assert len(calls)==previous
        page.get_by_role('button',name='今天回稿',exact=True).click()
        box.get_by_role('button',name='确认今天',exact=True).click()
        page.wait_for_timeout(200)
        assert calls[-1]['customer_deadline_time']=={'op':'between','from':'2026-10-25','to':'2026-10-25'}
        today=page.get_by_role('button',name='今天回稿',exact=True)
        tomorrow=page.get_by_role('button',name='明日及前回稿',exact=True)
        time_button=page.locator('.arrangement-toolbar').get_by_role('button',name=re.compile('时间筛选'))
        expect(today).to_have_class(re.compile('is-active-filter'))
        expect(time_button).to_have_attribute('aria-pressed','true')
        today.click();expect(today).to_have_attribute('aria-pressed','false')
        expect(box).not_to_be_visible()
        page.wait_for_timeout(150);assert 'customer_deadline_time' not in calls[-1]
        page.get_by_role('button',name='明日及前回稿',exact=True).click()
        expect(box).to_contain_text('是否是“明天”')
        box.get_by_role('button',name='确认明天',exact=True).click()
        page.wait_for_timeout(200)
        assert calls[-1]['customer_deadline_time']=={'op':'between','from':None,'to':'2026-10-26'}
        expect(tomorrow).to_have_class(re.compile('is-active-filter'))
        tomorrow.click();expect(tomorrow).to_have_attribute('aria-pressed','false')
        expect(box).not_to_be_visible()
        page.wait_for_timeout(150);assert 'customer_deadline_time' not in calls[-1]
        page.clock.set_fixed_time(datetime(2026,10,25,7,tzinfo=timezone(timedelta(hours=8))))
        page.get_by_role('button',name='今天回稿',exact=True).click()
        expect(box).not_to_be_visible()
        page.locator('.arrangement-toolbar').get_by_role('button',name=re.compile('时间筛选')).click()
        expect(time_button).to_have_attribute('aria-pressed','false')
        expect(today).to_have_attribute('aria-pressed','false')
        expect(page.locator('.arrangement-filter-popover:visible').filter(has_text='客户来稿时间（区间）')).to_have_count(0)
        time_button.click()
        time=page.locator('.arrangement-filter-popover:visible').filter(has_text='客户来稿时间（区间）')
        time.locator('.el-range-input').nth(0).fill('2026-10-20')
        time.locator('.el-range-input').nth(1).fill('2026-10-25')
        time.locator('.el-range-input').nth(1).press('Enter')
        page.locator('.arrangement-toolbar>strong').click()
        page.wait_for_timeout(200)
        assert calls[-1]['customer_reception_time']=={'op':'between','from':'2026-10-20','to':'2026-10-25'}
        expect(time_button).to_have_class(re.compile('is-active-filter'))
        today.click();expect(today).to_have_attribute('aria-pressed','true')
        today.click();expect(today).to_have_attribute('aria-pressed','false')
        expect(time_button).to_have_attribute('aria-pressed','true')
        page.wait_for_timeout(150);assert 'customer_reception_time' in calls[-1] and 'customer_deadline_time' not in calls[-1]
        time_button.click();expect(time_button).to_have_attribute('aria-pressed','false')
        page.wait_for_timeout(150);assert 'customer_reception_time' not in calls[-1]
        page.get_by_role('button',name='字段设置',exact=True).click()
        fields=page.locator('.table-column-settings-popover:visible')
        expect(fields.get_by_role('checkbox',name='客户回稿时间',exact=True)).to_be_checked()
        expect(page.locator('.project-summary--header')).to_contain_text('客户回稿时间')
        while fields.get_by_role('checkbox',checked=True).count():fields.get_by_role('checkbox',checked=True).first.locator('xpath=ancestor::label').click()
        expect(page.locator('.project-summary--header')).to_have_text('序号安排')
        fields.get_by_role('button',name='恢复默认',exact=True).click()
        expect(page.locator('.project-summary--header')).to_contain_text('客户简称')
        fields.get_by_role('checkbox',name='客户简称',exact=True).locator('xpath=ancestor::label').click()
        page.reload();expect(page.locator('.arrangement-project')).to_have_count(1)
        expect(page.locator('.project-summary--header')).not_to_contain_text('客户简称')
        page.evaluate("localStorage.setItem('user_id','other-qa')")
        page.reload();expect(page.locator('.project-summary--header')).to_contain_text('客户简称')
        page.evaluate("localStorage.setItem('user_id','filters-qa')")
        page.reload();expect(page.locator('.project-summary--header')).not_to_contain_text('客户简称')
        expect(page.get_by_role('button',name='查看详情',exact=True)).to_have_count(0)
        page.get_by_role('button',name='TP-TEST-001',exact=True).click()
        expect(page.locator('.business-detail-popover:visible')).to_contain_text('项目详情')
        page.locator('.arrangement-toolbar>strong').click()
        expect(page.locator('.business-detail-popover:visible')).to_have_count(0)
        page.screenshot(path='scratch/arrangement-filters.png',full_page=True)
        page.set_viewport_size({'width':640,'height':800})
        page.locator('.arrangement-toolbar').get_by_role('button',name=re.compile('时间筛选')).click()
        pop=page.locator('.arrangement-filter-popover:visible').filter(has_text='客户来稿时间（区间）')
        rect=pop.bounding_box();assert rect['x']>=0 and rect['x']+rect['width']<=640
        assert not errors,errors
        print(json.dumps({'passed':True,'exclusions':True,'date_intervals':True,'four_filter_buttons_highlight_and_toggle':True,'midnight_confirm_cancel':True,'seven_am_no_prompt':True,'fields_persistence_and_reset':True,'compact_header_and_small_screen':True}))
        browser.close()

if __name__=='__main__':run()
