"""真实状态汇报组件浏览器回归；拦截全部业务接口，不写业务库。"""
import json
import re
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE + '/src/components/annotation/AnnotationWorkStatusDialog.vue').read().decode()
    def dependency(name):
        return json.dumps(re.search(r'from ["\']([^"\']*/' + name + r'\.js[^"\']*)', compiled).group(1))
    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {createApp,h,ref} from VUE;import {createRouter,createWebHistory} from ROUTER;
    import Status from '/src/components/annotation/AnnotationWorkStatusDialog.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
    const visible=ref(true);const router=createRouter({history:createWebHistory(),routes:[{path:'/annotation-operations-test',component:{render:()=>null}},{path:'/workbench',name:'WorkDashboard',component:{render:()=>null}}]});
    const app=createApp({render:()=>h(Status,{modelValue:visible.value,request:{mode:new URLSearchParams(location.search).get('mode')||'report',projectId:'p1'},'onUpdate:modelValue':value=>visible.value=value})});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(router);app.mount('#app');</script>'''.replace('from VUE','from '+dependency('vue')).replace('from ROUTER','from '+dependency('vue-router'))
    projects = [dict(id=f'p{i}',orderNo=f'AP-TEST-{i}',projectName=f'标注测试项目{i}',arrangement_status='in_progress',revision=0,remaining_time='1_2h',submissions=[],entered_at='2026-11-01T07:00:00+08:00',cumulative_minutes=0) for i in [1,2]]
    items, reports, errors = [], [], []
    def api(route):
        path = urlparse(route.request.url).path
        body = route.request.post_data_json if route.request.method in ['POST','PUT'] else None
        if path == '/api/project-arrangements/annotation-status':
            result = dict(ready=True,work_date='2026-11-01',items=[projects[0]],available_slots=['end_shift'],current_slot='end_shift')
        elif path == '/api/project-arrangements/annotation-operations' and body:
            created=[]
            for group in body['projects']:
                project=next((row for row in projects if row['id']==group['project_id']),dict(id=group['project_id'],orderNo='OTHER' if group['project_id'] else '',projectName='其他项目' if group['project_id'] else ''))
                for operation in group['operations']:
                    row=dict(id=f'op{len(items)+1}',project_id=project['id'],project_type='非项目工作' if body.get('project_type')=='非项目任务' else body.get('project_type','标注项目'),order_no=project['orderNo'],project_name=project['projectName'],content=operation['content'],estimated_minutes=operation['estimated_minutes'],actual_minutes=0,quantity='',unit='',stage=body['stage'],revision=1,report_added=False)
                    items.append(row);created.append(row)
            result={'items':created}
        elif path == '/api/project-arrangements/annotation-operations':
            result=dict(work_date='2026-11-01',projects=projects,items=items)
        elif path.endswith('/annotation-operations/import-translation'):
            added=0
            if not any(row.get('project_type')=='笔译项目' for row in items):
                items.append(dict(id='translation-task',project_id='tp1',project_type='笔译项目',order_no='TP-TEST-001',project_name='安排给本人的笔译',content='核对笔译稿件',estimated_minutes=0,actual_minutes=0,quantity='',unit='',stage=body['stage'],revision=1,report_added=False));added=1
            result=dict(items=items,added=added,matched=1)
        elif path.endswith('/project-search'):
            params=parse_qs(urlparse(route.request.url).query)
            kind=params['project_type'][0]
            if kind=='口译项目':
                assert params.get('task_scope')==['true'] and params.get('period')==['all']
            else:
                assert 'task_scope' not in params
            result=dict(items=[dict(id='other-project',project_name=kind+'测试',order_no='OTHER',project_type=kind)],total=1)
        elif '/annotation-operations/' in path:
            key=path.split('/')[4];row=next(row for row in items if row['id']==key)
            if path.endswith('/report'):
                if not row['report_added']:reports.append(dict(row));row['report_added']=True
            else:
                if row['stage']!='performed' and body['stage']=='performed':body['actual_minutes']=body['estimated_minutes']
                row.update(body)
            row['revision']+=1;result=row
        else:result={}
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    def select(combo, label):
        combo.click();combo.fill(label)
        list_id=combo.get_attribute('aria-controls')
        option=page.locator(f'[id="{list_id}"]').get_by_role('option',name=label,exact=True)
        expect(option).to_be_visible();option.click(force=True)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport=dict(width=1440,height=1000),service_workers='block')
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/annotation-operations-test*',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(15000)
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/annotation-operations-test?mode=arrangement')
        arrangement=page.locator('.annotation-work-status-dialog:visible')
        expect(arrangement.get_by_role('button',name='保存今日安排',exact=True)).to_be_visible()
        expect(arrangement.locator('.annotation-operations')).to_have_count(0)
        expect(arrangement.get_by_role('button',name='编辑工作报告',exact=True)).to_have_count(0)
        expect(arrangement.locator('.el-dialog__header')).to_contain_text('今日安排')
        page.goto(BASE+'/annotation-operations-test')
        parent=page.locator('.annotation-work-status-dialog:visible')
        expect(parent.locator('.el-dialog__header')).to_contain_text('状态汇报')
        expect(parent).to_contain_text('当前空闲状态')
        expect(parent.get_by_role('button',name='提交本项目汇报',exact=True)).to_have_count(0)
        expect(parent.locator('.status-project-card')).to_have_count(1)
        expect(parent.locator('.status-project-card')).not_to_contain_text('AP-TEST')
        expect(parent.get_by_role('button',name='提交全部未汇报项目',exact=True)).to_have_count(0)
        expect(parent.locator('.operation-group').nth(1)).to_contain_text('进行中任务')
        picker=parent.locator('.operation-picker')
        picker.locator('.el-checkbox').nth(0).click();picker.locator('.el-checkbox').nth(1).click()
        picker.get_by_role('button',name='填写具体操作',exact=True).click()
        editor=page.locator('.annotation-operation-editor:visible')
        editor.get_by_role('button',name='增加具体操作',exact=True).first.click()
        # 首错定位不能关闭弹窗，底部保存按钮始终可见。
        editor.get_by_role('button',name='保存操作',exact=True).click()
        expect(editor.locator('.is-error').first).to_be_visible()
        for index, row in enumerate(editor.locator('.operation-edit-row').all()):
            row.locator('textarea').fill(f'样本具体操作{index+1}')
            select(row.get_by_role('combobox'),'30分钟')
        # 长表单只滚动正文；固定底部仍在视口内。
        editor.locator('.el-dialog__body').evaluate('(node)=>node.scrollTop=node.scrollHeight')
        expect(editor.get_by_role('button',name='保存操作',exact=True)).to_be_in_viewport()
        page.wait_for_function("() => !document.querySelector('[class*=dialog-fade-enter-]')")
        before=editor.bounding_box();header=editor.locator('.el-dialog__header').bounding_box()
        x,y=header['x']+230,header['y']+15
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+50,y+25,steps=8);page.mouse.up()
        after=editor.bounding_box();assert abs(after['x']-before['x'])+abs(after['y']-before['y'])>20
        page.mouse.move(x+50,y+25);page.mouse.down();page.mouse.move(-1800,-1800,steps=8);page.mouse.up()
        bounded=editor.bounding_box();assert bounded['x']>=0 and bounded['y']>=0
        editor.get_by_role('button',name='保存操作',exact=True).click();expect(editor).not_to_be_visible()
        expect(parent.locator('.operation-card')).to_have_count(3)
        assert len(items)==3
        # 待进行任务复用相同的多项目、多操作录入流程。
        pending=parent.locator('.operation-group').nth(2)
        pending.get_by_role('button',name='标注项目',exact=True).click()
        pending.locator('.el-checkbox').first.click()
        pending.get_by_role('button',name='填写具体操作',exact=True).click()
        expect(editor).to_be_visible()
        editor.locator('textarea').fill('待进行操作')
        select(editor.locator('.operation-edit-row').get_by_role('combobox'),'20分钟')
        editor.get_by_role('button',name='保存操作',exact=True).click()
        expect(editor).not_to_be_visible()
        expect(pending.locator('.operation-card')).to_have_count(1)
        # 两列和三列布局真实改变分区位置。
        toolbar=parent.locator('.operation-layout-toolbar')
        toolbar.get_by_text('两列',exact=True).click()
        boxes=[row.bounding_box() for row in parent.locator('.operation-group').all()]
        assert abs(boxes[0]['y']-boxes[1]['y'])<3 and boxes[2]['y']>boxes[0]['y']+30
        toolbar.get_by_text('三列',exact=True).click()
        boxes=[row.bounding_box() for row in parent.locator('.operation-group').all()]
        assert max(box['y'] for box in boxes)-min(box['y'] for box in boxes)<3
        assert boxes[0]['x']<boxes[1]['x']<boxes[2]['x']
        in_progress=parent.locator('.operation-group').nth(1)
        target=in_progress.locator('.operation-group__header')
        target.scroll_into_view_if_needed()
        pending.locator('.operation-card').first.drag_to(target)
        expect(pending.locator('.operation-card')).to_have_count(0)
        expect(in_progress.locator('.operation-card')).to_have_count(4)
        moved=next(row for row in items if row['content']=='待进行操作')
        assert moved['stage']=='in_progress' and moved['estimated_minutes']==20 and moved['actual_minutes']==0
        # 拖动完成后默认复制预计用时。
        target=parent.locator('.operation-group').first.locator('.operation-group__header')
        target.scroll_into_view_if_needed()
        parent.locator('.operation-card').first.drag_to(target)
        performed=parent.locator('.operation-group').first
        expect(performed.locator('.operation-card')).to_have_count(1)
        expect(performed).to_contain_text('今日实际花费时间：30分钟')
        performed.get_by_role('button',name='加至工作报告',exact=True).click()
        expect(editor).to_be_visible()
        page.wait_for_function("() => !document.querySelector('[class*=dialog-fade-enter-]')")
        initial=editor.bounding_box();header=editor.locator('.el-dialog__header').bounding_box()
        x,y=header['x']+230,header['y']+15
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+45,y+25,steps=8);page.mouse.up()
        editor.get_by_role('button',name='关闭窗口',exact=True).click();expect(editor).not_to_be_visible()
        expect(parent).to_be_visible()
        performed.get_by_role('button',name='加至工作报告',exact=True).click()
        page.wait_for_function("() => !document.querySelector('[class*=dialog-fade-enter-]')")
        reset=editor.bounding_box();assert abs(initial['x']-reset['x'])<3 and abs(initial['y']-reset['y'])<3
        editor.locator('.el-dialog__body').evaluate('(node)=>node.scrollTop=0')
        select(editor.locator('.el-form-item').filter(has=page.locator('label',has_text='今日实际花费时间')).get_by_role('combobox'),'20分钟')
        editor.get_by_placeholder('填写非负数字工作量').fill('2.5')
        select(editor.locator('.el-form-item').filter(has=page.locator('label',has_text=re.compile('^单位$'))).get_by_role('combobox'),'人')
        editor.get_by_role('button',name='保存并加至工作报告',exact=True).click()
        expect(performed.get_by_role('button',name='已加入工作报告',exact=True)).to_be_disabled()
        assert len(reports)==1 and reports[0]['actual_minutes']==20 and reports[0]['unit']=='人'
        # 两个任务区各有五类入口；笔译直接加入，重复点击及另一入口点击均不重复。
        for group in [in_progress,pending]:
            for kind in ['标注项目','笔译项目','口译项目','招聘项目','非项目任务']:
                expect(group.get_by_role('button',name=kind,exact=True)).to_have_count(1)
        before_count=len(items)
        in_progress.get_by_role('button',name='笔译项目',exact=True).click()
        expect(in_progress).to_contain_text('核对笔译稿件')
        in_progress.get_by_role('button',name='笔译项目',exact=True).click()
        pending.get_by_role('button',name='笔译项目',exact=True).click()
        assert len(items)==before_count+1
        expect(editor).not_to_be_visible()
        for kind in ['非项目任务','口译项目','招聘项目']:
            pending.get_by_role('button',name=kind,exact=True).click()
            if kind!='非项目任务':
                chooser=page.locator('.el-dialog:visible').filter(has=page.locator('.project-picker-search'))
                chooser.get_by_role('button',name='选定',exact=True).click()
            expect(editor).to_be_visible()
            editor.locator('textarea').fill(kind+'操作')
            select(editor.locator('.operation-edit-row').get_by_role('combobox'),'20分钟')
            editor.get_by_role('button',name='保存操作',exact=True).click()
            expect(editor).not_to_be_visible()
            expect(pending).to_contain_text(kind+'操作')
        # 刷新仍保留任务及加入状态，窄屏窗口和底部按钮不溢出。
        page.reload();expect(page.get_by_role('button',name='已加入工作报告',exact=True)).to_be_visible()
        parent=page.locator('.annotation-work-status-dialog:visible')
        expect(parent.locator('.operation-groups')).to_have_attribute('data-columns','3')
        expect(parent.locator('.annotation-operations .el-loading-mask')).not_to_be_visible()
        parent.locator('.el-dialog__body').evaluate("node=>{const section=node.querySelector('.annotation-operations');node.scrollTop=section.offsetTop-node.offsetTop}")
        page.screenshot(path='scratch/annotation-daily-operations.png')
        page.set_viewport_size(dict(width=600,height=800))
        rect=parent.bounding_box();assert rect['width']<=569 and rect['x']>=0
        boxes=[row.bounding_box() for row in parent.locator('.operation-group').all()]
        assert abs(boxes[0]['x']-boxes[1]['x'])<3 and boxes[1]['y']>boxes[0]['y']
        parent.locator('.el-dialog__body').evaluate('(node)=>node.scrollTop=node.scrollHeight')
        expect(parent.get_by_role('button',name='编辑工作报告',exact=True)).to_be_in_viewport()
        parent.get_by_role('button',name='编辑工作报告',exact=True).click()
        expect(page).to_have_url(re.compile(r'/workbench\?section=daily-report$'))
        expect(parent).not_to_be_visible()
        assert not errors, errors
        browser.close()
    print('annotation operations: multi-project/multiple operations, validation, drag dialog, drag complete, report, persistence, mobile and report navigation PASS')


if __name__=='__main__':
    run()
