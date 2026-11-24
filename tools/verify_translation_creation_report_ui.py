"""笔译新增各保存入口与强制日报；业务接口全模拟。"""
import json,re
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
source=Path('tools/verify_translation_submission_ui.py').read_text(encoding='utf-8')
setup=source[source.index('    compiled='):source.index('    with sync_playwright() as p:')]
scope=dict(urlopen=urlopen,re=re,json=json,BASE=BASE,urlparse=urlparse)
exec('def prepare():\n'+setup+'\n    return locals()\n',scope)
state=scope['prepare']()
root=state['root']
state['rows'].clear()
root.update(source_file_name='来稿.pdf',project_name='来稿.pdf',sub_orders=[],word_count_matrix={'company':{'words':100}},word_count_sub_order_count=0)
with sync_playwright() as p:
 for action in ['保存','保存并发送邮件','保存并发送会话','保存并发送会话和邮件','（紧急）项目预告知（会话和邮件）']:
  created=False;completed=False;reports=[];creates=[]
  def api(route):
   global created,completed
   path=urlparse(route.request.url).path
   if path=='/api/business-numbers/reserve':
    route.fulfill(json={'number':root['order_no'],'token':'number-test','expires_at':'2026-12-24T12:00:00+08:00'});return
   if path.startswith('/api/business-numbers/'):
    route.fulfill(json={});return
   if path=='/api/projects/translation/work-report/pending':
    route.fulfill(json=[{'id':'p1','order_no':root['order_no']}] if created and not completed else []);return
   if path=='/api/projects/translation/p1/work-report':
    if route.request.method=='POST':
     reports.append(route.request.post_data_json);completed=True
     route.fulfill(json={'report_id':'r1','report_date':'2026-11-24','already_saved':False})
    else:route.fulfill(json={'project_id':'p1','order_no':root['order_no'],'task_name':root['source_file_name'],'progress_content':'客户来稿','completed':completed,'report_date':'2026-11-24'})
    return
   if path=='/api/projects/translation/' and route.request.method=='POST':
    creates.append(route.request.post_data_json);created=True;route.fulfill(json=root);return
   state['api'](route)
  browser=p.chromium.launch(channel='msedge')
  page=browser.new_page(viewport={'width':1500,'height':1000})
  page.set_default_timeout(8000);errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
  page.route(re.compile(r'^http://localhost:3000/api/'),api)
  page.route(BASE+'/five-level-test',lambda r:r.fulfill(content_type='text/html',body=state['html']))
  page.goto(BASE+'/five-level-test')
  page.get_by_role('button',name='新增项目',exact=True).click()
  editor=page.locator('.project-editor-dialog:visible')
  expect(editor).to_be_visible()
  page.evaluate("""()=>{let c=document.querySelector('.project-editor-dialog').__vueParentComponent;while(c&&!c.setupState?.form)c=c.parent;window.editorState=c.setupState;Object.assign(editorState.form,{
   sourceFileName:'来稿.pdf',projectName:'来稿.pdf',clientName:'测试客户全称',clientShortName:'测试客户',contactName:'测试联系人',customerType:'企业客户',statementRequired:true,
   serviceContent:'翻译',languagePair:'中文→英语',customerRequirementProfessional:'无',customerRequirementSpecial:'无',originalStoragePath:'D:\\\\测试原文',
   customerReceptionTime:'2026-11-24 09:00:00',customerDeadlineTime:'2026-11-25 18:00:00',projectStatus:'confirmed',
   wordCountMatrix:{company:{words:100}}});}""")
  editor.get_by_role('button',name=action,exact=True).click()
  popup=page.locator('.consultation-report-dialog:visible')
  try:
   expect(popup).to_be_visible(timeout=15000)
  except:
   print('ACTION',action,'CREATES',creates,'TEXT',page.locator('body').inner_text()[-2000:],flush=True);raise
  assert len(creates)==1
  expect(popup.get_by_label('工作类型',exact=True)).to_have_value('项目工作 / 笔译')
  expect(popup.get_by_label('订单号',exact=True)).to_have_value(root['order_no'])
  expect(popup.get_by_label('项目名称',exact=True)).to_have_value('来稿.pdf')
  expect(popup.get_by_label('具体任务',exact=True)).to_have_value('客户来稿')
  if action=='保存':
   page.reload()
   expect(popup).to_be_visible()
  popup.get_by_role('button',name='保存',exact=True).click()
  expect(popup).to_contain_text('请填写非负数字工作量')
  assert not reports
  popup.get_by_label('具体任务',exact=True).fill('客户来稿，已核对文件')
  popup.get_by_label('工作量',exact=True).fill('1')
  popup.locator('.el-form-item').filter(has_text=re.compile('^单位')).locator('.el-select__wrapper').click()
  page.get_by_role('option',name='项',exact=True).click()
  popup.locator('.el-form-item').filter(has_text=re.compile('^耗时')).locator('.el-select__wrapper').click()
  page.get_by_role('option',name='10分钟',exact=True).click()
  popup.get_by_role('button',name='保存',exact=True).click()
  expect(popup).not_to_be_visible()
  assert reports[0]['progress_content']=='客户来稿，已核对文件'
  if '邮件' in action:
   expect(page.get_by_role('dialog').filter(has_text='内部项目邮件预览')).to_be_visible()
  assert not errors,errors
  print(action,'PASS',flush=True)
  browser.close()
print('PASS all create actions, copied identity, manual validation, pending restore and mail continuation')
