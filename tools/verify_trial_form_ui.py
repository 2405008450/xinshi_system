"""试采弹窗浏览器回归：全部接口模拟，不代表真实持久化验收；只在本机隔离目录运行。"""
import json, subprocess, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]/'frontend'
(root/'qa.html').write_text('<div id="app"></div><script type="module" src="/qa.js"></script>',encoding='utf-8')
(root/'qa.js').write_text('''import { createApp } from 'vue';
import { createRouter, createWebHistory } from 'vue-router';
import ElementPlus from 'element-plus'; import 'element-plus/dist/index.css';
import Page from './src/views/project/AnnotationTrials.vue';
import AppForm from './src/components/common/AppForm.vue';
const router=createRouter({history:createWebHistory(),routes:[{path:'/qa.html',component:Page}]});
createApp(Page).use(router).use(ElementPlus).component('AppForm',AppForm).mount('#app');''',encoding='utf-8')
log=(root/'qa-vite.log').open('w')
proc=subprocess.Popen(['node','node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','12219'],cwd=root,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
try:
 for _ in range(60):
  try: urllib.request.urlopen('http://127.0.0.1:12219/qa.html'); break
  except Exception: time.sleep(1)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,channel='msedge')
  page=browser.new_page(viewport={'width':1280,'height':800})
  page.on('pageerror',lambda error: print('PAGE ERROR:',str(error),flush=True))
  page.add_init_script("localStorage.setItem('user_roles','[\"admin\"]')")
  project={'id':'project-1','orderNo':'QA-001','projectName':'校验验收项目','languageItems':[{'id':'lang-1','display':'波兰语','sourceLanguageId':'pl'}]}
  person={'id':'person-1','fullName':'测试人员','resourceCode':'QA-001','annotationLanguageSkills':[{'sourceLanguageId':'pl'}]}
  fields=[{'id':'required-note','fieldLabel':'必填测试说明','dataType':'text','isRequired':True}]
  row={'id':'trial-1','projectId':'project-1','personId':'person-1','languageItemId':'lang-1','roundNo':1,'activityType':'trial','dutyRole':'executor','candidateStage':'backup','personName':'测试人员','customValues':{}}
  writes=[]
  def route(r):
   path=urllib.parse.urlparse(r.request.url).path
   if not path.startswith('/api/'): return r.continue_()
   if r.request.method in ['POST','PUT']:
    writes.append(r.request.post_data_json)
    return r.fulfill(status=400,json={'detail':{'message':'报价金额必须大于 0','fieldLabel':'报价金额'}})
   data=[]
   if path=='/api/projects/annotation/': data=[project]
   elif path=='/api/projects/annotation/project-1': data=project
   elif path=='/api/talent-options/': data=[person]
   elif path.endswith('/custom-fields'): data=fields
   elif path.endswith('/trials/count'): data={'total':1}
   elif path.endswith('/trials'): data=[row]
   r.fulfill(json=data)
  page.route('**/api/**',route)
  page.goto('http://127.0.0.1:12219/qa.html?projectId=project-1')
  page.wait_for_timeout(3000)
  print(page.locator('body').inner_text()[:1500],flush=True)
  page.get_by_role('button',name='新增候选',exact=True).click()
  dialog=page.locator('.trial-editor-dialog')
  dialog.wait_for()
  field=lambda label: dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=label))
  dialog.get_by_role('button',name='保存',exact=True).click()
  page.wait_for_timeout(600)
  assert field('人员').get_attribute('class').find('is-error')>=0
  assert len(writes)==0
  field('人员').locator('.el-select').click()
  page.get_by_role('option',name='测试人员（QA-001）').click()
  dialog.get_by_role('button',name='保存',exact=True).click()
  page.wait_for_timeout(700)
  assert field('必填测试说明').get_attribute('class').find('is-error')>=0
  assert field('必填测试说明').locator('textarea').evaluate('(el)=>el===document.activeElement')
  field('必填测试说明').locator('textarea').fill('已填写')
  field('报价金额').locator('input').fill('12')
  field('报价金额').locator('input').press('Tab')
  dialog.get_by_role('button',name='保存',exact=True).click()
  page.wait_for_timeout(700)
  assert 'is-required' in field('计费单位').get_attribute('class')
  assert 'is-error' in field('计费单位').get_attribute('class')
  assert len(writes)==0
  field('计费单位').locator('.el-select').click()
  page.get_by_role('option',name='条',exact=True).click()
  dialog.get_by_role('button',name='保存',exact=True).click()
  page.wait_for_timeout(700)
  assert len(writes)==1
  assert 'is-error' in field('报价金额').get_attribute('class')
  # 正文滚动到最底部时，操作栏仍在视口内。
  dialog.locator('.el-dialog__body').evaluate('(el)=>el.scrollTop=el.scrollHeight')
  box=dialog.get_by_role('button',name='保存',exact=True).bounding_box()
  assert box['y']+box['height']<=800
  dialog.get_by_role('button',name='取消',exact=True).click()
  page.get_by_role('button',name='编辑',exact=True).first.click()
  dialog.wait_for()
  dialog.get_by_role('button',name='保存',exact=True).click()
  page.wait_for_timeout(700)
  assert 'is-error' in field('必填测试说明').get_attribute('class')
  page.set_viewport_size({'width':540,'height':720})
  page.wait_for_timeout(300)
  box=dialog.get_by_role('button',name='保存',exact=True).bounding_box()
  assert box['y']+box['height']<=720
  page.screenshot(path=str(root/'qa-trial-form.png'))
  page.set_viewport_size({'width':1280,'height':800})
  dialog.get_by_role('button',name='取消',exact=True).click()
  page.get_by_role('button',name='新增候选',exact=True).click()
  page.wait_for_timeout(500)
  before=dialog.bounding_box()
  header=dialog.locator('.el-dialog__header').bounding_box()
  page.mouse.move(header['x']+5,header['y']+5)
  page.mouse.down(); page.mouse.move(header['x']+85,header['y']+65,steps=8); page.mouse.up()
  after=dialog.bounding_box()
  assert abs(after['x']-before['x'])>20
  page.mouse.move(after['x']+5,after['y']+5)
  page.mouse.down(); page.mouse.move(-800,-800,steps=8); page.mouse.up()
  bounded=dialog.bounding_box()
  assert bounded['x']>=-1 and bounded['y']>=-1
  dialog.locator('.el-dialog__headerbtn').click()
  page.get_by_role('button',name='新增候选',exact=True).click()
  page.wait_for_timeout(500)
  reopened=dialog.bounding_box()
  assert abs(reopened['x']-before['x'])<2 and abs(reopened['y']-before['y'])<2
  field('结果').filter(has=page.locator('.el-select')).locator('.el-select').click()
  page.get_by_role('option',name='部分通过',exact=True).click()
  assert 'is-required' in field('结果说明').get_attribute('class')
  dialog.locator('input[placeholder="搜索字段，如截止时间"]').fill('结果说')
  page.get_by_role('option').filter(has_text='结果说明').click()
  page.wait_for_timeout(300)
  assert 'is-dialog-field-search-highlight' in field('结果说明').get_attribute('class')
  browser.close()
  print('UI PASS: 新增/编辑必填校验、焦点定位、条件必填、接口错误定位、固定底栏、小屏幕；所有接口使用隔离模拟数据')
finally:
 subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
 log.close()