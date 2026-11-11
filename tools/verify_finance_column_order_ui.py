"""笔译财务表列排序联调，仅使用模拟接口。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect

BASE='http://localhost:3000'

def run():
    source=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=15).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',source).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;import Finance from '/src/views/project/translation/CustomerFinance.vue';const app=createApp({render:()=>h(Finance,{clientId:'c1'})});app.use(createRouter({history:createWebHistory(),routes:[{path:'/finance-column-order-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    errors=[];queries=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path.endswith('/page'):
            queries.append(parse_qs(urlparse(route.request.url).query))
            result={'items':[{'id':'p1','root_id':'p1','order_no':'TP-TEST','project_name':'排序测试项目','client_short_name':'排序客户','prices':[],'children':[],'word_count_matrix':{},'pricing_mode':'fixed','adjusted_total':'300','totals_excl_tax':{'CNY':'300'},'totals_incl_tax':{}}],'total':1,'client_subtotals':[]}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');ctx=browser.new_context(viewport={'width':1600,'height':1000})
        ctx.add_init_script("localStorage.setItem('user_id','qa-finance-column-order');localStorage.setItem('user_permissions',JSON.stringify(['projects:read']))")
        ctx.route(re.compile('^http://localhost:3000/api/'),api)
        ctx.route(BASE+'/finance-column-order-test',lambda r:r.fulfill(content_type='text/html',body=html))
        page=ctx.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/finance-column-order-test')
        table=page.locator('.finance-project-table')
        headers=table.locator('.el-table__header-wrapper thead th')
        def keys():return headers.evaluate_all('(nodes)=>nodes.map(node=>node.dataset.columnOrderKey).filter(Boolean)')
        expect(table).to_contain_text('TP-TEST')
        page.wait_for_function('document.querySelector(".finance-project-table th[data-column-order-key]")')
        assert keys()[:2]==['orderNo','projectName'],keys()
        page.get_by_role('button',name='字段设置',exact=True).click()
        popup=page.locator('.table-column-settings-popover:visible')
        handle=popup.get_by_role('button',name='拖动排序：项目名称',exact=True)
        handle.press('ArrowUp')
        expect(headers.nth(1)).to_contain_text('项目名称')
        assert keys()[:2]==['projectName','orderNo'],keys()
        page.locator('.finance-heading strong').click()
        first=table.locator('th[data-column-order-key="projectName"]');second=table.locator('th[data-column-order-key="orderNo"]')
        a=first.bounding_box();b=second.bounding_box()
        page.mouse.move(a['x']+40,a['y']+a['height']/2);page.mouse.down()
        page.mouse.move(b['x']+35,b['y']+b['height']/2,steps=12);page.mouse.up()
        expect(headers.nth(1)).to_contain_text('订单号')
        assert keys()[:2]==['orderNo','projectName'],keys()
        page.get_by_role('button',name='字段设置',exact=True).click()
        expect(popup.locator('.column-settings__item').first).to_contain_text('订单号')
        # 设置中的实际拖动同样驱动列顺序。
        a=popup.get_by_role('button',name='拖动排序：项目名称',exact=True).bounding_box()
        b=popup.get_by_role('button',name='拖动排序：订单号',exact=True).bounding_box()
        page.mouse.move(a['x']+a['width']/2,a['y']+a['height']/2);page.mouse.down()
        page.mouse.move(b['x']+b['width']/2,b['y']+b['height']/2,steps=12);page.mouse.up()
        expect(headers.nth(1)).to_contain_text('项目名称')
        page.reload();expect(table).to_contain_text('TP-TEST');expect(headers.nth(1)).to_contain_text('项目名称')
        assert keys().index('paymentStatus')==keys().index('explanation')+1
        # 四个表头直接筛选，筛选统一发送到服务端，重置全部清空。
        def select_header(label,option):
            table.get_by_role('button',name=label+'筛选',exact=True).click()
            popup=page.locator('.column-header-filter-popover:visible').filter(has_text=label+'筛选')
            popup.locator('.el-select').click()
            page.get_by_role('option',name=option,exact=True).click()
            return popup
        popup=select_header('付款状态','已付全款（含尾款）')
        page.wait_for_timeout(200);assert queries[-1]['payment_status']==['full']
        popup.get_by_role('button',name='清除筛选',exact=True).click()
        page.wait_for_timeout(200);assert 'payment_status' not in queries[-1]
        table.get_by_role('button',name='付款状态筛选',exact=True).click()
        popup=select_header('对账单','不需')
        page.wait_for_timeout(200);assert queries[-1]['statement_required']==['false']
        table.get_by_role('button',name='对账单筛选',exact=True).click()
        popup=select_header('计价模式','固定收费')
        page.wait_for_timeout(200);assert queries[-1]['pricing_mode']==['fixed'] and queries[-1]['statement_required']==['false']
        table.get_by_role('button',name='计价模式筛选',exact=True).click()
        table.get_by_role('button',name='项目状态筛选',exact=True).click()
        popup=page.locator('.column-header-filter-popover:visible').filter(has_text='项目状态筛选')
        popup.locator('label.el-checkbox').filter(has_text=re.compile('^已确认$')).click()
        popup.get_by_role('button',name='确定',exact=True).click()
        page.wait_for_timeout(200);assert queries[-1]['project_statuses']==['confirmed']
        page.get_by_role('button',name='重置',exact=True).click()
        page.wait_for_timeout(200)
        assert not any(key in queries[-1] for key in ('payment_status','statement_required','pricing_mode','project_statuses'))
        assert not errors,errors
        browser.close()
    print('PASS: column reorder, persistence, payment column placement, four server-side header filters and reset')

if __name__=='__main__':run()
