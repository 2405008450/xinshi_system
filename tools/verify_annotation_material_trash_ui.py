"""真实构建的资料历史/回收站 UI；合成接口，不读取业务数据库。"""
import json
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from playwright.sync_api import expect
from verify_annotation_materials_ui import run, BASE


def verify(page, context, project, rows, folders, output, errors):
    page.set_default_timeout(10000)
    output = output.parent / 'material-trash-ui'; output.mkdir(exist_ok=True)
    project_id = project['id']; checks, requests, trashed = [], [], {}
    initial = rows[0]
    for category in ('quotation', 'contract'):
        rows.append({**initial, 'id': str(uuid4()), 'file_id': str(uuid4()), 'category': category, 'original_name': category+'.txt'})
    blocked = rows[-1]['file_id']
    fail_history, fail_restore = [False], [False]
    role, permissions = ['admin'], ['projects:read', 'projects:write']

    def route_api(route):
        req = route.request; path = urlparse(req.url).path.rstrip('/'); query = parse_qs(urlparse(req.url).query)
        requests.append((req.method, path))
        if path == '/api/auth/session':
            route.fulfill(json=dict(id=project['client_manager_id'], user_id=project['client_manager_id'], username='qa', full_name='验收用户', roles=role, permissions=permissions)); return
        if path.endswith('/trash') and req.method == 'POST':
            file_id = path.split('/')[-2]
            if file_id == blocked:
                route.fulfill(status=409, json={'detail': '该文件正在由验收乙在线编辑，请稍后重试'}); return
            saved = next(row for row in reversed(rows) if row['file_id'] == file_id)
            trashed[file_id] = {**saved, 'version_count': sum(row['file_id'] == file_id for row in rows), 'trash_token': str(uuid4()),
                'original_folder_path': '项目资料 / 原目录', 'deleted_by_name': '验收用户', 'deleted_at': '2026-10-21T19:00:00+08:00'}
            route.fulfill(json=trashed[file_id]); return
        if path.endswith('/restore'):
            if fail_restore[0]:
                fail_restore[0] = False; route.fulfill(status=409, json={'detail': '回收站记录已变化，请刷新后重试'}); return
            trashed.pop(path.split('/')[-2], None); route.fulfill(json={'restored': True}); return
        if '/material-trash/' in path and req.method == 'DELETE':
            file_id = path.split('/')[-1]; trashed.pop(file_id, None); rows[:] = [row for row in rows if row['file_id'] != file_id]
            route.fulfill(status=204); return
        if path.endswith('/material-trash'):
            keyword = query.get('keyword', [''])[0].casefold()
            entries = [row for row in trashed.values() if all(word in (row['original_name']+' '+row['deleted_by_name']).casefold() for word in keyword.split())]
            offset = (int(query.get('page', ['1'])[0])-1)*20
            route.fulfill(json={'items': entries[offset:offset+20], 'total': len(entries)}); return
        if path.endswith('/materials'):
            latest = {}
            for row in sorted(rows, key=lambda row: -row['version_no']):
                if row['file_id'] not in trashed: latest.setdefault(row['file_id'], row)
            route.fulfill(json=list(latest.values())); return
        if path.endswith('/versions'):
            if fail_history[0]:
                fail_history[0] = False; route.fulfill(status=503, json={'detail': '模拟历史加载失败'}); return
            file_id = path.split('/')[-2]
            if file_id in trashed: route.fulfill(status=410, json={'detail': '文件已进入回收站，请恢复后查看历史版本'})
            else: route.fulfill(json=sorted([row for row in rows if row['file_id'] == file_id], key=lambda row: -row['version_no']))
            return
        if path == f'/api/projects/annotation/{project_id}' and req.method == 'PUT':
            for file_id in req.post_data_json.get('material_changes', {}).get('removed_file_ids', []):
                saved = next(row for row in rows if row['file_id'] == file_id)
                trashed[file_id] = {**saved, 'version_count': 1, 'trash_token': str(uuid4()), 'original_folder_path': saved['category'], 'deleted_by_name': '验收用户', 'deleted_at':'2026-10-21T19:00:00+08:00'}
            route.fulfill(json=project); return
        route.fallback()
    context.route('**/api/**', route_api)
    page.goto(BASE+'/annotation-details')
    def open_materials():
        page.get_by_role('button', name='项目资料', exact=True).first.click()
        panel = page.locator('.annotation-material-popover:visible'); expect(panel).to_be_visible()
        expect(panel.locator('.material-manager')).to_be_visible()
        return panel
    def close_history():
        history = page.get_by_role('dialog', name='资料历史版本', exact=True)
        history.get_by_role('button', name='关闭', exact=True).click()
        expect(history).not_to_be_visible()
        page.wait_for_timeout(350)
    def close_recycle():
        recycle = page.get_by_role('dialog', name='资料回收站', exact=True)
        recycle.get_by_role('button', name='关闭', exact=True).click()
        expect(recycle).not_to_be_visible()
        page.wait_for_timeout(350)
    panel = open_materials()
    panel.get_by_role('button', name='历史资料.txt的更多操作', exact=True).click()
    page.get_by_role('menuitem', name='历史版本', exact=True).click()
    dialog = page.get_by_role('dialog', name='资料历史版本', exact=True)
    expect(dialog.get_by_text('V1 · 历史资料.txt', exact=True)).to_be_visible()
    with page.expect_download(): dialog.get_by_role('button', name='下载', exact=True).click()
    expect(panel).not_to_be_visible()
    rows.append({**initial, 'id': str(uuid4()), 'version_no': 2, 'original_name': '历史资料.txt'})
    expect(dialog.get_by_text('V2 · 历史资料.txt', exact=True)).to_be_visible(timeout=10000)
    expect(dialog).to_be_visible()
    checks.append('菜单打开历史、父浮层销毁、轮询新增版本后仍显示')
    box = dialog.locator('.el-dialog').bounding_box(); header = dialog.locator('.el-dialog__header').bounding_box()
    page.mouse.move(header['x']+30, header['y']+15); page.mouse.down(); page.mouse.move(header['x']+90,header['y']+45,steps=6); page.mouse.up()
    assert abs(dialog.locator('.el-dialog').bounding_box()['x']-box['x']) > 20
    header = dialog.locator('.el-dialog__header').bounding_box()
    page.mouse.move(header['x']+30,header['y']+15);page.mouse.down();page.mouse.move(5000,5000,steps=8);page.mouse.up()
    bound = dialog.locator('.el-dialog').bounding_box()
    assert bound['x']>=-1 and bound['y']>=-1 and bound['x']+bound['width']<=1441 and bound['y']+bound['height']<=1001
    close_history(); panel=open_materials(); fail_history[0]=True
    panel.locator('.explorer-table tbody tr').filter(has_text='历史资料.txt').click()
    panel.get_by_role('button',name='历史版本',exact=True).first.click()
    expect(dialog.get_by_text('模拟历史加载失败',exact=True)).to_be_visible()
    dialog.get_by_role('button',name='重试',exact=True).click()
    expect(dialog.get_by_text('V2 · 历史资料.txt',exact=True)).to_be_visible()
    assert abs(dialog.locator('.el-dialog').bounding_box()['x']-box['x'])<3
    checks.append('历史下载、拖拽边界、重新打开复位、失败重试')
    close_history()
    if not panel.is_visible():panel=open_materials()
    panel.get_by_role('button',name='删除管理',exact=True).click()
    panel.get_by_role('checkbox',name='选择删除历史资料.txt',exact=True).locator('xpath=ancestor::label[1]').click()
    panel.get_by_role('checkbox',name='选择删除contract.txt',exact=True).locator('xpath=ancestor::label[1]').click()
    panel.get_by_role('button',name='删除所选（2）',exact=True).click()
    confirm=page.get_by_role('dialog',name='批量删除文件',exact=True)
    expect(confirm).to_be_visible();confirm.get_by_role('textbox').fill('删除');confirm.get_by_role('button',name='确定',exact=True).click()
    expect(panel.get_by_text('contract.txt：该文件正在由验收乙在线编辑，请稍后重试',exact=True)).to_be_visible()
    expect(panel.get_by_role('checkbox',name='选择删除contract.txt',exact=True)).to_be_checked()
    expect(panel.get_by_text('历史资料.txt',exact=True)).not_to_be_visible()
    checks.append('批量删除确认、跨端占用失败、成功刷新及失败保留选择')
    panel.get_by_role('button',name='退出',exact=True).click()
    panel.get_by_role('button',name='回收站',exact=True).click()
    recycle=page.get_by_role('dialog',name='资料回收站',exact=True)
    expect(recycle.get_by_text('历史资料.txt',exact=True)).to_be_visible()
    expect(recycle.get_by_text('2',exact=True)).to_be_visible()
    fail_restore[0]=True;recycle.get_by_role('button',name='恢复',exact=True).click()
    expect(page.get_by_text('回收站记录已变化，请刷新后重试',exact=True)).to_be_visible()
    recycle.get_by_role('button',name='恢复',exact=True).click()
    expect(recycle.get_by_text('历史资料.txt',exact=True)).not_to_be_visible()
    checks.append('全局回收站、恢复失败保留文件、恢复全部历史版本')
    close_recycle()
    panel=open_materials() if not panel.is_visible() else panel
    panel.get_by_role('button',name='删除管理',exact=True).click()
    panel.get_by_role('checkbox',name='选择删除历史资料.txt',exact=True).locator('xpath=ancestor::label[1]').click()
    panel.get_by_role('button',name='删除所选（1）',exact=True).click()
    page.get_by_role('dialog',name='删除文件',exact=True).get_by_role('button',name='确定',exact=True).click()
    expect(panel.get_by_text('历史资料.txt',exact=True)).not_to_be_visible()
    panel.get_by_role('button',name='回收站',exact=True).click()
    expect(recycle.get_by_text('历史资料.txt',exact=True)).to_be_visible()
    search=recycle.get_by_role('textbox',name='搜索回收站',exact=True)
    before=len([r for r in requests if r[1].endswith('/material-trash')])
    search.fill('不会匹配');page.wait_for_timeout(200)
    assert len([r for r in requests if r[1].endswith('/material-trash')])==before
    expect(recycle.get_by_text('历史资料.txt',exact=True)).not_to_be_visible()
    search.fill('');expect(recycle.get_by_text('历史资料.txt',exact=True)).to_be_visible()
    checks.append('回收站搜索防抖和清空即时恢复')
    recycle.get_by_role('button',name='彻底删除管理',exact=True).click()
    recycle.locator('.el-table__body .el-checkbox').first.click()
    page.set_viewport_size({'width':390,'height':740})
    expect(recycle.get_by_role('button',name='关闭',exact=True)).to_be_visible()
    assert recycle.locator('.el-dialog').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    recycle.screenshot(path=str(output/'recycle-mobile.png'))
    recycle.get_by_role('button',name='彻底删除所选（1）',exact=True).click()
    page.get_by_role('dialog',name='彻底删除确认',exact=True).get_by_role('button',name='确定',exact=True).click()
    expect(recycle.get_by_text('历史资料.txt',exact=True)).not_to_be_visible()
    checks.append('超级管理员彻底删除、小屏内部滚动和固定底部')
    close_recycle();page.set_viewport_size({'width':1440,'height':1000})
    # 表单仍是暂存变更；取消不删除，保存后才进入回收站。
    for save in (False, True):
        page.goto(BASE+f'/annotation-details?projectId={project_id}&openEditor=1')
        form=page.locator('.annotation-editor-dialog:visible');expect(form).to_be_visible()
        material=form.locator('.material-manager');material.scroll_into_view_if_needed()
        material.locator('.material-row').filter(has_text='quotation.txt').get_by_role('button',name='移除',exact=True).click()
        confirm=page.get_by_role('dialog',name='移除项目资料',exact=True)
        confirm.get_by_role('button',name='确定',exact=True).click();expect(confirm).not_to_be_visible();page.wait_for_timeout(350)
        assert not any(row['original_name']=='quotation.txt' for row in trashed.values())
        form.get_by_role('button',name='保存' if save else '取消',exact=True).click();expect(form).not_to_be_visible()
        assert any(row['original_name']=='quotation.txt' for row in trashed.values()) == save
    checks.append('编辑表单移除随保存生效，取消不改变文件')
    # 聊天资料入口与列表复用同一浮层和全局历史宿主。
    rows.append({**initial,'id':str(uuid4()),'file_id':str(uuid4()),'original_name':'聊天资料.txt'})
    context.route('**/api/chat/sessions', lambda route: route.fulfill(json={'items':[dict(key='annotation:'+project_id,kind='annotation',project_id=project_id,title=project['project_name'],subtitle=project['order_no'],following=True,is_creator=True,project_status='initial_consultation',unread=0,mention_unread=0)],'phase_one_enabled':True,'total':0}))
    def group_route(route):
        path=urlparse(route.request.url).path
        if path.endswith('/group'):route.fulfill(json={'members':[],'eligible_users':[],'following':True})
        else:route.fulfill(json={'items':[],'has_more':False})
    context.route('**/api/project-chat/annotation/**',group_route)
    context.route_web_socket('**/api/notifications/ws**',lambda ws:None)
    page.evaluate('(id)=>localStorage.setItem("user_id",id)', project['client_manager_id'])
    page.reload();page.get_by_role('button',name='聊天大屏',exact=True).click()
    workspace=page.locator('.chat-workspace-shell:visible')
    workspace.locator('.chat-workspace__session').filter(has_text=project['project_name']).click()
    workspace.locator('.chat-project-actions').get_by_role('button',name='项目资料',exact=True).first.click()
    panel=page.locator('.annotation-material-popover:visible')
    panel.get_by_role('button',name='聊天资料.txt的更多操作',exact=True).click()
    page.get_by_role('menuitem',name='历史版本',exact=True).click()
    expect(dialog.get_by_text('V1 · 聊天资料.txt',exact=True)).to_be_visible()
    with page.expect_download():dialog.get_by_role('button',name='下载',exact=True).click()
    expect(panel).not_to_be_visible();expect(dialog).to_be_visible()
    close_history()
    workspace.get_by_role('button',name='关闭当前会话',exact=True).click()
    checks.append('聊天大屏菜单历史独立显示、父浮层关闭和下载')
    role[:]=['项目经理'];page.reload();panel=open_materials();panel.get_by_role('button',name='回收站',exact=True).click()
    expect(recycle.get_by_role('button',name='彻底删除管理',exact=True)).to_have_count(0)
    close_recycle()
    permissions[:]=['projects:read'];page.reload();panel=open_materials()
    expect(panel.get_by_role('button',name='删除管理',exact=True)).to_have_count(0)
    expect(panel.get_by_role('button',name='回收站',exact=True)).to_have_count(0)
    checks.append('普通写权限可恢复、无彻底删除入口；只读隐藏删除和回收站')
    assert not errors, errors
    report={'status':'passed','checks':checks,'page_errors':errors}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    os.environ['MATERIAL_UI_DIST']='../.tmp/trash-build'
    run(verify_extra=verify)
