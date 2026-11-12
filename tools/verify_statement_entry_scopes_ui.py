"""验证对账单两个入口和行操作菜单，所有业务请求均模拟。"""
import json
import re
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'
ROUTE = '/statement-entry-scopes-test'


def run():
    compiled = urlopen(BASE + '/src/views/project/ProjectWorkspace.vue', timeout=15).read().decode()

    def dependency(name):
        return json.dumps(re.search(r'from ["\']([^"\']*/' + name + r'\.js[^"\']*)', compiled).group(1))

    html = '''<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="/node_modules/element-plus/dist/index.css">
<div id="app"></div><script type="module">
import {createApp,h} from VUE;
import {createRouter,createWebHistory} from ROUTER;
import Finance from '/src/views/project/translation/CustomerFinance.vue';
createApp({render:()=>h(Finance,{clientId:'c1',initialMonth:'2026-10'})})
  .use(createRouter({history:createWebHistory(),routes:[{path:ROUTE,component:{render:()=>null}}]})).mount('#app');
</script>'''.replace('from VUE', 'from '+dependency('vue')).replace('from ROUTER', 'from '+dependency('vue-router')).replace('path:ROUTE', 'path:'+json.dumps(ROUTE))

    def project(id_, month, name, client, required):
        return dict(id=id_, root_id=id_, order_no=f'TP-26{month}01-{id_[1:]:0>3}', project_name=name,
                    client_id=client, client_short_name='甲客户' if client=='c1' else '乙客户',
                    billing_month=f'2026-{month}', client_manager='测试经理', statement_required=required,
                    pricing_mode='fixed', currency='CNY', children=[], prices=[], word_count_matrix={})

    projects = [
        project('p1','10','当月需要的项目','c1',True),
        project('p2','10','当月无需的项目','c1',False),
        project('p3','09','其他月份项目','c1',True),
        project('p4','10','其他客户项目','c2',True),
    ]
    calls = []
    errors = []
    workspace = dict(client_id='c1', revision=0, documents=[], payload={'tasks':{}}, pending_tasks=[])

    fixed_statement = dict(
        company='测试公司', title='对账单', client_name='甲客户', month='2026-10', months=['2026-10'],
        rows=[dict(_row_id='fixed-1', task_ids=['p1'], order_no=projects[0]['order_no'], project_name=projects[0]['project_name'],
                   language_pair='中文→英语', pricing_mode='fixed', basis='固定收费\n客户统计：字数 1,234、页数 5',
                   unit_price=None, quantity=None, subtotal='500.00', currency='CNY')],
        totals={'CNY':'500.00'}, pending=[], settings={}, tax_included=False,
    )

    def api(route):
        parsed = urlparse(route.request.url)
        path, query = parsed.path, parse_qs(parsed.query)
        body = route.request.post_data_json if route.request.method in ('POST','PUT') else None
        calls.append((path,query,body))
        if path.endswith('/statement-customer-groups'):
            result = dict(items=[dict(id=id_, name=name, short_name=name, project_count=1)
                                 for id_,name in [('c1','甲客户'),('c2','乙客户')]], total=2)
        elif path.endswith('/statement-required'):
            projects[1]['statement_required'] = body['statement_required']
            result = {'id':'p2','statement_required':True,'affected_count':1}
        elif path.endswith('/translation-statement-workspaces/c1'):
            result = workspace
        elif path.endswith('/translation-statement-workspaces/import'):
            result = dict(workspace, imported=len(body['order_ids']), existing=0,
                          documents=[{'id':'board-1','name':'测试对账单','statement':fixed_statement}])
        elif path.endswith('/page'):
            clients = query.get('client_ids', query.get('client_id', ['c1','c2']))
            months = query.get('billing_month', ['2026-10','2026-09'])
            rows = [row for row in projects if row['client_id'] in clients and row['billing_month'] in months
                    and (query.get('statement_required')!=['true'] or row['statement_required'])]
            result = dict(items=rows,total=len(rows),client_subtotals=[])
        else:
            result = []
        route.fulfill(content_type='application/json', body=json.dumps(result,ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        page = browser.new_page(viewport={'width':1600,'height':1000})
        page.set_default_timeout(12000)
        page.add_init_script("localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write']))")
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.route(re.compile('^http://localhost:3000/api/'),api)
        page.route(BASE+ROUTE,lambda route:route.fulfill(content_type='text/html',body=html))
        page.goto(BASE+ROUTE)
        dialog = page.locator('.customer-statement-dialog:visible')
        page.locator('.finance-heading').get_by_role('button',name='对账单',exact=True).click()
        expect(dialog.locator('.client-title')).to_have_count(2)
        expect(dialog).to_contain_text('乙客户')
        request = next(query for path,query,_ in calls if path.endswith('/statement-customer-groups'))
        assert request['billing_month']==['2026-10'] and request['statement_required']==['true']
        assert not any(key in request for key in ('only_mine','manager_ids','client_ids','client_id'))
        dialog.get_by_role('button',name='关闭',exact=True).click()
        optional_row = page.locator('.finance-project-table .el-table__body tr').filter(has_text='当月无需的项目')
        optional_row.get_by_role('button',name='更多操作',exact=True).click()
        page.get_by_role('menuitem',name='对账单',exact=True).click()
        expect(page.get_by_text('TP-261001-002 已标为「无需对账单」',exact=False)).to_be_visible()
        expect(dialog.locator('.statement-client-context')).to_have_text('甲客户 · 2026-10')
        table = dialog.locator('.finance-project-table')
        expect(table).to_contain_text('当月需要的项目')
        expect(table).to_contain_text('当月无需的项目')
        expect(table).not_to_contain_text('其他月份项目')
        expect(dialog).not_to_contain_text('乙客户')
        expect(dialog.locator('.client-title')).to_have_count(0)
        generate = dialog.get_by_role('button',name='生成对账单',exact=True)
        generate.click()
        page.get_by_role('button',name='确认并记录',exact=True).click()
        expect(page.get_by_text('新增 1 项',exact=False)).to_be_visible()
        paper = dialog.locator('.statement-board-content .statement-paper')
        expect(paper.get_by_role('columnheader',name='固定价格',exact=True)).to_be_visible()
        expect(paper.get_by_role('columnheader',name='单价',exact=True)).to_have_count(0)
        expect(paper).to_contain_text('字数 1,234、页数 5')
        expect(paper.locator('tbody')).to_contain_text('CNY 500.00')
        imported = [body for path,_,body in calls if path.endswith('/translation-statement-workspaces/import')]
        assert imported[-1]['order_ids']==['p1'] and imported[-1]['required_only'] is True
        table.get_by_role('checkbox',name='TP-261001-002 是否需对账单').locator('xpath=ancestor::label').get_by_text('无需',exact=True).click()
        page.get_by_role('button',name='确认',exact=True).click()
        expect(table.get_by_role('checkbox',name='TP-261001-002 是否需对账单')).to_be_checked()
        changed = [body for path,_,body in calls if path.endswith('/statement-required')]
        assert not changed[-1].get('statement_sync') and not changed[-1].get('statement_customer_sync')
        assert not errors, errors
        browser.close()
    print('PASS: required customers for month, row-scoped all projects, optional exclusion and reconfirmation, ellipsis menu')


if __name__ == '__main__':
    run()
