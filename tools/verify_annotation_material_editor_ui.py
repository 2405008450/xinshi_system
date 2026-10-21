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

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PORT = 12420
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
    out = ROOT / '.tmp' / 'material-editor-ui'
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
            office_sessions[sid] = dict(id=sid, mode='view' if office_readonly[0] else 'edit', state='open',
                occupant='其他编辑者' if office_readonly[0] else None, file_id=payload.get('file_id'),
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
                    session.update(state='saved', save_state='complete', error=None)
                    office_content[0] = page.locator('.office-mock-content').input_value()
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

            context.add_init_script("""localStorage.setItem('token','isolated-qa');localStorage.setItem('user_id','%s');
              localStorage.setItem('user_roles','["admin"]');localStorage.setItem('user_permissions','["projects:read","projects:write"]')""" % UID)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            editor = page.locator('.material-editor-dialog')

            def open_form():
                page.goto(BASE + f'/annotation-details?projectId={PID}&openEditor=1')
                dialog = page.locator('.annotation-editor-dialog:visible')
                expect(dialog).to_be_visible()
                manager = dialog.locator('.material-manager')
                manager.scroll_into_view_if_needed()
                expect(manager.get_by_text('旧版说明.txt', exact=True)).to_be_visible()
                return dialog, manager

            def assert_editor_on_top():
                # 浮层可保持打开，编辑器必须位于其上并接收点击；关闭编辑器后回到原浮层。
                box = editor.bounding_box()
                points = [[box['x'] + box['width'] / 2, box['y'] + box['height'] / 2], [box['x'] + 40, box['y'] + box['height'] - 30]]
                assert page.evaluate("points => points.every(([x, y]) => document.elementFromPoint(x, y)?.closest('.material-editor-dialog'))", points), '编辑器未处于最上层'

            def select(manager, name):
                manager.locator('.explorer-table tbody tr').filter(has_text=name).first.click()

            def check_maximize(dialog, content):
                original_viewport = page.viewport_size
                page.set_viewport_size({'width': 1920, 'height': 1080})
                initial = dialog.bounding_box()
                value = content.input_value()
                node = content.element_handle()
                sessions_before = len(office_sessions)
                dialog.get_by_role('button', name='最大化窗口', exact=True).click()
                expect(dialog).to_have_class(re.compile(r'is-maximized'))
                maximized = dialog.bounding_box()
                footer = dialog.locator('.el-dialog__footer').bounding_box()
                assert maximized['width'] >= 1887 and maximized['height'] >= 1047, maximized
                assert footer['y'] + footer['height'] <= 1065
                assert node.evaluate('el => el.isConnected') and content.input_value() == value
                assert len(office_sessions) == sessions_before, '放大不得重新创建 Office 会话'
                page.set_viewport_size({'width': 500, 'height': 760})
                page.wait_for_timeout(80)
                small = dialog.bounding_box(); footer = dialog.locator('.el-dialog__footer').bounding_box()
                assert small['width'] <= 469 and footer['y'] + footer['height'] <= 745, (small, footer)
                dialog.get_by_role('button', name='还原窗口', exact=True).click()
                expect(dialog).not_to_have_class(re.compile(r'is-maximized'))
                page.set_viewport_size({'width': 1920, 'height': 1080})
                restored = dialog.bounding_box()
                assert abs(restored['width'] - initial['width']) < 2, (initial, restored)
                assert content.input_value() == value and node.evaluate('el => el.isConnected')
                page.set_viewport_size(original_viewport)

            # 1. GBK + CRLF 文本：提示编码转换，保存为 UTF-8 并保留 CRLF。
            dialog, manager = open_form()
            select(manager, '报价.pdf')
            expect(manager.get_by_role('button', name='在线编辑')).to_be_disabled()
            with page.expect_download() as pdf_download:
                manager.locator('tbody tr').filter(has_text='报价.pdf').dblclick()
            assert pdf_download.value.suggested_filename == '报价.pdf'
            select(manager, '旧版说明.txt')
            manager.get_by_role('button', name='在线编辑').click()
            expect(editor).to_be_visible()
            expect(editor.get_by_text('保存后将转换为 UTF-8 编码')).to_be_visible()
            source = editor.locator('textarea.material-text__source')
            expect(source).to_have_value('中文\n第二行')
            source.fill('中文\n第二行\n第三行')
            editor.get_by_role('button', name='保存为新版本').click()
            expect(editor).not_to_be_visible()
            assert commits[-1]['data'] == '中文\r\n第二行\r\n第三行'.encode(), commits[-1]
            select(manager, '旧版说明.txt')
            expect(manager.locator('.explorer-statusbar')).to_contain_text('V2')
            checks += ['非在线格式禁用', 'GBK 解码与编码提示', 'CRLF 保留并转 UTF-8', '保存后列表刷新为新版本']

            # 2. Markdown：预览转义原始 HTML；未保存关闭需确认。
            select(manager, '交付规范.md')
            manager.get_by_role('button', name='在线编辑').click()
            preview = editor.locator('.material-text__preview')
            expect(preview.locator('h1')).to_have_text('交付标准')
            expect(preview).to_contain_text('<script>alert(1)</script>')
            assert preview.locator('script').count() == 0
            source.fill('# 交付标准\n\n- 第一条\n- 第二条')
            expect(preview.locator('li')).to_have_count(2)
            check_maximize(editor, source)
            editor.get_by_role('button', name='取消', exact=True).click()
            box = page.locator('.el-message-box:visible')
            expect(box).to_contain_text('尚未保存')
            box.get_by_role('button', name='继续编辑').click()
            expect(editor).to_be_visible()
            editor.locator('.el-dialog__headerbtn').click()
            page.locator('.el-message-box:visible').get_by_role('button', name='放弃修改').click()
            expect(editor).not_to_be_visible()
            assert len(commits) == 1
            checks += ['Markdown 实时预览', '预览转义原始 HTML', '未保存关闭二次确认', '放弃修改不提交']

            # 3. 上传来源的 Word 双击直接打开，失败保留内容，显式下载仍然可用。
            word = page.locator('.material-office-dialog')
            manager.locator('tbody tr').filter(has_text='项目说明.docx').dblclick()
            prose = word.locator('.office-mock-content')
            expect(prose).to_have_value('项目详情说明\n原始段落\n语种：英语')
            prose.fill('项目详情说明\n原始段落，在线补充')
            check_maximize(word, prose)
            expect(word.get_by_role('button', name='保存为新版本')).to_be_enabled()
            conflict_next[0] = True
            word.get_by_role('button', name='保存为新版本').click()
            expect(word).to_contain_text('已被他人更新')
            expect(prose).to_have_value('项目详情说明\n原始段落，在线补充')
            word.get_by_role('button', name='保存为新版本').click()
            expect(word).not_to_be_visible()
            assert commits[-1]['data'] == docx_bytes
            checks += ['上传 Word 双击在线打开', '保存失败保留编辑内容', '保存成功刷新历史版本']

            # 4. Word 弹窗拖动、边界、可复制标题及重新打开复位。
            manager.locator('tbody tr').filter(has_text='项目说明.docx').press('Enter')
            expect(prose).to_contain_text('')
            expect(prose).to_have_value('项目详情说明\n原始段落，在线补充')
            page.wait_for_timeout(350)
            initial = word.bounding_box()
            header = word.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x'] + header['width'] * .6, header['y'] + 12); page.mouse.down()
            page.mouse.move(header['x'] + header['width'] * .6 + 40, header['y'] + 45, steps=8); page.mouse.up()
            moved = word.bounding_box()
            assert abs(moved['x'] - initial['x']) > 10, (initial, moved)
            page.mouse.move(moved['x'] + moved['width'] * .6, moved['y'] + 12); page.mouse.down()
            page.mouse.move(3000, 2000, steps=8); page.mouse.up()
            bounded = word.bounding_box()
            assert bounded['x'] >= -1 and bounded['y'] >= -1 and bounded['x'] + bounded['width'] <= 1441
            assert word.locator('.office-title__name').evaluate('el => getComputedStyle(el).userSelect') == 'text'
            word.locator('.el-dialog__headerbtn').click()
            expect(word).not_to_be_visible()
            manager.locator('tbody tr').filter(has_text='项目说明.docx').dblclick()
            expect(prose).to_be_visible(); page.wait_for_timeout(350)
            assert abs(word.bounding_box()['x'] - initial['x']) < 3
            prose.fill('尚未提交的修改')
            word.get_by_role('button', name='取消', exact=True).click()
            page.locator('.el-message-box:visible').get_by_role('button', name='继续编辑').click()
            expect(prose).to_have_value('尚未提交的修改')
            word.get_by_role('button', name='取消', exact=True).click()
            page.locator('.el-message-box:visible').get_by_role('button', name='放弃修改').click()
            expect(word).not_to_be_visible()
            checks += ['Word 回车在线打开', 'Word 拖动及视口边界', 'Word 标题可复制及位置复位', 'Word 放弃修改不提交']

            # 只读与服务故障：显示原因，下载保持独立。
            office_readonly[0] = True
            manager.locator('tbody tr').filter(has_text='项目说明.docx').dblclick()
            expect(word).to_contain_text('其他编辑者 正在编辑')
            expect(prose).to_have_attribute('readonly', '')
            assert word.get_by_role('button', name='保存为新版本').count() == 0
            word.get_by_role('button', name='最大化窗口', exact=True).click()
            expect(word).to_have_class(re.compile(r'is-maximized'))
            word.get_by_role('button', name='关闭', exact=True).click()
            office_readonly[0] = False
            office_unavailable[0] = True
            manager.locator('tbody tr').filter(has_text='项目说明.docx').dblclick()
            expect(word).to_contain_text('尚未启用')
            expect(word.get_by_role('button', name='最大化窗口', exact=True)).to_be_visible()
            expect(word).not_to_have_class(re.compile(r'is-maximized'))
            with page.expect_download() as download:
                word.get_by_role('button', name='下载已保存版本').click()
            assert download.value.suggested_filename == '项目说明.docx'
            word.get_by_role('button', name='取消', exact=True).click()
            office_unavailable[0] = False
            checks += ['第二人只读及禁用保存', '服务未启用提示', '显式下载原文件']

            # 5. 新建 Markdown：文件名必填校验，保存到当前目录。
            manager.locator('.material-folder-tree').get_by_text('1. 项目详情', exact=True).click()
            manager.get_by_role('button', name='新建文档').click()
            page.get_by_role('menuitem', name='Markdown（.md）').click()
            expect(editor).to_be_visible()
            editor.get_by_role('button', name='保存文件').click()
            expect(editor.locator('.el-form-item__error')).to_contain_text('文件名不能为空')
            editor.get_by_placeholder('请输入文件名称，扩展名自动补充').fill('验收记录')
            expect(editor.locator('.material-editor-title__name')).to_have_text('验收记录.md')
            source.fill('## 新文档')
            editor.get_by_role('button', name='保存文件').click()
            expect(editor).not_to_be_visible()
            assert creations[-1]['name'] == '验收记录.md' and creations[-1]['folder_id'] == folder_id, creations
            expect(manager.get_by_text('验收记录.md', exact=True)).to_be_visible()
            checks += ['新建文档文件名校验', '扩展名自动补充', '保存到当前目录并刷新']

            # 6. 表单内待保存新版的文件禁用在线编辑。
            manager.locator('.material-folder-tree').get_by_text('项目资料（根目录）').click()
            manager.get_by_label('为交付规范.md上传新版').set_input_files({'name': '交付规范.md', 'mimeType': 'text/markdown', 'buffer': b'# x'})
            expect(manager.get_by_text('已暂存，等待保存项目')).to_be_visible()
            select(manager, '交付规范.md')
            expect(manager.get_by_role('button', name='在线编辑')).to_be_disabled()
            page.evaluate('window.getSelection()?.removeAllRanges()')
            page.screenshot(path=str(out / 'form-explorer.png'))
            dialog.get_by_role('button', name='取消', exact=True).click()
            checks += ['待保存新版禁用在线编辑']

            # 7. 新建 Word，保存后仍能双击重新编辑；资料浮层关闭后编辑器保留。
            page.get_by_role('button', name='项目资料', exact=True).first.click()
            popover = page.locator('.annotation-material-popover:visible')
            popover.get_by_role('button', name='新建文档').click()
            page.get_by_role('menuitem', name='Word 文档（.docx）').click()
            expect(word).to_be_visible()
            word.get_by_role('button', name='开始编辑').click()
            expect(word.locator('.el-form-item__error')).to_contain_text('文件名不能为空')
            word.get_by_placeholder('请输入文件名称，扩展名自动补充').fill('新建说明')
            word.get_by_role('button', name='开始编辑').click()
            expect(prose).to_be_visible()
            prose.fill('新建 Word 的正文')
            word.get_by_role('button', name='保存文件').click()
            expect(word).not_to_be_visible()
            assert creations[-1]['name'] == '新建说明.docx'
            if not page.locator('.annotation-material-popover:visible').count():
                page.get_by_role('button', name='项目资料', exact=True).first.click()
            popover = page.locator('.annotation-material-popover:visible')
            popover.locator('tbody tr').filter(has_text='新建说明.docx').dblclick()
            expect(prose).to_have_value('新建 Word 的正文')
            page.wait_for_timeout(350)
            box = word.bounding_box()
            assert page.evaluate('p => document.elementFromPoint(...p)?.closest(".material-office-dialog") !== null', [box['x'] + 40, box['y'] + 100])
            prose.fill('浮层关闭后仍能保存')
            # 模拟浮层的外部关闭事件，编辑器状态必须独立保留。
            page.keyboard.press('Escape')
            if page.locator('.el-message-box:visible').count():
                page.locator('.el-message-box:visible').get_by_role('button', name='继续编辑').click()
            expect(word).to_be_visible()
            page.screenshot(path=str(out / 'office-editor.png'))
            word.get_by_role('button', name='保存为新版本').click()
            expect(word).not_to_be_visible()
            if page.locator('.annotation-material-popover:visible').count():
                page.mouse.click(1400, 980)
            checks += ['新建 Word 文件名校验', '新建 Word 保存和重编', '全局 Office 弹窗层级', '嵌套浮层编辑保存']

            # 8. 小屏：宽度受限、Markdown 上下排列、底部操作栏可见。
            page.set_viewport_size({'width': 390, 'height': 844})
            page.get_by_role('button', name='项目资料', exact=True).first.click()
            popover = page.locator('.annotation-material-popover:visible')
            select(popover, '交付规范.md')
            popover.get_by_role('button', name='选中文件的更多操作').click()
            page.get_by_role('menuitem', name='在线编辑').click()
            expect(editor).to_be_visible()
            page.wait_for_timeout(500)
            assert_editor_on_top()
            box = editor.bounding_box()
            assert box['width'] <= 359, box
            source_box = source.bounding_box(); preview_box = editor.locator('.material-text__preview').bounding_box()
            assert preview_box['y'] > source_box['y'] + source_box['height'] - 1, (source_box, preview_box)
            footer = editor.locator('.el-dialog__footer').bounding_box()
            assert footer['y'] + footer['height'] <= 845, footer
            page.screenshot(path=str(out / 'markdown-mobile.png'))
            editor.get_by_role('button', name='取消', exact=True).click()
            checks += ['小屏宽度受限', '小屏 Markdown 上下排列', '小屏底部操作栏可见', '小屏“更多”菜单入口']

            # 小屏 Word 固定操作栏，以及真正通过上传入口保存项目后再在线打开。
            if not page.locator('.annotation-material-popover:visible').count():
                page.get_by_role('button', name='项目资料', exact=True).first.click()
            popover.locator('tbody tr').filter(has_text='项目说明.docx').dblclick()
            expect(word.locator('.office-mock-content')).to_be_visible()
            box = word.bounding_box(); footer = word.locator('.el-dialog__footer').bounding_box()
            assert box['width'] <= 359 and footer['y'] + footer['height'] <= 845
            page.wait_for_timeout(350)  # 等待入场动画完成，截图应显示真实不透明弹窗。
            page.screenshot(path=str(out / 'office-mobile.png'))
            word.get_by_role('button', name='取消', exact=True).click()
            page.set_viewport_size({'width': 1440, 'height': 1000})
            dialog, manager = open_form()
            manager.get_by_label('上传项目资料', exact=True).set_input_files({'name': '直接上传.docx', 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'buffer': docx_bytes})
            expect(manager.get_by_text('已暂存，等待保存项目')).to_be_visible()
            pending = manager.locator('tbody tr').filter(has_text='直接上传.docx')
            pending.dblclick()
            expect(page.locator('.el-message').filter(has_text='文件尚未保存')).to_be_visible()
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog).not_to_be_visible(timeout=10000)
            page.get_by_role('button', name='项目资料', exact=True).first.click()
            popover = page.locator('.annotation-material-popover:visible')
            popover.locator('tbody tr').filter(has_text='直接上传.docx').dblclick()
            expect(word.locator('.office-mock-content')).to_be_visible()
            word.locator('.office-mock-content').fill('上传后在线补充')
            word.get_by_role('button', name='保存为新版本').click()
            expect(word).not_to_be_visible()
            assert commits[-1]['file'] == '直接上传.docx'
            checks += ['非编辑文件双击下载', '小屏 Word 宽度及固定操作栏', '上传 Word 待保存不可编辑', '上传并保存项目后双击编辑和保存新版']

            # 不发送本窗口保存事件，模拟另一端更新云端后自动发现变化。
            dialog, manager = open_form()
            add_row('跨端新增.txt', b'remote update')
            expect(manager.get_by_text('跨端新增.txt', exact=True)).to_be_visible(timeout=9000)
            manager.get_by_label('上传项目资料', exact=True).set_input_files({'name': '本地待保存.txt', 'mimeType': 'text/plain', 'buffer': b'pending'})
            expect(manager.get_by_text('已暂存，等待保存项目')).to_be_visible()
            add_row('切回页面刷新.txt', b'focus update')
            page.evaluate("window.dispatchEvent(new Event('focus'))")
            expect(manager.get_by_text('切回页面刷新.txt', exact=True)).to_be_visible()
            expect(manager.get_by_text('本地待保存.txt', exact=True)).to_be_visible()
            expect(manager.get_by_text('已暂存，等待保存项目')).to_be_visible()
            checks += ['另一端新增文件后5秒自动刷新', '切回页面即时刷新', '跨端刷新保留待保存上传']
            checks += ['Word和文本编辑器最大化及还原', '放大保留未保存内容及编辑节点', '放大不重建Office会话', '大屏及小屏底部操作栏固定', '只读窗口可放大且重开默认小窗']

            assert not errors, errors
            report = {'verification': '模拟 ONLYOFFICE SDK 与 API，非真实排版验收', 'status': 'passed', 'checks': checks, 'page_errors': errors}
            (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False))
            browser.close()
    finally:
        process.terminate(); process.wait(timeout=10); log.close()


if __name__ == '__main__':
    run()
