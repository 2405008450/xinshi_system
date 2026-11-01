"""技术任务创建会话、分组及置顶展示；全部业务请求拦截。"""
import json,re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',urlopen(BASE+'/src/main.js').read().decode()).group(1)
vr=re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)',urlopen(BASE+'/src/router/index.js').read().decode()).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import{createApp,h}from VUE;import{createRouter,createWebHistory}from VR;
import Page from '/src/views/technology/TechnicalDevelopment.vue';import Tree from '/src/components/chat/ChatSessionFolderTree.vue';
import{useAnnotationFollowed}from '/src/composables/useAnnotationFollowed.js';import{useProjectChatDock}from '/src/composables/useProjectChatDock.js';
import{sessionCategories}from '/src/composables/useChatSessionCategories.js';import '/src/styles/theme.css';import '/src/styles/common.css';
localStorage.setItem('user_id','u1');window.testDock=useProjectChatDock().state;window.testCategories=sessionCategories;
const router=createRouter({history:createWebHistory(),routes:[]});createApp({setup(){const{sessions}=useAnnotationFollowed();return()=>h('main',{style:'display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:16px'},[h(Page),h(Tree,{sessions:sessions.value})])}}).use(router).mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace('VR',json.dumps(vr))
compiled=urlopen(BASE+'/src/views/technology/TechnicalDevelopment.vue').read().decode()
for module in ['useAnnotationFollowed','useProjectChatDock','useChatSessionCategories']:
    path=re.search(r'from ["\']([^"\']*/'+module+r'\.js[^"\']*)',compiled).group(1)
    html=html.replace("'/src/composables/"+module+".js'",json.dumps(path))
ROOT='dcb1f917-6000-4000-8000-000000000012'
task=dict(id='task-a',task_no='DT-261030-001',name='接口开发',content='完善接口',arranger_id='u1',arranger_name='本人',executor_id='u1',executor_name='本人',parent_id=None,progress=0,revision=1,due_at=None,completed_on=None,on_time=None,completion_enabled=True)
created=False;opens=0;errors=[]
def catalog():
    items=[]
    if created:items.append(dict(id='room-task',name='DT-261030-001 · 接口开发',parent_key=ROOT,active=True,revision=1,is_conversation=True))
    items.append(dict(id='room-general',name='技术/开发沟通',parent_key=ROOT,active=True,revision=1,is_conversation=True,fixed_top=True))
    return dict(ready=True,hierarchy_ready=True,can_manage=False,technical_access=True,items=items)
def sessions():
    items=[dict(key='discussion:room-general',kind='discussion',project_id='room-general',title='技术/开发沟通',subtitle='群聊',category_ids=['room-general'],pinned=True)]
    if created:items.append(dict(key='discussion:room-task',kind='discussion',project_id='room-task',title='DT-261030-001 · 接口开发',subtitle='群聊',category_ids=['room-task']))
    return dict(items=items,session_categories=catalog())
def api(route):
    global created,opens
    path=urlparse(route.request.url).path
    if path=='/api/technical-development/tasks':result=dict(enabled=True,items=[{**task,'conversation':dict(created=True,room_id='room-task') if created else None}])
    elif path=='/api/technical-development/people':result=dict(arrangers=[],executors=[])
    elif path=='/api/technical-development/tasks/task-a/conversation':
        assert route.request.method=='POST';created=True;opens+=1;result=dict(room_id='room-task',task_id='task-a',title='DT-261030-001 · 接口开发')
    elif path=='/api/chat/sessions':result=sessions()
    elif path=='/api/chat/session-categories':result=catalog()
    else:result=dict(items=[])
    route.fulfill(content_type='application/json',body=json.dumps(result))
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context(viewport=dict(width=1800,height=1050),service_workers='block')
    context.route(re.compile(r'^http://localhost:3000/api/'),api)
    context.route(BASE+'/technical-conversation-check',lambda route:route.fulfill(content_type='text/html',body=html))
    page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/technical-conversation-check')
    expect(page.get_by_role('button',name='展开技术/开发项目',exact=True)).to_be_visible()
    page.get_by_role('button',name='更多操作',exact=True).click();page.get_by_role('menuitem',name='创建会话',exact=True).click()
    try: page.wait_for_function("window.testDock.windows.some(row=>row.projectId==='room-task'&&row.projectType==='discussion')")
    except Exception:
        print(json.dumps(dict(created=created,opens=opens,errors=errors,messages=page.locator('.el-message__content').all_text_contents(),windows=page.evaluate('window.testDock.windows.map(row=>({projectId:row.projectId,projectType:row.projectType}))'))));raise
    assert created and opens==1
    page.get_by_role('button',name='展开技术/开发项目',exact=True).click()
    group=page.locator('.chat-folder-tree__children').last
    expect(group).to_contain_text('DT-261030-001 · 接口开发');expect(group).to_contain_text('技术/开发沟通')
    names=group.locator('.chat-folder-tree__name').all_text_contents();assert names[0].startswith('技术/开发沟通'),names
    page.get_by_role('button',name='更多操作',exact=True).click();page.get_by_role('menuitem',name='打开会话',exact=True).click()
    page.wait_for_function("window.testDock.windows.length===1");assert opens==2
    page.evaluate('window.testCategories.technicalAccess=false')
    expect(page.get_by_role('button',name='收起技术/开发项目',exact=True)).to_have_count(0)
    assert not errors,errors
    print(json.dumps(dict(create_from_task_menu=True,opens_chat=True,reopen_without_duplicate=True,technical_group=True,general_pinned_first=True,department_scoped_group=True,page_errors=errors)))
    browser.close()
