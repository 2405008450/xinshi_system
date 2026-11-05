"""常用列表 100% 缩放布局验收；所有 API 均在浏览器内隔离，不连接业务库。"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'
OUTPUT = Path(__file__).resolve().parents[1] / 'artifacts' / 'viewport-list-layout'


def run():
    compiled = urlopen(BASE + '/src/views/project/ProjectWorkspace.vue').read().decode()
    def dependency(name):
        return re.search(r'from ["\']([^"\']*/' + name + r'\.js[^"\']*)', compiled).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><div id="app"></div><script type="module">
    import {createApp} from VUE;
    import {createRouter,createWebHistory} from ROUTER;
    import App from '/src/App.vue';
    import Layout from '/src/layout/index.vue';
    import Workspace from '/src/views/project/ProjectWorkspace.vue';
    import Annotation from '/src/views/project/AnnotationWorkspace.vue';
    import Consultations from '/src/views/client/Consultations.vue';
    import Clients from '/src/views/client/Clients.vue';
    import Talent from '/src/views/resource/TalentPool.vue';
    import Resources from '/src/views/resource/ResourceDevelopment.vue';
    import AppForm from '/src/components/common/AppForm.vue';
    import Dialog from '/src/components/common/DraggableFormDialog.vue';
    import '/src/styles/theme.css';
    import '/src/styles/common.css';
    import '/src/styles/projectSubOrders.css';
    const routes=[
      ...['translation','interpretation','recruitment'].map(module=>({path:module+'-details',component:Workspace,props:{module}})),
      {path:'annotation-details',component:Annotation},
      {path:'consultations',component:Consultations},
      {path:'clients',component:Clients},
      {path:'resource-management/talent-pool',component:Talent},
      {path:'resource-management/resource-development',component:Resources}
    ];
    const router=createRouter({history:createWebHistory(),routes:[{path:'/',component:Layout,children:routes}]});
    const app=createApp(App);app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);
    app.use(router);app.mount('#app');window.layoutTestRouter=router;
    </script>'''.replace('from VUE', 'from ' + json.dumps(dependency('vue'))).replace('from ROUTER', 'from ' + json.dumps(dependency('vue-router')))
    rows = [dict(id=f'layout-{i}', order_no=f'TP-TEST-{i:03}', project_name=f'布局验收项目 {i}', source_file_name=f'布局验收文件 {i}.docx',
                 client_short_name='布局验收客户', project_status='confirmed', status='active', name=f'验收人才 {i}',
                 client_name=f'验收客户 {i}', short_name=f'验收客户 {i}', consultation_code=f'ZX-{i}',
                 request_no=f'REQ-{i}', request_status='pending', demand_status='confirmed', items=[], sub_orders=[], sub_clients=[]) for i in range(1, 21)]
    translation_rows = [dict(row) for row in rows]
    translation_rows[0]['sub_orders'] = [dict(id='layout-child', parent_project_id='layout-1', sub_order_no='TP-TEST-001-01', project_name='布局验收子订单', project_status='confirmed')]
    errors, writes, reports = [], [], []
    state = {'empty': False}

    def api(route):
        path = urlparse(route.request.url).path
        if route.request.method not in ('GET', 'HEAD'):
            writes.append((route.request.method, path))
        if path.endswith('/page'):
            result = {'items': [] if state['empty'] else (translation_rows if '/projects/translation/' in path else rows), 'total': 0 if state['empty'] else 120}
        elif path.endswith('/departments/organization'):
            result = {'ready': True, 'membershipReady': True, 'items': [], 'people': [], 'aliases': {}}
        elif path.endswith('/resource-development/options'):
            result = {'can_write': True, 'can_enter': True, 'can_resource': True, 'can_requests': True, 'users': [], 'platforms': [], 'statuses': [], 'user_id': 'layout-qa'}
        elif path.endswith('/capabilities'):
            result = {'grandchild_orders': True, 'language_regions': True}
        elif path.endswith('/directory'):
            result = {'ready': True, 'items': []}
        elif path.endswith('/count'):
            result = 120
        elif path.endswith('/access'):
            result = {'can_enter': False, 'can_resource': True, 'can_requests': True}
        elif re.search(r'/(?:translation|interpretation|recruitment)/layout-\d+$', path):
            result = rows[0]
        else:
            result = []
        route.fulfill(content_type='application/json', body=json.dumps(result, ensure_ascii=False))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 924}, service_workers='block')
        context.add_init_script("""localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));
        localStorage.setItem('user_permissions',JSON.stringify(['*','projects:read','projects:write','clients:read','clients:write','consultations:read','consultations:write','talents:read','talents:write']));
        localStorage.setItem('user_id','layout-qa');localStorage.setItem('ui-zoom','1');""")
        context.route(BASE + '/api/**', api)
        context.route(re.compile(r'^http://localhost:3000/(?:translation-details|interpretation-details|recruitment-details|annotation-details|consultations|clients|resource-management/[^?]+)(?:\?.*)?$'),
                      lambda route: route.fulfill(content_type='text/html', body=html) if route.request.resource_type == 'document' else route.continue_())
        page = context.new_page()
        page.on('pageerror', lambda error: (errors.append(str(error)), print('PAGE ERROR', error, flush=True)))
        page.goto(BASE + '/translation-details')
        OUTPUT.mkdir(parents=True, exist_ok=True)

        def check(label):
            print('CHECK', label, flush=True)
            pagination = page.locator('.viewport-list-card .el-pagination:visible').last
            expect(pagination).to_be_visible()
            page.wait_for_timeout(250)
            measurement = page.evaluate('''() => {
              const main=document.querySelector('.main-content');
              const card=[...document.querySelectorAll('.viewport-list-card')].find(el=>el.offsetHeight);
              const pag=[...card.querySelectorAll('.el-pagination')].filter(el=>el.offsetHeight).at(-1);
              const region=card.querySelector('.viewport-list-table');
              const rect=el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right}};
              return {viewport:{width:innerWidth,height:innerHeight}, main:rect(main), card:rect(card), pagination:rect(pag), table:rect(region),
                overflow:main.scrollHeight-main.clientHeight, horizontalOverflow:main.scrollWidth-main.clientWidth,
                sidebar:rect(document.querySelector('.sidebar')),header:rect(document.querySelector('.header')),logo:rect(document.querySelector('.logo'))};
            }''')
            reports.append({'case': label, **measurement})
            if measurement['table']['height'] <= 80:
                page.screenshot(path=str(OUTPUT / 'layout-failure.png'))
            assert measurement['pagination']['bottom'] <= measurement['viewport']['height'], (label, measurement)
            assert measurement['pagination']['right'] <= measurement['viewport']['width'], (label, measurement)
            assert measurement['overflow'] <= 1 and measurement['horizontalOverflow'] <= 1, (label, measurement)
            assert measurement['table']['height'] > 80, (label, measurement)
            if measurement['viewport']['width'] > 768:
                assert abs(measurement['sidebar']['right'] - measurement['header']['x']) <= 1, (label, measurement)
                assert abs(measurement['logo']['bottom'] - measurement['header']['bottom']) <= 1, (label, measurement)

        def navigate(path):
            page.evaluate('(path)=>window.layoutTestRouter.push(path)', path)
            page.wait_for_timeout(500)
            expect(page.locator('.viewport-list-table:visible').first).to_be_visible()

        def dialog_check(button, label):
            button.click()
            dialog = page.locator('.el-dialog:visible').last
            expect(dialog).to_be_visible()
            page.wait_for_timeout(300)
            initial = dialog.bounding_box()
            footer = dialog.locator('.el-dialog__footer')
            expect(footer).to_be_visible()
            assert footer.bounding_box()['y'] + footer.bounding_box()['height'] <= page.viewport_size['height']
            dialog.evaluate('el=>el.querySelectorAll(".el-dialog__body,.editor-body").forEach(body=>body.scrollTop=body.scrollHeight)')
            assert footer.bounding_box()['y'] + footer.bounding_box()['height'] <= page.viewport_size['height']
            header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x'] + 5, header['y'] + 5)
            page.mouse.down()
            page.mouse.move(header['x'] + 45, header['y'] + 45, steps=5)
            page.mouse.up()
            moved = dialog.bounding_box()
            assert moved['y'] > initial['y'] + 10, (label, initial, moved)
            assert moved['x'] >= 0 and moved['y'] >= 0
            dialog.get_by_role('button', name='关闭窗口', exact=True).click()
            expect(dialog).not_to_be_visible()
            button.click()
            expect(dialog).to_be_visible()
            page.wait_for_timeout(300)
            reopened = dialog.bounding_box()
            assert abs(reopened['y'] - initial['y']) <= 1, (label, initial, reopened)
            dialog.get_by_role('button', name='关闭窗口', exact=True).click()
            expect(dialog).not_to_be_visible()
            check(label)

        paths = ['/translation-details', '/interpretation-details', '/annotation-details', '/recruitment-details', '/consultations', '/clients',
                 '/resource-management/talent-pool', '/resource-management/resource-development?section=requests']
        sizes = [(1366, 768)] if any(flag in sys.argv for flag in ['--quick', '--interactions']) else [(1920, 1080), (1920, 924), (1366, 768)]
        if '--mobile' in sys.argv:
            page.set_viewport_size({'width': 768, 'height': 924})
            for path in paths:
                navigate(path)
                check('768x924 ' + path)
            (OUTPUT / 'results-mobile.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
            assert not errors, errors
            browser.close()
            print(f'PASS: {len(reports)} narrow viewport scenarios')
            return
        for width, height in sizes:
            page.set_viewport_size({'width': width, 'height': height})
            for path in (paths[:1] if '--interactions' in sys.argv else paths):
                navigate(path)
                check(f'{width}x{height} {path}')
            navigate('/translation-details')
            check(f'{width}x{height} translation returned')
            page.locator('.collapse-btn').click()
            page.wait_for_timeout(300)
            check(f'{width}x{height} collapsed')
            page.locator('.collapse-btn').click()
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUTPUT / f'translation-{width}x{height}.png'))
        # 低高度视口下检查交互造成的尺寸变化和缓存页签恢复。
        page.get_by_role('button', name='展开子订单', exact=True).first.click()
        expect(page.locator('.sub-order-table:visible').first).to_be_visible()
        check('expanded child order')
        page.get_by_role('button', name='收起子订单', exact=True).first.click()
        wrap = page.locator('.viewport-list-table .el-table__body-wrapper .el-scrollbar__wrap').first
        assert wrap.evaluate('el=>el.scrollHeight>el.clientHeight')
        wrap.evaluate('el=>el.scrollTop=200')
        assert wrap.evaluate('el=>el.scrollTop') > 0
        check('table body scrolled')
        page.get_by_role('button', name='高级筛选', exact=False).click()
        expect(page.locator('.el-popover:visible').last).to_be_visible()
        check('advanced filters open')
        page.locator('.workspace-navigation').click(position={'x': 5, 'y': 5})
        page.get_by_role('button', name='字段设置', exact=True).click()
        settings = page.locator('.table-column-settings-popover:visible')
        expect(settings).to_be_visible()
        for checkbox in settings.locator('.el-checkbox-group').first.locator('.el-checkbox').all():
            if 'is-checked' in checkbox.get_attribute('class'):
                checkbox.click()
        check('all business columns hidden')
        for checkbox in settings.locator('.el-checkbox-group').first.locator('.el-checkbox').all():
            if 'is-checked' not in checkbox.get_attribute('class'):
                checkbox.click()
        check('all business columns shown')
        page.locator('.workspace-navigation').click(position={'x': 5, 'y': 5})
        page.get_by_role('button', name='删除管理', exact=True).click()
        check('delete mode')
        page.get_by_role('button', name='退出', exact=True).click()
        dialog_check(page.get_by_role('button', name='新增项目', exact=True), 'translation create dialog')
        dialog_check(page.locator('.viewport-list-table').get_by_role('button', name='编辑', exact=True).first, 'translation edit dialog')
        navigate('/translation-details?section=arrangements')
        check('arrangement tab')
        navigate('/translation-details')
        check('management tab restored')
        for path, label in [('/consultations', '新增咨询'), ('/clients', '新增客户')]:
            navigate(path)
            dialog_check(page.get_by_role('button', name=label, exact=True), label + ' dialog')
        page.locator('.client-short-name-link').first.click()
        expect(page.locator('.el-popover:visible .detail-popover')).to_be_visible()
        check('client detail popover')
        page.mouse.click(page.viewport_size['width'] - 8, 4)
        navigate('/translation-details')
        state['empty'] = True
        page.reload()
        page.wait_for_timeout(500)
        check('empty after reload')
        for path in paths[1:]:
            navigate(path)
            check('empty ' + path)
        # 页面既有的后台提醒和批量会话查询使用 POST，同样只返回模拟数据。
        assert all(path in ['/api/project-arrangements/annotation-status-reminder', '/api/project-chat/annotation/conversation-status'] for method, path in writes), writes
        assert not errors, errors
        (OUTPUT / 'results.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'PASS: {len(reports)} layout scenarios, all APIs isolated, no page errors; {OUTPUT}')
        browser.close()


if __name__ == '__main__':
    run()
