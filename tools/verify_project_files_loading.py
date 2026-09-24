"""调试机浏览器回归：拦截所有 API，验证表单加载，不读写业务数据。"""
import json
import socket
import sys
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

assert socket.gethostname().upper() == 'WIN-LOLJ8UHT2G5', '仅在局域网调试机运行'
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
project = {'id': 'qa-files', 'order_no': 'QA-FILES', 'project_name': '加载回归', 'project_status': 'pending'}
state = {'fail': True, 'calls': 0}

def intercept(route):
    path = urlparse(route.request.url).path
    result = []
    if path.endswith('/auth/session'):
        result = {'user_id': 'qa', 'username': 'qa', 'roles': ['admin'], 'permissions': ['*']}
    elif '/project-files/project/' in path:
        state['calls'] += 1
        if state['fail']:
            route.fulfill(status=503, json={'detail': '模拟网络失败'})
            return
        result = [{'id': 'file-qa', 'storage_path': 'loaded-path'}]
    elif path.endswith('/projects/translation/page'):
        result = {'items': [project], 'total': 1}
    elif path.endswith('/projects/translation/qa-files'):
        result = project
    elif path.endswith('/count'):
        result = 0
    route.fulfill(json=result)

class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory='E:/xinshi_runtime/validation-project-files', **kwargs)

    def do_GET(self):
        if self.path == '/translation-details':
            self.path = '/index.html'
        super().do_GET()

    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), PreviewHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 950})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/api/**', intercept)
    page.add_init_script("localStorage.setItem('token', 'qa-mocked-session')")
    page.goto(f'http://127.0.0.1:{server.server_port}/translation-details')
    row = page.locator('.el-table__row', has_text='QA-FILES').first
    row.get_by_role('button', name='编辑', exact=True).click()
    dialog = page.locator('.project-editor-dialog')
    dialog.get_by_role('tab', name='项目文件', exact=True).click()
    expect(dialog.get_by_role('button', name='重新加载')).to_be_visible()
    state['fail'] = False
    dialog.get_by_role('button', name='重新加载').click()
    field = dialog.locator('.el-form-item', has=page.locator('label', has_text='原文路径')).locator('input')
    expect(field).to_have_value('loaded-path')
    field.fill('unsaved-path')
    dialog.get_by_role('tab').first.click()
    dialog.get_by_role('tab', name='项目文件', exact=True).click()
    expect(field).to_have_value('unsaved-path')
    assert state['calls'] == 2, state
    dialog.get_by_role('button', name='取消', exact=True).click()
    expect(dialog).not_to_be_visible()
    row.get_by_role('button', name='编辑', exact=True).click()
    dialog.get_by_role('tab', name='项目文件', exact=True).click()
    expect(field).to_have_value('loaded-path')
    assert state['calls'] == 3, state
    page.screenshot(path='E:/xinshi_runtime/project-files-loading.png')
    assert not errors, errors
    print(json.dumps({'retry': True, 'unsaved_preserved': True, 'reopen_reload': True, 'page_errors': errors}))
    browser.close()
server.shutdown()
