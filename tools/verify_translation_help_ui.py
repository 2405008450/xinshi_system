"""笔译帮助：真实页面组件，独立浏览器，不访问业务库。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
def run():
 compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode()
 dep=lambda name:re.search(r'from [\"\']([^\"\']*/'+name+r'\.js[^\"\']*)',compiled).group(1)
 html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/theme.css"><link rel="stylesheet" href="/src/styles/common.css"><style>html,body,#app{margin:0;height:100%;overflow:hidden}#app{padding:12px;box-sizing:border-box}</style><div id="app"></div><script type="module">
import AppStyles from '/src/App.vue';import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;import Workspace from '/src/views/project/ProjectWorkspace.vue';
const app=createApp({render:()=>h(Workspace,{module:'translation'})});const router=createRouter({history:createWebHistory(),routes:[{path:'/translation-help-test',component:{render:()=>null}}]});app.use(router);await router.isReady();app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000})
  requests=[];errors=[];image_errors=[]
  page.add_init_script("localStorage.setItem('user_id','help-reader');localStorage.setItem('user_permissions','[\"projects:read\"]')")
  page.route(re.compile(r'^http://localhost:3000/api/'),lambda r:(requests.append(r.request.url),r.fulfill(content_type='application/json',body='[]')))
  page.route(BASE+'/translation-help-test*',lambda r:r.fulfill(content_type='text/html',body=html))
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('response',lambda r:image_errors.append((r.url,r.status)) if '/help/translation/' in r.url and r.status!=200 else None)
  page.goto(BASE+'/translation-help-test?section=help')
  expect(page.get_by_role('heading',name='笔译操作帮助',exact=True)).to_be_visible()
  tabs=page.locator('.workspace-navigation [role=tab]');labels=tabs.all_text_contents()
  assert labels.index('帮助')==labels.index('笔译须知')+1,labels
  expect(page.get_by_role('tab',name='帮助',exact=True)).to_have_attribute('aria-selected','true')
  expect(page.locator('.help-section')).to_have_count(15)
  assert page.locator('.help-section').first.get_attribute('id')=='translation-help-order-basics'
  body=page.locator('.help-content');expect(body).to_be_visible()
  page.get_by_role('button',name='15. 遇到这些情况，先这样检查',exact=True).click()
  expect(page.locator('#translation-help-faq h3')).to_be_in_viewport()
  page.get_by_role('button',name='2. 新增项目时，应该选哪个入口？',exact=True).click()
  image=page.locator('#translation-help-choose-entry .el-image');image.scroll_into_view_if_needed();image.click()
  expect(page.locator('.el-image-viewer__wrapper')).to_be_visible();page.locator('.el-image-viewer__close').click()
  search=page.get_by_role('textbox',name='搜索笔译帮助',exact=True);search.fill('母订单 .002');search.press('Enter')
  expect(page.locator('.help-section')).to_have_count(3)
  expect(page.locator('#translation-help-supplement')).to_be_visible()
  search.fill('不存在%_格式');expect(page.get_by_text('没有匹配的帮助内容',exact=True)).to_be_visible()
  search.fill('');expect(page.locator('.help-section')).to_have_count(15)
  page.set_viewport_size({'width':540,'height':800})
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'mobile page overflows horizontally'
  page.get_by_role('button',name='1. 先分清母订单与子订单',exact=True).click();expect(page.locator('#translation-help-order-basics h3')).to_be_in_viewport()
  assert body.evaluate('e=>e.clientHeight>120&&e.scrollHeight>e.clientHeight')
  page.set_viewport_size({'width':1440,'height':1000});page.locator('.translation-help').screenshot(path='scratch/translation-help-page.png')
  for name in ['create-entry.png','folder-preview.png','statistics.png','send-actions.png','customer-directions.png','statistics-report.png']:
   assert urlopen(BASE+'/help/translation/'+name).status==200
  assert not errors,errors
  assert not image_errors,image_errors
  assert not requests,requests
  browser.close()
 print('help next to notices / 15 ordered chapters / search AND+literal / directory navigation / image zoom / mobile scrolling / screenshot assets / no business requests PASS')
if __name__=='__main__':run()
