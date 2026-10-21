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
PORT = 12421
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
    out = ROOT / '.tmp' / 'office-page-ui'
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
            result = {**office_sessions[sid], 'script_url': 'https://office.example.test/sdk.js', 'config': {
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
                    office_content[0] = request.frame.page.locator('.office-mock-content').input_value()
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
            context.route('https://office.example.test/sdk.js', lambda route: route.fulfill(content_type='application/javascript', body="""
window.DocsAPI = { DocEditor: class {
  constructor(id, config) {
    this.host = document.getElementById(id);
    const field = document.createElement('textarea'); field.className = 'office-mock-content';
    field.setAttribute('aria-label', '模拟 Word 正文'); field.style.cssText = 'width:100%;height:100%;min-height:300px';
    field.value = config.mockContent; field.readOnly = config.editorConfig.mode === 'view';
    field.oninput = () => { config.events.onDocumentStateChange({data:true}); setTimeout(() => config.events.onDocumentStateChange({data:false}), 30); };
    this.host.appendChild(field); setTimeout(() => config.events.onDocumentReady(), 30);
  }
  destroyEditor() { this.host.replaceChildren(); }
} };
"""))


            context.add_init_script("""if(location.protocol==='http:'){localStorage.setItem('token','isolated-qa');localStorage.setItem('user_id','%s');
              localStorage.setItem('user_roles','["admin"]');localStorage.setItem('user_permissions','["projects:read","projects:write"]')}""" % UID)
            context.on('page', lambda tab: tab.on('pageerror', lambda failure: errors.append(str(failure))))
            page = context.new_page()
            add_row('预算.xlsx', docx_bytes)
            page.goto(BASE + f'/annotation-details?projectId={PID}&openEditor=1')
            dialog=page.locator('.annotation-editor-dialog:visible');expect(dialog).to_be_visible()
            manager=dialog.locator('.material-manager');manager.scroll_into_view_if_needed()

            def popup(action):
                with context.expect_page() as result: action()
                tab=result.value
                tab.wait_for_url('**/annotation-office?**')
                expect(tab.locator('.office-editor-page')).to_be_visible()
                assert tab.evaluate('window.opener === null')
                assert 'token' not in tab.url and 'config' not in tab.url
                assert tab.locator('.sidebar,.el-aside,.material-office-dialog').count()==0
                return tab

            def ready(tab):
                field=tab.locator('.office-mock-content');expect(field).to_be_visible();return field

            def close_clean(tab):
                tab.get_by_role('button',name='关闭',exact=True).click()
                expect(tab.get_by_text('编辑已结束',exact=True)).to_be_visible();tab.close()

            def ensure_materials():
                expect(page.locator('.annotation-editor-dialog:visible')).to_be_visible()

            tab=popup(lambda: manager.locator('tbody tr').filter(has_text='项目说明.docx').dblclick())
            field=ready(tab)
            box=tab.locator('.office-editor-page').bounding_box()
            assert box['x']==0 and box['y']==0 and box['width']==1440 and box['height']==1000,box
            assert field.bounding_box()['width']>=1435 and field.bounding_box()['height']>=830
            field.fill('独立页面修改')
            # 浏览器刷新/关闭需原生确认；选择继续编辑应保留内容。
            dialogs=[]
            def dismiss(event): dialogs.append(event.type);event.dismiss()
            tab.on('dialog',dismiss)
            try: tab.reload(timeout=1500)
            except PlaywrightTimeout: pass  # 取消离开后不会产生新的 load 事件。
            tab.remove_listener('dialog',dismiss)
            assert dialogs==['beforeunload'];expect(field).to_have_value('独立页面修改')
            checks+=['Word双击新标签页打开','独立页面无侧栏及弹窗边距','编辑区占满页面宽度','地址不含登录凭证或Office配置','新页与来源页解除opener关联','刷新未保存内容原生确认并可取消']
            # 原项目资料关闭或导航不影响新页。
            dialog.get_by_role('button',name='取消',exact=True).click()
            expect(field).to_have_value('独立页面修改')
            checks+=['关闭项目资料后新页编辑现场保留']
            tab.get_by_role('button',name='关闭',exact=True).click()
            tab.locator('.el-message-box:visible').get_by_role('button',name='继续编辑').click()
            expect(field).to_have_value('独立页面修改')
            conflict_next[0]=True
            tab.get_by_role('button',name='保存为新版本').click()
            expect(tab.get_by_text(re.compile('已被他人更新'))).to_be_visible();expect(field).to_have_value('独立页面修改')
            tab.get_by_role('button',name='保存为新版本').click()
            expect(tab.locator('.el-message--success').last).to_contain_text('文件已保存')
            assert commits[-1]['file']=='项目说明.docx'
            expect(ready(tab)).to_have_value('独立页面修改')
            node=field.element_handle();count=len(office_sessions);committed=len(commits)
            expect(tab.get_by_role('button',name='保存为新版本')).to_be_disabled()
            field.fill('同一编辑器继续修改')
            tab.get_by_role('button',name='保存为新版本').click()
            expect(tab.get_by_text('已保存，可继续编辑',exact=True)).to_be_visible()
            assert node.evaluate('el=>el.isConnected') and len(office_sessions)==count and len(commits)==committed+1
            expect(field).to_have_value('同一编辑器继续修改')
            checks+=['关闭未保存二次确认及继续编辑','独立页面保存失败保留现场','保存新版本成功提示且不退出','同一编辑器连续保存不重建会话且保留写锁','无新修改禁用保存']
            close_clean(tab)

            # Excel 回车、工具栏、菜单统一打开独立页，跨标签页同用户也只能一个写者。
            page.goto(BASE + f'/annotation-details?projectId={PID}&openEditor=1')
            dialog=page.locator('.annotation-editor-dialog:visible');expect(dialog).to_be_visible()
            manager=dialog.locator('.material-manager');manager.scroll_into_view_if_needed()
            excel=manager.locator('tbody tr').filter(has_text='预算.xlsx')
            tab=popup(lambda:excel.press('Enter'));field=ready(tab)
            second=popup(lambda:manager.get_by_role('button',name='在线编辑',exact=True).click())
            expect(ready(second)).to_have_attribute('readonly','')
            assert second.get_by_role('button',name='保存为新版本').count()==0
            close_clean(second)
            # 小屏尺寸改变不重建 Office 会话。
            count=len(office_sessions);node=field.element_handle();field.fill('Excel独立编辑')
            for width,height in [(1920,1080),(390,844),(1440,1000)]:
                tab.set_viewport_size({'width':width,'height':height})
                box=tab.locator('.office-editor-page').bounding_box();footer=tab.locator('.office-page-header').bounding_box()
                assert box['width']==width and box['height']==height and footer['y']+footer['height']<=height+1
            assert len(office_sessions)==count and node.evaluate('el=>el.isConnected')
            tab.screenshot(path=str(out/'standalone-excel.png'))
            tab.get_by_role('button',name='保存为新版本').click();expect(tab.get_by_text('已保存，可继续编辑',exact=True)).to_be_visible()
            # 同源新页面通知来源页，列表立即刷新，不需要等定时轮询。
            expect(manager.locator('.explorer-statusbar')).to_contain_text('V2',timeout=4000)
            close_clean(tab)
            checks+=['Excel回车和在线编辑按钮打开独立页','同账号第二个标签页只读','只读无保存入口','大屏及手机宽高占满视口','右上角小按钮固定可见且无底部占位','调整窗口保留内容和Office会话','独立页保存通知原列表刷新']

            excel.get_by_role('button',name='预算.xlsx的更多操作').click()
            tab=popup(lambda:page.get_by_role('menuitem',name='在线编辑',exact=True).click());ready(tab);close_clean(tab)
            ensure_materials()
            excel.get_by_role('button',name='预算.xlsx的更多操作').click()
            page.get_by_role('menuitem',name='小窗编辑',exact=True).click()
            small=page.locator('.material-office-dialog:visible');expect(small.locator('.office-mock-content')).to_be_visible()
            small.get_by_role('button',name='最大化窗口',exact=True).click();expect(small).to_have_class(re.compile('is-maximized'))
            small.get_by_role('button',name='还原窗口',exact=True).click();small.get_by_role('button',name='取消',exact=True).click()
            checks+=['文件菜单在线编辑打开新页','保留小窗编辑及最大化还原']

            manager=dialog.locator('.material-manager')
            # 弹出窗口被拦截时提供提示，不创建会话。
            page.evaluate('window.originalOpen=window.open;window.open=()=>null')
            count=len(office_sessions);excel.dblclick()
            expect(page.locator('.el-message').filter(has_text='浏览器阻止')).to_be_visible()
            assert len(office_sessions)==count
            page.evaluate('window.open=window.originalOpen')
            # 新建两种格式在独立页命名、保存、继续编辑新文件。
            for kind,label in [('docx','Word 文档（.docx）'),('xlsx','Excel 工作簿（.xlsx）')]:
                ensure_materials()
                manager.get_by_role('button',name='新建文档',exact=True).click()
                tab=popup(lambda:page.get_by_role('menuitem',name=label,exact=True).click())
                tab.get_by_role('button',name='开始编辑',exact=True).click()
                expect(tab.locator('.el-form-item__error')).to_be_visible()
                tab.get_by_placeholder('请输入文件名称，扩展名自动补充').fill('独立新建'+kind)
                tab.get_by_role('button',name='开始编辑',exact=True).click();ready(tab).fill('新文档内容')
                tab.get_by_role('button',name='保存文件',exact=True).click();expect(tab.get_by_text('已保存，可继续编辑',exact=True)).to_be_visible()
                expect(ready(tab)).to_have_value('新文档内容')
                node=ready(tab).element_handle();count=len(office_sessions)
                ready(tab).fill('新文档保存后继续修改')
                tab.get_by_role('button',name='保存为新版本',exact=True).click()
                expect(tab.get_by_text('已保存，可继续编辑',exact=True)).to_be_visible()
                assert node.evaluate('el=>el.isConnected') and len(office_sessions)==count
                assert 'file=' in tab.url and 'create=' not in tab.url
                close_clean(tab)
            checks+=['弹窗被拦截有明确提示且不占锁','新建Word与Excel独立页文件名校验','新建首次保存更新地址且同一编辑器连续生成版本']

            office_unavailable[0]=True
            ensure_materials()
            tab=popup(lambda:excel.dblclick())
            expect(tab.get_by_text('Word 在线编辑尚未启用',exact=True)).to_be_visible()
            with tab.expect_download() as result:tab.get_by_role('button',name='下载已保存版本',exact=True).click()
            assert result.value.suggested_filename=='预算.xlsx'
            office_unavailable[0]=False
            tab.get_by_role('button',name='重新加载',exact=True).click();ready(tab);close_clean(tab)
            checks+=['文档服务故障显示重试与显式下载','重试成功后恢复编辑']
            tab=context.new_page();tab.goto(BASE+f'/annotation-office?project={PID}&file=missing')
            expect(tab.get_by_text('无法打开文档',exact=True)).to_be_visible();assert tab.locator('iframe').count()==0;tab.close()
            checks+=['无效文件地址不创建Office会话']
            assert not errors,errors
            report={'verification':'模拟ONLYOFFICE SDK与API；不写业务数据库','status':'passed','checks':checks,'page_errors':errors}
            (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False))
            browser.close()
    finally:
        process.terminate();process.wait(timeout=10);log.close()

if __name__=='__main__':run()
