"""全部会话置顶排序与更新刷新回归；API 全部模拟。"""
import json
import re
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

base = 'http://localhost:3000'
compiled = urlopen(base + '/src/components/common/AppForm.vue').read().decode()
vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
items = [dict(key=f'discussion:{i}', projectId=str(i), kind='discussion', title=f'测试会话{i:02d}', subtitle='讨论群', pinned=False) for i in range(25)]
html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><style>#app{height:650px;display:flex;flex-direction:column}</style><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import History from '/src/components/chat/ChatSessionHistory.vue';
createApp({setup(){const revision=ref('initial');return()=>[h('button',{onClick:()=>revision.value=String(Math.random()),id:'refresh-prefs'},'模拟置顶状态更新'),h(History,{active:true,preferencesRevision:revision.value})]}}).mount('#app');</script>'''.replace('VUE', json.dumps(vue))

def api(route):
    url = urlparse(route.request.url)
    if url.path.endswith('/sessions/history'):
        params = parse_qs(url.query)
        start, size = int(params.get('offset', ['0'])[0]), int(params.get('limit', ['20'])[0])
        rows = sorted(items, key=lambda row: (not row['pinned'], row['title']))
        data = {'items': rows[start:start + size], 'total': len(rows)}
    else:
        data = {'items': [], 'total': 0}
    route.fulfill(content_type='application/json', body=json.dumps(data))

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1100, 'height': 800})
    page.route(re.compile(r'^http://localhost:3000/api/'), api)
    page.route(base + '/directory-pin-check', lambda r: r.fulfill(content_type='text/html', body=html))
    page.goto(base + '/directory-pin-check')
    rows = page.locator('.chat-history-session')
    expect(rows).to_have_count(20)
    expect(rows.first).to_contain_text('测试会话00')
    page.get_by_role('button', name='Go to next page').click()
    expect(rows).to_have_count(5)
    items[-1]['pinned'] = True
    page.locator('#refresh-prefs').click()
    expect(rows).to_have_count(20)
    expect(rows.first).to_contain_text('测试会话24')
    expect(rows.first.locator('.chat-history-session__pin')).to_have_count(1)
    page.reload()
    expect(rows.first).to_contain_text('测试会话24')
    items[-1]['pinned'] = False
    page.locator('#refresh-prefs').click()
    expect(rows.first).to_contain_text('测试会话00')
    expect(page.locator('.chat-history-session__pin')).to_have_count(0)
    browser.close()
print('PASS: directory pin refresh resets page, pinned indicator, reload persistence and unpin')
