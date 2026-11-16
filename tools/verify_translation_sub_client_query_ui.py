"""验证项目子客户查询和客户目录跳转，所有业务请求使用模拟数据。"""
import json
import re
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright


BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE + '/src/views/project/ProjectWorkspace.vue', timeout=30).read().decode()

    def dependency(name):
        return json.dumps(re.search(r'from ["\']([^"\']*/' + name + r'\.js[^"\']*)', compiled).group(1))

    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css">
<div id="app"></div><script type="module">
import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;
import Projects from '/src/views/project/translation/ProjectDetails.vue';
import Clients from '/src/views/client/Clients.vue';
import AppForm from '/src/components/common/AppForm.vue';
import Dialog from '/src/components/common/DraggableFormDialog.vue';
const router=createRouter({history:createWebHistory(),routes:[
  {path:'/translation-client-test',component:Projects},{path:'/clients',name:'Clients',component:Clients},
]});
createApp({render:()=>h(RouterView)}).component('AppForm',AppForm).component('DraggableFormDialog',Dialog)
  .use(router).mount('#app');
</script>'''.replace('from VUE', 'from ' + dependency('vue')).replace('from ROUTER', 'from ' + dependency('vue-router'))

    customer = dict(id='c1', client_id='c1', client_name='Alpha Company', client_short_name='Alpha',
                    client_code='CL-01', order_count=2, with_sub_client=1, without_sub_client=1,
                    sub_clients=[dict(id='s1', sub_client_code='SC-01', client_name='West Office', client_short_name='West')])
    orders = [
        dict(id='p1', order_no='TP-261116-001', project_name='first.pdf', sub_client_id='s1',
             sub_client_short_name='West', received_at='2026-11-16T10:00:00+08:00'),
        dict(id='p2', order_no='TP-261116-002', project_name='second.pdf', received_at='2026-11-16T11:00:00+08:00'),
    ]
    requests = []

    def api(route):
        url = urlparse(route.request.url)
        params = parse_qs(url.query)
        requests.append((url.path, params))
        if url.path.endswith('/sub-client-projects/orders'):
            presence = params.get('presence', ['all'])[0]
            items = orders if presence == 'all' else [item for item in orders
                                                      if bool(item.get('sub_client_id')) == (presence == 'with')]
        elif url.path.endswith('/sub-client-projects') or url.path == '/api/clients/page':
            items = [customer]
        else:
            items = []
        route.fulfill(json={'items':items, 'total':len(items)})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge')
        page = browser.new_page(viewport={'width':1450, 'height':960}, timezone_id='America/Los_Angeles')
        page.add_init_script("""localStorage.setItem('user_id','qa');
localStorage.setItem('user_permissions','["projects:read","clients:read"]');""")
        page.route(re.compile(r'^http://localhost:3000/api/'), api)
        page.route(BASE + '/translation-client-test', lambda route: route.fulfill(content_type='text/html', body=html))
        page.goto(BASE + '/translation-client-test')
        page.get_by_role('button', name='子客户查询', exact=True).click()
        dialog = page.locator('.translation-sub-client-query:visible')
        expect(dialog.get_by_text('Alpha Company', exact=True)).to_be_visible()
        dialog.locator('.el-table__expand-icon').first.click()
        details = dialog.locator('.sub-client-orders')
        expect(details.get_by_text('未关联子客户')).to_be_visible()
        expect(details.get_by_text('West', exact=True)).to_be_visible()
        expect(details.get_by_text('2026年11月16日 10:00', exact=True)).to_be_visible()
        details.get_by_text('无子客户', exact=True).click()
        expect(details.get_by_text('second.pdf')).to_be_visible()
        expect(details.get_by_text('first.pdf')).to_have_count(0)

        dialog.locator('.el-date-editor input').click()
        months = page.locator('.el-month-table:visible td')
        expect(months).to_have_count(12)
        months.nth(0).click()
        months.nth(2).click()
        page.locator('.el-picker-panel__footer:visible button:visible').click()
        expect(dialog.get_by_text('Alpha Company', exact=True)).to_be_visible()
        keyword = dialog.get_by_placeholder('客户全称、简称或编号', exact=True)
        keyword.fill('alpha CL-01')
        page.wait_for_timeout(600)
        last = next(params for path, params in reversed(requests) if path.endswith('/sub-client-projects'))
        assert last['keyword'] == ['alpha CL-01']
        assert {'01','03'} <= {item[-2:] for item in last['months'][0].split(',')}

        start = dialog.bounding_box()
        header = dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 160, header['y'] + 16)
        page.mouse.down()
        page.mouse.move(header['x'] + 160, header['y'] + 70, steps=5)
        page.mouse.up()
        assert dialog.bounding_box()['y'] > start['y'] + 20
        page.set_viewport_size({'width':650,'height':720})
        expect(dialog.get_by_role('button', name='关闭', exact=True)).to_be_in_viewport()
        page.set_viewport_size({'width':1450,'height':960})
        dialog.get_by_role('button', name='打开客户管理 · 子客户').click()
        directory = page.locator('.sub-client-query-dialog:visible')
        expect(directory.get_by_placeholder('输入名称、简称或编号')).to_have_value('alpha CL-01')
        expect(directory.get_by_text('Alpha Company', exact=True)).to_be_visible()
        directory.locator('.el-table__expand-icon').first.click()
        expect(directory.get_by_text('West Office')).to_be_visible()
        directory.get_by_placeholder('输入名称、简称或编号').clear()
        page.wait_for_timeout(150)
        last = next(params for path, params in reversed(requests)
                    if path == '/api/clients/page' and params.get('has_sub_clients') == ['true'])
        assert 'sub_client_query' not in last
        directory.get_by_role('button', name='关闭', exact=True).click()
        expect(directory).not_to_be_visible()
        expect(page).to_have_url(BASE + '/clients')
        browser.close()
    print('PASS: multiple months, customer search, expandable projects, presence filter, drag and client directory')


if __name__ == '__main__':
    run()
