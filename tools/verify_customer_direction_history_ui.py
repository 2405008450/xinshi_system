"""历史方向真实弹窗：自动扩大范围、方向增减、确认应用、客户/项目隔离，所有接口模拟。"""
import json,re
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000';ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tools/verify_translation_submission_ui.py').read_text(encoding='utf8');setup=source[source.index('    compiled='):source.index('    with sync_playwright() as p:')]
namespace={'urlopen':urlopen,'re':re,'json':json,'BASE':BASE,'urlparse':urlparse};exec('def prepare():\n'+setup+'\n    return locals()\n',namespace);state=namespace['prepare']();requests=[];writes=[];mode='month'
state['root']['client_id']='00000000-0000-4000-8000-000000000001'
def api(route):
 path=urlparse(route.request.url).path;method=route.request.method
 if path=='/api/projects/translation/customer-history':
  params=parse_qs(urlparse(route.request.url).query);requests.append(params);period=params['period'][0]
  present=(period=='month' and mode=='month')or(period=='all' and mode=='all')
  data={'items':[{'id':'historic','order_no':'TP-261001-001','project_name':'历史合同.pdf','language_pair':'中文→英语；中文→法语','created_at':'2026-10-20T10:00:00+08:00'}] if present else [],'total':1 if present else 0}
  route.fulfill(content_type='application/json',body=json.dumps(data));return
 if '/projects/languages' in path:
  route.fulfill(content_type='application/json',body=json.dumps([{'id':'zh','label':'中文'},{'id':'en','label':'英语'},{'id':'fr','label':'法语'},{'id':'ja','label':'日语'}]));return
 if '/business-numbers/reserve' in path:
  route.fulfill(content_type='application/json',body=json.dumps({'token':'00000000-0000-4000-8000-000000000099','number':'TP-261109-999'}));return
 if method in ('POST','PUT','PATCH','DELETE') and not any(value in path for value in ('editor-drafts','business-numbers','project-status-sync/snapshot')):writes.append(path)
 state['api'](route)
state['html']=state['html'].replace('import {createApp,h} from',"import AppStyles from '/src/App.vue';import {createApp,h} from")
state['html']=state['html'].replace('<div id="app">','<link rel="stylesheet" href="/src/styles/theme.css"><div id="app">')
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1450,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
 page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(BASE+'/five-level-test',lambda r:r.fulfill(content_type='text/html',body=state['html']))
 page.goto(BASE+'/five-level-test');page.get_by_role('button',name='新增项目',exact=True).click();editor=page.locator('.project-editor-dialog:visible');expect(editor).to_be_visible()
 button=editor.get_by_role('button',name='同客户历史项目',exact=True);expect(button).to_be_disabled()
 page.evaluate("""()=>{let c=document.querySelector('.project-editor-dialog').__vueParentComponent;while(c&&!c.setupState?.form)c=c.parent;window.editorState=c.setupState;Object.assign(editorState.form,{clientId:'00000000-0000-4000-8000-000000000001',clientShortName:'测试客户',languagePair:'英语→中文'})}""")
 button.click();dialog=page.locator('.customer-direction-history-dialog:visible');expect(dialog).to_be_visible();expect(dialog).to_contain_text('历史合同.pdf');assert [item['period'][0] for item in requests]==['week','month'];expect(dialog).to_contain_text('已自动扩大')
 dialog.get_by_text('TP-261001-001',exact=True).click();expect(dialog).to_contain_text('将带入的翻译方向')
 assert page.evaluate('editorState.form.languagePair')=='英语→中文'
 # 使用实际 LanguagePairSelect 的选中值接口验证增加与删除，未确认不影响外层表单。
 page.evaluate("""()=>{let c=document.querySelector('.customer-history-selection .language-pair-select').__vueParentComponent;while(c&&!('selectedPairs' in c.setupState))c=c.parent;c.setupState.selectedPairs=['中文→英语','中文→日语']}""")
 dialog.screenshot(path=str(ROOT/'frontend/public/help/translation/customer-directions.png'))
 dialog.get_by_role('button',name='同步翻译方向',exact=True).click();expect(dialog).not_to_be_visible();assert page.evaluate('editorState.form.languagePair')=='中文→英语；中文→日语'
 assert not writes,writes
 editor.get_by_role('button',name='取消',exact=True).click()
 # 编辑入口使用相同组件并排除当前项目；没有近一年记录时扩大至全部。
 mode='all';requests.clear();page.get_by_role('button',name='编辑',exact=True).first.click();expect(editor).to_be_visible();button.click();expect(dialog).to_contain_text('历史合同.pdf')
 assert [item['period'][0] for item in requests]==['week','month','year','all'];assert requests[-1]['exclude_project_id']==['p1']
 dialog.get_by_text('TP-261001-001',exact=True).click();dialog.get_by_role('button',name='取消',exact=True).click();expect(dialog).not_to_be_visible()
 assert not writes and not errors,(writes,errors)
 browser.close()
print('new/edit entry / precise customer / week-month-year-all expansion / selected direction add-remove / confirmation only / cancel preserved / no project writes PASS')
