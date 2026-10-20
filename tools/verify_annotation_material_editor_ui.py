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
    out = ROOT / '.tmp' / 'material-editor-ui'
    out.mkdir(parents=True, exist_ok=True)
    docx_bytes = docx_fixture(out / 'fixture.docx')
    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', str(PORT), '--strictPort'],
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

    def latest(file_id):
        return max((row for row in rows if row['file_id'] == file_id), key=lambda row: row['version_no'])

    def route_api(route):
        request = route.request
        path = urlparse(request.url).path.removeprefix('/api')
        method, result, status = request.method, [], 200
        if path == '/auth/session':
            result = dict(id=UID, username='qa', full_name='验收用户', roles=['admin'], permissions=['projects:read', 'projects:write'])
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

            # 1. GBK + CRLF 文本：提示编码转换，保存为 UTF-8 并保留 CRLF。
            dialog, manager = open_form()
            select(manager, '报价.pdf')
            expect(manager.get_by_role('button', name='在线编辑')).to_be_disabled()
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

            # 3. docx：解析标题和表格，编辑后生成 docx；409 冲突保留内容。
            select(manager, '项目说明.docx')
            manager.get_by_role('button', name='在线编辑').click()
            prose = editor.locator('.material-docx__prose')
            expect(prose.locator('h1')).to_have_text('项目详情说明')
            expect(prose.locator('table')).to_contain_text('英语')
            expect(editor.get_by_text('页眉页脚、批注、修订')).to_be_visible()
            prose.locator('p').filter(has_text='原始段落').click()
            page.keyboard.press('End'); page.keyboard.type('，在线补充')
            # 固定底部：正文滚到底部时操作栏仍在视口内，只有正文滚动。
            body = editor.locator('.el-dialog__body')
            body.evaluate('element => { element.scrollTop = element.scrollHeight }')
            footer = editor.locator('.el-dialog__footer').bounding_box()
            assert footer['y'] + footer['height'] <= 1001, footer
            assert page.evaluate('document.scrollingElement.scrollTop') == 0
            conflict_next[0] = True
            editor.get_by_role('button', name='保存为新版本').click()
            expect(page.locator('.el-message--error')).to_contain_text('已被他人更新')
            expect(editor).to_be_visible()
            expect(prose).to_contain_text('在线补充')
            editor.get_by_role('button', name='保存为新版本').click()
            expect(editor).not_to_be_visible()
            saved = commits[-1]
            assert saved['file'] == '项目说明.docx' and saved['data'][:2] == b'PK', saved['file']
            checks += ['docx 标题表格解析', '有损格式提示', '正文独立滚动及底部固定', '409 冲突保留内容', '保存生成有效 docx']

            # 4. 拖动、视口边界与重新打开复位。
            select(manager, '项目说明.docx')
            manager.get_by_role('button', name='在线编辑').click()
            expect(prose).to_contain_text('在线补充')
            expect(prose).to_contain_text('原始段落')
            panel = editor
            page.wait_for_timeout(350)
            initial = panel.bounding_box()
            header = editor.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x'] + 30, header['y'] + 12); page.mouse.down(); page.mouse.move(header['x'] + 130, header['y'] + 60, steps=8); page.mouse.up()
            moved = panel.bounding_box()
            assert abs(moved['x'] - initial['x']) > 30, (initial, moved)
            page.mouse.move(moved['x'] + 30, moved['y'] + 12); page.mouse.down(); page.mouse.move(3000, 2000, steps=8); page.mouse.up()
            bounded = panel.bounding_box()
            assert bounded['x'] >= -1 and bounded['y'] >= -1 and bounded['x'] + bounded['width'] <= 1441, bounded
            name_box = editor.locator('.material-editor-title__name')
            assert name_box.evaluate('element => getComputedStyle(element).userSelect') == 'text'
            editor.get_by_role('button', name='取消', exact=True).click()
            expect(editor).not_to_be_visible()
            select(manager, '项目说明.docx')
            manager.get_by_role('button', name='在线编辑').click()
            page.wait_for_timeout(350)
            reopened = panel.bounding_box()
            assert abs(reopened['x'] - initial['x']) < 3, (initial, reopened)
            editor.get_by_role('button', name='取消', exact=True).click()
            checks += ['标题栏拖动', '无法拖出视口', '文件名可复制', '重新打开位置复位']

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

            # 7. 只读资料浮层：浮层关闭后编辑器仍保留，并可保存。
            page.get_by_role('button', name='项目资料', exact=True).first.click()
            popover = page.locator('.annotation-material-popover:visible')
            select(popover, '项目说明.docx')
            popover.get_by_role('button', name='在线编辑').click()
            expect(editor).to_be_visible()
            expect(prose.locator('h1')).to_have_text('项目详情说明')
            page.wait_for_timeout(500)
            assert_editor_on_top()
            prose.locator('h1').click(); page.keyboard.press('End'); page.keyboard.type('（浮层）')
            page.screenshot(path=str(out / 'docx-editor.png'))
            editor.get_by_role('button', name='保存为新版本').click()
            expect(editor).not_to_be_visible()
            assert commits[-1]['file'] == '项目说明.docx' and len(commits) == 3
            page.wait_for_timeout(400)
            if not page.locator('.annotation-material-popover:visible').count():
                page.get_by_role('button', name='项目资料', exact=True).first.click()
            popover = page.locator('.annotation-material-popover:visible')
            select(popover, '项目说明.docx')
            expect(popover.locator('.explorer-statusbar')).to_contain_text('V3')
            page.mouse.click(1400, 980)
            expect(popover).not_to_be_visible()
            checks += ['只读浮层入口', '编辑器位于浮层之上', '保存后浮层列表刷新']

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

            assert not errors, errors
            report = {'status': 'passed', 'checks': checks, 'page_errors': errors}
            (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False))
            browser.close()
    finally:
        process.terminate(); process.wait(timeout=10); log.close()


if __name__ == '__main__':
    run()
