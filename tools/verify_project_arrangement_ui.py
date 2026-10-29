"""隔离接口验收项目安排和今日任务，不连接或写入业务数据库。需本地 Vite 已启动。"""
import json
from copy import deepcopy
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'
ROOT = Path(__file__).resolve().parents[1]


def run():
    compiled = urlopen(BASE + '/src/components/common/AppForm.vue').read().decode()
    vue_url = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
    people = [dict(id=f'person-{n}', name=f'测试人员{n}', username=f'qa{n}', active=True,
                   departments=[dict(id='project', name='项目部')]) for n in range(1, 4)]
    departments = [dict(id='project', name='项目部'), dict(id='hr', name='HR部'), dict(id='layout', name='排版')]
    for index, department in enumerate(departments):
        if index:
            people.append(dict(id=f'person-{index+3}', name=f'部门人员{index}', username=f'dept{index}', active=True, departments=[department]))
    tasks, calls, errors = [], [], []
    events=[]
    instruction={"common_instruction":"","instruction_revision":0}
    def detail():
        return dict(**instruction,ready=True,tasks=tasks,revision=len(events),history=list(reversed(events)),history_total=len(events),updated_by_name='测试安排人',updated_at='2026-10-25T15:00:00+08:00')
    def record(operation,before):
        events.append(dict(id=f'event-{len(events)+1}',revision=len(events)+1,operation=operation,actor_name='测试安排人',created_at='2026-10-25T15:00:00+08:00',before_snapshot={'tasks':before},after_snapshot={'tasks':deepcopy(tasks)}))
    storage_ready = False
    service_unavailable = False
    html = f'''<!doctype html><html><head><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"></head><body><div id="app"></div><script type="module">
      import {{createApp,ref,h}} from {json.dumps(vue_url)};
      import Personnel from '/src/components/common/ArrangementPersonnel.vue';
      import Projects from '/src/views/project/translation/components/ProjectArrangementTable.vue';
      import TodayTasks from '/src/views/schedule/components/TodayTasks.vue';
      import AppForm from '/src/components/common/AppForm.vue';
      import Dialog from '/src/components/common/DraggableFormDialog.vue';
      const app=createApp({{setup(){{const selected=ref([]),projects=[{{id:'project-1',orderNo:'TP-TEST-001',projectName:'隔离测试项目',clientShortName:'测试客户',projectStatus:'进行中',languagePair:'中英'}}];
      return()=>h('div',{{style:'padding:16px'}},[h('div',{{style:'display:grid;grid-template-columns:1fr 3fr;gap:16px'}},[h(Personnel,{{modelValue:selected.value,'onUpdate:modelValue':value=>selected.value=value}}),h(Projects,{{projects,people:selected.value,canWrite:true}})]),h(TodayTasks,{{day:'2026-10-25'}})])}}}});
      app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.mount('#app');
    </script></body></html>'''

    def api(route):
        request = route.request
        parsed = urlparse(request.url)
        path, query = parsed.path, parse_qs(parsed.query)
        body = request.post_data_json if request.method in ('POST', 'PATCH', 'PUT') else None
        calls.append((request.method, path, body))
        if path == '/api/departments/organization':
            result = dict(people=people, items=list(reversed(departments)))
        elif path.endswith('/directory'):
            if service_unavailable:
                route.fulfill(status=404, content_type='application/json', body='{"detail":"Not Found"}')
                return
            result = dict(ready=storage_ready, people=people, departments=departments)
        elif path.endswith('/editor-context'):
            result = dict(task_history=[], work_categories={'项目工作': ['笔译项目']}, can_add_project_category=False, category_storage_ready=True)
        elif path.endswith('/detail'):
            result=detail()
        elif path.endswith('/instruction') and request.method=='PUT':
            before=deepcopy(tasks);instruction.update(common_instruction=body['content'],instruction_revision=instruction['instruction_revision']+1)
            record('instruction',before);result=detail()
        elif path.endswith('/order') and request.method=='PUT':
            before=deepcopy(tasks)
            ordered=[next(task for task in tasks if task['id']==task_id) for task_id in body['task_ids']]
            tasks[:]=ordered;record('reorder',before);result=detail()
        elif '/project/' in path and request.method == 'POST':
            before=deepcopy(tasks)
            if 'common_instruction' in body:instruction.update(common_instruction=body['common_instruction'],instruction_revision=instruction['instruction_revision']+1)
            for item in body['items']:
                person = next(p for p in people if p['id'] == item['assignee_id'])
                tasks.append(dict(id=f'task-{len(tasks)+1}', project_id='project-1', order_no='TP-TEST-001', project_name='隔离测试项目', assignee_name=person['name'],assigned_by_name='测试安排人',created_at='2026-10-25T15:00:00+08:00', estimated_minutes=0, actual_minutes=0, status='pending', revision=1, **item))
            record('assign',before)
            result = tasks
        elif request.method == 'PATCH':
            before=deepcopy(tasks)
            task = next(t for t in tasks if path.endswith('/'+t['id']))
            task.update(body); task['revision'] += 1; result = task
            record('edit',before)
        elif path.endswith('/complete'):
            task = next(t for t in tasks if '/'+t['id']+'/' in path)
            task.update(status='completed', actual_minutes=body['item']['duration_minutes'], revision=task['revision']+1)
            result = task
        elif path == '/api/project-arrangements':
            chain=[dict(id=t['id'],step=i+1,assignee_name=t['assignee_name'],status=t['status']) for i,t in enumerate(tasks)]
            result = dict(ready=True, items=[{**t,**instruction,'execution_sequence':chain} for t in tasks[:10]], total=len(tasks))
        else:
            result = []
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result, ensure_ascii=False))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 1000}, service_workers='block')
        context.set_default_timeout(10000)
        context.route(re.compile(r'^http://localhost:3000/api/'), api)
        context.route(BASE+'/arrangement-test', lambda route: route.fulfill(content_type='text/html', body=html))
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('requestfailed', lambda request: print('request failed', request.url, request.failure))
        page.goto(BASE+'/arrangement-test')
        page.wait_for_function("document.querySelector('.arrangement-personnel') !== null", timeout=15000)
        if errors:
            raise AssertionError(errors)
        roster = page.locator('.arrangement-personnel')
        expect(roster.locator('strong').first).to_have_text('部门人员')
        expect(roster.locator('.el-collapse-item__header')).to_have_text([re.compile('项目部（3）'), re.compile('HR部（1）'), re.compile('排版（1）')])
        roster.get_by_role('button',name='调整项目部部门顺序',exact=True).drag_to(roster.locator('.el-collapse-item__header').filter(has_text='排版（1）'))
        expect(roster.locator('.el-collapse-item__header')).to_have_text([re.compile('HR部（1）'),re.compile('排版（1）'),re.compile('项目部（3）')])
        project_group=roster.locator('.el-collapse-item').filter(has_text='项目部（3）')
        project_group.get_by_role('button',name='调整测试人员1人员顺序',exact=True).drag_to(project_group.locator('.person').filter(has_text='测试人员3'))
        expect(project_group.locator('.person label')).to_have_text(['测试人员2','测试人员3','测试人员1'])
        assert not any(method in ('POST','PUT','PATCH') for method,_,_ in calls)
        page.reload()
        expect(roster.locator('.el-collapse-item__header')).to_have_text([re.compile('HR部（1）'),re.compile('排版（1）'),re.compile('项目部（3）')])
        expect(project_group.locator('.person label')).to_have_text(['测试人员2','测试人员3','测试人员1'])
        roster.get_by_role('button',name='恢复默认顺序',exact=True).click()
        expect(roster.locator('.el-collapse-item__header')).to_have_text([re.compile('项目部（3）'),re.compile('HR部（1）'),re.compile('排版（1）')])
        expect(project_group.locator('.person label')).to_have_text(['测试人员1','测试人员2','测试人员3'])
        expect(roster.get_by_text('部门人员2', exact=True)).to_be_visible()
        expect(roster.get_by_text('任务保存尚未开通，需先初始化数据库；人员仍可查看与选择。')).to_be_visible()
        roster.get_by_role('button', name='全部收起', exact=True).click()
        expect(roster.get_by_text('测试人员1', exact=True)).not_to_be_visible()
        roster.get_by_role('button', name='全部展开', exact=True).click()
        roster.get_by_text('全体人员', exact=True).click()
        expect(roster.locator('.person')).to_have_count(5)
        roster.get_by_role('button',name='调整测试人员1人员顺序',exact=True).drag_to(roster.locator('.person').filter(has_text='测试人员3'))
        expect(roster.locator('.person label')).to_have_text(['测试人员2','测试人员3','测试人员1','部门人员1','部门人员2'])
        roster.get_by_role('button',name='恢复默认顺序',exact=True).click()
        roster.get_by_label('搜索安排人员', exact=True).fill('dept2')
        expect(roster.locator('.person')).to_have_count(1)
        expect(roster.get_by_text('部门人员2', exact=True)).to_be_visible()
        roster.get_by_label('搜索安排人员', exact=True).fill('')
        roster.get_by_role('radio', name='部门人员', exact=True).locator('..').click()
        page.locator('.person').filter(has_text='测试人员1').locator('label').click()
        page.locator('.person').filter(has_text='测试人员2').locator('label').click()
        storage_ready = True
        roster.get_by_role('button', name='刷新', exact=True).click()
        expect(roster.get_by_text('任务保存尚未开通，需先初始化数据库；人员仍可查看与选择。')).not_to_be_visible()
        page.get_by_role('button', name='安排', exact=True).click()
        fields = page.locator('.project-assignees > .assignment-line textarea')
        page.get_by_label('项目共同说明',exact=True).fill('统一使用客户术语表，回稿前检查文件')
        expect(fields).to_have_count(2)
        fields.nth(0).fill('核对术语')
        fields.nth(1).fill('检查排版')
        page.get_by_role('button', name='保存安排', exact=True).click()
        expect(page.locator('.assignment-line')).to_have_count(2)
        expect(page.locator('.assignment-line').first.locator('textarea')).to_have_value('核对术语')
        assert instruction['common_instruction']=='统一使用客户术语表，回稿前检查文件'
        page.get_by_label('项目共同说明',exact=True).fill('统一使用最新客户术语表，回稿前检查文件')
        page.get_by_role('button',name='保存共同说明',exact=True).click()
        expect(page.get_by_role('button',name='保存共同说明',exact=True)).to_be_disabled()
        assert events[-1]['operation']=='instruction'
        page.locator('.assignment-line').first.locator('textarea').fill('核对术语并校对')
        page.get_by_role('button', name='保存修改').first.click()
        expect(page.get_by_text('任务已更新，修改记录已保存', exact=True)).to_be_visible()
        assert tasks[0]['content']=='核对术语并校对',tasks
        plan=page.locator('.arrangement-plan-panel')
        plan.locator('.task-drag-handle').first.drag_to(plan.locator('.assignment-line').nth(1))
        expect(plan.locator('.assignment-line').first.locator('textarea')).to_have_value('检查排版')
        assert events[-1]['operation']=='reorder'
        plan.locator('.task-drag-handle').first.drag_to(plan.locator('.assignment-line').nth(1))
        expect(plan.locator('.assignment-line').first.locator('textarea')).to_have_value('核对术语并校对')
        plan.locator('.el-collapse-item__header').filter(has_text='安排与调整记录').click()
        expect(plan.get_by_text(re.compile('第.*版 · 调整执行顺序')).first).to_be_visible()
        # 未勾选人员通过真实 HTML5 drop 事件加入项目。
        target = page.locator('.arrangement-project')
        target.evaluate('''(element, people)=>{const transfer=new DataTransfer();transfer.setData('application/x-project-personnel',JSON.stringify(people));element.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}))}''', [people[2]])
        expect(page.locator('.assignment-line')).to_have_count(3)
        page.locator('.assignment-line').last.locator('textarea').fill('复核文件')
        page.get_by_role('button', name='保存安排', exact=True).click()
        expect(page.locator('.assignment-line')).to_have_count(3)
        page.locator('.today-header').get_by_role('button', name='刷新').click()
        expect(page.locator('.today-tasks .el-table__body-wrapper tbody tr')).to_have_count(3)
        expect(page.locator('.today-tasks .execution-sequence').first).to_contain_text('1. 测试人员1')
        expect(page.locator('.today-tasks .execution-sequence').first).to_contain_text('2. 测试人员2')
        page.locator('.today-tasks .common-instruction-preview').first.click()
        expect(page.locator('.task-common-instruction-popover:visible')).to_contain_text('统一使用最新客户术语表')
        page.locator('.today-header h3').click()
        state = page.locator('.today-tasks .el-table__body-wrapper tbody tr').first.locator('.el-select').last
        state.click(); page.get_by_role('option', name='已完成', exact=True).click()
        dialog = page.get_by_role('dialog')
        expect(dialog).to_be_visible()
        expect(dialog.get_by_label('第1行具体任务', exact=True)).to_have_value('核对术语并校对')
        page.get_by_role('button', name='保存报告并完成任务', exact=True).click()
        expect(dialog.locator('.el-form-item.is-error').first).to_be_visible()
        assert not any(path.endswith('/complete') for _, path, _ in calls)
        dialog.get_by_label('第1行工作量', exact=True).fill('2')
        dialog.get_by_label('第1行单位', exact=True).click(); page.get_by_role('option', name='份', exact=True).click()
        dialog.get_by_label('第1行耗时', exact=True).click(); page.get_by_role('option', name='30分钟', exact=True).click()
        # 标题可拖动；关闭重开会复位。
        content = page.locator('.el-dialog').first
        before = content.bounding_box()
        header = dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+250, header['y']+header['height']-10); page.mouse.down(); page.mouse.move(header['x']+290, header['y']+header['height']+30, steps=8); page.mouse.up()
        after = content.bounding_box()
        if abs(after['x']-before['x']) <= 10:
            print('drag diagnostics', before, after, errors, dialog.get_attribute('style'))
        assert abs(after['x']-before['x']) > 10
        dialog.get_by_role('button', name='关闭窗口', exact=True).click()
        page.set_viewport_size({'width': 1600, 'height': 1000})
        service_unavailable = True
        roster.get_by_role('button', name='刷新', exact=True).click()
        expect(roster.get_by_text('任务保存服务暂不可用，人员仍可查看与选择。')).to_be_visible()
        expect(roster.get_by_text('测试人员1', exact=True)).to_be_visible()
        expect(dialog).not_to_be_visible()
        state.click(); page.get_by_role('option', name='已完成', exact=True).click()
        expect(dialog).to_be_visible()
        reset = content.bounding_box()
        assert abs(reset['x']-before['x']) < 5
        dialog.get_by_label('第1行工作量', exact=True).fill('2')
        dialog.get_by_label('第1行单位', exact=True).click(); page.get_by_role('option', name='份', exact=True).click()
        dialog.get_by_label('第1行耗时', exact=True).click(); page.get_by_role('option', name='30分钟', exact=True).click()
        footer = dialog.locator('.el-dialog__footer').bounding_box()
        assert footer['y']+footer['height'] <= 1000
        page.get_by_role('button', name='保存报告并完成任务', exact=True).click()
        expect(dialog).not_to_be_visible()
        assert any(path.endswith('/complete') for _, path, _ in calls)
        expect(page.locator('.today-tasks').get_by_text('已完成', exact=True)).to_be_visible()
        assert not errors, errors
        screenshots = ROOT/'scratch'/'project-arrangement-ui'
        screenshots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshots/'desktop.png'), full_page=True)
        page.set_viewport_size({'width': 640, 'height': 720})
        state2 = page.locator('.today-tasks .el-table__body-wrapper tbody tr').nth(1).locator('.el-select').last
        state2.click(); page.get_by_role('option', name='已完成', exact=True).click()
        expect(dialog).to_be_visible()
        page.wait_for_function("!document.querySelector('[class*=fade-enter-active], [class*=fade-leave-active]')")
        small = content.bounding_box()
        assert small['width'] <= 624 and small['x'] >= 0 and small['y'] >= 0
        footer = dialog.locator('.el-dialog__footer').bounding_box()
        assert footer['y']+footer['height'] <= 720
        page.screenshot(path=str(screenshots/'small-dialog.png'))
        dialog.get_by_role('button', name='关闭窗口', exact=True).click()
        print(json.dumps({'passed': True, 'common_instruction_saved_edited_and_visible':True,'assigned_tasks': len(tasks), 'completed': sum(t['status']=='completed' for t in tasks), 'page_errors': errors}, ensure_ascii=False))
        context.close(); browser.close()


if __name__ == '__main__':
    run()
