"""使用构建产物和全量 API 拦截验收日志界面，不访问业务库。"""
import functools
import http.server
import json
from pathlib import Path
import threading
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.tmp/talent-edit-audit-ui'


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if not Path(self.translate_path(self.path)).is_file() and not Path(self.path).suffix:
            self.path = '/index.html'
        super().do_GET()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(ROOT / 'frontend/dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    history_requests, errors = [], []
    identifier = '00000000-0000-0000-0000-000000000001'
    record = dict(id=identifier, full_name='日志验收人才', resource_code='AUDIT-UI', status='standby',
                  capability_types=[], updated_at='2026-11-17T10:00:00.123456+08:00')
    def api(route):
        url = urlparse(route.request.url)
        path = url.path.removeprefix('/api').rstrip('/')
        result = []
        if path == '/auth/session':
            result = dict(user_id='ui-test', username='验收账号', roles=['admin'], permissions=['*'])
        elif path == '/talents/page':
            result = dict(items=[record], total=1)
        elif path.endswith('/edit-history'):
            history_requests.append(url.query)
            skip = int(parse_qs(url.query).get('skip', ['0'])[0])
            result = dict(total=21, items=[dict(id=f'event-{skip}', actor_name='补充人员', actor_account='resume-editor',
                source='manual', created_at='2026-11-17T10:15:00+08:00', changes={
                    'primary_phone': dict(before='旧电话', after='新电话'),
                    'resume_profile.self_assessment': dict(before='旧自评', after='新自评'),
                    'remarks': dict(before='旧备注', after='补充内容' * 300),
                })])
        elif path == f'/talents/{identifier}':
            result = record
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result, ensure_ascii=False))
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            context = browser.new_context(viewport=dict(width=1440, height=1000), timezone_id='America/New_York')
            context.add_init_script("localStorage.setItem('token','isolated-ui-test')")
            context.route('**/api/**', api)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            try:
                page.goto(f'http://127.0.0.1:{server.server_port}/resource-management/talents')
                button = page.get_by_role('button', name='编辑记录', exact=True).first
                expect(button).to_be_visible()
                assert not history_requests
                button.click()
                popup = page.locator('.talent-edit-history-popper:visible')
                expect(popup.get_by_text('补充人员（resume-editor）')).to_be_visible()
                expect(popup.get_by_text('手机', exact=True)).to_be_visible()
                expect(popup.get_by_text('简历补充 / 自我评价', exact=True)).to_be_visible()
                expect(popup).to_contain_text('2026年11月17日')
                assert popup.get_attribute('data-popper-placement').startswith('left')
                assert popup.locator('.history-body').evaluate('(el)=>el.scrollHeight>el.clientHeight')
                popup.locator('.history-body').evaluate('(el)=>el.scrollTop=el.scrollHeight')
                popup.locator('button.btn-next').click()
                page.wait_for_timeout(300)
                assert any('skip=20' in query for query in history_requests)
                page.screenshot(path=str(OUT / 'desktop.png'))
                page.mouse.click(20, 150)
                expect(popup).not_to_be_visible()
                page.set_viewport_size(dict(width=390, height=844))
                button.click()
                popup = page.locator('.talent-edit-history-popper:visible')
                expect(popup).to_be_visible()
                box = popup.bounding_box()
                assert box['x'] >= 0 and box['x'] + box['width'] <= 391
                page.screenshot(path=str(OUT / 'mobile.png'))
                assert not errors, errors
                print('日志按需加载、中文字段、UTC+8、分页、左侧小窗、内部滚动、小屏和无页面异常通过')
            except Exception:
                page.screenshot(path=str(OUT / 'failure.png'))
                (OUT / 'failure.txt').write_text(page.locator('body').inner_text() + '\n' + str(errors), encoding='utf-8')
                raise
            finally:
                browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    run()
