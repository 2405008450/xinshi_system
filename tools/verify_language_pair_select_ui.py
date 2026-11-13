"""真实语种选择组件隔离验收；所有接口均模拟，不写业务数据。"""
import json
import sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    base = 'http://localhost:3000'
    rows = [dict(id=str(index), label=f'测试语种{index}', shortcuts=[f'测试语种{index}']) for index in range(498)]
    rows += [dict(id='zh', code='zh-CN', label='中文（简体）', shortcuts=['中', '简中']),
             dict(id='en', code='en-US', label='英语（美国）', shortcuts=['英', '美英'])]
    html = '''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css">
    <div id="app"></div><script type="module">
    import {createApp,ref,h} from '/node_modules/.vite/deps/vue.js';
    import Select from '/src/components/LanguagePairSelect.vue';
    createApp({setup(){const value=ref('历史语种→历史译文'),opened=ref(true);return ()=>h('main',[
      h('button',{onClick:()=>opened.value=!opened.value},'切换编辑窗口'),
      h('div',{style:'width:700px;margin:30px'},[
        opened.value?h(Select,{modelValue:value.value,'onUpdate:modelValue':v=>value.value=v,allowCreate:false,allowProofreading:true}):null,
        h('output',value.value)])]);}}).mount('#app');
    </script>'''
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        page = browser.new_page(viewport={'width': 1100, 'height': 800})
        page.on('pageerror', lambda error: print(str(error)))
        requests = []
        fail = [True]
        def api(route):
            if not urlparse(route.request.url).path.startswith('/api/'):
                route.continue_()
                return
            requests.append(route.request.url)
            if fail[0]:
                fail[0] = False
                route.fulfill(status=503, content_type='application/json', body='{"detail":"模拟目录读取失败"}')
            else:
                route.fulfill(content_type='application/json', body=json.dumps(rows, ensure_ascii=False))
        page.route('**/api/**', api)
        page.route('**/language-pair-isolated-qa', lambda route: route.fulfill(content_type='text/html', body=html))
        page.goto(base + '/language-pair-isolated-qa')
        expect(page.get_by_text('重新加载语种', exact=True)).to_be_visible()
        page.get_by_text('重新加载语种', exact=True).click()
        expect(page.get_by_text('重新加载语种', exact=True)).to_have_count(0)
        expect(page.locator('output')).to_have_text('历史语种→历史译文')
        field = page.locator('input').first
        field.fill('中译英')
        option = page.locator('.language-pair-option__label').filter(has_text='中文（简体）→英语（美国）')
        expect(option).to_be_visible()
        option.click()
        expect(page.locator('output')).to_have_text('历史语种→历史译文；中文（简体）→英语（美国）')
        page.get_by_text('切换编辑窗口', exact=True).click()
        page.get_by_text('切换编辑窗口', exact=True).click()
        expect(page.locator('output')).to_contain_text('中文（简体）→英语（美国）')
        expect(page.locator('input').first).to_be_visible()
        assert len(requests) == 2, '重新打开应复用目录缓存，检索不重复请求接口'
        browser.close()
    print('PASS: 500语种、失败重试、简称检索、历史值保留、多选及重新打开缓存')


if __name__ == '__main__':
    run()
