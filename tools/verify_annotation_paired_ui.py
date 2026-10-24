"""本机浏览器验收；API全部拦截为内存模拟，禁止连接业务数据库。"""
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
PID,UID,LID=[str(uuid4()) for _ in range(3)]
NOW='2026-10-24T09:00:00+08:00'
BASE='http://127.0.0.1:12431'


def run():
    if socket.gethostname().upper()!='PC' or ROOT!=Path(r'E:\xinshi_system'):
        raise SystemExit('仅允许在PC项目目录运行隔离验收')
    out=ROOT/'.tmp/paired-ui';out.mkdir(parents=True,exist_ok=True)
    log=(out/'vite.log').open('w',encoding='utf-8')
    process=subprocess.Popen(['node','node_modules/vite/bin/vite.js','preview','--outDir','../.tmp/paired-build','--host','127.0.0.1','--port','12431','--strictPort'],cwd=ROOT/'frontend',stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    project=dict(id=PID,order_no='AP-261024-QA',project_name='双人对话采标隔离验收',project_types=['paired_collection_annotation'],project_status='project_in_progress',priority='medium',order_level=0,child_count=0,child_status_counts={},language_items=[dict(id=str(uuid4()),source_language_id=LID,source_language_label='温州话',display='温州话',sequence_no=1)],language_items_display='温州话',price_items=[],assignees=[],role_assignments=[],custom_values={},created_at=NOW,updated_at=NOW,client_short_name='验收客户')
    people=[dict(id=str(uuid4()),full_name='采集员'+str(index+1),resource_code='QA'+str(index+1),region='温州',language_skills=[dict(id=str(uuid4()),language_id=LID,label='温州话',accent='市区口音')]) for index in range(3)]
    contacts=[dict(id=str(uuid4()),project_id=PID,person_id=person['id'],willingness='available',data={'sources':['企微好友'],'availability':[],'channel_states':[],'quote':'待协商'},revision=1,created_at=NOW,person=person) for person in people]
    ws=dict(project_id=PID,allow_multiple_groups=False,archived=False,notes={},revision=1,created_at=NOW)
    groups=[];tasks=[];records=[];requests=[];errors=[]
    def api(route):
        req=route.request;url=urlparse(req.url)
        if not url.path.startswith('/api/'):
            route.continue_();return
        path=url.path.removeprefix('/api');query=parse_qs(url.query);result=[]
        payload=req.post_data_json if req.method in ['POST','PUT'] and req.post_data else {}
        base=f'/annotation-ops/projects/{PID}/paired-workspace'
        requests.append((req.method,path))
        if path=='/auth/session':result=dict(id=UID,username='qa',full_name='验收经理',roles=['admin'],permissions=['*'])
        elif path in ['/projects/annotation/page','/projects/annotation/']:result=dict(items=[project],total=1) if path.endswith('page') else [project]
        elif path==f'/projects/annotation/{PID}':result=project
        elif path=='/projects/languages':result=[dict(id=LID,label='温州话')]
        elif path.rstrip('/')=='/users' or 'role-candidates' in path:result=[dict(id=UID,username='qa',full_name='验收经理')]
        elif path.endswith('/language-reserves/lookup'):result=dict(items=[])
        elif path.startswith(base):
            suffix=path[len(base):]
            if suffix in ['', '/initialize']:
                if req.method=='PUT':ws.update(payload);ws['revision']+=1
                result=ws
            elif suffix=='/people':result=people
            elif suffix=='/candidates':result=dict(items=[{**person,'joined':True,'company_accounts':['HR1企微'],'small_groups':'温州群','added_sources':[],'wechat':'******','phone':'******','email':'******'} for person in people],total=3,daily_new=[])
            elif suffix.startswith('/list/'):
                kind=suffix.rsplit('/',1)[-1];rows=contacts if kind=='contacts' else groups if kind=='groups' else [row for row in tasks if row['stage']==kind];result=dict(items=rows,total=len(rows))
            elif suffix.startswith('/contacts/') and req.method=='PUT':
                row=next(row for row in contacts if row['id']==suffix.split('/')[2]);row.update(payload);row['revision']+=1;result=row
            elif suffix=='/groups' and req.method=='POST':
                row=dict(id=str(uuid4()),project_id=PID,revision=1,created_at=NOW,**payload,members=dict(id=str(uuid4()),version=1,person1_id=payload['person1_id'],person2_id=payload['person2_id']))
                groups.append(row)
                tasks.append(dict(id=str(uuid4()),project_id=PID,group_id=row['id'],members_id=row['members']['id'],request_key=str(uuid4()),name=row['name']+' · 首批采集',stage='collection',status='pending',person_ids=[payload['person1_id'],payload['person2_id']],data={},revision=1,created_at=NOW))
                result=row
            elif suffix=='/transfer':
                for source_id in payload['task_ids']:
                    source=next(row for row in tasks if row['id']==source_id)
                    tasks.append({**source,'id':str(uuid4()),'name':source['name']+' · 标注','source_task_id':source_id,'person_ids':payload['person_ids'],'stage':'annotation'})
                result=[row for row in tasks if row['stage']=='annotation']
            elif suffix.endswith('/records'):
                task_id=suffix.split('/')[2]
                if req.method=='POST':
                    row=dict(id=str(uuid4()),task_id=task_id,position=len(records)+1,revision=1,created_at=NOW,updated_at=NOW,**payload);records.append(row);result=row
                else:result=[row for row in records if row['task_id']==task_id]
            elif suffix=='/history':result=dict(items=[],total=0)
            elif '/languages/' in suffix:result=dict(accent=payload['accent'])
        elif path.endswith('/unread-count'):result=dict(count=0)
        elif path.endswith('/page'):result=dict(items=[],total=0)
        elif path=='/resource-requests/source-statuses':result={}
        route.fulfill(json=result)
    try:
        for _ in range(100):
            try:
                with urlopen(BASE,timeout=1):break
            except Exception:time.sleep(.15)
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge')
            context=browser.new_context(viewport=dict(width=1500,height=960))
            context.route('**/api/**',api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_id','qa')")
            page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(BASE+'/annotation-details')
            try:
                expect(page.locator('.annotation-table')).to_be_visible(timeout=15000)
            except Exception:
                page.screenshot(path=str(out/'failure.png'))
                print('页面错误',errors,'请求',requests,'页面内容',page.locator('body').inner_text()[:3000])
                raise
            page.locator('.annotation-table .el-table__body-wrapper tr').first.get_by_role('button').last.click()
            page.get_by_text('双人采标管理',exact=True).click()
            window=page.locator('.paired-workspace:visible')
            expect(window.get_by_text('采集员1',exact=True)).to_be_visible()
            # 详情必须为Popover；编辑使用统一长表单。
            window.get_by_role('button',name='查看详情',exact=True).nth(1).click()
            expect(page.locator('.business-detail-popover:visible')).to_be_visible()
            window.locator('.workspace-heading').click()
            window.screenshot(path=str(out/'before-edit.png'))
            window.get_by_role('button',name='编辑',exact=True).first.click()
            editor=page.locator('.paired-form-editor:visible')
            expect(editor.get_by_text('可工作时间',exact=True)).to_be_visible()
            editor.get_by_role('button',name='增加时间安排').click()
            editor.locator('.el-dialog__body').evaluate('(el)=>el.scrollTop=el.scrollHeight')
            expect(editor.get_by_role('button',name='保存',exact=True)).to_be_in_viewport()
            editor.get_by_role('button',name='保存',exact=True).click()
            expect(page.locator('.el-dialog:visible')).to_have_count(1)
            # 实际拖拽、边界及重新打开复位。
            expect(page.locator('.dialog-fade-enter-active')).to_have_count(0)
            original=window.bounding_box()
            handle=window.locator('.app-window-drag-strip');box=handle.bounding_box()
            page.mouse.move(box['x']+80,box['y']+12);page.mouse.down();page.mouse.move(box['x']+140,box['y']+72,steps=8);page.mouse.up()
            moved=window.bounding_box();assert abs(moved['x']-original['x'])>5 or abs(moved['y']-original['y'])>5
            handle=window.locator('.app-window-drag-strip');box=handle.bounding_box();page.mouse.move(box['x']+80,box['y']+12);page.mouse.down();page.mouse.move(-500,-500,steps=8);page.mouse.up()
            bound=window.bounding_box();assert bound['x']>=-2 and bound['y']>=-2
            window.get_by_role('tab',name='分组管理',exact=True).click()
            window.get_by_role('button',name='新增分组',exact=True).click()
            editor=page.locator('.paired-form-editor:visible')
            def select(label,option):
                editor.locator('.el-dialog__footer').click(position=dict(x=10,y=10))
                expect(page.locator('.el-select-dropdown:visible')).to_have_count(0)
                editor.locator('.el-form-item').filter(has=page.locator('label',has_text=label)).locator('.el-select').click()
                page.locator('.el-select-dropdown:visible').last.get_by_text(option,exact=True).click()
                editor.locator('.el-dialog__footer').click(position=dict(x=10,y=10))
                expect(page.locator('.el-select-dropdown:visible')).to_have_count(0)
            select('第一位采集员','QA1 · 采集员1');select('第二位采集员','QA2 · 采集员2')
            editor.get_by_role('button',name='保存',exact=True).click()
            expect(window.get_by_text('采集员1、采集员2',exact=True)).to_be_visible()
            window.get_by_role('tab',name='采集管理',exact=True).click()
            expect(window.get_by_text('分组1 · 首批采集',exact=True)).to_be_visible()
            window.get_by_role('button',name='转入标注',exact=True).click()
            editor=page.locator('.paired-form-editor:visible')
            select('标注人员','QA3 · 采集员3');editor.locator('.dialog-field-search-header__title').click()
            editor.get_by_role('button',name='保存',exact=True).click()
            expect(editor).not_to_be_visible()
            window.get_by_role('tab',name='标注管理',exact=True).click()
            expect(window.get_by_text('采集员3',exact=True)).to_be_visible()
            window.get_by_role('button',name='过程记录',exact=True).click()
            record_window=page.locator('.el-dialog:visible').last
            record_window.get_by_role('button',name='新增进度节点',exact=True).click()
            editor=page.locator('.paired-form-editor:visible')
            editor.locator('.el-form-item').filter(has_text='预计完成进度（自由填写）').locator('textarea').fill('完成第一段对话')
            editor.get_by_role('button',name='保存',exact=True).click()
            expect(record_window.get_by_text('完成第一段对话',exact=False)).to_be_visible()
            record_window.get_by_role('button',name='关闭',exact=True).click()
            expect(page.locator('.dialog-fade-leave-active')).to_have_count(0)
            window.screenshot(path=str(out/'workspace.png'))
            window.get_by_role('button',name='关闭',exact=True).click()
            page.locator('.annotation-table .el-table__body-wrapper tr').first.get_by_role('button').last.click();page.get_by_text('双人采标管理',exact=True).click()
            expect(window).to_be_visible()
            expect(page.locator('.dialog-fade-enter-active')).to_have_count(0)
            reset=window.bounding_box()
            assert abs(reset['x']-original['x'])<5 and abs(reset['y']-original['y'])<5,(original,reset)
            page.set_viewport_size(dict(width=700,height=760))
            expect(window.get_by_role('button',name='关闭',exact=True)).to_be_in_viewport()
            assert not errors,errors
            browser.close()
        (out/'results.json').write_text(json.dumps(dict(success=True,requests=len(requests),groups=len(groups),annotation_tasks=len([row for row in tasks if row['stage']=='annotation']),records=len(records),errors=errors),ensure_ascii=False,indent=2),encoding='utf-8')
        print('浏览器验收通过：联系编辑、详情Popover、分组、非原采集员标注、过程记录、固定底栏、拖动边界、位置复位、小屏。')
    finally:
        process.terminate();process.wait(timeout=10);log.close()


if __name__=='__main__':run()
