"""笔译管理、独立项目安排页签与路由回退验收；仅使用隔离接口。"""
import json
import re
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright, expect

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    vue,router=dep('vue'),dep('vue-router')
    html=f'''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {{createApp,h}} from {json.dumps(vue)};
    import {{createRouter,createWebHistory,RouterView}} from {json.dumps(router)};
    import Workspace from '/src/views/project/ProjectWorkspace.vue';
    import AppForm from '/src/components/common/AppForm.vue';
    import Dialog from '/src/components/common/DraggableFormDialog.vue';
    const router=createRouter({{history:createWebHistory(),routes:[{{path:'/translation-workspace-test',component:Workspace,props:{{module:'translation'}}}}]}});
    const app=createApp({{render:()=>h(RouterView)}});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(router);app.mount('#app');</script>'''
    project_data={'id':'project-1','order_no':'TP-TEST-001','project_name':'系统开发测试项目','source_file_name':'系统开发测试项目','client_short_name':'系统开发测试客户','project_status':'arranged','language_pair':'中→英','assigned_translators':[{'arrangement_id':'assignment-qa','translator_name':'测试译员','translator_return_time':'2026-10-26T16:00:00+08:00','translator_unit_price':0.1,'translator_total_price':100}],'sub_orders':[]}
    updates=[]
    list_sorts=[]
    list_filters=[]
    errors=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/projects/translation/page':
            list_sorts.append(parse_qs(urlparse(route.request.url).query).get('sort',[''])[0])
            list_filters.append(json.loads(parse_qs(urlparse(route.request.url).query).get('field_filters',['{}'])[0]))
            result={'total':1,'items':[project_data]}
        elif path=='/api/projects/translation/project-1' and route.request.method=='PUT':
            payload=route.request.post_data_json;updates.append(payload)
            if 'project_status' in payload:project_data['project_status']=payload['project_status']
            for item in payload.get('assigned_translator_completions',[]):
                project_data['assigned_translators'][0].update(item)
            result=project_data
        elif path=='/api/word-count-matrices/project/project-1':result={'company':{'words':1200},'customer':{},'translator_estimate':{},'translators':[]}
        elif path=='/api/departments/organization':
            result={'ready':True,'membershipReady':True,'canManage':True,'aliases':{},'items':[{'id':'project','name':'项目部','revision':1,'userCount':1}],'people':[{'id':'person','name':'测试人员','username':'test-person','active':True,'primaryDepartment':'项目部','departments':[{'id':'project','name':'项目部'}]}]}
        elif path.endswith('/project-arrangements/directory'):result={'ready':True}
        elif path.endswith('/project/project-1/detail'):
            task={'id':'task-1','assignee_name':'测试人员','content':'测试执行任务','status':'pending','work_date':'2026-10-25','estimated_minutes':0,'actual_minutes':0,'assigned_by_name':'测试安排人','created_at':'2026-10-25T15:00:00+08:00','revision':1}
            result={'ready':True,'revision':1,'project_status':'arranged','tasks':[task],'updated_by_name':'测试安排人','updated_at':'2026-10-25T15:00:00+08:00','history_total':1,'history':[{'id':'event-1','revision':1,'operation':'assign','actor_name':'测试安排人','created_at':'2026-10-25T15:00:00+08:00','before_snapshot':{'tasks':[]},'after_snapshot':{'tasks':[task]}}]}
        elif path=='/api/project-arrangements':result={'ready':True,'total':0,'items':[]}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1600,'height':1000},service_workers='block')
        context.add_init_script("localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write']));localStorage.setItem('user_id','qa')")
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(re.compile(r'^http://localhost:3000/translation-workspace-test(?:\?.*)?$'),lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/translation-workspace-test')
        tabs=page.locator('.workspace-navigation').get_by_role('tab')
        expect(tabs).to_have_text(['笔译项目管理','项目安排','笔译须知'])
        expect(page.locator('.project-detail-list-table')).to_be_visible()
        expect(page.locator('.project-detail-list-table .el-table__header-wrapper')).to_contain_text('已分配译员')
        for field,prefix in [('customerDeadlineTime','customer_deadline_time'),('translatorReturnTime','translator_return_time'),('assignedTranslators','assigned_translator_name')]:
            button=page.locator(f'.project-detail-list-table [data-sort-field="{field}"]')
            for direction,mode in [('ascending',prefix+'_asc'),('descending',prefix+'_desc'),('none','order_no_desc')]:
                with page.expect_response(lambda response:'/api/projects/translation/page?' in response.url):button.click()
                expect(button).to_have_attribute('data-sort-direction',direction)
                assert list_sorts[-1]==mode,(list_sorts,mode)
        management_exclusion=page.get_by_role('button',name=re.compile('^排除状态'))
        expect(management_exclusion).to_have_attribute('aria-pressed','false')
        assert 'excluded_project_status' not in list_filters[-1]
        def enable_management_exclusions():
            management_exclusion.click()
            page.locator('.project-status-exclusion-popover:visible').get_by_role('button',name='恢复默认',exact=True).click()
            page.locator('.card-header').first.click(position={'x':10,'y':10})
            expect(management_exclusion).to_have_attribute('aria-pressed','true')
        enable_management_exclusions()
        tabs.nth(0).click()
        expect(management_exclusion).to_have_attribute('aria-pressed','false')
        enable_management_exclusions()
        tabs.nth(1).click();tabs.nth(0).click()
        expect(management_exclusion).to_have_attribute('aria-pressed','false')
        page.locator('.project-detail-list-table .translator-return-trigger').click()
        expect(page.locator('.translator-completion-popover:visible')).to_contain_text('译员回稿及结算信息')
        page.locator('.translator-completion-popover:visible').get_by_role('button',name='取消',exact=True).click()
        expect(page.locator('.arrangement-personnel')).to_have_count(0)
        expect(page.get_by_role('button',name='新增项目',exact=True)).to_be_visible()
        expect(page.locator('.project-detail-list-table').get_by_text('已安排',exact=True)).to_be_visible()
        page.locator('.project-detail-list-table').get_by_text('已安排',exact=True).click(button='right')
        history_dialog=page.locator('.arrangement-history-dialog.el-dialog')
        expect(history_dialog).to_be_visible()
        expect(history_dialog).to_contain_text('测试安排人')
        history_dialog.locator('.el-collapse-item__header').filter(has_text='安排与调整记录').click()
        expect(history_dialog).to_contain_text('新增安排')
        history_dialog.get_by_role('button',name='关闭',exact=True).click()
        expect(history_dialog).not_to_be_visible()
        tabs.nth(1).click()
        expect(page).to_have_url(re.compile('section=arrangements'))
        expect(page.locator('.arrangement-personnel')).to_be_visible()
        expect(page.locator('.arrangement-projects')).to_be_visible()
        exclusion_button=page.get_by_role('button',name=re.compile('^排除状态'))
        expect(exclusion_button).to_contain_text('5')
        def clear_exclusions():
            exclusion_button.click()
            page.locator('.arrangement-filter-popover:visible').get_by_role('button',name='取消全部',exact=True).click()
            page.locator('.arrangement-toolbar>strong').click()
            expect(exclusion_button).not_to_contain_text('5')
        clear_exclusions()
        tabs.nth(1).click()
        expect(exclusion_button).to_contain_text('5')
        clear_exclusions()
        tabs.nth(0).click();tabs.nth(1).click()
        expect(exclusion_button).to_contain_text('5')
        expect(page.locator('.project-summary--header')).to_contain_text('客户回稿时间')
        expect(page.locator('.project-summary--header')).to_contain_text('已分配译员')
        for field,prefix in [('customerDeadlineTime','customer_deadline_time'),('translatorReturnTime','translator_return_time'),('assignedTranslators','assigned_translator_name')]:
            button=page.locator(f'.arrangement-projects [data-sort-field="{field}"]')
            expect(button).to_be_visible()
            for direction,mode in [('ascending',prefix+'_asc'),('descending',prefix+'_desc'),('none','order_no_desc')]:
                with page.expect_response(lambda response:'/api/projects/translation/page?' in response.url):button.click()
                expect(button).to_have_attribute('data-sort-direction',direction)
                assert list_sorts[-1]==mode
                assert len(list_filters[-1]['excluded_project_status']['value'])==5
        expect(page.locator('.fixed-detail')).to_have_count(0)
        page.locator('.arrangement-projects').get_by_role('button',name='TP-TEST-001',exact=True).click()
        expect(page.locator('.business-detail-popover:visible')).to_contain_text('项目详情')
        page.locator('.arrangement-toolbar>strong').click()
        expect(page.locator('.business-detail-popover:visible')).to_have_count(0)
        page.locator('.arrangement-projects .translator-return-trigger').click()
        expect(page.locator('.translator-completion-popover:visible')).to_contain_text('译员回稿及结算信息')
        page.locator('.translator-completion-popover:visible').get_by_role('button',name='取消',exact=True).click()
        page.locator('.arrangement-projects').get_by_text('已安排',exact=True).click(button='right')
        expect(history_dialog).to_be_visible()
        history_dialog.get_by_role('button',name='关闭',exact=True).click()
        page.locator('.arrangement-projects').get_by_role('button',name='订单号筛选',exact=True).click()
        expect(page.locator('.column-header-filter-popover:visible')).to_be_visible()
        page.locator('.arrangement-toolbar>strong').click()
        page.get_by_role('button',name='字段设置',exact=True).click()
        fields=page.locator('.table-column-settings-popover:visible')
        fields.get_by_role('checkbox',name='字数统计',exact=True).locator('xpath=ancestor::label').click()
        page.locator('.arrangement-toolbar>strong').click()
        page.locator('.arrangement-projects .word-count-compact-link').click()
        expect(page.locator('.word-count-matrix-popper:visible')).to_contain_text('项目字数统计')
        page.locator('.arrangement-toolbar>strong').click()
        page.locator('.arrangement-projects .translator-return-trigger').click()
        panel=page.locator('.translator-completion-popover:visible')
        panel.locator('.el-input-number input').first.fill('0.2')
        panel.get_by_role('button',name='保存',exact=True).click()
        expect(panel).not_to_be_visible()
        assert updates[-1]['assigned_translator_completions'][0]['translator_unit_price']==0.2
        page.locator('.arrangement-projects .status-switch-tag').click()
        page.locator('.el-dropdown-menu:visible').get_by_text('初步咨询',exact=True).click()
        expect(page.locator('.arrangement-projects .status-switch-tag')).to_have_text('初步咨询')
        assert updates[-1]['project_status']=='initial_consultation'
        expect(page.locator('.project-detail-list-table:visible')).to_have_count(0)
        expect(page.get_by_role('button',name='新增项目',exact=True)).not_to_be_visible()
        splitter=page.get_by_role('separator',name='调整人员区与项目区宽度',exact=True)
        expect(splitter).to_be_visible()
        left=page.locator('.arrangement-personnel')
        before=left.bounding_box()['width']
        handle=splitter.bounding_box()
        page.mouse.move(handle['x']+handle['width']/2,handle['y']+30)
        page.mouse.down();page.mouse.move(handle['x']+handle['width']/2+140,handle['y']+30,steps=8);page.mouse.up()
        resized=left.bounding_box()['width']
        assert resized>before+100
        assert page.locator('.project-arrangement-main').bounding_box()['width']>=359
        assert page.evaluate('document.body.style.userSelect')!='none'
        page.locator('.project-list-keyword-filter input').fill('系统开发测试')
        tabs.nth(0).click()
        expect(page.locator('.project-detail-list-table')).to_be_visible()
        expect(page.locator('.arrangement-personnel:visible')).to_have_count(0)
        expect(page.locator('.project-list-keyword-filter input:visible')).to_have_value('')
        page.go_back()
        expect(page.locator('.arrangement-personnel')).to_be_visible()
        expect(page.locator('.project-list-keyword-filter input:visible')).to_have_value('系统开发测试')
        page.reload()
        expect(page.locator('.arrangement-personnel')).to_be_visible()
        assert abs(left.bounding_box()['width']-resized)<5
        splitter.focus();splitter.press('ArrowLeft')
        assert left.bounding_box()['width']<resized
        splitter.dblclick()
        assert abs(left.bounding_box()['width']-before)<5
        page.set_viewport_size({'width':640,'height':720})
        expect(splitter).not_to_be_visible()
        assert page.locator('.project-arrangement-main').bounding_box()['y']>left.bounding_box()['y']
        assert not errors,errors
        print(json.dumps({'passed':True,'tabs':['projects','arrangements','notices'],'default_original_list':True,'independent_filters':True,'history_and_reload':True,'split_drag_restore_keyboard_small_screen':True,'page_errors':errors}))
        context.close();browser.close()


if __name__=='__main__':run()
