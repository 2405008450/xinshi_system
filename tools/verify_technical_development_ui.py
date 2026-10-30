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


with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='msedge', headless=True)
    context = browser.new_context(viewport=dict(width=1600, height=1000), service_workers='block')
    context.route(re.compile(r'^http://localhost:3000/api/'), api)
    context.route(BASE + '/technical-ui-check', lambda route: route.fulfill(content_type='text/html', body=html))
    page = context.new_page(); page.set_default_timeout(10000); page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE + '/technical-ui-check')
    expect(page.locator('.el-table__body')).to_contain_text('三级任务C')
    expect(page.locator('.el-table__header th').first).to_contain_text('任务编号')
    expect(page.locator('.el-table__body')).to_contain_text('DT-261030-003')
    expect(page.locator('.el-table__body').get_by_role('button', name='更多操作', exact=True)).to_have_count(4)
    third_level = page.locator('.el-table__body tr').filter(has_text='三级任务C')
    third_level.get_by_role('button', name='更多操作', exact=True).click()
    expect(page.get_by_role('menuitem', name='添加子任务', exact=True)).not_to_be_visible()
    expect(page.get_by_role('menuitem', name='编辑', exact=True)).to_be_visible()
    page.keyboard.press('Escape')
    # 真正拖拽：D -> B，成为三级，再恢复一级；循环/四级均被前端拒绝。
    page.get_by_role('button', name='拖动任务：独立任务D', exact=True).drag_to(page.locator('.task-name').filter(has_text='子任务B'))
    expect(page.locator('.el-table__body')).to_contain_text('独立任务D')
    assert rows[3]['parent_id'] == 'b'
    page.get_by_role('button', name='拖动任务：独立任务D', exact=True).drag_to(page.locator('.tree-help'))
    page.wait_for_function("document.querySelector('.count')?.textContent.includes('4')")
    assert rows[3]['parent_id'] is None
    before = len(writes)
    page.get_by_role('button', name='拖动任务：母任务A', exact=True).drag_to(page.locator('.task-name').filter(has_text='三级任务C'))
    assert len(writes) == before
    # 独立进度记录，回退原因校验且不影响父任务。
    page.get_by_role('button', name='子任务B：进度 90%，查看和修改进度', exact=True).click()
    progress_dialog = page.get_by_role('dialog', name='任务进度与修改记录', exact=True)
    expect(progress_dialog).to_be_visible()
    item(progress_dialog, '进度（1—100）').locator('input').fill('80')
    item(progress_dialog, '具体进度').locator('textarea').fill('重新测试')
    progress_dialog.get_by_role('button', name='保存进度', exact=True).click()
    expect(progress_dialog.locator('.el-form-item__error')).to_contain_text('进度回退必须填写修改原因')
    item(progress_dialog, '修改原因').locator('textarea').fill('发现遗漏用例')
    progress_dialog.get_by_role('button', name='保存进度', exact=True).click()
    expect(progress_dialog.locator('.history-record')).to_contain_text('90% → 80%')
    expect(progress_dialog.locator('.history-record')).to_contain_text('发现遗漏用例')
    assert rows[0]['progress'] == 90 and rows[1]['progress'] == 80
    progress_dialog.get_by_role('button', name='关闭', exact=True).last.click()
    table_row = page.locator('.el-table__body tr').filter(has_text='三级任务C')
    table_row.get_by_role('button', name='查看 / 填写反馈', exact=True).click()
    feedback_dialog = page.get_by_role('dialog', name='任务反馈意见', exact=True)
    item(feedback_dialog, '反馈意见').locator('textarea').fill('三级任务反馈')
    feedback_dialog.get_by_role('button', name='提交反馈', exact=True).click()
    expect(feedback_dialog.locator('.history-record')).to_contain_text('运坚')
    expect(feedback_dialog.locator('.history-record')).to_contain_text('2026年10月30日')
    feedback_dialog.get_by_role('button', name='关闭', exact=True).last.click()
    # 报告添加前不提交，可编辑全部四字段；预览每日进度为独立、可关闭的嵌套窗口。
    rows[1]['progress_history'].append(dict(id='previous-day', previous_percentage=0, percentage=90, content='前日具体进度', reason='', author_name='技术同事', created_at='2026-10-29T16:00:00+08:00'))
    table_row = page.locator('.el-table__body tr').filter(has_text='子任务B')
    report_before = len(added_reports)
    table_row.get_by_role('button', name='更多操作', exact=True).click()
    page.get_by_role('menuitem', name='加至工作报告', exact=True).click()
    report_dialog = page.get_by_role('dialog', name='加至工作报告', exact=True)
    expect(item(report_dialog, '订单号').locator('input')).to_have_value('DT-261030-002')
    expect(item(report_dialog, '项目名称').locator('input')).to_have_value('子任务B')
    assert len(added_reports) == report_before
    report_dialog.get_by_role('button', name='子任务B · 查看各天具体进度', exact=True).click()
    daily = page.get_by_role('dialog', name='技术任务每日进度', exact=True)
    expect(daily).to_contain_text('2026-10-29'); expect(daily).to_contain_text('2026-10-30'); expect(daily).to_contain_text('前日具体进度'); expect(daily).to_contain_text('发现遗漏用例')
    daily.get_by_role('button', name='关闭', exact=True).last.click()
    item(report_dialog, '订单号').locator('input').fill('DT-自定义报告编号')
    item(report_dialog, '项目名称').locator('input').fill('报告中编辑的任务名')
    item(report_dialog, '具体任务').locator('textarea').fill('报告中编辑的具体任务')
    item(report_dialog, '任务/项目类型').locator('.el-select').click(); page.get_by_role('option', name='开发任务', exact=True).click(); page.get_by_role('option', name='管理工作', exact=True).click(); page.keyboard.press('Escape')
    report_dialog.get_by_role('button', name='确认添加', exact=True).click()
    expect(report_dialog.locator('.el-form-item__error').first).to_be_visible()
    assert not added_reports
    item(report_dialog, '工作量').locator('input').fill('2.5')
    item(report_dialog, '单位').locator('.el-select').click(); page.get_by_role('option', name='项', exact=True).click()
    item(report_dialog, '耗时').locator('.el-select').click(); page.get_by_role('option', name='30分钟', exact=True).click()
    expect(report_dialog).to_contain_text('添加时间')
    report_dialog.get_by_role('button', name='确认添加', exact=True).click(); expect(report_dialog).not_to_be_visible()
    assert added_reports[-1]['task_name'] == '报告中编辑的任务名' and added_reports[-1]['display_metadata']['report_types'] == ['管理工作']
    assert added_reports[-1]['duration_minutes'] == 30 and added_reports[-1]['display_metadata']['quantity'] == '2.5'
    assert rows[1]['name'] == '子任务B'
    snapshot_html = html.replace("import Page from '/src/views/technology/TechnicalDevelopment.vue'", "import Page from '/src/views/schedule/components/ReportSnapshot.vue'").replace('h(Page)', 'h(Page,{report:' + json.dumps(dict(report_date='2026-10-30', items=added_reports)) + '})')
    context.route(BASE + '/technical-report-ui-check', lambda route: route.fulfill(content_type='text/html', body=snapshot_html))
    snapshot = context.new_page(); snapshot.on('pageerror', lambda error: errors.append(str(error))); snapshot.goto(BASE + '/technical-report-ui-check')
    snapshot.get_by_role('button', name='报告中编辑的任务名', exact=True).click()
    expect(snapshot.get_by_role('dialog', name='技术任务每日进度', exact=True)).to_contain_text('前日具体进度')
    snapshot.get_by_role('dialog', name='技术任务每日进度', exact=True).get_by_role('button', name='关闭', exact=True).last.click()
    snapshot.get_by_role('button', name='DT-自定义报告编号', exact=True).click()
    expect(snapshot.get_by_role('dialog', name='技术开发任务详情', exact=True)).to_contain_text('DT-261030-002')
    snapshot.close()
    # 新增与编辑共用字段；长表单只滚动正文，底栏固定。
    page.get_by_role('button', name='新增任务', exact=True).click()
    editor = page.get_by_role('dialog', name='新增技术开发任务', exact=True)
    expect(item(editor, '安排人')).to_be_visible()
    item(editor, '任务名称').locator('input').fill('新任务')
    item(editor, '安排人').locator('.el-select').click(); page.get_by_role('option', name='赵震锋', exact=True).click()
    item(editor, '执行人').locator('.el-select').click(); expect(page.get_by_role('option', name='赵震锋', exact=True)).to_have_count(0); page.get_by_role('option', name='技术同事', exact=True).click()
    item(editor, '备注').locator('textarea').fill('新增备注')
    footer = editor.locator('.el-dialog__footer')
    expect(footer).to_be_in_viewport()
    page.wait_for_timeout(350)
    original = editor.locator('.el-dialog').bounding_box()
    header = editor.locator('.el-dialog__header').bounding_box()
    page.mouse.move(header['x'] + 100, header['y'] + 25); page.mouse.down(); page.mouse.move(header['x'] + 180, header['y'] + 90, steps=8); page.mouse.up()
    page.wait_for_timeout(150)
    shifted = editor.locator('.el-dialog').bounding_box(); assert shifted['x'] != original['x'] or shifted['y'] != original['y']
    assert shifted['x'] >= 0 and shifted['y'] >= 0
    editor.get_by_role('button', name='保存', exact=True).click(); expect(editor).not_to_be_visible()
    page.get_by_role('button', name='新增任务', exact=True).click(); editor = page.get_by_role('dialog', name='新增技术开发任务', exact=True)
    page.wait_for_timeout(350)
    restored = editor.locator('.el-dialog').bounding_box(); assert abs(restored['x'] - original['x']) < 3 and abs(restored['y'] - original['y']) < 3
    editor.get_by_role('button', name='取消', exact=True).click()
    table_row = page.locator('.el-table__body tr').filter(has_text='三级任务C')
    table_row.get_by_role('button', name='更多操作', exact=True).click()
    page.get_by_role('menuitem', name='编辑', exact=True).click(); editor = page.get_by_role('dialog', name='编辑技术开发任务', exact=True)
    expect(item(editor, '任务名称').locator('input')).to_have_value('三级任务C')
    field_search = editor.locator('.project-field-search input')
    field_search.fill('反馈后'); page.locator('.project-field-search-popper:visible').get_by_text('反馈后调整', exact=True).click()
    item(editor, '反馈后调整').locator('textarea').fill('按反馈调整三级任务')
    expect(editor.locator('.el-dialog__footer')).to_be_in_viewport()
    editor.get_by_role('button', name='保存', exact=True).click(); expect(editor).not_to_be_visible()
    table_row = page.locator('.el-table__body tr').filter(has_text='三级任务C')
    table_row.get_by_role('button', name='DT-261030-003', exact=True).click()
    popover = page.locator('.el-popover:visible')
    expect(popover).to_contain_text('按反馈调整三级任务')
    assert 'el-popover' in popover.get_attribute('class')
    page.get_by_role('textbox', name='搜索技术开发任务').fill('三级 任务')
    page.wait_for_timeout(450)
    expect(page.locator('.el-table__body')).to_contain_text('母任务A')
    expect(page.locator('.el-table__body')).not_to_contain_text('独立任务D')
    page.get_by_role('textbox', name='搜索技术开发任务').fill('')
    expect(page.locator('.el-table__body')).to_contain_text('独立任务D')
    page.set_viewport_size(dict(width=640, height=740))
    page.get_by_role('button', name='新增任务', exact=True).click(); editor = page.get_by_role('dialog', name='新增技术开发任务', exact=True)
    expect(editor.locator('.el-dialog__footer')).to_be_in_viewport()
    bounds = editor.locator('.el-dialog').bounding_box(); assert bounds['width'] <= 608
    assert not errors, errors
    print(json.dumps(dict(three_levels=True, task_numbers=True, report_preview_edit_confirm=True, report_links_and_daily_history=True, drag_and_restore=True, cycle_rejected=True, rollback_reason_and_history=True, independent_feedback=True, shared_form=True, field_search=True, fixed_footer=True, draggable_reset=True, responsive=True, details_popover=True, errors=errors)))
    browser.close()
