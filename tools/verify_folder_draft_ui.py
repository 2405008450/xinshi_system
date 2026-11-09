"""新增目录只更新表单；关闭重开、账号隔离、保存动作，全部接口模拟。"""
from pathlib import Path
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tools/verify_translation_submission_ui.py').read_text(encoding='utf8')
setup=source[source.index('    compiled='):source.index('    with sync_playwright() as p:')]
namespace={'urlopen':urlopen,'re':re,'json':json,'BASE':BASE,'urlparse':urlparse}
exec('def prepare():\n'+setup+'\n    return locals()\n',namespace)
state=namespace['prepare']();writes=[];cloud={}
def mocks(route):
 path=urlparse(route.request.url).path;method=route.request.method
 if method in ('POST','PUT','PATCH','DELETE') and not any(value in path for value in ('editor-drafts','business-numbers','project-status-sync/snapshot')):
  writes.append((path,route.request.post_data_json))
 if '/business-numbers/reserve' in path:
  route.fulfill(content_type='application/json',body=json.dumps({'token':'00000000-0000-4000-8000-000000000099','number':'TP-261108-999'}));return
 if '/editor-drafts' in path:
  route.fulfill(content_type='application/json',body=json.dumps({'payload':None,'revision':0}));return
 if '/projects/languages' in path:
  route.fulfill(content_type='application/json',body=json.dumps([{'id':'zh','label':'中文'},{'id':'en','label':'英语'}]));return
 if path=='/api/projects/translation/' and method=='POST':
  route.fulfill(content_type='application/json',body=json.dumps({**route.request.post_data_json,'id':'saved-root','order_no':'TP-261108-999','sub_orders':[]}));return
 state['api'](route)
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 page.add_init_script("localStorage.setItem('user_id','folder-owner-a');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\",\"project_files:read\",\"project_files:write\"]')")
 page.route(re.compile(r'^http://localhost:3000/api/'),mocks)
 page.route(BASE+'/five-level-test',lambda r:r.fulfill(content_type='text/html',body=state['html']))
 page.goto(BASE+'/five-level-test');page.get_by_role('button',name='新增项目',exact=True).click()
 editor=page.locator('.project-editor-dialog:visible');expect(editor).to_be_visible()
 editor.get_by_role('tab',name='新增母子订单',exact=True).click();editor.get_by_role('button',name='读取路径',exact=True).click()
 batch=page.locator('.suborder-batch-create-dialog:visible');batch.get_by_role('tab',name='本地',exact=True).click()
 page.evaluate("window.xinshiDesktop={chooseTranslationFolder:async()=>({rootPath:'D:\\\\客户资料',entries:[{relativePath:'客户资料',files:['合同.pdf']},{relativePath:'客户资料/附件',files:['报价.xlsx']},{relativePath:'客户资料/空目录',files:[]}]})}")
 batch.get_by_role('button',name='选择本地文件夹',exact=True).click()
 batch.get_by_role('button',name='应用到新增表单',exact=True).click();expect(batch).not_to_be_visible()
 expect(editor.locator('[data-field-key="sourceFileName"] input')).to_have_value('客户资料')
 expect(editor.get_by_placeholder('每行一个文件名称，须带扩展名；保存时同时创建子订单')).to_have_count(0)
 assert not writes,writes
 # 真实新增表单使用真实 useFormDraft；关闭后等待账号隔离保存，再重新打开。
 editor.get_by_role('button',name='取消',exact=True).click();expect(editor).not_to_be_visible()
 page.wait_for_timeout(500);page.get_by_role('button',name='新增项目',exact=True).click()
 expect(editor.locator('[data-field-key="sourceFileName"] input')).to_have_value('客户资料')
 expect(editor.get_by_placeholder('每行一个文件名称，须带扩展名；保存时同时创建子订单')).to_have_count(0)
 assert not writes,writes
 assert page.get_by_text('恢复草稿',exact=True).count()==0
 # 从真实组件读取当前录入数据，验证目录仍无记录 ID。
 form=page.evaluate("""()=>{let c=document.querySelector('.project-editor-dialog').__vueParentComponent;while(c&&!c.setupState?.form)c=c.parent;window.testEditor=c.setupState;return JSON.parse(JSON.stringify(c.setupState.form))}""")
 assert not form['id'] and len(form['pendingFolderImport']['entries'])==3
 editor.get_by_role('button',name='取消',exact=True).click()
 page.evaluate("localStorage.setItem('user_id','folder-owner-b')")
 page.get_by_role('button',name='新增项目',exact=True).click()
 expect(editor.locator('[data-field-key="sourceFileName"] input')).to_have_value('')
 assert not writes,writes
 editor.get_by_role('button',name='取消',exact=True).click()
 page.evaluate("localStorage.setItem('user_id','folder-owner-a')")
 page.get_by_role('button',name='新增项目',exact=True).click()
 expect(editor.locator('[data-field-key="sourceFileName"] input')).to_have_value('客户资料')
 expect(editor.get_by_placeholder('每行一个文件名称，须带扩展名；保存时同时创建子订单')).to_have_count(0)
 # 补齐母订单必要字段后，外层保存是唯一创建入口。
 page.evaluate("""()=>{let c=document.querySelector('.project-editor-dialog').__vueParentComponent;while(c&&!c.setupState?.form)c=c.parent;Object.assign(c.setupState.form,{clientName:'测试有限公司',clientShortName:'测试公司',contactName:'测试联系人',customerType:'企业客户',serviceContent:'翻译',languagePair:'中文→英语',customerReceptionTime:'2026-11-08 09:00:00',customerDeadlineTime:'2026-11-09 18:00:00',customerRequirementProfessional:'无',customerRequirementSpecial:'无'});} """)
 editor.get_by_role('button',name='保存',exact=True).click();page.wait_for_timeout(1200)
 project_writes=[payload for path,payload in writes if path=='/api/projects/translation/']
 assert len(project_writes)==1,(writes,page.locator('.el-message').all_text_contents())
 assert project_writes[0]['initial_folder_import']['root_path']==r'D:\客户资料'
 assert not any(path=='/api/sub-orders/folders/import' for path,_ in writes),writes
 assert not errors,errors
 browser.close()
print('directory apply: no business writes; close/reopen recovery; other-account isolation; no recovery prompt; outer Save creates once PASS')
