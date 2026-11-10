"""笔译会话关闭/恢复与删除入口保护：真实聊天列表，所有接口模拟。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    workspace_source=urlopen(BASE+'/src/components/chat/ChatWorkspace.vue',timeout=30).read().decode()
    categories_url=re.search(r'from ["\']([^"\']*/useChatSessionCategories\.js[^"\']*)',workspace_source).group(1)
    html='''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><style>html,body,#app{width:100%;height:100%;margin:0}.chat-workspace__frame{height:95vh}</style><div id="app"></div><script type="module">
import {createApp,h,computed} from VUE;import {createRouter,createWebHistory} from ROUTER;import Workspace from '/src/components/chat/ChatWorkspace.vue';import {useProjectChatDock} from '/src/composables/useProjectChatDock.js';import {filterClosedSessions} from '/src/utils/chatSessionList.js';import {applySessionCategories} from '/src/composables/useChatSessionCategories.js';
applySessionCategories({ready:true,hierarchyReady:true,canManage:true,technicalAccess:false,items:[{id:'translation-room',name:'TP-261110-027',active:true,revision:1,isConversation:true,deletionProtected:true},{id:'ordinary-room',name:'普通讨论',active:true,revision:1,isConversation:true}]});
const dock=useProjectChatDock(),rows=[{key:'discussion:translation-room',projectId:'translation-room',projectType:'discussion',title:'TP-261110-027',subtitle:'群聊',deletionProtected:true,storageReady:true,memberCount:56,lastMessage:{preview:'笔译项目正文',senderName:'测试人员'}},{key:'discussion:ordinary-room',projectId:'ordinary-room',projectType:'discussion',title:'普通讨论',subtitle:'群聊',storageReady:true,lastMessage:{preview:'普通讨论正文',senderName:'测试人员'}}];
const sessions=computed(()=>filterClosedSessions(rows.map(row=>({...row,opened:dock.state.windows.some(w=>w.projectId===row.projectId)})),dock.state.closedSessionKeys));
const app=createApp({render:()=>h(Workspace,{sessions:sessions.value,recentClosed:dock.state.recentClosedSessions,maximized:true,active:true,onClose:row=>dock.closeSessionEntry(row),onOpen:row=>dock.openChat(row),onRestoreClosed:row=>dock.restoreClosedSession(row)})});app.use(createRouter({history:createWebHistory(),routes:[{path:'/protected-chat-qa',component:{render:()=>null}}]}));app.mount('#app');
</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router'))).replace("from '/src/composables/useChatSessionCategories.js'",'from '+json.dumps(categories_url))
    writes=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script("localStorage.setItem('user_id','protected-chat-qa');localStorage.setItem('user_permissions','[\"*\"]')")
        def api(route):
            if route.request.method not in ('GET','HEAD'):writes.append(route.request.url)
            if urlparse(route.request.url).path=='/api/chat/session-categories':
                result={'ready':True,'hierarchy_ready':True,'can_manage':True,'items':[{'id':'translation-room','name':'TP-261110-027','active':True,'revision':1,'is_conversation':True,'deletion_protected':True},{'id':'ordinary-room','name':'普通讨论','active':True,'revision':1,'is_conversation':True}]}
            else:result=[]
            route.fulfill(content_type='application/json',body=json.dumps(result))
        page.route(BASE+'/api/**',api);page.route(BASE+'/protected-chat-qa',lambda route:route.fulfill(content_type='text/html',body=html))
        page.goto(BASE+'/protected-chat-qa')
        # Vite 热更新可能存在不同查询串的模块实例，向本次挂载的组件注入管理权限夹具。
        page.locator('.chat-workspace__frame').evaluate('el=>{let vm=el.__vueParentComponent;while(vm&&!vm.setupState?.categories)vm=vm.parent;Object.assign(vm.setupState.categories,{ready:true,hierarchyReady:true,loaded:true,canManage:true,items:[{id:"translation-room",name:"TP-261110-027",active:true,revision:1,isConversation:true,deletionProtected:true},{id:"ordinary-room",name:"普通讨论",active:true,revision:1,isConversation:true}]})}')
        row=page.locator('.chat-workspace__session',has_text='TP-261110-027')
        expect(row).to_be_visible();expect(row.get_by_role('button',name='删除会话',exact=True)).to_have_count(0)
        expect(page.locator('.chat-workspace__session',has_text='普通讨论').get_by_role('button',name='删除会话',exact=True)).to_be_visible()
        row.get_by_role('button',name='关闭会话',exact=True).click();expect(row).to_have_count(0)
        page.get_by_role('button',name='最近关闭（1/10）',exact=True).click()
        page.get_by_role('button',name='恢复 TP-261110-027',exact=True).click();expect(row).to_be_visible()
        expect(row.get_by_role('button',name='删除会话',exact=True)).to_have_count(0)
        assert not any('/session-categories/' in url for url in writes),writes
        assert not errors,errors
        browser.close()
    print('PASS: protected translation chat hides deletion / close is personal / recent restore / ordinary discussion deletion unchanged / no delete request')
if __name__=='__main__':run()
