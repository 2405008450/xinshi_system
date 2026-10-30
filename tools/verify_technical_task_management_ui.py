"""技术开发交互验收：所有业务 API 拦截，不写入真实数据库。"""
import json
import re
from copy import deepcopy
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'
compiled = urlopen(BASE + '/src/components/common/AppForm.vue').read().decode()
vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Page from '/src/views/technology/TechnicalDevelopment.vue';import '/src/styles/theme.css';import '/src/styles/common.css';localStorage.setItem('user_id','technical-ui-check');createApp({render:()=>h(Page)}).mount('#app');</script>'''.replace('VUE', json.dumps(vue))
STAMP = '2026-10-30T14:00:00+08:00'
def task(uid, name, parent=None):
    return dict(id=uid, task_no=f"DT-261030-{dict(a=1,b=2,c=3,d=4).get(uid,5):03d}", name=name, parent_id=parent, content='具体任务正文', arranger_id='u1', arranger_name='赵震锋', executor_id='u3', executor_name='技术同事', due_at='2026-11-01T18:00:00+08:00', progress=90, progress_updated_at=STAMP, adjustment='原调整', notes='原备注', revision=1, created_at=STAMP, updated_at=STAMP, progress_history=[], feedback=[])

rows = [task('a', '母任务A'), task('b', '子任务B', 'a'), task('c', '三级任务C', 'b'), task('d', '独立任务D')]
writes, errors, added_reports = [], [], []


def api(route):
    request = route.request
    path = urlparse(request.url).path
    if path == '/api/technical-development/people':
        result = dict(arrangers=[dict(id='u1', name='赵震锋'), dict(id='u2', name='运坚'), dict(id='u3', name='技术同事')], executors=[dict(id='u3', name='技术同事')])
    elif path == '/api/technical-development/tasks' and request.method == 'GET':
        result = dict(enabled=True, items=rows)
    elif path == '/api/technical-development/tasks' and request.method == 'POST':
        body = request.post_data_json; writes.append((path, body))
        result = task('new', body['name'], body.get('parent_id')); result.update(body); rows.append(result)
    elif path.startswith('/api/technical-development/tasks/'):
        parts = path.split('/'); row = next(row for row in rows if row['id'] == parts[4])
        if path.endswith('/report'):
            if request.method == 'GET':
                result = dict(task_id=row['id'], report_date='2026-10-30', report_type='开发任务', order_no=row['task_no'], task_name=row['name'], progress_content=row['content'])
            else:
                body = request.post_data_json; writes.append((path, body)); added_reports.append(dict(task_type=body['report_type'], task_name=body['task_name'], progress_content=body['progress_content'], duration_minutes=body['duration_minutes'], display_metadata=dict(report_types=body['report_types'], quantity=body['quantity'], quantity_unit=body['quantity_unit'], added_at=STAMP, order_no=body['order_no'], technical_task_id=row['id'], source='technical_development')))
                result = dict(report_id='mock-report', report_date='2026-10-30')
            route.fulfill(content_type='application/json', body=json.dumps(result)); return
        if request.method != 'GET':
            body = request.post_data_json; writes.append((path, body))
            if path.endswith('/progress'):
                row['progress_history'].insert(0, dict(id=f'p{len(writes)}', previous_percentage=row['progress'], percentage=body['percentage'], content=body['content'], reason=body['reason'], author_name='技术同事', created_at=STAMP))
                row['progress'] = body['percentage']; row['revision'] += 1
            elif path.endswith('/feedback'):
                row['feedback'].insert(0, dict(id=f'f{len(writes)}', content=body['content'], author_name='运坚', created_at=STAMP))
            else:
                row.update(body); row['revision'] += 1
        result = row
    else:
        result = {}
    route.fulfill(content_type='application/json', body=json.dumps(deepcopy(result)))


def item(dialog, label):
    return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label').filter(has_text=re.compile('^' + re.escape(label) + '$')))



base_api=api
rows[1]['task_no']=rows[0]['task_no']+'.001'
rows[2]['task_no']=rows[1]['task_no']+'.001'
rows.append(task('e','独立任务E'))
deletes=[]
def api(route):
    request=route.request
    path=urlparse(request.url).path
    if request.method=='DELETE':
        uid=path.split('/')[4]
        if any(row['parent_id']==uid for row in rows):
            route.fulfill(status=409,content_type='application/json',body=json.dumps(dict(detail='任务下还有子任务，请先删除子任务')));return
        rows[:]=[row for row in rows if row['id']!=uid];deletes.append(uid)
        route.fulfill(content_type='application/json',body=json.dumps(dict(deleted=True)));return
    if path.endswith('/swap'):
        uid=path.split('/')[4];target=request.post_data_json['target_id'];replace={uid:target,target:uid}
        original={row['id']:row['parent_id'] for row in rows};mapping={row['id']:row for row in rows}
        for old,parent in original.items():
            mapping[replace.get(old,old)]['parent_id']=replace.get(parent,parent)
        mapping[uid]['task_no'],mapping[target]['task_no']=mapping[target]['task_no'],mapping[uid]['task_no']
        route.fulfill(content_type='application/json',body='{}');return
    base_api(route)

with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context(viewport=dict(width=1600,height=1000),service_workers='block')
    context.route(re.compile(r'^http://localhost:3000/api/'),api)
    context.route(BASE+'/technical-management-check',lambda route:route.fulfill(content_type='text/html',body=html))
    page=context.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(BASE+'/technical-management-check')
    def row(name): return page.locator('.el-table__body tr').filter(has=page.locator('.task-name').filter(has_text=name))
    expect(page.get_by_role('columnheader',name='详情',exact=True)).to_have_count(0)
    row('母任务A').get_by_role('button',name='DT-261030-001',exact=True).click()
    expect(page.locator('.el-popover:visible')).to_contain_text('技术开发任务详情')
    page.locator('.page-title').click()
    row('母任务A').get_by_role('button',name='更多操作',exact=True).click();page.get_by_role('menuitem',name='互换位置',exact=True).click()
    dialog=page.get_by_role('dialog',name='互换任务位置',exact=True);expect(dialog).to_be_visible()
    dialog.locator('.el-select').click();page.get_by_role('option',name='DT-261030-001.001.001 三级任务C',exact=True).click()
    dialog.get_by_role('button',name='确认互换',exact=True).click();expect(dialog).not_to_be_visible()
    expect(row('三级任务C').get_by_role('button',name='DT-261030-001',exact=True)).to_be_visible()
    expect(row('母任务A').get_by_role('button',name='DT-261030-001.001.001',exact=True)).to_be_visible()
    page.get_by_role('button',name='删除管理',exact=True).click()
    expect(page.get_by_role('button',name='新增任务',exact=True)).not_to_be_visible()
    expect(page.get_by_role('columnheader',name='操作',exact=True)).to_have_count(0)
    expect(page.get_by_role('button',name='删除所选（0）',exact=True)).to_be_disabled()
    row('独立任务D').locator('.el-checkbox').click();page.get_by_role('button',name='删除所选（1）',exact=True).click()
    page.get_by_role('button',name='确定删除',exact=True).click();expect(row('独立任务D')).to_have_count(0)
    assert deletes==['d']
    page.get_by_role('button',name='删除管理',exact=True).click()
    row('三级任务C').locator('.el-checkbox').click();row('独立任务E').locator('.el-checkbox').click()
    page.get_by_role('button',name='删除所选（2）',exact=True).click()
    prompt=page.get_by_role('dialog',name='批量删除确认',exact=True)
    prompt.get_by_role('textbox').fill('删除');prompt.get_by_role('button',name='确定删除',exact=True).click()
    expect(row('独立任务E')).to_have_count(0);expect(page.get_by_role('button',name='删除所选（1）',exact=True)).to_be_enabled()
    expect(row('三级任务C').locator('.el-checkbox')).to_have_class(re.compile('is-checked'))
    page.locator('.el-notification__closeBtn').click()
    page.get_by_role('button',name='退出',exact=True).click();page.get_by_role('button',name='删除管理',exact=True).click()
    for name in ['三级任务C','子任务B','母任务A']: row(name).locator('.el-checkbox').click()
    page.get_by_role('button',name='删除所选（3）',exact=True).click();prompt=page.get_by_role('dialog',name='批量删除确认',exact=True)
    prompt.get_by_role('textbox').fill('删除');prompt.get_by_role('button',name='确定删除',exact=True).click()
    expect(page.get_by_role('button',name='删除管理',exact=True)).to_be_visible()
    assert deletes==['d','e','a','b','c'] and not rows
    assert not errors,errors
    print(json.dumps(dict(number_opens_detail=True,no_detail_column=True,ancestor_and_third_swap=True,delete_mode=True,single_confirmation=True,strong_batch_confirmation=True,partial_failure_retains_selection=True,children_deleted_first=True,page_errors=errors)))
    browser.close()
