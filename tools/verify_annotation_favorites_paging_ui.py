"""收藏夹 101 个关注项目的分页可达性回归，所有 API 使用模拟数据。"""
import json
import re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

base = 'http://localhost:3000'
compiled = urlopen(base + '/src/components/common/AppForm.vue').read().decode()
vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h} from VUE;
import {createRouter,createMemoryHistory} from '/node_modules/.vite/deps/vue-router.js';
import Inbox from '/src/components/chat/AnnotationChatInbox.vue';
import Dialog from '/src/components/common/DraggableFormDialog.vue';
const app=createApp({render:()=>h(Inbox)});
app.use(createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]}));
app.component('DraggableFormDialog',Dialog);app.mount('#app');</script>'''.replace('VUE', json.dumps(vue))
items = [dict(key=f'annotation:{i}', projectId=str(i), kind='annotation', following=True,
              title=f'收藏测试项目{i:03d}', subtitle=f'AP-{i:03d}') for i in range(1, 102)]

def api(route):
    path = route.request.url.split('?')[0]
    data = {'items': items} if path.endswith('/chat/sessions') else {'items': [], 'people': [], 'total': 0}
    route.fulfill(content_type='application/json', body=json.dumps(data, ensure_ascii=False))

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='msedge', headless=True)
    for width, height in [(1400, 900), (800, 650)]:
        context = browser.new_context(viewport={'width': width, 'height': height}, service_workers='block')
        context.add_init_script("localStorage.setItem('user_id','test');localStorage.setItem('user_permissions',JSON.stringify(['projects:read']));")
        context.route(re.compile(r'^http://localhost:3000/api/'), api)
        context.route(base + '/favorites-paging-check', lambda r: r.fulfill(content_type='text/html', body=html))
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base + '/favorites-paging-check')
        page.get_by_role('button', name='收藏夹', exact=True).click()
        panel = page.locator('.annotation-favorites-popover:visible')
        panel.get_by_role('tab', name='各类项目', exact=False).click()
        rows = panel.locator('.favorite-row')
        expect(rows).to_have_count(20)
        paging = panel.locator('.annotation-favorites-paging')
        status = paging.get_by_role('status')
        expect(status).to_contain_text('1–20 条，共 101 条')
        box = paging.bounding_box()
        assert box['y'] >= 0 and box['y'] + box['height'] <= height, box
        seen = []
        panel.locator('.favorite-group > summary').first.click()
        for index in range(6):
            seen.extend(rows.locator('.favorite-row__open small').all_text_contents())
            if index < 5:
                panel.get_by_role('button', name='Go to next page').click()
        assert len(seen) == len(set(seen)) == 101
        expect(status).to_contain_text('101–101 条，共 101 条')
        paging.locator('.el-select__wrapper').click()
        page.get_by_role('option', name='50 条/页', exact=True).click()
        expect(rows).to_have_count(50)
        panel.get_by_role('textbox', name='搜索收藏项目').fill('AP-101')
        try:
            expect(rows).to_have_count(1)
        except Exception:
            print(panel.inner_text(), errors, flush=True)
            raise
        expect(status).to_contain_text('1–1 条，共 1 条')
        assert not errors, errors
        context.close()
    browser.close()
print('PASS: 101 favorites accessible across all pages, visible pagination, 50/page and search at two viewport sizes')
