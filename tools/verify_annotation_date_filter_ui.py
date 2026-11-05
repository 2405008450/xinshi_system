"""标注高级筛选日期面板回归；全部 API 使用隔离响应，不连接业务数据库。"""
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def run():
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('只允许在本机项目目录执行隔离验收')
    out = ROOT / '.tmp' / 'annotation-date-filter-ui'
    out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    base_url = f'http://127.0.0.1:{port}'
    queries, unexpected, errors = [], [], []

    def api(route):
        request = route.request
        url = urlparse(request.url)
        path = url.path.removeprefix('/api')
        result = []
        if request.method not in ('GET', 'HEAD') and path != '/project-arrangements/annotation-status-reminder':
            unexpected.append((request.method, path))
        if path == '/auth/session':
            result = dict(id='date-filter-qa', username='date-filter-qa', full_name='日期筛选验收',
                          roles=['admin'], permissions=['projects:read', 'projects:write'])
        elif path == '/openapi.json':
            result = {'paths': {'/projects/annotation/page': {'get': {}}}}
        elif path == '/projects/annotation/page':
            queries.append(parse_qs(url.query))
            result = dict(items=[], total=0)
        elif 'source-statuses' in path:
            result = {}
        route.fulfill(status=200, json=result)

    with (out / 'preview.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            ['node', 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1',
             '--port', str(port), '--strictPort'], cwd=ROOT / 'frontend',
            stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for _ in range(50):
                if process.poll() is not None:
                    raise RuntimeError('预览服务启动失败，见 preview.log')
                try:
                    urlopen(base_url, timeout=1).close()
                    break
                except OSError:
                    time.sleep(.2)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, channel='chrome')
                context = browser.new_context(viewport=dict(width=1500, height=960), timezone_id='Asia/Hong_Kong')
                context.route('**/api/**', api)
                context.add_init_script("localStorage.setItem('token','mock-only');localStorage.setItem('user_name','date-filter-qa')")
                page = context.new_page()
                page.set_default_timeout(5000)
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base_url + '/annotation-details')
                panel = page.locator('.annotation-advanced-popover:visible')
                calendar = page.locator('.el-date-range-picker:visible')
                page.get_by_role('button', name='高级筛选', exact=True).click()
                expect(panel).to_be_visible()
                # 先复现原始场景：不搜索字段，滚动到创建时间后打开日期面板。
                field = panel.locator('.compact-filter-cell').filter(has=page.locator('.compact-filter-cell__label', has_text='创建时间'))
                field.get_by_placeholder('开始', exact=True).click()
                expect(calendar).to_be_visible()
                before = len(queries)
                left = calendar.locator('.el-date-range-picker__content.is-left')
                heading = left.locator('.el-date-range-picker__header div')
                initial = heading.inner_text()
                left.locator('button.arrow-left').click()
                page.wait_for_timeout(500)
                expect(panel).to_be_visible()
                expect(calendar).to_be_visible()
                expect(heading).not_to_have_text(initial)
                left.locator('button.arrow-right').click()
                expect(heading).to_have_text(initial)
                left.locator('button.d-arrow-left').click()
                expect(calendar).to_be_visible()
                left.locator('button.d-arrow-right').click()
                expect(heading).to_have_text(initial)
                assert len(queries) == before, '切换月份不应执行查询'
                left.locator('td.available').filter(has_text='10').first.click()
                left.locator('td.available').filter(has_text='15').first.click()
                expect(calendar).not_to_be_visible()
                expect(panel).to_be_visible()
                expect(page.get_by_role('button', name='高级筛选', exact=False).filter(has=page.locator('.advanced-filter-count'))).to_be_visible()
                expect(field.get_by_placeholder('开始', exact=True)).not_to_have_value('')
                # 日期原样传递，列表查询复用同一字段范围。
                page.wait_for_timeout(500)
                filters = json.loads(queries[-1]['field_filters'][0])
                assert filters['created_at']['from'].endswith('-10')
                assert filters['created_at']['to'].endswith('-15')
                page.locator('.card-header > span').first.click()
                expect(panel).not_to_be_visible()
                page.wait_for_timeout(400)
                page.get_by_role('button', name='高级筛选', exact=False).filter(has=page.locator('.advanced-filter-count')).click()
                expect(field.get_by_placeholder('开始', exact=True)).not_to_have_value('')
                panel.get_by_role('button', name='清空高级条件', exact=True).click()
                expect(field.get_by_placeholder('开始', exact=True)).to_have_value('')
                expect(page.get_by_role('button', name='高级筛选', exact=True)).to_be_visible()
                # 更新时间共用日期控件，同样可以翻月；日历打开时点击外部仍可关闭。
                updated = panel.locator('.compact-filter-cell').filter(has=page.locator('.compact-filter-cell__label', has_text='更新时间'))
                updated.get_by_placeholder('开始', exact=True).click()
                calendar.locator('.is-right button.arrow-right').click()
                page.wait_for_timeout(400)
                expect(panel).to_be_visible()
                expect(calendar).to_be_visible()
                page.locator('.card-header > span').first.click()
                expect(panel).not_to_be_visible()
                page.wait_for_timeout(400)
                page.set_viewport_size(dict(width=760, height=700))
                page.get_by_role('button', name='高级筛选', exact=True).click()
                expect(panel).to_be_visible()
                bounds = panel.bounding_box()
                assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= 760
                panel.get_by_placeholder('搜索筛选字段名称，支持多个关键词').fill('创建时间')
                field.get_by_placeholder('开始', exact=True).click()
                calendar.locator('.is-left button.arrow-left').click()
                page.wait_for_timeout(400)
                expect(panel).to_be_visible()
                expect(calendar).to_be_visible()
                assert calendar.evaluate('(el) => el.closest(".annotation-advanced-popover") !== null')
                assert calendar.evaluate('(el) => el.closest(".advanced-filter-body") === null')
                page.screenshot(path=str(out / 'calendar-small-viewport.png'), full_page=True)
                calendar_bounds = calendar.bounding_box()
                assert calendar_bounds['y'] >= 0 and calendar_bounds['y'] + calendar_bounds['height'] <= 700, calendar_bounds
                assert calendar.evaluate('''el => {const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height-20))}'''), '日期面板底部不能被浮窗裁切'
                page.locator('.card-header > span').first.click()
                expect(panel).not_to_be_visible()
                page.wait_for_timeout(400)
                page.get_by_role('button', name='高级筛选', exact=True).click()
                panel.get_by_role('button', name='关闭', exact=True).click()
                expect(panel).not_to_be_visible()
                assert not unexpected, unexpected
                assert not errors, errors
                page.screenshot(path=str(out / 'verified.png'), full_page=True)
                browser.close()
                print('PASS: month/year navigation, date range, filter count, outside close, persistence and clear')
        except Exception:
            print('Page errors:', errors)
            print('Queries:', queries[-3:])
            raise
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    run()
