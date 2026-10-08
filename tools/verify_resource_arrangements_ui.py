"""本机构建页面验收：隔离接口状态，覆盖草稿、冲突和弹窗交互。"""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import socket
import subprocess
import time
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from playwright.sync_api import expect, sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:12457'


def run():
    if socket.gethostname().upper()!='PC' or str(ROOT).lower()!=r'e:\xinshi_system':
        raise SystemExit('仅允许在本机执行')
    out=ROOT/'.tmp/resource-arrangements-ui'; out.mkdir(parents=True,exist_ok=True)
    today=datetime.now(ZoneInfo('Asia/Hong_Kong')).date()
    previous=(today-timedelta(days=1)).isoformat(); today=today.isoformat()
    manager,owner,language,request,project=[str(uuid4()) for _ in range(5)]
    platforms=[dict(id=str(uuid4()),kind='platform',category='national',name=name) for name in ['Boss1','Boss2','智联1']]
    source=dict(source_type='annotation',project_id=project,order_no='AP-测试-01',project_name='温州话子订单',parent_project_id=str(uuid4()))
    target=dict(kind='request',request_id=request,language_id=language,label='温州话',request_no='RR-测试',source_name='温州话子订单',project=source,active=True,inactive_reason='')
    initial_cell=dict(platform_id=platforms[0]['id'],platform_name='Boss1',owner_id=owner,owner_name='负责人',targets=[target],projects=[source],manual_projects=[],remarks='昨日账号备注',completed=True,completed_by=manager,completed_by_name='实际操作人',completed_at=previous+'T10:30:00',can_edit=True)
    days={previous:dict(work_date=previous,revision=1,remarks='昨日每日备注',cells=[initial_cell],can_manage=True)}
    mode=['manager']; errors=[]; writes=[]; cancelled=[False]; conflict=[False]

    def api(route):
        req=route.request; path=urlparse(req.url).path.removeprefix('/api'); query=parse_qs(urlparse(req.url).query)
        user=manager if mode[0]=='manager' else owner
        if path=='/auth/session':
            result=dict(user_id=user,username='qa',full_name='验收人员',roles=['admin'] if mode[0]=='manager' else ['staff'],permissions=['talents:read']+(['talents:write'] if mode[0]!='readonly' else []))
        elif path=='/resource-development/options' and req.method=='GET':
            result=dict(options=platforms,users=[dict(id=manager,name='实际操作人'),dict(id=owner,name='负责人')],languages=[dict(id=language,label='温州话',language_type='dialect')],user_id=user,is_admin=mode[0]=='manager',can_delegate=mode[0]=='manager',can_write=mode[0]!='readonly',default_date=previous)
        elif path=='/resource-development/options' and req.method=='POST':
            result=dict(id=str(uuid4()),**req.post_data_json); platforms.append(result)
        elif path=='/resource-development/channels' and req.method=='POST':
            result=dict(id=str(uuid4()),kind='platform',**req.post_data_json); platforms.append(result)
        elif path=='/resource-development/days': result=dict(items=[],total=0)
        elif path=='/resource-development/arrangement-options': result=dict(targets=[] if cancelled[0] else [target],projects=[source] if query.get('source_type') else [])
        elif path=='/resource-development/arrangement-project-detail': result=source|dict(project_status='resource_sourcing',requirements=[dict(request_no='RR-测试',demand_status='cancelled' if cancelled[0] else 'confirmed',languages=['温州话'])])
        elif path=='/resource-development/arrangements':
            values=[copy.deepcopy(d) for key,d in sorted(days.items(),reverse=True) if query.get('start',[''])[0]<=key<=query.get('end',['9999'])[0]]
            result=dict(items=values,total=len(values))
        elif path.startswith('/resource-development/arrangements/'):
            parts=path.split('/'); day=parts[3]
            if path.endswith('/carry-preview'):
                result=copy.deepcopy(days[previous]); result.update(work_date=day,revision=0,carried_from=previous,warnings=[])
                for cell in result['cells']: cell.update(completed=False,completed_at=None,completed_by=None,completed_by_name='')
            elif req.method=='PUT':
                payload=req.post_data_json; writes.append(copy.deepcopy(payload))
                if conflict[0]:
                    conflict[0]=False; route.fulfill(status=409,json=dict(detail='这一天已被其他人修改，请重新加载')); return
                result=copy.deepcopy(days.get(day,dict(work_date=day,revision=0,remarks='',cells=[])))
                result['revision']+=1; result['remarks']=payload.get('remarks',result['remarks'])
                for value in payload['cells']:
                    old=next((c for c in result['cells'] if c['platform_id']==value['platform_id']),None)
                    cell=old or dict(platform_id=value['platform_id'],platform_name=next(p['name'] for p in platforms if p['id']==value['platform_id']))
                    manual_projects=[copy.deepcopy(source) for p in value['projects'] if p['project_id']==project]
                    cell.update(value,owner_name='负责人' if value['owner_id']==owner else '实际操作人' if value['owner_id'] else '',manual_projects=manual_projects,completed=False,completed_by=None,completed_at=None,completed_by_name='',can_edit=True)
                    cell['targets']=[copy.deepcopy(target) if t['kind']=='request' else t|dict(label='内部招聘' if t['kind']=='internal' else '温州话',active=True) for t in value['targets']]
                    linked=manual_projects+([source] if any(t['kind']=='request' for t in value['targets']) else [])
                    cell['projects']=list({(p['source_type'],p['project_id']):p for p in linked}.values())
                    if old is None: result['cells'].append(cell)
                days[day]=copy.deepcopy(result)
            elif req.method=='PATCH':
                result=copy.deepcopy(days[day]); cell=next(c for c in result['cells'] if c['platform_id']==parts[5]); cell.update(completed=req.post_data_json['completed'],completed_by=user,completed_by_name='实际操作人',completed_at=day+'T14:30:00'); result['revision']+=1; days[day]=copy.deepcopy(result)
            else: result=copy.deepcopy(days.get(day,dict(work_date=day,revision=0,remarks='',cells=[],can_manage=mode[0]=='manager')))
        elif path.endswith('/unread-count'): result=dict(count=0)
        else: result={}
        # GET 历史内容模拟失效状态；不修改保存的数据快照。
        if cancelled[0] and isinstance(result,dict):
            for d in result.get('items',[result]):
                for cell in d.get('cells',[]):
                    for t in cell.get('targets',[]):
                        if t['kind']=='request': t.update(active=False,inactive_reason='需求已取消')
        route.fulfill(status=200,json=result)

    log=(out/'preview.log').open('w',encoding='utf-8')
    preview=subprocess.Popen(['node','node_modules/vite/bin/vite.js','preview','--outDir','../.tmp/resource-arrangements-dist','--host','127.0.0.1','--port','12457','--strictPort'],cwd=ROOT/'frontend',stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(60):
            try: urlopen(BASE,timeout=1).close(); break
            except Exception: time.sleep(.2)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,channel='msedge')
            context=browser.new_context(viewport=dict(width=1440,height=900),timezone_id='America/New_York')
            context.route('**/api/**',api); context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            page=context.new_page(); page.on('pageerror',lambda e:errors.append(str(e)))
            def open_panel():
                page.goto(BASE+'/resource-management/resource-development'); page.get_by_role('tab',name='每日安排',exact=True).click()
                expect(page.locator('.arrangement-table')).to_be_visible()
            open_panel(); expect(page.get_by_text('尚未保存',exact=True)).to_be_visible()
            assert not writes
            page.get_by_role('button',name='沿用最近一次安排',exact=True).click()
            dialog=page.locator('.arrangement-editor:visible'); expect(dialog).to_contain_text('保存后生效')
            expect(dialog.locator('textarea').first).to_have_value('昨日账号备注')
            assert not writes and today not in days
            # 标题拖动、视口约束、关闭按钮与再次打开复位。
            header=dialog.locator('.el-dialog__header'); before=dialog.bounding_box(); box=header.bounding_box()
            page.mouse.move(box['x']+35,box['y']+20); page.mouse.down(); page.mouse.move(box['x']+130,box['y']+65,steps=6); page.mouse.up()
            moved=dialog.bounding_box(); assert abs(moved['x']-before['x'])>20
            page.mouse.move(box['x']+130,box['y']+65); page.mouse.down(); page.mouse.move(3000,1800,steps=6); page.mouse.up()
            bounded=dialog.bounding_box(); assert bounded['x']>=-2 and bounded['y']>=-2 and bounded['x']+bounded['width']<=1442 and bounded['y']+bounded['height']<=902
            dialog.locator('.el-dialog__headerbtn').click(); expect(dialog).not_to_be_visible()
            page.get_by_role('button',name='沿用最近一次安排',exact=True).click(); expect(dialog).to_be_visible()
            reopened=dialog.bounding_box(); assert abs(reopened['x']-before['x'])<3
            # 保存沿用后的草稿，只提交业务字段。
            dialog.locator('textarea').first.fill('当天可调整备注'); dialog.get_by_role('button',name='保存',exact=True).click()
            expect(dialog).not_to_be_visible(); assert today in days and not days[today]['cells'][0]['completed']
            assert writes[-1]['carried_from']==previous and 'completed_by' not in writes[-1]['cells'][0]
            # 多选、自选、内部招聘、手动关联及字段搜索。
            page.get_by_role('button',name='编辑当日',exact=True).click(); expect(dialog).to_be_visible()
            section=dialog.locator('.arrangement-edit-cell').first
            direction=section.locator('.el-form-item').nth(1).locator('.el-select')
            direction.click(); page.get_by_role('option',name='温州话（自选）',exact=True).click(); page.get_by_role('option',name='内部招聘',exact=True).click()
            page.keyboard.press('Escape')
            project_selector=section.locator('.arrangement-project-selector .el-select').last
            project_selector.click(); page.get_by_role('option',name='AP-测试-01 · 温州话子订单',exact=True).click()
            expect(dialog).to_be_visible()
            search=dialog.locator('.dialog-field-search-header input')
            search.fill('账号备注'); page.locator('.project-field-search-popper:visible').get_by_text('账号备注',exact=True).first.click()
            expect(section.locator('textarea')).to_be_focused()
            dialog.get_by_role('button',name='保存',exact=True).click(); expect(dialog).not_to_be_visible()
            assert {t['kind'] for t in writes[-1]['cells'][0]['targets']}=={'request','manual','internal'}
            assert writes[-1]['cells'][0]['projects'][0]['project_id']==project
            page.locator('.arrangement-owner .el-checkbox').first.click(); expect(page.get_by_text('实际操作人 ·',exact=False)).to_be_visible()
            # 真实 Popover 及准确子订单关联。
            page.locator('.arrangement-linked-projects button').first.click(); popover=page.locator('.development-detail:visible'); expect(popover).to_contain_text('温州话子订单'); assert 'el-popover' in popover.get_attribute('class')
            expect(popover).to_have_attribute('data-popper-placement','left')
            popover_box=popover.bounding_box(); assert popover_box['x']>=0 and popover_box['x']+popover_box['width']<=1442
            page.mouse.click(600,220)
            # 修改、冲突、草稿保留。
            page.get_by_role('button',name='编辑当日',exact=True).click(); expect(dialog).to_be_visible()
            dialog.locator('textarea').first.fill('冲突时保留的草稿'); conflict[0]=True; dialog.get_by_role('button',name='保存',exact=True).click()
            expect(dialog).to_contain_text('当前草稿已保留'); expect(dialog.locator('textarea').first).to_have_value('冲突时保留的草稿')
            dialog.get_by_role('button',name='取消',exact=True).click(); page.get_by_role('button',name='放弃修改',exact=True).click(); expect(dialog).not_to_be_visible()
            cancelled[0]=True; page.get_by_role('button',name='查询',exact=True).click(); expect(page.get_by_text('需求已取消',exact=False).first).to_be_visible()
            # 新平台通过共享配置增加，动态列立即更新；嵌套弹窗保持焦点。
            page.get_by_role('button',name='增加平台',exact=True).click()
            option_dialog=page.locator('.el-dialog:visible').filter(has=page.get_by_text(re.compile(r'^新增(?:渠道|选项)$'))).first
            expect(option_dialog).to_be_visible(); option_dialog.locator('.el-form-item').first.locator('input').fill('新增验收平台')
            option_dialog.get_by_role('button',name='保存',exact=True).click(); expect(option_dialog).not_to_be_visible()
            settings=page.get_by_role('dialog').filter(has=page.get_by_text('平台与选项维护',exact=True))
            settings.get_by_role('button',name='关闭',exact=True).click(); expect(page.locator('.arrangement-table')).to_contain_text('新增验收平台')
            # 新增/编辑及小屏内容滚动，固定底栏。
            page.get_by_role('button',name='新增／编辑安排',exact=True).click(); expect(dialog).to_be_visible()
            page.set_viewport_size(dict(width=600,height=700)); footer=dialog.locator('.el-dialog__footer'); body=dialog.locator('.el-dialog__body')
            body.evaluate('(el)=>el.scrollTop=el.scrollHeight'); expect(footer.get_by_role('button',name='保存',exact=True)).to_be_visible()
            bounds=dialog.bounding_box(); assert bounds['width']<=570 and bounds['height']<=632
            assert body.evaluate('(el)=>el.scrollHeight>el.clientHeight')
            page.wait_for_function("document.getAnimations().filter(a => a.effect?.target?.closest?.('.el-overlay')).every(a => a.playState !== 'running')")
            page.screenshot(path=str(out/'small-screen.png'),full_page=True)
            dialog.get_by_role('button',name='取消',exact=True).click(); expect(dialog).not_to_be_visible()
            page.set_viewport_size(dict(width=1440,height=900))
            page.wait_for_function("document.getAnimations().every(a => a.playState !== 'running')")
            page.screenshot(path=str(out/'desktop.png'),full_page=True)
            mode[0]='owner'; open_panel(); expect(page.get_by_role('button',name='新增／编辑安排',exact=True)).to_have_count(0)
            page.get_by_role('button',name='编辑安排',exact=True).first.click(); expect(dialog).to_be_visible()
            assert dialog.locator('.arrangement-edit-cell .el-select').first.locator('input').is_disabled()
            dialog.get_by_role('button',name='取消',exact=True).click(); expect(dialog).not_to_be_visible()
            mode[0]='readonly'; open_panel(); expect(page.get_by_role('button',name='新增／编辑安排',exact=True)).to_have_count(0)
            assert page.locator('.arrangement-owner .el-checkbox input').first.is_disabled()
            assert not errors,errors
            (out/'result.json').write_text(json.dumps(dict(passed=True,writes=len(writes),errors=errors,scenarios=['空白读取','沿用草稿','调整保存','多选开拓方向','手动项目关联','字段搜索','平台新增及嵌套弹窗','完成检查','项目Popover','并发冲突','需求取消','弹窗拖动和复位','小屏固定底栏','普通人员及只读权限']),ensure_ascii=False,indent=2),encoding='utf-8')
            browser.close()
        print('每日安排页面验收通过')
    finally:
        preview.terminate(); preview.wait(timeout=15); log.close()


if __name__=='__main__': run()
