"""稿件分页浏览器验收；拦截全部 API，不连接业务库或发送邮件。"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'
OUTPUT = Path(__file__).resolve().parents[1] / 'artifacts' / 'manuscript-pagination'


def run():
    compiled = urlopen(BASE + '/src/views/manuscript/ManuscriptArrangements.vue').read().decode()
    def dependency(name):
        return json.dumps(re.search(r'from ["\']([^"\']*/' + name + r'\.js[^"\']*)', compiled).group(1))
    html = '''<!doctype html><meta charset="UTF-8"><div id="app"></div><script type="module">
    import {createApp} from VUE; import {createRouter,createWebHistory} from ROUTER;
    import Component from '/src/views/manuscript/ManuscriptArrangements.vue';
    import App from '/src/App.vue';
    import AppForm from '/src/components/common/AppForm.vue';
    import Dialog from '/src/components/common/DraggableFormDialog.vue';
    import '/src/styles/theme.css'; import '/src/styles/common.css';
    const router=createRouter({history:createWebHistory(),routes:[{path:'/:pathMatch(.*)*',component:Component}]});
    const app=createApp(App);app.component('AppForm',AppForm);
    app.component('DraggableFormDialog',Dialog);app.use(router);app.mount('#app');
    </script>'''.replace('from VUE', 'from ' + dependency('vue')).replace('from ROUTER', 'from ' + dependency('vue-router'))
    project = dict(entity_type='project', translation_project_id='qa-project', order_no='TP-QA-001',
        project_name='隔离分页验收', project_status='confirmed', can_manage_manuscript=True,
        word_count_matrix={}, customer_deadline_time='2026-11-05T12:00:00+08:00')
    def dispatch(index):
        return dict(id=f'batch-{index}', entity_type='project', translation_project_id='qa-project',
            order_no_snapshot='TP-QA-001', project_name_snapshot=f'分页记录{index:02}',
            status='draft' if index == 0 else 'sent', arrangements=[], can_manage_manuscript=True,
            created_at='2026-11-04T12:00:00.123456+08:00', updated_at='2026-11-04T12:00:00.123456+08:00')
    records = [dispatch(i) for i in range(22, -1, -1)]
    calls, errors, writes, delayed = [], [], [], []
    def api(route):
        path = urlparse(route.request.url).path
        params = parse_qs(urlparse(route.request.url).query)
        if route.request.method not in ('GET', 'HEAD'):
            writes.append((route.request.method, path))
        if path.endswith('/manuscript-arrangements/context'):
            result = dict(active_projects=dict(items=[project], total=1, overdue_total=0, due_soon_total=0), translators=[])
        elif path.endswith('/manuscript-arrangements/batches/page'):
            calls.append(params)
            keyword = params.get('keyword', [''])[0]
            if keyword == '旧请求':
                delayed.append(route)
                return
            filtered = [r for r in records if keyword in r['project_name_snapshot']]
            limit = int(params['limit'][0]); skip = int(params['skip'][0])
            skip = min(skip, ((len(filtered) - 1) // limit) * limit) if filtered else 0
            workbench = [dispatch(22), dispatch(0)] if params.get('project_id') else []
            result = dict(items=filtered[skip:skip+limit], total=len(filtered), skip=skip, limit=limit,
                workbench_items=workbench, creator_options=[])
        elif path.endswith('/manuscript-arrangements/mail-status'):
            result = dict(mode='disabled', configured=False, detail='隔离验收不发送邮件')
        else:
            result = []
        route.fulfill(content_type='application/json', body=json.dumps(result, ensure_ascii=False))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport=dict(width=1920, height=1080), timezone_id='America/Los_Angeles', service_workers='block')
        context.add_init_script("localStorage.setItem('user_id','qa-user');localStorage.setItem('user_permissions','[\"*\"]');localStorage.setItem('user_roles','[\"超级管理员\"]');")
        context.route(BASE + '/api/**', api)
        context.route(re.compile(r'^http://localhost:3000/translation-details(?:\?.*)?$'),
            lambda route: route.fulfill(content_type='text/html', body=html) if route.request.resource_type == 'document' else route.continue_())
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/translation-details?section=manuscript')
        if errors:
            raise AssertionError(errors)
        table = page.locator('.records-panel')
        search = table.get_by_placeholder('搜索订单、项目、译员或邮箱')
        expect(table.get_by_text('分页记录22', exact=True)).to_be_visible()
        expect(table.locator('.el-pagination__total')).to_have_text('共 23 条')
        # 上一条请求尚未完成时发起新查询，迟到的旧响应不能覆盖新数据。
        search.fill('旧请求')
        search.press('Enter')
        page.wait_for_timeout(50)
        assert delayed
        search.fill('分页记录03')
        search.press('Enter')
        expect(table.get_by_text('分页记录03', exact=True)).to_be_visible()
        delayed[0].fulfill(content_type='application/json', body=json.dumps(dict(
            items=records[:10], total=23, skip=0, limit=10, workbench_items=[])))
        expect(table.locator('.el-pagination__total')).to_have_text('共 1 条')
        expect(table.get_by_text('分页记录03', exact=True)).to_be_visible()
        search.fill('')
        expect(table.locator('.el-pagination__total')).to_have_text('共 23 条')
        assert calls[-1]['limit'] == ['10'] and calls[-1]['skip'] == ['0']
        table.locator('.btn-next').click()
        expect(table.get_by_text('分页记录12', exact=True)).to_be_visible()
        assert calls[-1]['skip'] == ['10']
        # 第二页选择订单，工作台应从独立数据中找到第一页之外的草稿。
        page.locator('.legacy-project-panel .el-table__row').first.click()
        expect(page.locator('.legacy-assignment-panel .el-tag').first).to_have_text('草稿')
        assert calls[-1]['project_id'] == ['qa-project']
        before = len(calls)
        search.fill('分页记录02')
        page.wait_for_timeout(200)
        assert len(calls) == before
        expect(table.get_by_text('分页记录02', exact=True)).to_be_visible()
        expect(table.locator('.el-pagination__total')).to_have_text('共 1 条')
        assert calls[-1]['skip'] == ['0']
        # 清空立即恢复列表；回车不会受到旧防抖请求影响。
        search.fill('')
        expect(table.locator('.el-pagination__total')).to_have_text('共 23 条')
        search.fill('不存在')
        search.press('Enter')
        expect(table.locator('.el-pagination__total')).to_have_text('共 0 条')
        expect(table.get_by_text('暂无数据')).to_be_visible()
        search.fill('')
        expect(table.locator('.el-pagination__total')).to_have_text('共 23 条')
        # 浏览器设为美国时区，仍显示香港业务日期时间。
        expect(table.get_by_text('2026年11月04日 12:00', exact=True).first).to_be_visible()
        OUTPUT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(OUTPUT / 'pagination.png'), full_page=True)
        assert not errors, errors
        assert not writes, writes
        summary = dict(result='passed', requests=len(calls), errors=errors, writes=writes,
            checks=['backend pagination', 'off-page workbench draft', '400ms debounce', 'clear', 'enter', 'empty', 'stale response', 'UTC+8'])
        (OUTPUT / 'result.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False))
        browser.close()


if __name__ == '__main__':
    run()
