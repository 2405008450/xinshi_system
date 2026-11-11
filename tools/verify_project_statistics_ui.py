"""三个真实项目页面的新老客户统计入口与交互；API 全部模拟，不写业务数据。"""
import json
import re
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    def dep(name): return re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><style>html,body,#app{height:100%;margin:0}#app{display:flex;flex-direction:column}</style><div id="app"></div><script type="module">
import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;
import I from '/src/views/project/interpretation/InterpretationProjectDetails.vue';import A from '/src/views/project/AnnotationProjects.vue';import R from '/src/views/project/RecruitmentProjects.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const module=new URLSearchParams(location.search).get('module');const app=createApp({render:()=>h({interpretation:I,annotation:A,recruitment:R}[module])});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/project-statistics-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    requests=[];writes=[]
    def api(route):
        path=urlparse(route.request.url).path
        if route.request.method!='GET': writes.append(path)
        if path.startswith('/api/project-statistics/'):
            requests.append((path.rsplit('/',1)[1],parse_qs(urlparse(route.request.url).query)))
            period=dict(period_start='2026-11-01',period_end='2026-11-30',order_count=3,customer_count=2,new_customer_count=1,old_customer_count=1,new_customer_share=50,old_customer_share=50,new_order_count=1,old_order_count=2,unknown_order_count=0,new_order_share=33.33,old_order_share=66.67,unknown_order_share=0,amounts=[])
            customer=dict(period_start='2026-11-01',period_end='2026-11-30',client_short_name='统计客户',client_name='统计客户有限公司',first_order_date='2026-10-01',cohort='old',order_count=2,order_share=66.67,amounts=[])
            result=dict(periods=[period],customers=[customer],order_count=3,generated_at='2026-11-09T12:30:00+08:00',fallback_date_orders=0,undated_orders=0)
        elif path.endswith('/page'): result={'items':[],'total':0}
        elif path.endswith('/count'): result=0
        elif path.endswith('/editor-drafts'): result={'payload':None,'revision':0}
        else: result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge')
        page=browser.new_page(viewport={'width':1450,'height':1000})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api)
        page.route(BASE+'/project-statistics-test*',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        for module,label in [('interpretation','口译'),('annotation','标注'),('recruitment','招聘')]:
            page.set_viewport_size({'width':1450,'height':1000})
            page.goto(BASE+'/project-statistics-test?module='+module)
            page.get_by_role('button',name='数据统计',exact=True).click()
            dialog=page.locator('.translation-statistics-dialog:visible')
            expect(dialog).to_contain_text(label+'项目 · 数据统计')
            expect(dialog.locator('.statistics-overview')).to_contain_text('33.33%')
            assert requests[-1][0]==module and 'tax_basis' not in requests[-1][1]
            expect(dialog.get_by_text('总金额（按币种）',exact=True)).to_have_count(0)
            dialog.get_by_role('tab',name='客户明细（1）',exact=True).click()
            expect(dialog.locator('.statistics-customers')).to_contain_text('首次'+label+'下单')
            expect(dialog.locator('.statistics-customers')).to_contain_text('统计客户')
            dialog.get_by_text('每周',exact=True).click();page.wait_for_timeout(150)
            assert requests[-1][1]['granularity']==['week']
            dialog.get_by_text('每天',exact=True).click();page.wait_for_timeout(150)
            assert requests[-1][1]['granularity']==['day']
            keyword=dialog.get_by_placeholder('客户全称、简称或编号')
            before=len(requests);keyword.fill('统计 客户');page.wait_for_timeout(150);assert len(requests)==before
            page.wait_for_timeout(450);assert requests[-1][1]['client_keyword']==['统计 客户']
            keyword.fill('');page.wait_for_timeout(150);assert not requests[-1][1].get('client_keyword',[''])[0]
            dialog.get_by_role('button',name=re.compile('^高级筛选')).click()
            popper=page.locator('.el-popover:visible');expect(popper).to_contain_text('日期依据')
            expect(popper.get_by_text('金额口径',exact=True)).to_have_count(0)
            popper.get_by_role('button',name='关闭',exact=True).click();expect(popper).not_to_be_visible()
            dialog.get_by_role('button',name='重置',exact=True).click();page.wait_for_timeout(150)
            assert requests[-1][1]['granularity']==['month']
            initial=dialog.bounding_box();header=dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x']+320,header['y']+18);page.mouse.down();page.mouse.move(header['x']+300,header['y']+48,steps=5);page.mouse.up()
            assert dialog.bounding_box()['y']>initial['y']+5
            page.set_viewport_size({'width':650,'height':780});expect(dialog.locator('.el-dialog__footer')).to_be_visible()
            assert dialog.bounding_box()['width']<=650
            dialog.locator('.el-dialog__footer').get_by_role('button',name='关闭',exact=True).click();expect(dialog).not_to_be_visible()
            page.set_viewport_size({'width':1450,'height':1000});page.get_by_role('button',name='数据统计',exact=True).click();expect(dialog).to_be_visible()
            assert dialog.bounding_box()['y']<80
            dialog.locator('.el-dialog__footer').get_by_role('button',name='关闭',exact=True).click()
        assert not errors,errors
        assert not writes,writes
        browser.close()
    print('three real page entries / module scope / cohorts / day-week-month / debounce-clear / advanced close / reset / drag / small viewport / reopen / no writes PASS')


if __name__=='__main__':run()
