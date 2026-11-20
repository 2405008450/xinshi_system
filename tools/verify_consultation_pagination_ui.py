"""在本机 Vite 验证咨询分页；所有业务请求均由浏览器拦截。"""
import json
import re
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'
PATH = '/consultation-pagination-test'


def run():
    compiled = urlopen(BASE + '/src/views/client/Consultations.vue', timeout=15).read().decode()
    vue, router = (json.dumps(re.search(rf'from ["\']([^"\']*/{name}\.js[^"\']*)', compiled)[1]) for name in ('vue', 'vue-router'))
    html = '''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp} from VUE;import {createRouter,createWebHistory} from ROUTER;
import Consultations from '/src/views/client/Consultations.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
import {installAutoDrafts} from '/src/utils/autoDrafts.js';
const app=createApp(Consultations);installAutoDrafts(app);app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:location.pathname,component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE', 'from ' + vue).replace('from ROUTER', 'from ' + router)
    calls, errors, draft_reads = [], [], []
    state = {'empty_next': False}
    rows = [dict(id=f'qa-{index}', consultation_code=f'ZX-QA-{index:03}', client_short_name='甲客户' if index <= 12 else '乙客户', status='following') for index in range(1, 23)]

    def api(route):
        parsed = urlparse(route.request.url)
        result = []
        if parsed.path == '/api/consultations/page':
            params = parse_qs(parsed.query)
            skip, limit = (int(params[key][0]) for key in ('skip', 'limit'))
            filters = json.loads(params.get('field_filters', ['{}'])[0])
            calls.append((skip, limit, filters))
            value = filters.get('client_short_name', {}).get('value', '')
            matched = [row for row in rows if value in row['client_short_name']]
            result = {'items': matched[skip:skip + limit], 'total': len(matched)}
            if skip and state['empty_next']:
                state['empty_next'] = False
                result = {'items': [], 'total': 0}
        elif parsed.path == '/api/clients/':
            result = [
                {'id': '802c34ab-798a-46f2-ab7f-e15ecbe00001', 'client_short_name': '甲客户', 'client_name': '甲方公司', 'client_code': 'CL-001'},
                {'id': '802c34ab-798a-46f2-ab7f-e15ecbe00002', 'client_short_name': '乙客户', 'client_name': '乙方公司', 'client_code': 'CL-002'},
            ]
        elif parsed.path == '/api/editor-drafts':
            key = parse_qs(parsed.query).get('key', [''])[0]
            draft_reads.append(key)
            payload = {'id': key, 'data': '802c34ab-798a-46f2-ab7f-e15ecbeab761'} if 'Filter' in key else None
            result = {'payload': payload, 'revision': 1, 'updated_at': '2026-11-19T20:00:00+08:00'}
        route.fulfill(json=result)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge')
        page = browser.new_page(viewport={'width': 1600, 'height': 1000})
        page.set_default_timeout(7000)
        page.add_init_script('localStorage.setItem("user_id", "qa");localStorage.setItem("user_roles", \'["admin"]\')')
        page.route(BASE + '/api/**', api)
        page.route(BASE + PATH, lambda route: route.fulfill(content_type='text/html; charset=utf-8', body=html))
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + PATH)
        pager = page.locator('.consultations-pagination')
        table = page.locator('.consultation-list-table')
        expect(table).to_contain_text('ZX-QA-001')
        page.wait_for_timeout(1000)
        page.get_by_role('button', name='客户简称筛选', exact=True).click()
        popup = page.locator('.column-header-filter-popover:visible')
        field = popup.get_by_placeholder('输入客户简称、全称或编号', exact=True)
        expect(field).to_have_value('')
        assert not any('Filter' in key for key in draft_reads), f'筛选组件不应读取云端草稿: {draft_reads}'
        field.fill('甲客户')
        page.get_by_role('option', name=re.compile('甲客户')).click()
        expect(field).to_have_value('甲客户')
        popup.get_by_role('button',name='确定',exact=True).click()
        expect(pager.locator('.el-pagination__total')).to_contain_text('12')
        page.get_by_role('button', name='客户简称筛选', exact=True).click()
        expect(field).to_have_value('甲客户')
        expect(field).not_to_have_value(re.compile(r'^[0-9a-f]{8}-'))
        popup.get_by_role('button',name='关闭窗口',exact=True).click()
        page.get_by_text('新咨询管理', exact=True).click()
        before = len(calls)
        pager.locator('li.number').get_by_text('2', exact=True).click()
        expect(table).to_contain_text('ZX-QA-011')
        expect(table).not_to_contain_text('ZX-QA-013')
        expect(pager.locator('.el-pagination__total')).to_contain_text('12')
        assert calls[before:] == [(10, 10, {'client_short_name': {'op': 'contains', 'value': '甲客户'}})], calls[before:]
        pager.locator('li.number').get_by_text('1', exact=True).click()
        expect(table).to_contain_text('ZX-QA-001')
        state['empty_next'] = True
        before = len(calls)
        pager.locator('li.number').get_by_text('2', exact=True).click()
        expect(pager.locator('li.is-active')).to_have_text('1')
        expect(table).to_contain_text('ZX-QA-001')
        expect(pager.locator('.el-pagination__total')).to_contain_text('12')
        assert [call[0] for call in calls[before:]] == [10, 0], calls[before:]
        assert calls[-1][2] == calls[-2][2]
        pager.locator('li.number').get_by_text('2', exact=True).click()
        expect(table).to_contain_text('ZX-QA-011')
        pager.locator('.el-pagination__sizes .el-select').click()
        page.get_by_role('option', name=re.compile(r'^20\b')).click()
        expect(table).to_contain_text('ZX-QA-001')
        assert calls[-1][:2] == (0, 20)
        page.reload()
        expect(table).to_contain_text('ZX-QA-001')
        page.wait_for_timeout(1000)
        page.get_by_role('button', name='客户简称筛选', exact=True).click()
        expect(field).to_have_value('')
        expect(pager.locator('.el-pagination__total')).to_contain_text('22')
        assert not any('Filter' in key for key in draft_reads), f'刷新后筛选组件不应读取云端草稿: {draft_reads}'
        assert not errors, errors
        browser.close()
    print('PASS: 筛选后正常翻页、空页恢复、总数保持一致、调整每页数量回到第一页')


if __name__ == '__main__':
    run()
