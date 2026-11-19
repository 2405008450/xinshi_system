"""筛选关闭保留回归验收：本机前端、全量业务接口拦截，不连接数据库。"""
import json
import re
import functools
import http.server
import threading
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://127.0.0.1:3000'


def run():
    requests, errors = [], []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def handle(self):
            try:
                super().handle()
            except ConnectionError:
                pass  # 页面切换时可能中断尚未完成的静态资源连接。

        def log_message(self, *args):
            pass

        def do_GET(self):
            if not Path(self.translate_path(self.path)).is_file() and not Path(self.path).suffix:
                self.path = '/index.html'
            super().do_GET()

    root = Path(__file__).resolve().parents[1]
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(root / 'frontend/dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def api(route):
        path = urlparse(route.request.url).path.removeprefix('/api').rstrip('/')
        result = []
        if path == '/auth/session':
            result = dict(user_id='filter-ui-test', username='筛选验收', roles=['admin'], permissions=['*'])
        elif path == '/talents/page':
            requests.append(route.request.url)
            result = dict(items=[], total=0)
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport=dict(width=1440, height=1000))
        context.add_init_script("localStorage.setItem('token','isolated-filter-ui-test')")
        context.route('**/api/**', api)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_port}/resource-management/talents')
        trigger = page.get_by_role('button', name='状态筛选', exact=True)
        try:
            expect(trigger).to_be_visible(timeout=20000)
        except AssertionError:
            print(page.locator('body').inner_text()[:2500], errors, flush=True)
            raise
        panel = page.locator('.column-header-filter-popover:visible')

        def open_status():
            trigger.click()
            expect(panel).to_be_visible()

        def check_selected(labels):
            expect(panel.locator('.el-checkbox input:checked')).to_have_count(len(labels))
            for label in labels:
                expect(panel.get_by_role('checkbox', name=label, exact=True)).to_be_checked()

        def close_window():
            panel.get_by_role('button', name='关闭窗口', exact=True).click()
            expect(panel).to_have_count(0)

        open_status()
        panel.get_by_text('备用', exact=True).click()
        panel.get_by_text('活跃', exact=True).click()
        panel.get_by_role('button', name='确定', exact=True).click()
        expect(panel).to_have_count(0)
        expect(trigger).to_have_class(re.compile('is-active'))
        page.wait_for_timeout(500)
        assert requests and 'standby' in requests[-1] and 'active' in requests[-1], requests
        request_count = len(requests)
        open_status()
        check_selected(['备用', '活跃'])
        close_window()
        page.wait_for_timeout(500)
        assert len(requests) == request_count, '关闭不应触发清空查询'
        open_status()
        check_selected(['备用', '活跃'])
        panel.get_by_text('休眠', exact=True).click()
        panel.get_by_role('button', name='取消', exact=True).click()
        open_status()
        check_selected(['备用', '活跃'])
        panel.get_by_text('休眠', exact=True).click()
        page.locator('.page-title').click()
        expect(panel).to_have_count(0)
        open_status()
        check_selected(['备用', '活跃'])
        # 清空仍是临时选择；取消后恢复，确定后才清除正式条件。
        panel.get_by_role('button', name='清空', exact=True).click()
        panel.get_by_role('button', name='取消', exact=True).click()
        open_status()
        check_selected(['备用', '活跃'])
        panel.get_by_role('button', name='确定', exact=True).click()
        expect(panel).to_have_count(0)
        open_status()
        panel.get_by_role('button', name='清空', exact=True).click()
        panel.get_by_role('button', name='确定', exact=True).click()
        expect(trigger).not_to_have_class(re.compile('is-active'))
        print('人才总库：确认应用、关闭保留、取消/外部点击放弃草稿、明确清空 PASS', flush=True)

        # 挂载真实公共组件，覆盖组合筛选及独立时间/排除状态控件。
        source = urlopen(BASE + '/src/components/common/searchableControls.js').read().decode()
        vue_url = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', source).group(1)
        html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive} from VUE;
import Configured from '/src/components/common/ConfiguredColumnHeaderFilter.vue';
import Advanced from '/src/components/common/AdvancedFilterPopover.vue';
import Arrangement from '/src/views/project/translation/components/ArrangementFilterToolbar.vue';
const s=window.testState=reactive({status:['a'],text:'原条件',advanced:false,resets:0,queries:0,excluded:['a'],reception:['2026-11-01','2026-11-18'],deadline:[]});
const options=Array.from({length:30},(_,i)=>({label:'选项'+i,value:i===0?'a':String(i)}));
createApp({render:()=>h('main',{style:{padding:'40px',display:'grid',gap:'20px'}},[
h('button',{id:'outside'},'外部'),
h(Configured,{definition:{type:'group',label:'组合',fields:[{key:'status',label:'状态',type:'select',options},{key:'text',label:'文本',type:'text'}]},model:s,'onUpdate-field':(key,value)=>s[key]=value,onEnter:()=>s.queries++}),
h(Advanced,{visible:s.advanced,'onUpdate:visible':v=>s.advanced=v,count:1,onReset:()=>s.resets++,onClear:()=>s.text=''},{default:()=>h('input',{id:'advanced-text',value:s.text,onInput:e=>s.text=e.target.value})}),
h(Arrangement,{excluded:s.excluded,statuses:options,reception:s.reception,deadline:s.deadline,'onUpdate:excluded':v=>s.excluded=v,'onUpdate:reception':v=>s.reception=v,'onUpdate:deadline':v=>s.deadline=v})
])}).mount('#app');</script>'''.replace('from VUE', 'from ' + json.dumps(vue_url))
        page.route('**/filter-retention-test', lambda route: route.fulfill(content_type='text/html', body=html))
        page.goto(BASE + '/filter-retention-test')
        page.get_by_role('button', name='组合筛选', exact=True).click()
        group = page.locator('.column-header-filter-popover:visible')
        group.get_by_text('选项1', exact=True).click()
        group.get_by_role('button', name='确定', exact=True).click()
        expect(group).to_have_count(0)
        assert page.evaluate('testState.status') == ['a', '1']
        page.get_by_role('button', name='组合筛选', exact=True).click()
        group.get_by_text('选项2', exact=True).click()
        group.get_by_role('button', name='取消', exact=True).click()
        assert page.evaluate('testState.status') == ['a', '1']
        assert page.evaluate('testState.text') == '原条件'
        page.get_by_role('button', name=re.compile('高级筛选')).click()
        advanced = page.locator('.common-advanced-filter-popover:visible')
        advanced.locator('#advanced-text').fill('保留高级条件')
        advanced.get_by_role('button', name='关闭', exact=True).click()
        assert page.evaluate('testState.resets') == 0
        page.get_by_role('button', name=re.compile('高级筛选')).click()
        expect(advanced.locator('#advanced-text')).to_have_value('保留高级条件')
        advanced.get_by_role('button', name='重置', exact=True).click()
        assert page.evaluate('testState.resets') == 1
        page.locator('#outside').click()
        assert page.evaluate('testState.resets') == 1
        page.get_by_role('button', name=re.compile('时间筛选')).click()
        time_panel = page.locator('.arrangement-filter-popover:visible')
        expect(time_panel).to_be_visible()
        page.locator('#outside').click()
        assert page.evaluate('testState.reception') == ['2026-11-01', '2026-11-18']
        page.get_by_role('button', name=re.compile('时间筛选')).click()
        time_panel.get_by_role('button', name='清空时间条件', exact=True).click()
        assert page.evaluate('testState.reception') == []
        page.locator('#outside').click()
        page.get_by_role('button', name=re.compile('^排除状态')).click()
        exclusion = page.locator('.project-status-exclusion-popover:visible')
        exclusion.get_by_text('选项1', exact=True).click()
        page.locator('#outside').click()
        assert page.evaluate('testState.excluded') == ['a', '1']
        page.get_by_role('button', name=re.compile('^排除状态')).click()
        expect(exclusion.get_by_role('checkbox', name='选项1', exact=True)).to_be_checked()
        exclusion.get_by_role('button', name='取消全部', exact=True).click()
        assert page.evaluate('testState.excluded') == []
        assert not errors, errors
        print('组合筛选、高级筛选关闭/重置、时间筛选重开/清空、排除状态保留 PASS', flush=True)
        browser.close()
    server.shutdown()


if __name__ == '__main__':
    run()
