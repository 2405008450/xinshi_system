"""口译、招聘、标注新增工作报告：接口全模拟。"""
import json,re,runpy
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
scope=runpy.run_path('tools/verify_project_delivery_ui.py')
BASE=scope['BASE'];PROJECT=scope['PROJECT'];USER=scope['USER'];OTHER=scope['OTHER']
src=Path('tools/verify_project_delivery_ui.py').read_text(encoding='utf-8')
setup=src[src.index('    compiled='):src.index('    with sync_playwright() as p:')]
exec('def prepare():\n'+setup+'\n    return locals()\n',scope)
fixture=dict(id='',orderNo='TEST-261110-999',projectName='隔离项目',clientId=str(uuid4()),clientName='测试客户',clientFullName='测试客户',clientShortName='测试',
clientManagerId=USER,contactName='测试联系人',projectTypes=['translation'],taskDescription='具体任务',projectStatus='initial_follow_up',locations=['广州'],
timeRanges=[{'scheduledStart':'2026-11-24T09:00:00','scheduledEnd':'2026-11-24T18:00:00','actualStart':'','actualEnd':'',
             'locations':['广州'],'languageDirections':[{'languageIds':[USER,OTHER],'requiredCount':1}]}],
interpretationDomain='商务',filePath=r'D:\fixture\test',
languageDirections=[{'languageIds':[USER,OTHER],'requiredCount':1}],languageItems=[{'mode':'single','sourceLanguageId':USER,'targetLanguageId':'','regions':[]}],
taskDispatchedAt='2026-11-24T09:00:00',taskSubmittedAtPending=True,taskSubmittedAt='',taskImageUploadIds=[],positionTitle='招聘岗位',headcountMin=1,headcountMax=1,
employmentRange=['2026-11-24','2026-12-10'],workLocation='广州',roleAssignments=[])
with sync_playwright() as p:
 for module,label in [('interpretation','口译'),('recruitment','招聘'),('annotation','标注')]:
  for action in (['保存','保存并发送会话','（紧急）项目预告知','保存并发送邮件','保存并发送会话和邮件'] if module=='interpretation' else ['保存','保存并发送会话','（紧急）项目预告知']):
   state=scope['prepare']();created=False;completed=False;writes=[]
   def api(route):
    global created,completed
    path=urlparse(route.request.url).path
    if path.endswith('/work-report/pending'):
     route.fulfill(json=[{'id':PROJECT}] if created and not completed else []);return
    if path.endswith('/work-report'):
     if route.request.method=='POST':
      completed=True;writes.append(route.request.post_data_json);route.fulfill(json={'report_id':'r1','report_date':'2026-11-24'})
     else:route.fulfill(json={'order_no':'TEST-261110-999','task_name':'隔离项目','progress_content':'客户来稿','completed':completed,'report_date':'2026-11-24'})
     return
    if path.rstrip('/')==f'/api/projects/{module}' and route.request.method=='POST':
     created=True
     route.fulfill(json={'id':PROJECT,'order_no':'TEST-261110-999','project_name':'隔离项目','updated_at':'2026-11-24T12:00:00+08:00'});return
    if path.endswith('/progress-mention-defaults'):
     route.fulfill(json={'supports_creation':True,'ready':True,'can_manage':True,'users':[{'id':USER,'name':'甲'},{'id':OTHER,'name':'乙'}],
                         'departments':[],'current_user_id':USER,'automatic_user_ids':[],'user_ids':[],'department_ids':[]});return
    state['api'](route)
   browser=p.chromium.launch(channel='msedge')
   page=browser.new_page(viewport={'width':1450,'height':1000})
   page.set_default_timeout(7000);errors=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.add_init_script(f"localStorage.setItem('user_id','{USER}');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
   page.route(re.compile(r'^http://localhost:3000/api/'),api)
   page.route(BASE+'/project-delivery-test*',lambda r:r.fulfill(content_type='text/html',body=state['html']))
   page.goto(BASE+'/project-delivery-test?module='+module)
   page.get_by_role('button',name='新增'+label+'项目',exact=True).click()
   dialog=page.locator({'interpretation':'.interpretation-editor-dialog:visible','annotation':'.annotation-editor-dialog:visible','recruitment':'.recruitment-editor:visible'}[module])
   expect(dialog).to_be_visible()
   page.evaluate('(data)=>Object.assign(window.testVm.$.setupState.form,data)',fixture)
   page.wait_for_timeout(200)
   page.evaluate("()=>{const s=window.testVm.$.setupState;s.form.projectName='隔离项目';s.form.contactName='测试联系人'}")
   if module=='interpretation':dialog.get_by_role('textbox',name='项目名称',exact=True).fill('隔离项目')
   dialog.locator('.el-dialog__footer').get_by_role('button',name=action,exact=True).click()
   if module=='annotation':
    confirmation=page.get_by_role('dialog',name='新增项目并同步会话',exact=True)
    expect(confirmation).to_be_visible()
    confirmation.get_by_text('只保存进度',exact=True).click()
    confirmation.get_by_role('button',name='确认仅保存',exact=True).click()
   popup=page.locator('.consultation-report-dialog:visible')
   try:expect(popup).to_be_visible(timeout=12000)
   except:
    print(module,action,'CREATED',created,'ERRORS',errors,'TEXT',page.locator('body').inner_text()[-1700:],flush=True);raise
   expect(popup.get_by_label('工作类型',exact=True)).to_have_value('项目工作 / '+label)
   expect(popup.get_by_label('订单号',exact=True)).to_have_value('TEST-261110-999')
   expect(popup.get_by_label('具体任务',exact=True)).to_have_value('客户来稿')
   popup.get_by_label('工作量',exact=True).fill('1')
   popup.locator('.el-form-item').filter(has_text=re.compile('^单位')).locator('.el-select__wrapper').click()
   page.get_by_role('option',name='项',exact=True).click()
   popup.locator('.el-form-item').filter(has_text=re.compile('^耗时')).locator('.el-select__wrapper').click()
   page.get_by_role('option',name='10分钟',exact=True).click()
   popup.get_by_role('button',name='保存',exact=True).click()
   expect(popup).not_to_be_visible()
   assert len(writes)==1 and writes[0]['progress_content']=='客户来稿'
   if module=='interpretation' and action in ['保存并发送邮件','保存并发送会话和邮件','（紧急）项目预告知']:
    expect(page.locator('.business-mail-dialog:visible')).to_be_visible()
   assert not errors,errors
   print(module,action,'PASS',flush=True)
   browser.close()
print('PASS 11 create actions and report identity for three modules')
