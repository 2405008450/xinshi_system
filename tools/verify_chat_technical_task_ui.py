"""技术沟通消息直接新增任务：所有 API 均拦截，不使用真实业务数据。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'
vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', urlopen(BASE+'/src/main.js').read().decode()).group(1)
vr = re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)', urlopen(BASE+'/src/router/index.js').read().decode()).group(1)
html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app" style="height:95vh;position:relative;z-index:2200"></div><script type="module">
import {createApp,h,reactive} from VUE;import {createRouter,createWebHistory} from VR;
import Page from '/src/components/chat/DiscussionConversation.vue';
import {technicalDevelopmentAccess} from '/src/utils/technicalDevelopmentAccess.js';
import '/src/styles/theme.css';import '/src/styles/common.css';
localStorage.setItem('user_id','u1');technicalDevelopmentAccess.userId='u1';technicalDevelopmentAccess.can_enter=true;
window.testAccess=technicalDevelopmentAccess;window.testProps=reactive({projectId:'room-a',roomTitle:'技术/开发沟通',active:true});
const router=createRouter({history:createWebHistory(),routes:[]});
createApp({render:()=>h(Page,{...window.testProps})}).use(router).mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace('VR',json.dumps(vr))
content='新增接口并支持进度回滚\n保留调整原因和操作记录'
message=dict(id='1',messageType='user',content=content,senderUserId='u2',senderName='技术同事',createdAt='2026-10-30T18:00:00+08:00',attachments=[],mentions=[])
writes=[]
errors=[]

def api(route):
    request=route.request
    path=urlparse(request.url).path
    if path=='/api/chat/discussions/room-a/messages': result=dict(items=[message],hasMore=False)
    elif path=='/api/chat/technical/rooms/room-a': result=dict(enabled=False)
    elif path=='/api/technical-development/people': result=dict(arrangers=[dict(id='u1',name='本人')],executors=[dict(id='u1',name='本人'),dict(id='u2',name='技术同事')])
    elif path=='/api/technical-development/tasks':
        if request.method=='POST':
            writes.append(request.post_data_json)
            result=dict(id='new-task',task_no='DT-261030-001',**request.post_data_json)
        else: result=dict(enabled=True,items=[])
    else: result=dict(items=[],viewsAvailable=False,can_collect=False,eligibleUsers=[],invitableUsers=[])
    route.fulfill(content_type='application/json',body=json.dumps(result))

with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context(viewport=dict(width=1500,height=1000),service_workers='block')
    context.route(re.compile(r'^http://localhost:3000/api/'),api)
    context.route(BASE+'/chat-task-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
    page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(BASE+'/chat-task-ui-check')
    def field(dialog,label):
        return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label').filter(has_text=re.compile('^'+re.escape(label)+'$')))
    def open_task():
        page.get_by_role('button',name='消息操作',exact=True).click()
        page.get_by_role('menuitem',name='新增技术开发任务',exact=True).click()
        dialog=page.get_by_role('dialog',name='新增技术开发任务',exact=True)
        expect(dialog).to_be_visible()
        return dialog
    dialog=open_task()
    expect(field(dialog,'具体任务').locator('textarea')).to_have_value(content)
    expect(page.get_by_role('button',name='新增任务',exact=True)).not_to_be_visible()
    assert page.url==BASE+'/chat-task-ui-check' and not writes
    field(dialog,'具体任务').locator('textarea').fill('可编辑的聊天任务')
    dialog.get_by_role('button',name='取消',exact=True).click();expect(dialog).not_to_be_visible();assert not writes
    dialog=open_task();expect(field(dialog,'具体任务').locator('textarea')).to_have_value(content)
    field(dialog,'任务名称').locator('input').fill('群聊新增任务')
    field(dialog,'安排人').locator('.el-select').click();page.get_by_role('option',name='本人',exact=True).click()
    field(dialog,'执行人').locator('.el-select').click();page.get_by_role('option',name='本人',exact=True).last.click();page.get_by_role('option',name='技术同事',exact=True).click()
    division=page.get_by_role('dialog',name='执行人分工',exact=True);expect(division).to_be_visible();division.get_by_role('button',name='取消',exact=True).click();expect(division).not_to_be_visible()
    field(dialog,'具体任务').locator('textarea').fill('编辑后的具体任务')
    dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible()
    assert len(writes)==1 and writes[0]['content']=='编辑后的具体任务' and writes[0]['name']=='群聊新增任务'
    page.evaluate("window.testProps.roomTitle='其他沟通'")
    page.get_by_role('button',name='消息操作',exact=True).click();expect(page.get_by_role('menuitem',name='新增技术开发任务',exact=True)).not_to_be_visible();page.keyboard.press('Escape')
    page.evaluate("window.testProps.roomTitle='技术/开发沟通';window.testAccess.can_enter=false")
    page.get_by_role('button',name='消息操作',exact=True).click();expect(page.get_by_role('menuitem',name='新增技术开发任务',exact=True)).not_to_be_visible()
    assert not errors,errors
    print(json.dumps(dict(chat_menu=True,direct_shared_dialog=True,editable_message_prefill=True,cancel_does_not_save=True,reopen_resets=True,nested_division=True,save_creates_task=True,group_and_department_scope=True,page_errors=errors)))
    browser.close()
