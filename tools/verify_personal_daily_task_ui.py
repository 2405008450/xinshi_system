"""自主任务、报告选择项目、完整完成校验及历史日期快捷入口；仅使用隔离接口。"""
import json,re
from datetime import datetime,timezone,timedelta
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    projects={'笔译项目':{'id':'project-tp','project_type':'笔译项目','order_no':'TP-TEST-001','project_name':'笔译系统测试'},'口译项目':{'id':'project-ip','project_type':'口译项目','order_no':'IP-TEST-001','project_name':'口译系统测试'}}
    tasks=[];calls=[];errors=[]
    html=f'''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
      import {{createApp,h,ref}} from {json.dumps(vue)};
      import Today from '/src/views/schedule/components/TodayTasks.vue';import Editor from '/src/views/schedule/components/DailyReportEditor.vue';
      import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
      const app=createApp({{setup(){{const report=ref(false),rows=[{{source_type:'manual',task_type:'非项目工作',task_name:'',progress_content:'',duration_minutes:0,display_metadata:{{report_types:[]}}}}];return()=>h('div',[h(Today,{{day:'2026-10-25'}}),h('button',{{onClick:()=>report.value=true}},'填写工作报告'),report.value?h('div',{{id:'report-area'}},[h(Editor,{{rows,editable:true}})]):null])}}}});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.mount('#app');</script>'''
    def api(route):
        request=route.request;path=urlparse(request.url).path;query=parse_qs(urlparse(request.url).query)
        body=request.post_data_json if request.method in ('POST','PATCH','PUT') else None
        calls.append((request.method,path,query,body))
        if path=='/api/daily-reports/editor-context':result={'task_history':[],'work_categories':{'项目工作':['笔译项目','口译项目']},'can_add_project_category':False,'category_storage_ready':True}
        elif path=='/api/project-arrangements/project-search':result={'items':[projects[query['project_type'][0]]],'total':1}
        elif path=='/api/project-arrangements/personal-batch' and request.method=='POST':
            created=[]
            for item in body['items']:
                task={'id':f'personal-{len(tasks)+1}','source':'personal','assignee_name':'测试人员','order_no':item['display_metadata']['order_no'],'project_name':item['task_name'],'content':item['progress_content'],'work_date':body['work_date'],'estimated_minutes':item['duration_minutes'],'actual_minutes':0,'status':'pending','revision':1,'execution_sequence':[],'report_row':item};tasks.append(task);created.append(task)
            result={'items':created}
        elif path.endswith('/personal/personal-1/complete'):
            task=tasks[0];task.update(status='completed',actual_minutes=body['item']['duration_minutes'],revision=2);result=task
        elif path=='/api/project-arrangements':result={'ready':True,'personal_ready':True,'items':tasks,'total':len(tasks)}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1700,'height':1050},service_workers='block',timezone_id='Asia/Shanghai')
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/personal-task-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.clock.set_fixed_time(datetime(2026,10,25,15,tzinfo=timezone(timedelta(hours=8))))
        page.goto(BASE+'/personal-task-test')
        page.get_by_role('button',name='自行填写任务',exact=True).click()
        personal=page.locator('.task-report-dialog.el-dialog').filter(has_text='自行填写今日任务')
        expect(personal).to_be_visible()
        initial=personal.bounding_box()
        header=personal.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+20,header['y']+header['height']-3)
        page.mouse.down();page.mouse.move(header['x']+60,header['y']+header['height']+35,steps=8);page.mouse.up()
        moved=personal.bounding_box()
        assert abs(moved['x']-initial['x'])>10 or abs(moved['y']-initial['y'])>10
        page.mouse.move(moved['x']+20,moved['y']+header['height']-3)
        page.mouse.down();page.mouse.move(-1500,-1500,steps=10);page.mouse.up()
        bounded=personal.bounding_box()
        assert bounded['x']>=0 and bounded['y']>=0
        personal.get_by_role('button',name='关闭窗口',exact=True).click()
        expect(personal).not_to_be_visible()
        page.get_by_role('button',name='自行填写任务',exact=True).click()
        expect(personal).to_be_visible()
        reset=personal.bounding_box()
        assert abs(reset['x']-initial['x'])<3 and abs(reset['y']-initial['y'])<3
        def choose_type(container,name,index=0):
            container.locator('.el-cascader').nth(index).click()
            page.locator('.el-cascader-node__label:visible').get_by_text('项目工作',exact=True).click()
            page.locator('.el-cascader-node:visible').filter(has_text=name).locator('.el-checkbox').click()
        choose_type(personal,'笔译项目')
        picker=page.locator('.report-project-picker.el-dialog');expect(picker).to_be_visible()
        picker.get_by_role('button',name='选定',exact=True).click();expect(picker).not_to_be_visible()
        assert 'TP-TEST-001' in personal.locator('input').evaluate_all('(inputs)=>inputs.map(input=>input.value)')
        personal.get_by_label('第1行具体任务',exact=True).fill('自行处理系统测试项目')
        personal.get_by_role('button',name='＋ 新增一行',exact=True).click()
        personal.get_by_label('新增行数',exact=True).fill('2')
        personal.get_by_role('button',name='新增多行',exact=True).click()
        expect(personal.locator('.report-grid tbody tr')).to_have_count(4)
        for index in range(1,4):
            choose_type(personal,'笔译项目',index)
            expect(picker).to_be_visible();picker.get_by_role('button',name='选定',exact=True).click()
            personal.get_by_label(f'第{index+1}行具体任务',exact=True).fill(f'多行测试任务{index+1}')
        personal.get_by_role('button',name='保存任务',exact=True).click()
        expect(personal).not_to_be_visible()
        assert len(tasks)==4
        # 已有任务时也保持新增行入口，不受安排或自主任务数量影响。
        page.get_by_role('button',name='自行填写任务',exact=True).click()
        expect(personal.get_by_role('button',name='新增多行',exact=True)).to_be_visible()
        personal.get_by_role('button',name='取消',exact=True).click()
        expect(personal).not_to_be_visible()
        assert tasks[0]['report_row']['display_metadata']['project_id']=='project-tp'
        row=page.locator('.today-tasks .el-table__body-wrapper tbody tr').first
        row.locator('.el-select').last.click();page.get_by_role('option',name='已完成',exact=True).click()
        completion=page.locator('.task-report-dialog.el-dialog').filter(has_text='加入工作报告')
        expect(completion).to_be_visible()
        completion.get_by_role('button',name='保存报告并完成任务',exact=True).click()
        assert not any(path.endswith('/complete') for _,path,_,_ in calls)
        completion.get_by_label('第1行工作量',exact=True).fill('1')
        completion.get_by_label('第1行单位',exact=True).click();page.get_by_role('option',name='份',exact=True).click()
        completion.get_by_label('第1行耗时',exact=True).click();page.get_by_role('option',name='30分钟',exact=True).click()
        completion.get_by_role('button',name='保存报告并完成任务',exact=True).click();expect(completion).not_to_be_visible()
        page.get_by_role('button',name='昨日安排',exact=True).click()
        expect(page.locator('.task-hint')).to_contain_text('历史任务')
        page.get_by_role('button',name='上周安排',exact=True).click()
        page.get_by_role('button',name='填写工作报告',exact=True).click()
        report=page.locator('#report-area');choose_type(report,'口译项目')
        expect(picker).to_be_visible();picker.get_by_role('button',name='选定',exact=True).click()
        values=report.locator('input').evaluate_all('(inputs)=>inputs.map(input=>input.value)')
        assert 'IP-TEST-001' in values and '口译系统测试' in values
        expect(report.get_by_label('第1行具体任务',exact=True)).to_have_value('')
        assert any(query.get('date_from')==['2026-10-24'] and query.get('date_to')==['2026-10-24'] for _,path,query,_ in calls if path=='/api/project-arrangements')
        assert any(query.get('date_from')==['2026-10-12'] and query.get('date_to')==['2026-10-18'] for _,path,query,_ in calls if path=='/api/project-arrangements')
        assert not errors,errors
        print(json.dumps({'passed':True,'self_task_without_assignment':True,'add_one_and_multiple_rows':True,'add_with_existing_tasks':True,'translation_and_interpretation_picker':True,'full_report_required':True,'archive_shortcuts':True,'page_errors':errors}))
        context.close();browser.close()


if __name__=='__main__':run()
