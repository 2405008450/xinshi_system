"""项目资料在线编辑浏览器验收：本机启动前端预览，全部接口由 Playwright 模拟，不连接或写入业务数据库。"""
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeout

ROOT = Path(__file__).resolve().parents[1]
PORT = 12422
BASE = f'http://127.0.0.1:{PORT}'
PID, UID, LID = str(uuid4()), str(uuid4()), str(uuid4())
NOW = '2026-10-20T04:00:00'


def docx_fixture(path):
    # 使用前端同一套导出逻辑生成含标题、表格的 docx，作为待编辑的已有版本。
    script = """
import { tiptapJsonToDocx } from './src/utils/materialDocx.js'
import { writeFileSync } from 'node:fs'
const doc = { type: 'doc', content: [
  { type: 'heading', attrs: { level: 1 }, content: [{ type: 'text', text: '项目详情说明' }] },
  { type: 'paragraph', content: [{ type: 'text', text: '原始段落' }] },
  { type: 'table', content: [{ type: 'tableRow', content: [
    { type: 'tableCell', content: [{ type: 'paragraph', content: [{ type: 'text', text: '语种' }] }] },
    { type: 'tableCell', content: [{ type: 'paragraph', content: [{ type: 'text', text: '英语' }] }] }] }] },
]}
writeFileSync(process.argv[1], await tiptapJsonToDocx(doc))
"""
    subprocess.run(['node', '--input-type=module', '-e', script, str(path)], cwd=ROOT / 'frontend', check=True)
    return path.read_bytes()


def multipart_file(body):
    match = re.search(rb'filename="[^"]*"\r\nContent-Type: [^\r]*\r\n\r\n(.*)\r\n--', body, re.S)
    return match.group(1) if match else b''


def run():
    if socket.gethostname().upper() != 'PC':
        raise SystemExit('仅允许在本机 PC 执行')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    out = ROOT / '.tmp' / 'office-shortcut-ui'
    out.mkdir(parents=True, exist_ok=True)
    docx_bytes = docx_fixture(out / 'fixture.docx')
    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', str(PORT), '--strictPort', '--outDir', '../.tmp/office-build'],
                               cwd=ROOT / 'frontend', stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    project = dict(id=PID, order_no='AP-QA-EDITOR', project_name='在线编辑验收项目', project_types=['text_annotation'],
                   task_description='在线编辑隔离验收', client_short_name='测试客户', client_manager_id=UID,
                   project_status='initial_consultation', priority='medium', status_effective_on=NOW,
                   task_dispatched_at=NOW, task_submitted_at=None, updated_at=NOW, created_at=NOW,
                   language_items=[dict(id=str(uuid4()), source_language_id=LID, source_language_label='中文', display='中文', sequence_no=1)],
                   price_items=[], assignees=[], custom_values={}, role_assignments=[], project_path='')
    folder_id = str(uuid4())
    folders = [dict(id=folder_id, parent_id=None, name='1. 项目详情', created_at=NOW)]
    contents = {}

    def add_row(name, data, file_id=None, folder=None, version=1):
        row = dict(id=str(uuid4()), file_id=file_id or str(uuid4()), category='project', folder_id=folder, version_no=version,
                   original_name=name, file_size=len(data), uploader_name='验收用户', created_at=NOW)
        rows.append(row); contents[row['id']] = data
        return row

    rows = []
    add_row('旧版说明.txt', '中文\r\n第二行'.encode('gb18030'))
    add_row('交付规范.md', '# 交付标准\n\n- 第一条\n\n<script>alert(1)</script>'.encode())
    add_row('项目说明.docx', docx_bytes)
    add_row('报价.pdf', b'%PDF')
    uploads, commits, creations, errors = {}, [], [], []
    conflict_next = [False]
    office_sessions, office_content = {}, ['项目详情说明\n原始段落\n语种：英语']
    office_readonly, office_unavailable = [False], [False]

    def latest(file_id):
        return max((row for row in rows if row['file_id'] == file_id), key=lambda row: row['version_no'])

    def route_api(route):
        request = route.request
        path = urlparse(request.url).path.removeprefix('/api')
        method, result, status = request.method, [], 200
        if path == '/auth/session':
            result = dict(id=UID, username='qa', full_name='验收用户', roles=['admin'], permissions=['projects:read', 'projects:write'])
        elif path.endswith('/office/sessions') and method == 'POST':
            if office_unavailable[0]:
                route.fulfill(status=503, json={'detail': 'Word 在线编辑尚未启用'}); return
            payload = request.post_data_json
            sid = str(uuid4())
            old = latest(payload['file_id']) if payload.get('file_id') else None
            office_sessions[sid] = dict(id=sid, mode='view' if office_readonly[0] or any(s['file_id'] and s['file_id'] == payload.get('file_id') and s['mode'] == 'edit' and s['state'] == 'open' for s in office_sessions.values()) else 'edit', state='open',
                occupant='其他编辑者', file_id=payload.get('file_id'),
                name=old['original_name'] if old else payload['name'], folder_id=old['folder_id'] if old else payload.get('folder_id'))
            result = {**office_sessions[sid], 'script_url': 'https://office.example.test/sdk.js', 'config': {'mockSessionId': sid,
                'document': {'title': office_sessions[sid]['name']}, 'mockContent': office_content[0] if old else '',
                'editorConfig': {'mode': office_sessions[sid]['mode']}}}
        elif '/office/sessions/' in path:
            pieces = path.split('/office/sessions/')[1].split('/')
            session = office_sessions[pieces[0]]
            if len(pieces) > 1 and pieces[1] == 'save':
                session['save_id'] = request.post_data_json['save_id']
                if conflict_next[0]:
                    conflict_next[0] = False
                    session.update(save_state='failed', error='文件已被他人更新，请保留当前内容')
                else:
                    old = latest(session['file_id']) if session['file_id'] else None
                    new = add_row(session['name'], docx_bytes, session['file_id'], session['folder_id'], old['version_no'] + 1 if old else 1)
                    session.update(state='open', save_state='complete', error=None, version_id=new['id'], file_id=new['file_id'])
                    office_content[0] = request.frame.page.frame_locator('iframe').locator('.office-mock-content').input_value()
                    if old: commits.append(dict(file=session['name'], data=docx_bytes))
                    else: creations.append(dict(name=session['name'], folder_id=session['folder_id'], data=docx_bytes))
            elif len(pieces) > 1 and pieces[1] == 'discard' and session['state'] != 'saved':
                session['state'] = 'discarded'
            result = session
        elif path.endswith('/material-uploads') and method == 'POST':
            body = request.post_data_buffer or b''
            name = re.search(rb'filename="([^"]+)"', body).group(1).decode('utf-8')
            key = str(uuid4())
            uploads[key] = dict(name=name, data=multipart_file(body))
            result, status = dict(id=key, original_name=name, file_size=len(uploads[key]['data']), uploader_name='验收用户',
                                  created_at=NOW, expires_at='2099-01-01T00:00:00'), 201
        elif '/material-uploads/' in path and method == 'DELETE':
            route.fulfill(status=204); return
        elif path.endswith('/download'):
            version_id = path.rsplit('/', 2)[-2]
            route.fulfill(body=contents[version_id], headers={'Content-Type': 'application/octet-stream'}); return
        elif path.endswith('/online-versions'):
            file_id = path.rsplit('/', 2)[-2]
            payload = request.post_data_json
            if conflict_next[0] or latest(file_id)['id'] != payload['base_version_id']:
                conflict_next[0] = False
                route.fulfill(status=409, json={'detail': '文件已被他人更新，请刷新后重试'}); return
            upload = uploads[payload['upload_id']]
            old = latest(file_id)
            result, status = add_row(old['original_name'], upload['data'], file_id, old['folder_id'], old['version_no'] + 1), 201
            commits.append(dict(file=old['original_name'], data=upload['data']))
        elif path.endswith('/online-files'):
            payload = request.post_data_json
            upload = uploads[payload['upload_id']]
            result, status = add_row(upload['name'], upload['data'], folder=payload['folder_id']), 201
            creations.append(dict(name=upload['name'], folder_id=payload['folder_id'], data=upload['data']))
        elif path.endswith('/versions'):
            target = path.rsplit('/', 2)[-2]
            result = sorted((row for row in rows if row['file_id'] == target), key=lambda row: -row['version_no'])
        elif path.endswith('/materials'):
            result = [latest(file_id) for file_id in dict.fromkeys(row['file_id'] for row in rows)]
        elif path.endswith('/material-folders'):
            result = folders
        elif path == '/projects/annotation/page':
            result = {'items': [project], 'total': 1}
        elif path == '/projects/annotation/' + PID:
            if method == 'PUT':
                payload = request.post_data_json
                for item in payload.get('material_changes', {}).get('additions', []):
                    upload = uploads[item['upload_id']]
                    add_row(upload['name'], upload['data'], folder=item.get('folder_id'))
                project.update({key: value for key, value in payload.items() if key != 'material_changes'})
            result = project
        elif 'project-languages' in path:
            result = [{'id': LID, 'label': '中文', 'language_name': '中文'}]
        elif path.rstrip('/') == '/users' or 'role-candidates' in path:
            result = [{'id': UID, 'username': 'qa', 'full_name': '验收用户', 'is_active': True}]
        elif path.endswith('/unread-count'):
            result = {'count': 0}
        route.fulfill(status=status, json=result)

    checks = []
    try:
        for _ in range(40):
            try:
                urlopen(BASE, timeout=1).close(); break
            except Exception:
                time.sleep(.25)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel='msedge')
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.route('**/api/**', route_api)

            bridge=(ROOT/'frontend/public/office-save-bridge.v1.js').read_text(encoding='utf-8')
            context.route('https://office.example.test/office-save-bridge.v1.js',lambda route:route.fulfill(content_type='application/javascript',body=bridge))
            context.route('https://office.example.test/editor*',lambda route:route.fulfill(content_type='text/html',body="""<!doctype html><html><head><script src="/office-save-bridge.v1.js"></script></head><body style="margin:0"><textarea class="office-mock-content" style="width:100%;height:90vh"></textarea><script>
const field=document.querySelector('textarea');
window.addEventListener('message',e=>{if(e.source===parent && e.data.kind==='mock-init'){field.value=e.data.content;field.readOnly=e.data.readonly;}});
field.oninput=()=>{parent.postMessage({kind:'mock-state',data:true},new URL(document.referrer).origin);setTimeout(()=>parent.postMessage({kind:'mock-state',data:false},new URL(document.referrer).origin),300);};
</script></body></html>"""))
            context.route('https://office.example.test/sdk.js',lambda route:route.fulfill(content_type='application/javascript',body="""
window.DocsAPI={DocEditor:class {
constructor(id,config){this.host=document.getElementById(id);this.frame=document.createElement('iframe');this.frame.style.cssText='width:100%;height:100%;border:0';this.frame.src='https://office.example.test/editor?sid='+config.mockSessionId;
this.listen=e=>{if(e.source===this.frame.contentWindow && e.origin==='https://office.example.test' && e.data.kind==='mock-state')config.events.onDocumentStateChange({data:e.data.data});};window.addEventListener('message',this.listen);
this.frame.onload=()=>{this.frame.contentWindow.postMessage({kind:'mock-init',content:config.mockContent,readonly:config.editorConfig.mode==='view'},'https://office.example.test');config.events.onDocumentReady();};this.host.appendChild(this.frame);}
destroyEditor(){window.removeEventListener('message',this.listen);this.host.replaceChildren();}
}};
"""))
            context.add_init_script("""if(location.protocol==='http:'){localStorage.setItem('token','isolated-qa');localStorage.setItem('user_id','%s');localStorage.setItem('user_roles','["admin"]');localStorage.setItem('user_permissions','["projects:read","projects:write"]')}"""%UID)
            context.on('page',lambda tab:tab.on('pageerror',lambda e:errors.append(str(e))))
            page=context.new_page();add_row('预算.xlsx',docx_bytes)
            page.goto(BASE+f'/annotation-details?projectId={PID}&openEditor=1')
            dialog=page.locator('.annotation-editor-dialog:visible');expect(dialog).to_be_visible();manager=dialog.locator('.material-manager');manager.scroll_into_view_if_needed()
            checks=[]
            def open_tab(name):
                with context.expect_page() as result:manager.locator('tbody tr').filter(has_text=name).dblclick()
                tab=result.value;expect(tab.locator('iframe')).to_be_visible();expect(tab.locator('.el-loading-mask:visible')).to_have_count(0)
                return tab
            def field(tab):return tab.frame_locator('iframe').locator('.office-mock-content')
            def saved(tab):expect(tab.get_by_text('已保存，可继续编辑',exact=True)).to_be_visible(timeout=15000)
            def close(tab):tab.get_by_role('button',name='关闭',exact=True).click();expect(tab.get_by_text('编辑已结束',exact=True)).to_be_visible();tab.close()
            for name in ['项目说明.docx','预算.xlsx']:
                tab=open_tab(name);prose=field(tab);expect(prose).to_be_visible();tab.wait_for_timeout(250)
                button=tab.get_by_role('button',name='保存为新版本',exact=True);expect(button).to_have_text('保存')
                assert not tab.locator('.office-page-footer').count()
                box=button.bounding_box();assert box['width']<100 and box['height']<=26 and box['x']>1250 and box['y']<15,box
                checks+=['右上角小保存按钮且底部无占位：'+name]
                before=len(commits);node=tab.locator('iframe').element_handle();sid=list(office_sessions)[-1]
                prose.fill('CtrlS跨域编辑区保存：'+name)
                prose.press('Control+s')
                saved(tab)
                assert len(commits)==before+1 and office_sessions[sid]['state']=='open' and node.evaluate('el=>el.isConnected')
                expect(prose).to_have_value('CtrlS跨域编辑区保存：'+name)
                checks+=['跨域编辑区Ctrl+S等待同步后保存并保留现场：'+name]
                prose.press('Control+s');tab.wait_for_timeout(500);assert len(commits)==before+1
                checks+=['无修改快捷保存不新增版本：'+name]
                prose.fill('重复快捷键只保存一次：'+name)
                for _ in range(5):prose.press('Control+s')
                saved(tab);assert len(commits)==before+2 and node.evaluate('el=>el.isConnected')
                checks+=['快速重复快捷键合并为一次业务保存：'+name]
                prose.fill('外层页面快捷保存：'+name)
                tab.locator('.office-page-header').click(position={'x':10,'y':10});tab.keyboard.press('Control+s');saved(tab)
                assert len(commits)==before+3
                checks+=['外层页面Ctrl+S调用同一保存流程：'+name]
                prose.fill('按钮保存：'+name);expect(button).to_be_enabled();button.click();saved(tab);assert len(commits)==before+4
                checks+=['右上角按钮连续保存及同一会话：'+name]
                for width,height in [(390,844),(1920,1080)]:
                    tab.set_viewport_size({'width':width,'height':height});box=button.bounding_box()
                    assert box['x']>=0 and box['x']+box['width']<=width+1 and box['y']+box['height']<=height
                checks+=['小屏和大屏右上角按钮始终可见：'+name]
                # 来自父页面自己的伪造 message，不能冒充编辑器源窗口。
                prose.fill('保留未保存修改');tab.wait_for_timeout(400)
                tab.evaluate("window.postMessage({channel:'xinshi-office-save-v1',type:'save',nonce:'bad'},location.origin)")
                tab.wait_for_timeout(250);assert len(commits)==before+4
                checks+=['伪造消息不触发保存：'+name]
                tab.get_by_role('button',name='关闭',exact=True).click();tab.locator('.el-message-box:visible').get_by_role('button',name='放弃修改',exact=True).click();tab.close()
                office_readonly[0]=True;tab=open_tab(name);tab.wait_for_timeout(200);field(tab).press('Control+s');tab.wait_for_timeout(400)
                assert tab.get_by_role('button',name='保存为新版本').count()==0 and len(commits)==before+4
                checks+=['只读快捷键不能保存：'+name];close(tab);office_readonly[0]=False
            assert not errors,errors
            report={'status':'passed','verification':'跨域iframe、SDK和业务API模拟；非真实ONLYOFFICE验收','checks':checks,'page_errors':errors}
            (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
            browser.close()
    finally:
        process.terminate();process.wait(timeout=10);log.close()

if __name__=='__main__':run()
