"""真实笔译项目完整表单中的简单需求入口；所有业务接口模拟，不写业务库。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import expect, sync_playwright

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;
    import Workspace from '/src/views/project/ProjectWorkspace.vue';import Bell from '/src/components/NotificationBell.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
    const router=createRouter({history:createWebHistory(),routes:[{path:'/translation-notes-test',component:Workspace,props:{module:'translation'}}]});const app=createApp({render:()=>h('main',{},[h(Bell),h(RouterView)])});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(router);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    project=dict(id='project1',order_no='TP-NOTE-TEST',source_file_name='记录测试.pdf',project_name='记录测试.pdf',project_status='confirmed',updated_at='2026-10-31T10:00:00+08:00',sub_orders=[])
    project['customer_deadline_time']='2026-11-02T18:00:00+08:00'
    notes=[];posts=[];errors=[];settings_posts=[];dispatches=[];dispatch_posts=[];receipt_posts=[];changes=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path.endswith('/short-notes'):result={'items':[dict(id='legacy',content='升级前的记录',actor_name='旧操作人',created_at='2026-10-30T10:00:00+08:00')],'total':1}
        elif path=='/api/translation-simple-requirements/recipients':result={'items':[{'id':'shaofei','name':'少妃'},{'id':'thomas','name':'Thomas'}],'default_recipient_ids':['shaofei']}
        elif path=='/api/translation-simple-requirements/projects/project1':
            if route.request.method=='POST':
                body=route.request.post_data_json;posts.append(body)
                item={**body,'id':str(len(notes)+1),'project_id':'project1','previous_status':project['project_status'],'actor_name':'测试操作人','actor_username':'tester','created_at':'2026-10-31T16:30:00+08:00','recipients':[{'user_id':uid,'user_name':'少妃' if uid=='shaofei' else 'Thomas','received_at':None,'reply':None} for uid in body['recipient_ids']]}
                notes.insert(0,item);project.update(project_status=body['saved_status'],updated_at='2026-10-31T16:30:00+08:00')
                result={'item':item,'project_status':project['project_status'],'project_updated_at':project['updated_at']}
            else:result={'items':notes,'total':len(notes),'project_status':project['project_status'],'project_updated_at':project['updated_at'],'customer_deadline_time':project['customer_deadline_time'],'latest_requirement':notes[0] if notes else None}
        elif path=='/api/translation-simple-requirements/projects/project1/settings':
            body=route.request.post_data_json;settings_posts.append(body);before={key:project.get(key) for key in ('project_status','customer_deadline_time')};fields=[key for key in before if key in body];project.update({key:body[key] for key in fields});project['updated_at']=f'2026-11-01T08:30:{len(settings_posts):02d}+08:00'
            changes.insert(0,dict(id=str(len(changes)),actor_name='测试操作人',created_at=project['updated_at'],before=before,after={key:project.get(key) for key in before}))
            result={'item':{'project_id':'project1'},'project_status':project['project_status'],'project_updated_at':project['updated_at'],'customer_deadline_time':project['customer_deadline_time'],'changed_fields':fields}
        elif path=='/api/translation-simple-requirements/projects/project1/dispatches':
            if route.request.method=='POST':
                body=route.request.post_data_json;dispatch_posts.append(body);record={**body,'id':'dispatch1','project_id':'project1','actor_name':'测试操作人','created_at':'2026-11-01T09:00:00+08:00','customer_deadline_time':project['customer_deadline_time'],'requirement_snapshot':notes[0] if notes else None,'recipients':[{'user_id':uid,'user_name':'少妃' if uid=='shaofei' else 'Thomas','received_at':None,'reply':None} for uid in body['recipient_ids']]};dispatches.insert(0,record);result=record
            else:result={'items':dispatches,'total':len(dispatches),'changes':changes,'changes_total':len(changes)}
        elif path.startswith('/api/translation-simple-requirements/dispatches/dispatch1'):
            record=dispatches[0]
            if route.request.method=='POST':
                step=path.rsplit('/',1)[-1];body=route.request.post_data_json;receipt_posts.append((step,body));person=record['recipients'][0];person['received_at' if step=='received' else 'completed_at']='2026-11-01T09:10:00+08:00';person['reply' if step=='received' else 'completed_reply']=body['reply']
            person=record['recipients'][0];result={**record,'order_no':project['order_no'],'project_name':project['project_name'],'current_status':project['project_status'],'current_customer_deadline_time':project['customer_deadline_time'],'is_recipient':True,'can_reply':not person.get('received_at'),'can_complete':bool(person.get('received_at') and not person.get('completed_at')),'my_completed_at':person.get('completed_at')}
        elif path=='/api/notifications/':result=[dict(id='dispatch-notice',title='项目经理安排测试通知',content='请查看安排',notification_type='translation_simple_dispatch',is_read=False,related_entity_id='dispatch1',related_project_id='project1',created_at='2026-11-01T09:00:00+08:00')] if dispatches else []
        elif path.endswith('/unread-count'):result={'count':1 if dispatches else 0}
        elif path=='/api/notifications/dispatch-notice/read':result={'id':'dispatch-notice','is_read':True}
        elif path=='/api/projects/translation/page':result={'items':[project],'total':1}
        elif path=='/api/projects/translation/project1':result=project
        elif path=='/api/projects/translation/next-order-no':result={'order_no':'TP-NEW-001'}
        elif path.endswith('/drafts/active') or '/project-client-managers/' in path:result={}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1600,'height':1000},service_workers='block',timezone_id='America/New_York')
        context.add_init_script("if(localStorage.getItem('user_roles')===null){localStorage.setItem('user_id','qa');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write','project_files:read']));}")
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/translation-notes-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda error:errors.append(error.stack));page.goto(BASE+'/translation-notes-test')
        def drag_window(window):
            page.wait_for_function("() => !document.querySelector('[class*=dialog-fade-enter-]')")
            original=window.bounding_box();header=window.locator('.el-dialog__header').bounding_box()
            x=header['x']+250;y=header['y']+15
            page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+50,y+30,steps=8);page.mouse.up()
            moved=window.bounding_box();assert abs(moved['x']-original['x'])+abs(moved['y']-original['y'])>20
            page.mouse.move(x+50,y+30);page.mouse.down();page.mouse.move(-2000,-2000,steps=8);page.mouse.up()
            bounded=window.bounding_box();assert bounded['x']>=0 and bounded['y']>=0 and bounded['x']+bounded['width']<=1601 and bounded['y']+bounded['height']<=1001
            return original
        page.get_by_role('button',name='新增项目',exact=True).click();dialog=page.locator('.project-editor-dialog:visible')
        expect(dialog.get_by_role('button',name='简单需求',exact=True)).to_be_disabled();dialog.get_by_role('button',name='取消',exact=True).click()
        page.get_by_role('button',name='TP-NOTE-TEST',exact=True).click();dialog=page.locator('.project-editor-dialog:visible')
        for tab in ['基础信息','进度跟踪','子订单','项目文件']:
            dialog.get_by_role('tab',name=tab,exact=True).click();expect(dialog.get_by_role('button',name='保存',exact=True)).to_be_visible()
        dialog.get_by_role('button',name='简单需求',exact=True).click();popup=page.locator('.simple-requirement-dialog:visible')
        expect(popup).to_contain_text('项目原状态：已确认');expect(popup).to_contain_text('少妃')
        expect(popup.locator('.requirement-deadline input')).to_have_value('2026-11-02 18:00:00')
        popup.locator('.requirement-deadline input').fill('2026-11-03 19:30:00');popup.locator('.requirement-deadline input').press('Enter');popup.get_by_role('button',name='保存回稿时间',exact=True).click();expect(popup.get_by_role('button',name='保存回稿时间',exact=True)).to_be_enabled();assert settings_posts[0]['customer_deadline_time']=='2026-11-03T19:30:00+08:00'
        popup.get_by_role('button',name=re.compile('调整项目状态')).click();page.get_by_role('menuitem',name='简单需求',exact=True).click();expect(popup).to_contain_text('项目原状态：简单需求')
        popup.get_by_role('button',name='保存需求',exact=True).click();expect(popup).to_contain_text('请填写原文');expect(popup).to_contain_text('请选择收费或不收费');assert not posts
        popup.get_by_label('原文',exact=True).fill('客户确认使用新版术语。');popup.get_by_label('译文',exact=True).fill('Use the new terminology.')
        popup.locator('label.el-radio').filter(has_text=re.compile('^不收费$')).click();popup.get_by_role('button',name='保存需求',exact=True).click()
        expect(popup.locator('.requirement-record')).to_have_count(1);assert posts[0]['chargeable'] is False and posts[0]['recipient_ids']==['shaofei']
        assert posts[0]['expected_updated_at']=='2026-11-01T08:30:02+08:00'
        expect(popup).to_contain_text('简单需求 → 简单需求');expect(popup.get_by_label('原文',exact=True)).to_have_value('')
        popup.get_by_role('button',name=re.compile('调整项目状态')).click();page.get_by_role('menuitem',name='原文件+简单需求',exact=True).click();expect(popup).to_contain_text('项目原状态：原文件+简单需求')
        popup.get_by_label('原文',exact=True).fill('原文件附带第二项需求');popup.locator('label.el-radio').filter(has_text=re.compile('^收费$')).click();popup.get_by_role('button',name='保存需求',exact=True).click()
        expect(popup.locator('.requirement-record')).to_have_count(2);assert posts[1]['chargeable'] is True and posts[1]['saved_status']=='source_file_simple_requirement'
        assert posts[0]['request_id']!=posts[1]['request_id']
        notes[0]['recipients'][0].update(received_at='2026-10-31T16:40:00+08:00',reply='收到，正在处理')
        popup.get_by_role('button',name='刷新回复',exact=True).click();expect(popup).to_contain_text('收到，正在处理')
        popup.locator('.legacy-notes>summary').click();expect(popup).to_contain_text('升级前的记录')
        popup.get_by_role('button',name='项目经理安排',exact=True).click();compose=page.locator('.requirement-dispatch-compose:visible');original=drag_window(compose);compose.get_by_role('button',name='关闭窗口',exact=True).click();expect(compose).not_to_be_visible();popup.get_by_role('button',name='项目经理安排',exact=True).click();expect(compose).to_be_visible();page.wait_for_function("() => !document.querySelector('[class*=dialog-fade-enter-]')");reset=compose.bounding_box();assert abs(reset['x']-original['x'])<3 and abs(reset['y']-original['y'])<3
        combo=compose.get_by_role('combobox');combo.click();options=page.locator('.el-select-dropdown:visible');options.get_by_role('option',name='少妃',exact=True).click();options.get_by_role('option',name='Thomas',exact=True).click();compose.get_by_label('安排具体内容（共同可见）',exact=True).fill('共同安排：请完成术语核对，再回传译文。');compose.get_by_role('button',name='发送',exact=True).click();expect(compose).not_to_be_visible();expect(popup.locator('.dispatch-history')).to_contain_text('共同安排：请完成术语核对');assert set(dispatch_posts[0]['recipient_ids'])=={'shaofei','thomas'} and dispatch_posts[0]['requirement_id']==notes[0]['id']
        page.screenshot(path='scratch/translation-simple-requirements.png')
        popup.get_by_role('button',name='关闭窗口',exact=True).click();expect(popup).not_to_be_visible()
        dialog.get_by_role('tab',name='基础信息',exact=True).click();expect(dialog.locator('[data-field-key="customerDeadlineTime"] input')).to_have_value('2026-11-03 19:30')
        dialog.get_by_role('button',name='取消',exact=True).click();page.get_by_role('button',name='系统通知',exact=True).click();page.get_by_role('button').filter(has_text='项目经理安排测试通知').click();receipt=page.locator('.el-dialog:visible').filter(has_text='项目经理安排 · 收到及已完成回执');expect(receipt).to_contain_text('共同安排：请完成术语核对');expect(receipt.get_by_role('button',name='回复已完成',exact=True)).to_be_disabled();receipt.get_by_role('button',name='回复收到',exact=True).click();expect(receipt.get_by_role('button',name='回复已完成',exact=True)).to_be_enabled();receipt.get_by_label('已完成回执',exact=True).fill('已完成，术语已统一');receipt.get_by_role('button',name='回复已完成',exact=True).click();expect(receipt).to_contain_text('已完成回执已发送');assert [entry[0] for entry in receipt_posts]==['received','completed'];receipt.get_by_role('button',name='关闭窗口',exact=True).click();expect(receipt).not_to_be_visible()
        page.evaluate("localStorage.setItem('user_roles','[]');localStorage.setItem('user_permissions',JSON.stringify(['projects:read','project_files:read']))");page.reload();page.get_by_role('button',name='TP-NOTE-TEST',exact=True).click()
        readonly=page.locator('.project-editor-dialog:visible');expect(readonly.get_by_role('button',name='保存',exact=True)).to_have_count(0)
        readonly.get_by_role('button',name='简单需求',exact=True).click();popup=page.locator('.simple-requirement-dialog:visible');expect(popup.locator('.requirement-history>.requirement-record')).to_have_count(2);expect(popup.locator('textarea')).to_have_count(0);expect(popup.get_by_role('button',name='项目经理安排',exact=True)).to_have_count(0);expect(popup.locator('.dispatch-history')).to_contain_text('已完成，术语已统一')
        page.set_viewport_size({'width':600,'height':800});rect=popup.bounding_box();assert rect['width']<=569 and rect['x']>=0 and rect['y']>=0;expect(popup.get_by_role('button',name='关闭窗口',exact=True)).to_be_visible()
        assert not errors,errors;browser.close()
    print('full project form: deadline sync in foreign timezone, status dropdown, requirements, shared multi-recipient dispatch, received/completed notifications, legacy history and readonly PASS')


if __name__=='__main__':run()
