"""真实讨论消息根据服务端提及关系显示 @；不发送消息或通知。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode();vue=re.search(r'from [\"\']([^\"\']*/vue\.js[^\"\']*)',compiled).group(1)
html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><style>body,#app{height:900px}</style><div id="app"></div><script type="module">import {createApp,h} from VUE;import Discussion from '/src/components/chat/DiscussionConversation.vue';createApp({render:()=>h(Discussion,{projectId:'00000000-0000-4000-8000-000000000099',active:true})}).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1200,'height':950});errors=[];writes=[]
 page.add_init_script("localStorage.setItem('user_id','qa')");page.on('pageerror',lambda e:errors.append(str(e)))
 def api(route):
  path=urlparse(route.request.url).path
  if path.endswith('/messages') and route.request.method=='GET':data={'items':[{'id':'1','sender_user_id':'other','sender_name':'测试发件人','content':'测试项目自动通知','created_at':'2026-11-09T12:00:00+08:00','mentions':[{'mentioned_user_id':'qa','mentioned_user_name':'少妃','is_all':False}],'metadata':{'mention_all':False}}],'has_more':False}
  elif path.endswith('/group'):data={'eligible_users':[],'invitable_users':[]}
  else:data={}
  if path.endswith('/messages') and route.request.method=='POST':writes.append(path)
  route.fulfill(content_type='application/json',body=json.dumps(data))
 page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(BASE+'/automatic-mention-test',lambda r:r.fulfill(content_type='text/html',body=html))
 page.goto(BASE+'/automatic-mention-test');badge=page.locator('.discussion-chat__mention-recipients');expect(badge).to_have_text('@少妃');expect(badge.locator('.discussion-mention-highlight')).to_have_text('@少妃');expect(page.locator('.discussion-chat__bubble')).to_contain_text('测试项目自动通知')
 assert not writes and not errors,(writes,errors)
 browser.close()
print('real discussion message displays persisted automatic mention and current-user highlight; body preserved; no message sends PASS')
