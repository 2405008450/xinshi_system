"""真实项目窗口：仅当前提交按钮转圈；紧急预告知携带会话与邮件，所有接口模拟。"""
import json,re
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000';root=Path(__file__).resolve().parents[1]
source=(root/'tools/verify_translation_submission_ui.py').read_text(encoding='utf8')
setup=source[source.index('    compiled='):source.index('    with sync_playwright() as p:')]
namespace={'urlopen':urlopen,'re':re,'json':json,'BASE':BASE,'urlparse':urlparse}
exec('def prepare():\n'+setup+'\n    return locals()\n',namespace);state=namespace['prepare']()
state['rows'].clear();state['root'].update({'project_name':'测试.docx','source_file_name':'测试.docx','sub_orders':[],'word_count_matrix':{'company':{'words':100}},'word_count_sub_order_count':0})
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
 page.route(re.compile(r'^http://localhost:3000/api/'),state['api']);page.route(BASE+'/five-level-test',lambda r:r.fulfill(content_type='text/html',body=state['html']))
 page.goto(BASE+'/five-level-test');page.get_by_role('button',name='编辑',exact=True).first.click();editor=page.locator('.project-editor-dialog:visible');expect(editor).to_be_visible()
 page.evaluate("""()=>{let c=document.querySelector('.project-editor-dialog').__vueParentComponent;while(c&&!c.setupState?.form)c=c.parent;window.editorState=c.setupState;}""")
 labels=['保存','（紧急）项目预告知（会话和邮件）','保存并发送会话和邮件','保存并发送邮件','保存并发送会话']
 for label in labels:
  print('checking',label,flush=True)
  page.evaluate("editorState.submitAction='save';editorState.submitLoading=false")
  action=dict(zip(labels,['save','emergency','chatMail','mail','chat']))[label]
  page.evaluate('(action)=>{editorState.submitAction=action;editorState.submitLoading=true}',action)
  button=editor.get_by_role('button',name=label,exact=True)
  expect(button).to_have_class(re.compile('is-loading'));expect(editor.locator('.el-dialog__footer button.is-loading')).to_have_count(1)
  for other in labels:expect(editor.get_by_role('button',name=other,exact=True)).to_be_disabled()
  page.evaluate('editorState.submitLoading=false');expect(editor.locator('.el-dialog__footer button.is-loading')).to_have_count(0)
 # 通过校验后只打开预览；确认发送同时包含会话，不提前发送。
 print('loading states PASS',flush=True)
 editor.get_by_role('button',name=labels[1],exact=True).click()
 page.wait_for_function('editorState.mailComposerVisible===true')
 assert page.evaluate('editorState.mailAlsoChat===true')
 assert state['project_writes'][-1]['submission_mode']=='emergency_notice'
 assert not state['mail_writes'] and not state['chat_writes']
 composer=page.get_by_role('dialog').filter(has_text='内部项目邮件预览');expect(composer).to_be_visible()
 composer.get_by_role('button',name='发送邮件',exact=True).click();page.wait_for_timeout(700)
 assert len(state['mail_writes'])==1 and state['mail_writes'][0]['send_translation_chat'] is True,state['mail_writes']
 assert not errors,errors
 browser.close()
print('five actions: only clicked action spins, other actions disabled; emergency preview and confirmed mail+chat PASS')
