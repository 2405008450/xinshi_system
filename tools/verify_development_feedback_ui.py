"""反馈表整链路与截图验收，拦截所有业务 API，不写真实数据。"""
import base64
import json
import re
from copy import deepcopy
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'
app_source = urlopen(BASE + '/src/main.js').read().decode()
vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', app_source).group(1)
router_source = urlopen(BASE + '/src/router/index.js').read().decode()
vue_router = re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)', router_source).group(1)
html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Tasks from '/src/views/technology/TechnicalDevelopment.vue';import Company from '/src/views/system/CompanyManagement.vue';import Feedback from '/src/views/technology/DevelopmentFeedback.vue';import '/src/styles/theme.css';import '/src/styles/common.css';localStorage.setItem('user_id','feedback-ui-check');const router=createRouter({history:createWebHistory(),routes:[{path:'/feedback-ui-check',component:Tasks},{path:'/company-management',component:Company,children:[{path:'development-feedback',name:'DevelopmentFeedback',component:Feedback}]}]});createApp({render:()=>h(RouterView)}).use(router).mount('#app');</script>'''.replace('VUE', json.dumps(vue)).replace('ROUTER', json.dumps(vue_router))
STAMP = '2026-10-30T15:30:00+08:00'
actor = 'developer'
task = dict(id='task-a', name='开发测试任务', task_no='DT-261030-001', parent_id=None, content='具体开发任务', arranger_id='dev', arranger_name='开发员', executor_id='dev', executor_name='开发员', due_at=None, progress=0, progress_updated_at=None, adjustment='', notes='', revision=1, created_at=STAMP, updated_at=STAMP)
groups, writes, errors = [], [], []
image_id = '11111111-1111-4111-8111-111111111111'
png = b''


def row_for(user):
    return dict(id=f'row-{len(groups[0]["items"])+1}', feedback_no=f'FB-261030-{len(groups[0]["items"])+1:03d}', task_id=task['id'], submitted_on='2026-10-30', submitted_by=user, submitted_name=user, submitted_username=user, module='', content='', urgency='中', attachments='', status='待处理', assignee_id=None, assignee_name='', result='', completed_on=None, notes='', revision=1, opinions=[])


def serialize(row):
    return {**row, 'can_edit': actor == row['submitted_by'] or actor in ('developer','williamzhao')}


def api(route):
    request = route.request; path = urlparse(request.url).path
    if path == '/api/editor-screenshots' and request.method == 'POST':
        writes.append((path, 'upload')); result = dict(id=image_id, reference=f'screenshot://{image_id}#'+'0'*64)
    elif path == '/api/editor-screenshots/' + image_id:
        route.fulfill(content_type='image/png', body=png); return
    elif path == '/api/technical-development/tasks': result = dict(enabled=True, items=[task])
    elif path == '/api/technical-development/people': result = dict(arrangers=[dict(id='dev',name='开发员')],executors=[dict(id='dev',name='开发员')])
    elif path == '/api/development-feedback': result = dict(enabled=True, groups=[{**group,'items':[serialize(row) for row in group['items']]} for group in groups], access=dict(william=actor=='williamzhao',development=actor=='developer'), assignees=[dict(id='dev',name='开发员')])
    elif path.endswith('/generate'):
        writes.append((path, {}))
        if not groups:
            groups.append(dict(task_id=task['id'], task_name=task['name'], task_no=task['task_no'], items=[])); groups[0]['items'].append(row_for(actor))
        result = dict(task_id=task['id'])
    elif path.endswith('/rows') and request.method == 'POST':
        writes.append((path,request.post_data_json)); result=row_for(actor); groups[0]['items'].append(result); result=serialize(result)
    elif path.startswith('/api/development-feedback/rows/'):
        row = next(row for row in groups[0]['items'] if row['id'] == path.split('/')[4])
        body=request.post_data_json; writes.append((path,body))
        if path.endswith('/opinions'):
            last=next((op for op in row['opinions'] if op['kind']==body['kind']),None)
            assert body['expected_latest_id'] == (last['id'] if last else None)
            row['opinions'].insert(0,dict(id=f'op-{len(writes)}',kind=body['kind'],content=body['content'],author_name=actor,author_username=actor,created_at=STAMP))
        else:
            assert body['revision']==row['revision']
            row.update({key:value for key,value in body.items() if key!='revision'});row['revision']+=1
            if row['assignee_id']=='dev':row['assignee_name']='开发员'
        result=serialize(row)
    else: result={}
    route.fulfill(content_type='application/json',body=json.dumps(deepcopy(result)))


with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context(viewport={'width':1700,'height':1050},service_workers='block')
    context.route(re.compile(r'^http://localhost:3000/api/'),api)
    context.route(BASE+'/feedback-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
    context.route(BASE+'/company-management/development-feedback*',lambda route:route.fulfill(content_type='text/html',body=html))
    page=context.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(BASE+'/feedback-ui-check')
    page.get_by_role('button',name='更多操作',exact=True).click()
    page.get_by_role('menuitem',name='生成反馈表',exact=True).click()
    expect(page).to_have_url(re.compile('/company-management/development-feedback'))
    expect(page.get_by_role('tab',name='开发反馈',exact=True)).to_have_attribute('aria-selected','true')
    expect(page.locator('.el-collapse-item__header')).to_contain_text('（开发）开发测试任务')
    expect(page.locator('.feedback-editable-table .el-table__body')).to_contain_text('')

    def cell(label,row_index=0):
        headers=page.locator('.feedback-editable-table .el-table__header th').all_text_contents()
        index=next(i for i,text in enumerate(headers) if text.strip()==label)
        return page.locator('.feedback-editable-table .el-table__body tr').nth(row_index).locator('td').nth(index)

    expect(cell('反馈编号').locator('input')).to_have_value('FB-261030-001')
    expect(cell('反馈编号').locator('input')).to_have_attribute('readonly','')
    cell('涉及功能模块').locator('input').fill('工作报告');cell('反馈内容').locator('textarea').fill('筛选结果错误');cell('反馈内容').locator('textarea').press('Control+Enter')
    page.wait_for_function("!document.querySelector('.feedback-cell-error') && [...document.querySelectorAll('.feedback-cell small')].every(e=>!e.textContent.includes('保存中'))")
    assert groups[0]['items'][0]['module']=='工作报告' and groups[0]['items'][0]['content']=='筛选结果错误'
    assert cell('William意见').locator('textarea').count()==0
    cell('开发部门意见').locator('textarea').fill('已经复现');cell('开发部门意见').locator('textarea').press('Control+Enter')
    expect(cell('开发部门意见')).to_contain_text('developer（developer）')
    cell('开发部门意见').locator('textarea').fill('已修复待验证');cell('开发部门意见').locator('textarea').press('Control+Enter')
    expect(cell('开发部门意见').get_by_role('button',name='意见记录（2）',exact=True)).to_be_visible()
    cell('紧急程度').locator('.el-select').click();page.get_by_role('option',name='紧急',exact=True).click()
    cell('处理状态').locator('.el-select').click();page.get_by_role('option',name='处理中',exact=True).click()
    cell('负责人').locator('.el-select').click();page.get_by_role('option',name='开发员',exact=True).click()
    expect(cell('负责人')).to_contain_text('开发员')
    png=base64.b64decode(page.evaluate("()=>{const c=document.createElement('canvas');c.width=10;c.height=10;c.getContext('2d').fillRect(0,0,10,10);return c.toDataURL('image/png').split(',')[1]}"))
    cell('附件或截图链接').locator('input[type=file]').set_input_files(dict(name='feedback.png',mimeType='image/png',buffer=png))
    expect(cell('附件或截图链接').locator('.el-image')).to_be_visible()
    page.wait_for_function('()=>[...document.querySelectorAll(".feedback-cell small")].every(e=>!e.textContent.includes("保存中"))')
    assert 'screenshot://' in groups[0]['items'][0]['attachments']
    cell('备注').locator('textarea').fill('截图已上传');cell('备注').locator('textarea').press('Control+Enter')
    cell('完成日期').locator('input').fill('2026-10-31');cell('完成日期').locator('input').press('Enter');cell('完成日期').locator('input').press('Tab')
    page.get_by_role('button',name='刷新',exact=True).click()
    expect(cell('备注').locator('textarea')).to_have_value('截图已上传')
    assert groups[0]['items'][0]['completed_on']=='2026-10-31'
    actor='employee';page.reload()
    expect(cell('反馈内容').locator('.feedback-cell-readonly')).to_contain_text('筛选结果错误')
    assert cell('开发部门意见').locator('textarea').count()==0 and cell('William意见').locator('textarea').count()==0
    page.get_by_role('button',name='新增反馈',exact=True).click()
    expect(page.locator('.feedback-editable-table .el-table__body tr')).to_have_count(2)
    expect(cell('反馈人',1).locator('input')).to_have_value('employee（employee）')
    cell('反馈内容',1).locator('textarea').fill('普通员工反馈');cell('反馈内容',1).locator('textarea').press('Control+Enter')
    actor='williamzhao';page.reload()
    cell('William意见').locator('textarea').fill('按此方案修复');cell('William意见').locator('textarea').press('Control+Enter')
    expect(cell('William意见')).to_contain_text('williamzhao（williamzhao）')
    page.get_by_role('textbox',name='搜索开发反馈').fill('普通 员工')
    expect(page.locator('.feedback-editable-table .el-table__body tr')).to_have_count(1)
    page.get_by_role('textbox',name='搜索开发反馈').fill('')
    expect(page.locator('.feedback-editable-table .el-table__body tr')).to_have_count(2)
    page.locator('.el-collapse-item__header').click();expect(page.locator('.feedback-editable-table')).not_to_be_visible()
    page.locator('.el-collapse-item__header').click();expect(page.locator('.feedback-editable-table')).to_be_visible()
    assert not errors,errors
    print(json.dumps(dict(generate_and_navigate=True,company_subsection=True,editable_cells_and_serial_saves=True,automatic_identity=True,opinion_permissions_and_history=True,screenshot_upload_and_autosave=True,completion_date=True,regular_employee_submission=True,filter_and_collapse=True,page_errors=errors)))
    browser.close()
