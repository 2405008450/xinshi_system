"""真实构建页面的三级订单交互验收；所有 API 均模拟，不连接业务库。"""
import copy
import json
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:12425'


def run():
    global BASE
    if socket.gethostname().upper()!='PC' or ROOT!=Path(r'E:\xinshi_system'):
        raise SystemExit('仅允许在本机项目目录运行隔离验收')
    out=ROOT/'.tmp'/'grandchild-ui';out.mkdir(parents=True,exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    BASE=f'http://127.0.0.1:{port}'
    root_id,child_id,leaf_id,language_id,client_id,user_id,area_id,field_id=[str(uuid4()) for _ in range(8)]
    now='2026-10-12T18:00:00+08:00'
    base=dict(project_name='三级采集项目',project_types=['text_annotation'],task_description='公共任务要求',
              client_id=client_id,client_short_name='验收客户',client_full_name='验收客户全称',client_code='QA',client_manager_id=user_id,client_manager_name='验收人员',task_dispatched_at=now,
              project_status='initial_consultation',priority='medium',status_effective_on=now,created_at=now,updated_at=now,
              language_items=[dict(id=str(uuid4()),source_language_id=language_id,source_language_label='英语',display='英语',sequence_no=1)],
              language_items_display='英语',price_items=[],assignees=[],role_assignments=[],custom_values={field_id:'公共自定义值'},
              parent_project_id=None,child_count=0,child_status_counts={},area_id=None,area_labels=['北美片区'],inheritance_overrides=[],arrangement_included=True)
    orders={root_id:{**copy.deepcopy(base),'id':root_id,'order_no':'AP-QA-AREA','order_level':0,'child_count':1},
            child_id:{**copy.deepcopy(base),'id':child_id,'order_no':'AP-QA-AREA.001','order_level':1,'parent_project_id':root_id,'parent_order_no':'AP-QA-AREA','child_count':1},
            leaf_id:{**copy.deepcopy(base),'id':leaf_id,'order_no':'AP-QA-AREA.001.001','order_level':2,'parent_project_id':child_id,'parent_order_no':'AP-QA-AREA.001','area_id':area_id,'inheritance_overrides':['potential_demand']}}
    areas=[dict(id=area_id,label='北美片区')];queries=[];creates=[];saves=[];errors=[]
    session=dict(id=user_id,username='grandchild-qa',full_name='验收人员',roles=['admin'],permissions=['projects:read','projects:write'])
    field=dict(id=field_id,table_code='project',field_key='qa_common',field_label='客户特殊要求',data_type='text',sequence_no=1,is_active=True,is_required=False,options=[])

    def api(route):
        request=route.request;url=urlparse(request.url);path=url.path.removeprefix('/api');query=parse_qs(url.query)
        result=[];status=200
        if path=='/auth/session':result=session
        elif path=='/annotation-ops/project-arrangements/context':
            result=dict(projects=[{**orders[id],'tasks':[]} for id in query.get('project_id',[])],task_types=[],assignees=[])
        elif path=='/projects/annotation/areas':
            if request.method=='POST':
                label=request.post_data_json['label'].strip();existing=next((area for area in areas if area['label']==label),None)
                if not existing:existing=dict(id=str(uuid4()),label=label);areas.append(existing)
                result=existing
            else:result=areas
        elif path=='/projects/annotation/page':
            queries.append(query);scope=query.get('order_scope',['all'])[0];levels={'parent':0,'child':1,'grandchild':2}
            rows=[row for row in orders.values() if scope=='all' or row['order_level']==levels[scope]]
            if query.get('parent_project_id'):rows=[row for row in rows if row['parent_project_id']==query['parent_project_id'][0]]
            result=dict(items=rows,total=len(rows))
        elif path.startswith('/projects/annotation/') and path.endswith(('/children','/children/batch')):
            parent_id=path.split('/')[3]
            if request.method=='POST':
                payload=request.post_data_json;items=payload.get('items',[payload]);creates.append((parent_id,items))
                result=[]
                for item in items:
                    parent=orders[parent_id];new_id=str(uuid4());row={**copy.deepcopy(parent),**item,'id':new_id,'order_level':parent['order_level']+1,'parent_project_id':parent_id,'order_no':parent['order_no']+'.002','child_count':0,'inheritance_overrides':[]}
                    orders[new_id]=row;result.append(row)
                status=201
                if '/batch' not in path:result=result[0]
            else:
                rows=[row for row in orders.values() if row['parent_project_id']==parent_id];result=dict(items=rows,total=len(rows))
        elif path.startswith('/projects/annotation/') and path.rsplit('/',1)[-1] in orders:
            row=orders[path.rsplit('/',1)[-1]]
            if request.method=='PUT':
                payload=request.post_data_json;saves.append(payload);row.update(payload)
            result=row
        elif '/custom-fields' in path:result=[field] if query.get('table_code',['project'])[0]=='project' else []
        elif path.startswith('/clients'):result=[dict(id=client_id,client_short_name='验收客户',client_name='验收客户全称',client_code='QA',sub_clients=[])]
        elif path=='/projects/languages':result=[dict(id=language_id,label='英语')]
        elif path.startswith('/users') or 'role-candidates' in path:result=[dict(id=user_id,username='grandchild-qa',full_name='验收人员',is_active=True)]
        elif 'source-statuses' in path:result={}
        elif '/materials/' in path:result=[]
        elif path.endswith('/folder-changes'):result=dict(created_folders=[],renamed_folders=[],deleted_folder_ids=[])
        elif 'status-history' in path:result=[]
        route.fulfill(status=status,json=result)

    log=(out/'preview.log').open('w',encoding='utf-8')
    process=subprocess.Popen(['node','node_modules/vite/bin/vite.js','preview','--host','127.0.0.1','--port',str(port),'--strictPort'],cwd=ROOT/'frontend',stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(40):
            if process.poll() is not None:
                raise RuntimeError((out/'preview.log').read_text(encoding='utf-8'))
            try:
                urlopen(BASE,timeout=1).close();break
            except OSError:time.sleep(.2)
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,channel='chrome')
            context=browser.new_context(viewport={'width':1600,'height':1000})
            context.route('**/api/**',api)
            context.add_init_script("localStorage.setItem('token','mock-only'); localStorage.setItem('user_name','grandchild-qa')")
            page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(BASE+'/annotation-details')
            expect(page.get_by_role('button',name='展开子订单',exact=True)).to_be_visible()
            page.get_by_role('button',name='展开子订单',exact=True).click()
            page.get_by_role('button',name='展开三级订单',exact=True).click()
            expect(page.get_by_role('button',name=orders[leaf_id]['order_no'],exact=True)).to_be_visible()
            page.get_by_role('button',name=orders[leaf_id]['order_no'],exact=True).click()
            expect(page.locator('.annotation-detail-popover:visible')).to_be_visible()
            page.locator('.project-list-keyword-filter input').click()
            expect(page.locator('.annotation-detail-popover:visible')).not_to_be_visible()
            tables=page.locator('.annotation-order-table')
            expect(tables).to_have_count(3)
            headers=tables.evaluate_all("tables=>tables.map(table=>table.querySelector(':scope > .el-table__inner-wrapper > .el-table__header-wrapper thead')?.innerText)")
            headers=[' '.join(header.split()) for header in headers]
            assert headers[0]==headers[1]==headers[2],headers
            assert '片区' in headers[0] and '详情' in headers[0]
            for index in range(3):
                box=tables.nth(index).get_by_role('button',name='查看详情',exact=True).first.bounding_box()
                assert box['x']+box['width']<=1600,box
            assert not re.search('母订单|孙订单',page.locator('body').inner_text())
            for index in [1,2]:
                tables.nth(index).get_by_role('button',name='更多操作',exact=True).first.click()
                page.get_by_role('menuitem',name='安排',exact=True).last.click()
                arrangement=page.locator('.annotation-arrangement-quick-dialog:visible')
                expect(arrangement).to_be_visible()
                expect(arrangement.locator('.quick-dialog-heading')).to_contain_text('子订单：' if index==1 else '三级订单：')
                assert not re.search('母订单|孙订单',arrangement.inner_text())
                arrangement.get_by_role('button',name='关闭此对话框').click()
                confirm=page.locator('.el-message-box:visible')
                expect(confirm).to_be_visible()
                confirm.get_by_role('button',name='确定',exact=True).click()
                expect(arrangement).not_to_be_visible()
            page.get_by_role('button',name='新增子订单',exact=True).click()
            create_dialog=page.locator('.annotation-child-create-dialog:visible')
            expect(create_dialog).to_be_visible()
            expect(create_dialog.locator('.el-form-item__label').first).to_have_text('订单')
            expect(create_dialog.locator('.el-dialog__header')).to_contain_text('新增标注子订单')
            create_dialog.get_by_role('button',name='取消',exact=True).click()
            expect(create_dialog).not_to_be_visible()
            page.screenshot(path=str(out/'three-level-list.png'),full_page=True)
            page.get_by_role('button',name='删除管理',exact=True).click()
            expect(page.get_by_role('button',name='新增三级订单',exact=True)).to_have_count(0)
            expect(page.get_by_role('button',name='更多操作',exact=True)).to_have_count(0)
            expect(page.get_by_role('button',name='查看详情',exact=True).last).to_be_visible()
            page.get_by_role('button',name='退出',exact=True).click()
            page.get_by_role('button',name='查看详情',exact=True).last.click()
            expect(page.locator('.annotation-detail-popover:visible')).to_be_visible()
            expect(page.locator('.annotation-detail-popover:visible')).to_contain_text('北美片区')
            page.mouse.click(300,160)
            # 表头漏斗的多选确定后携带规范的重复参数，重置恢复完整列表。
            table_header=page.locator('.annotation-table > .el-table__inner-wrapper > .el-table__header-wrapper')
            funnel=table_header.locator('th').filter(has_text='片区').get_by_role('button')
            funnel.click()
            popover=page.locator('.el-popover:visible').filter(has_text='北美片区')
            popover.locator('.el-checkbox').filter(has_text='北美片区').click()
            popover.get_by_role('button',name='确定',exact=True).click()
            page.wait_for_function('document.querySelectorAll(".el-loading-mask").length === 0')
            assert any(query.get('area_ids')==[area_id] for query in queries),queries
            page.get_by_role('button',name='重置',exact=True).click()
            # 在子订单下创建三级订单：语种只读，片区支持自行新增。
            page.get_by_role('button',name='新增三级订单',exact=True).click()
            dialog=page.locator('.annotation-child-create-dialog:visible')
            expect(dialog).to_be_visible()
            expect(dialog.locator('.el-dialog__header')).to_contain_text('新增标注三级订单')
            expect(dialog.locator('.el-form-item__label').first).to_have_text('子订单')
            area=dialog.locator('.el-form-item').filter(has_text='片区').locator('input')
            area.fill('欧洲片区');area.press('Enter')
            expect(dialog.get_by_role('button',name='确认创建',exact=True)).to_be_enabled()
            dialog.get_by_role('button',name='确认创建',exact=True).click()
            expect(dialog).not_to_be_visible()
            assert creates and creates[-1][0]==child_id
            assert creates[-1][1][0]['area_id'] in [area['id'] for area in areas if area['label']=='欧洲片区']
            assert creates[-1][1][0]['language_items'][0]['source_language_id']==language_id
            # 编辑三级订单，恢复继承在保存时传入字段键。
            page.goto(BASE+f'/annotation-child-orders?orderScope=grandchild&parentProjectId={child_id}&projectId={leaf_id}&openEditor=1')
            editor=page.locator('.annotation-editor-dialog:visible');expect(editor).to_be_visible()
            expect(page.get_by_text('标注三级订单管理',exact=True)).to_have_count(2)
            expect(editor).to_contain_text('所属子订单：')
            expect(editor.locator('.el-form-item').filter(has_text='语种方向').locator('input').first).to_have_attribute('readonly','')
            editor.get_by_role('button',name='恢复继承',exact=True).click()
            inheritance=page.locator('.el-popover:visible').filter(has_text='全部恢复')
            inheritance.locator('.el-checkbox').filter(has_text='需求量').click()
            page.mouse.click(400,80)
            footer=editor.locator('.el-dialog__footer')
            before=footer.bounding_box();editor.locator('.el-dialog__body').evaluate('(element)=>element.scrollTop=element.scrollHeight')
            after=footer.bounding_box();assert abs(before['y']-after['y'])<2
            # 拖动范围约束、关闭按钮与重开复位。
            title=editor.locator('.el-dialog__header');original=editor.bounding_box();position=title.bounding_box()
            page.mouse.move(position['x']+20,position['y']+20);page.mouse.down();page.mouse.move(5000,5000,steps=10);page.mouse.up()
            moved=editor.bounding_box();assert moved['x']>=-1 and moved['y']>=-1 and moved['x']+moved['width']<=1601 and moved['y']+moved['height']<=1001,moved
            footer.get_by_role('button',name='保存',exact=True).click()
            expect(editor).not_to_be_visible()
            assert saves[-1]['restore_inheritance']==['potential_demand']
            page.goto(BASE+f'/annotation-child-orders?orderScope=grandchild&parentProjectId={child_id}&projectId={leaf_id}&openEditor=1')
            expect(editor).to_be_visible()
            page.wait_for_function("expected=>Math.abs(document.querySelector('.annotation-editor-dialog').getBoundingClientRect().y-expected)<1",arg=original['y'])
            reset=editor.bounding_box();assert abs(reset['x']-original['x'])<2 and abs(reset['y']-original['y'])<2,(original,reset)
            editor.get_by_role('button',name='关闭此对话框').click();expect(editor).not_to_be_visible()
            page.set_viewport_size({'width':760,'height':700})
            page.get_by_role('button',name='新增三级订单',exact=True).first.click();expect(dialog).to_be_visible()
            box=dialog.bounding_box();assert box['width']<=729 and box['height']<=631,box
            expect(dialog.locator('.el-dialog__footer')).to_be_visible()
            dialog.get_by_role('button',name='取消',exact=True).click()
            expect(dialog).not_to_be_visible()
            for id,scope,parent_id,expected in [(root_id,'parent',None,None),(child_id,'child',root_id,'所属订单：')]:
                url=f'/annotation-details?projectId={id}&openEditor=1' if scope=='parent' else f'/annotation-child-orders?parentProjectId={parent_id}&projectId={id}&openEditor=1'
                page.goto(BASE+url);expect(editor).to_be_visible()
                if expected:expect(editor).to_contain_text(expected)
                assert not re.search('母订单|孙订单',editor.inner_text())
                editor.get_by_role('button',name='关闭此对话框').click();expect(editor).not_to_be_visible()
            page.screenshot(path=str(out/'grandchild-orders.png'),full_page=True)
            assert not errors,errors
            browser.close()
        print(json.dumps({'passed':True,'checks':['三级展开与同列','片区多选筛选','三级订单创建与新增片区','语种只读','恢复继承','固定操作栏','拖拽边界及重开复位','小屏幕'],'requests':len(queries)},ensure_ascii=False))
    finally:
        process.terminate();process.wait(timeout=10);log.close()


if __name__=='__main__':run()
