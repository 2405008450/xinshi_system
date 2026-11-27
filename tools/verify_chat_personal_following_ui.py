"""双账号个人关注、会话选择及分隔线宽度回归；所有 API 拦截。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
base='http://localhost:3000'
compiled=urlopen(base+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
sessions=[{'key':'annotation:a','projectId':'a','projectType':'annotation','kind':'annotation','title':'甲会话','subtitle':'AP-001','starred':False,'categoryIds':[]},{'key':'direct:b','projectId':'b','projectType':'direct','kind':'direct','title':'乙私聊','subtitle':'私聊','starred':False,'categoryIds':[]},{'key':'discussion:c','projectId':'c','projectType':'discussion','kind':'discussion','title':'丙讨论','subtitle':'讨论','starred':False,'categoryIds':[]}]
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><style>html,body,#app{margin:0;width:100%;height:100%;}</style><div id="app"></div><script type="module">import {createApp,h,ref,computed} from VUE;import {createRouter,createMemoryHistory} from '/node_modules/.vite/deps/vue-router.js';import Workspace from '/src/components/chat/ChatWorkspace.vue';import {useChatWorkspaceSplit} from '/src/composables/useChatWorkspaceSplit.js';const app=createApp({setup(){const root=ref(),panel=ref(300),items=ref(SESSIONS);const uid=localStorage.getItem('user_id');let saved=JSON.parse(localStorage.getItem('test-following:'+uid)||'null');items.value.forEach(item=>item.starred=saved?saved.includes(item.key):uid==='alice'&&item.key!=='discussion:c');const split=useChatWorkspaceSplit(root,ref(true),ref(false),ref(true),{reservedWidth:()=>panel.value});window.preferences=[];return()=>h('div',{ref:root,style:'height:100%;width:100%'},[h(Workspace,{sessions:items.value,searchSessions:items.value,active:true,maximized:true,narrow:false,activeKey:'annotation:a',projectId:'a',projectType:'annotation',title:'测试对话',sessionWidth:split.width.value,splitMaximum:split.maximum.value,onSplitStart:split.start,onSplitKeydown:split.keyboard,onSplitReset:split.reset,onSessionPanelWidth:value=>panel.value=value,onPreference:({session,data})=>{window.preferences.push({session,data});const target=items.value.find(item=>item.key===session.key);if(target)Object.assign(target,data);localStorage.setItem('test-following:'+uid,JSON.stringify(items.value.filter(item=>item.starred).map(item=>item.key)))}})])}});app.use(createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace('SESSIONS',json.dumps(sessions,ensure_ascii=False))
def api(route):
 path=route.request.url.split('?')[0]
 if path.endswith('/sessions/history'):data={'items':[{**s,'project_id':s['projectId']} for s in sessions],'total':3}
 elif path.endswith('/session-categories'):data={'ready':True,'hierarchyReady':True,'canManage':False,'technicalAccess':False,'items':[]}
 elif path.endswith('/notifications/unread-count'):data={'count':0}
 else:data={'items':[],'total':0,'count':0,'people':[],'departments':[]}
 route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 errors=[]
 def actor(uid):
  context=browser.new_context(viewport={'width':1600,'height':1000},service_workers='block')
  context.add_init_script("localStorage.setItem('user_id',"+json.dumps(uid)+");localStorage.setItem('user_permissions',JSON.stringify(['projects:read']));localStorage.setItem('xinshi.chatSessionPanel.'+localStorage.getItem('user_id'),'middle');localStorage.setItem('xinshi.chatFolder.'+localStorage.getItem('user_id'),'personal:following');")
  context.route(re.compile(r'^http://localhost:3000/api/'),api)
  context.route(base+'/personal-following-check',lambda r:r.fulfill(content_type='text/html',body=html))
  page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(base+'/personal-following-check')
  return context,page
 first,page=actor('alice')
 try:expect(page.locator('.chat-folder-tree__name').filter(has_text='我的关注')).to_be_visible()
 except Exception:
  print('PAGE_ERRORS',errors,flush=True);print(page.locator('body').inner_text()[:1200],flush=True);raise
 tabs=page.locator('[aria-label="会话列表范围"]')
 labels=[text.strip() for text in tabs.locator('button').all_text_contents()]
 assert labels==['全部会话','近期会话','我的项目','最近关闭','收藏夹','我的关注'],labels
 tabs.get_by_role('button',name='我的关注',exact=True).click()
 expect(page.locator('.chat-workspace__session')).to_have_count(2)
 handle=page.get_by_role('separator',name='调整中间会话列表与聊天区域宽度',exact=True)
 before=int(handle.get_attribute('aria-valuenow'));box=handle.bounding_box()
 page.mouse.move(box['x']+3,box['y']+box['height']/2);page.mouse.down();page.mouse.move(box['x']+83,box['y']+box['height']/2,steps=5);page.mouse.up()
 assert int(handle.get_attribute('aria-valuenow'))>=before+70
 width=int(handle.get_attribute('aria-valuenow'))
 assert page.evaluate("JSON.parse(localStorage.getItem('xinshi.chatWorkspaceMiddleSplit.alice'))")==width
 page.reload();expect(handle).to_have_attribute('aria-valuenow',str(width))
 left=page.get_by_role('separator',name='调整会话列表与聊天区域宽度',exact=True)
 left_before=int(left.get_attribute('aria-valuenow'));left_box=left.bounding_box()
 page.mouse.move(left_box['x']+3,left_box['y']+left_box['height']/2);page.mouse.down();page.mouse.move(left_box['x']+43,left_box['y']+left_box['height']/2,steps=4);page.mouse.up()
 assert int(left.get_attribute('aria-valuenow'))>=left_before+30
 page.get_by_role('button',name='选择会话',exact=True).click()
 dialog=page.get_by_role('dialog',name='选择我的关注会话',exact=True)
 expect(dialog).to_be_visible()
 content=page.locator('.chat-personal-following-dialog.el-dialog')
 initial=content.bounding_box();header=content.locator('.el-dialog__header').bounding_box()
 handle_x=header['x']+header['width']*.65
 page.mouse.move(handle_x,header['y']+15);page.mouse.down();page.mouse.move(handle_x+50,header['y']+30,steps=4);page.mouse.up()
 assert content.bounding_box()['x']>initial['x']+30
 expect(dialog.get_by_role('button',name='完成',exact=True)).to_be_visible()
 dialog.locator('.chat-session-directory__item').filter(has_text='丙讨论').click()
 assert page.evaluate('window.preferences.at(-1).session.projectId')=='c'
 dialog.get_by_role('button',name='完成',exact=True).click()
 expect(page.locator('.chat-workspace__session')).to_have_count(3)
 page.get_by_role('button',name='选择会话',exact=True).click();expect(dialog).to_be_visible()
 assert abs(content.bounding_box()['x']-initial['x'])<2
 dialog.get_by_role('button',name='完成',exact=True).click()
 second,other=actor('bob')
 other.locator('[aria-label="会话列表范围"]').get_by_role('button',name='我的关注',exact=True).click()
 expect(other.locator('.chat-workspace__session')).to_have_count(0)
 expect(other.get_by_role('separator',name='调整中间会话列表与聊天区域宽度',exact=True)).to_have_attribute('aria-valuenow','300')
 assert not errors,errors
 print('PASS: private following including direct chats, tab order, picker, resize, persistence and account isolation')
 browser.close()
