"""在调试机隔离快照中启动前端预览，用模拟接口验证真实标注页面，不写业务数据。"""
import json
import os
import re
import socket
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:12419'
PID, UID, LID = str(uuid4()), str(uuid4()), str(uuid4())
NOW = '2026-09-29T08:00:00'


def run():
    if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5' or 'xinshi_validation' not in str(ROOT):
        raise SystemExit('仅允许在局域网调试机隔离验证目录执行')
    out = ROOT / '.tmp' / 'material-ui'
    out.mkdir(parents=True, exist_ok=True)
    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '12419', '--strictPort'],
                               cwd=ROOT / 'frontend', stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    project = dict(id=PID, order_no='AP-QA-MATERIAL', project_name='资料验收项目', project_types=['text_annotation'],
                   task_description='资料管理隔离验收', client_short_name='测试客户', client_manager_id=UID,
                   project_status='initial_consultation', priority='medium', status_effective_on=NOW,
                   task_dispatched_at=NOW, task_submitted_at=None, updated_at=NOW, created_at=NOW,
                   language_items=[dict(id=str(uuid4()), source_language_id=LID, source_language_label='中文', display='中文', sequence_no=1)],
                   price_items=[], assignees=[], custom_values={}, role_assignments=[], project_path=r'\\Win-server\历史\资料')
    file_id = str(uuid4())
    rows = [dict(id=str(uuid4()), file_id=file_id, category='project', version_no=1, original_name='历史资料.txt', file_size=5, uploader_name='验收用户', created_at=NOW)]
    uploads, saves, cancels, errors = {}, [], [], []
    fail_next = [False]

    def route_api(route):
        request = route.request
        path = urlparse(request.url).path.removeprefix('/api')
        method = request.method
        result = []
        status = 200
        if path == '/auth/session':
            result = dict(id=UID, username='qa', full_name='验收用户', roles=['admin'], permissions=['projects:read', 'projects:write'])
        elif path.endswith('/material-uploads') and method == 'POST':
            if fail_next[0]:
                fail_next[0] = False
                route.fulfill(status=503, json={'detail': '模拟上传失败'}); return
            content = request.post_data_buffer or b''
            match = re.search(br'filename="([^"]+)"', content)
            name = match.group(1).decode('utf-8') if match else '资料.txt'
            key = str(uuid4())
            result = dict(id=key, original_name=name, file_size=5, uploader_name='验收用户', created_at=NOW,
                          expires_at=(datetime.utcnow() + timedelta(hours=24)).isoformat())
            uploads[key] = result
            status = 201
        elif '/material-uploads/' in path and method == 'DELETE':
            cancels.append(path.rsplit('/', 1)[-1]); route.fulfill(status=204); return
        elif path.endswith('/download'):
            route.fulfill(body='hello', headers={'Content-Type': 'application/octet-stream', 'Content-Disposition': 'attachment; filename="file.txt"'}); return
        elif path.endswith('/versions'):
            result = sorted(rows, key=lambda row: -row['version_no'])
        elif path.endswith('/materials'):
            latest = {}
            for row in sorted(rows, key=lambda row: -row['version_no']): latest.setdefault(row['file_id'], row)
            result = list(latest.values())
        elif path == '/projects/annotation/page':
            result = {'items': [project], 'total': 1}
        elif path == '/projects/annotation/' + PID:
            if method == 'PUT':
                payload = request.post_data_json
                saves.append(payload)
                changes = payload['material_changes']
                rows[:] = [row for row in rows if row['file_id'] not in changes['removed_file_ids']]
                for item in changes['additions']:
                    original = uploads[item['upload_id']]
                    target = item.get('file_id') or str(uuid4())
                    version = max([row['version_no'] for row in rows if row['file_id'] == target] or [0]) + 1
                    rows.append({**original, 'id': str(uuid4()), 'file_id': target, 'category': item['category'], 'version_no': version})
                project.update({key: value for key, value in payload.items() if key != 'material_changes'})
                project['updated_at'] = datetime.now().isoformat()
            result = project
        elif 'project-languages' in path:
            result = [{'id': LID, 'label': '中文', 'language_name': '中文'}]
        elif path.rstrip('/') == '/users' or 'role-candidates' in path:
            result = [{'id': UID, 'username': 'qa', 'full_name': '验收用户', 'is_active': True}]
        elif path.endswith('/language-reserves/lookup'):
            result = []
        elif path.endswith('/unread-count'):
            result = {'count': 0}
        route.fulfill(status=status, json=result)

    try:
        for _ in range(40):
            try:
                urlopen(BASE, timeout=1).close(); break
            except Exception: time.sleep(.25)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel='msedge')
            context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
            context.route('**/api/**', route_api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))

            def edit():
                page.goto(BASE + f'/annotation-details?projectId={PID}&openEditor=1')
                dialog = page.locator('.annotation-editor-dialog:visible')
                expect(dialog).to_be_visible()
                expect(dialog.locator('.material-manager')).to_be_attached()
                return dialog

            dialog = edit()
            field_search = dialog.locator('.project-field-search input')
            field_search.fill('项目资料')
            page.locator('.project-field-search-option').filter(has_text='项目资料').first.click()
            expect(dialog.locator('.material-manager')).to_be_visible()
            expect(dialog.get_by_text('历史资料.txt', exact=True)).to_be_visible()
            dialog.get_by_label('上传报价单', exact=True).set_input_files({'name': '取消报价.txt', 'mimeType': 'text/plain', 'buffer': b'hello'})
            expect(dialog.get_by_text('已暂存，等待保存项目')).to_be_visible()
            dialog.get_by_role('button', name='取消', exact=True).click()
            expect(dialog).not_to_be_visible()
            page.wait_for_timeout(400)
            assert cancels and not saves and len(rows) == 1

            dialog = edit()
            fail_next[0] = True
            dialog.get_by_label('为历史资料.txt上传新版').set_input_files({'name': '新版资料.txt', 'mimeType': 'text/plain', 'buffer': b'hello'})
            expect(dialog.get_by_text('模拟上传失败', exact=True)).to_be_visible()
            dialog.get_by_role('button', name='保存', exact=True).click()
            page.wait_for_timeout(400)
            assert not saves
            expect(dialog.locator('.material-manager')).to_be_visible()
            dialog.get_by_role('button', name='重试', exact=True).click()
            expect(dialog.get_by_text('已暂存，等待保存项目')).to_be_visible()
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog).not_to_be_visible(timeout=10000)
            assert len(saves) == 1 and len(rows) == 2

            dialog = edit()
            dialog.locator('.material-manager').scroll_into_view_if_needed()
            expect(dialog.get_by_text('新版资料.txt', exact=True)).to_be_visible()
            dialog.get_by_role('button', name='历史版本', exact=True).click()
            history_dialog = page.get_by_role('dialog', name='资料历史版本')
            expect(history_dialog.get_by_text('V1 · 历史资料.txt')).to_be_visible()
            expect(history_dialog.get_by_text('V2 · 新版资料.txt')).to_be_visible()
            with page.expect_download() as download:
                history_dialog.get_by_role('button', name='下载', exact=True).last.click()
            assert download.value.suggested_filename == '历史资料.txt'
            page.wait_for_timeout(350)
            history_panel = history_dialog.locator('.el-dialog')
            initial = history_panel.bounding_box()
            header = history_dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x'] + header['width'] / 2, header['y'] + 10); page.mouse.down(); page.mouse.move(header['x'] + header['width'] / 2 + 80, header['y'] + 60, steps=8); page.mouse.up()
            moved = history_panel.bounding_box()
            assert abs(moved['x'] - initial['x']) > 30, (initial, header, moved)
            moved_header = history_dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(moved_header['x'] + moved_header['width'] / 2, moved_header['y'] + 10); page.mouse.down(); page.mouse.move(3000, 2000, steps=8); page.mouse.up()
            bounded = history_panel.bounding_box()
            assert bounded['x'] >= -1 and bounded['y'] >= -1 and bounded['x'] + bounded['width'] <= 1441 and bounded['y'] + bounded['height'] <= 1001
            history_dialog.locator('.el-dialog__headerbtn').click()
            dialog.get_by_role('button', name='历史版本', exact=True).click()
            page.wait_for_timeout(350)
            reopened = history_panel.bounding_box()
            assert abs(reopened['x'] - initial['x']) < 3
            history_dialog.get_by_role('button', name='关闭', exact=True).click()
            page.set_viewport_size({'width': 390, 'height': 844})
            page.wait_for_timeout(250)
            dialog.locator('.material-manager').scroll_into_view_if_needed()
            bounds = dialog.bounding_box()
            assert bounds['width'] <= 359
            footer = dialog.locator('.el-dialog__footer').bounding_box()
            assert footer['y'] >= 0 and footer['y'] + footer['height'] <= 845
            page.evaluate('window.getSelection()?.removeAllRanges()')
            page.screenshot(path=str(out / 'editor-mobile.png'))
            dialog.get_by_role('button', name='取消', exact=True).click()
            page.set_viewport_size({'width': 1440, 'height': 1000})
            page.get_by_role('button', name='项目资料', exact=True).first.click()
            popover = page.locator('.annotation-material-popover:visible')
            expect(popover.get_by_text('新版资料.txt', exact=True)).to_be_visible()
            assert popover.locator('input[type=file]').count() == 0
            page.screenshot(path=str(out / 'readonly-popover.png'))
            page.mouse.click(1250, 90)
            page.get_by_role('button', name='新增标注项目', exact=True).click()
            dialog = page.locator('.annotation-editor-dialog:visible')
            expect(dialog.locator('.material-manager')).to_be_attached()
            dialog.get_by_label('上传合同', exact=True).set_input_files({'name': '新合同.txt', 'mimeType': 'text/plain', 'buffer': b'hello'})
            expect(dialog.get_by_text('已暂存，等待保存项目')).to_be_visible()
            dialog.get_by_role('button', name='取消', exact=True).click()
            assert not errors, errors
            report = {'status': 'passed', 'checks': ['取消上传不保存', '失败阻止保存及重试', '新版随保存生效', '历史下载', '拖动及视口边界', '重开复位', '小屏固定底部', '只读资料浮层', '新增态上传'], 'page_errors': errors}
            (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False))
            browser.close()
    finally:
        process.terminate(); process.wait(timeout=10); log.close()


if __name__ == '__main__':
    run()
