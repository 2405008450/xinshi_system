"""真实项目列表和编辑弹窗回归，业务接口在浏览器内隔离。"""
import re
from uuid import uuid4
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'
PROJECT = '/filter-session-check'


def run():
    with urlopen(BASE + '/src/views/project/ProjectWorkspace.vue', timeout=20) as response:
        compiled = response.read().decode()

    def dep(name):
        return re.search(r'from ["\']([^"\']*/' + name + r'\.js[^"\']*)', compiled)[1]

    html = f'''<!doctype html><meta charset="UTF-8"><div id="app"></div>
      <link rel="stylesheet" href="/node_modules/element-plus/dist/index.css">
      <script type="module">
      import {{createApp,h}} from {dep('vue')!r}
      import {{createRouter,createWebHistory}} from {dep('vue-router')!r}
      import App from '/src/App.vue'
      import Workspace from '/src/views/project/ProjectWorkspace.vue'
      import FinanceWorkspace from '/src/views/project/FinanceWorkspace.vue'
      import AppForm from '/src/components/common/AppForm.vue'
      import Dialog from '/src/components/common/DraggableFormDialog.vue'
      import {{clearAuthSession}} from '/src/utils/authSession.js'
      import {{installAutoDrafts}} from '/src/utils/autoDrafts.js'
      window.signOut = clearAuthSession
      window.signIn = () => {{
        localStorage.setItem('user_id','filter-qa')
        localStorage.setItem('user_roles','["super_admin"]')
        localStorage.setItem('user_permissions','["*"]')
        localStorage.setItem('token','isolated-browser-fixture')
      }}
      const router = createRouter({{history:createWebHistory(),routes:[
        {{path:{PROJECT!r},component:Workspace,props:{{module:'translation'}}}},
        {{path:'/finance-management/:module',component:FinanceWorkspace}},
        {{path:'/login',component:{{render:()=>h('h1','测试登录页')}}}},
      ]}})
      const app=createApp(App)
      installAutoDrafts(app)
      app.component('AppForm',AppForm).component('DraggableFormDialog',Dialog).use(router)
      app.mount('#app')
      </script>'''

    def api(route):
        path = urlparse(route.request.url).path
        result = []
        if path in ('/api/projects/translation/page', '/api/translation-customer-finance/page'):
            result = {'items': [], 'total': 0}
        elif path == '/api/editor-drafts':
            result = {'payload': None, 'revision': 0}
        elif path == '/api/business-numbers/reserve':
            result = {'token': str(uuid4()), 'number': 'TP-261118-009'}
        elif path.startswith('/api/business-numbers/'):
            result = {'ok': True}
        route.fulfill(json=result)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge')
        context = browser.new_context(viewport={'width': 1500, 'height': 1000})
        context.route(BASE + '/api/**', api)
        context.route(re.compile(BASE + r'/(filter-session-check|login|finance-management/[^?]+)(\?.*)?$'),
                      lambda route: route.fulfill(content_type='text/html', body=html))
        page = context.new_page()
        page.goto(BASE + '/login')
        page.wait_for_function("typeof window.signIn === 'function'")
        page.evaluate('window.signIn()')
        page.goto(BASE + PROJECT)

        keyword = page.get_by_role('textbox', name='关键词', exact=True)
        advanced = page.get_by_role('button', name='高级筛选', exact=True)
        panel = page.locator('.translation-advanced-filter-popover:visible')
        for close in ('button', 'outside'):
            keyword.fill('临时查询')
            advanced.click()
            expect(panel).to_be_visible()
            if close == 'button':
                panel.get_by_role('button', name='关闭', exact=True).click()
            else:
                page.get_by_role('tab', name='笔译项目管理', exact=True).click()
            expect(panel).to_be_hidden()
            expect(keyword).to_have_value('临时查询')
        advanced.click()
        panel.get_by_role('button', name='取消筛选', exact=True).click()
        expect(keyword).to_have_value('')

        keyword.fill('切换页签前的查询')
        page.get_by_role('tab', name='笔译须知').click()
        expect(keyword).to_have_count(0)
        page.get_by_role('tab', name='笔译项目管理').click()
        expect(keyword).to_have_value('')
        keyword.fill('退出前的查询')

        new = page.get_by_role('button', name='新增项目', exact=True)
        dialog = page.locator('.project-editor-dialog:visible')
        name = dialog.locator('[data-field-key="sourceFileName"] input.el-input__inner')
        new.click()
        name.fill('关闭后保留.docx')
        dialog.get_by_role('button', name='关闭窗口', exact=True).click()
        expect(dialog).to_be_hidden()
        new.click()
        expect(name).to_have_value('关闭后保留.docx')

        other = context.new_page()
        other.goto(BASE + '/login')
        other.wait_for_function("typeof window.signOut === 'function'")
        # 在同一任务中输入并退出，覆盖尚未等到防抖写入的情况。
        page.bring_to_front()
        name.fill('另一标签页退出后保留.docx')
        other.evaluate('window.signOut()')
        expect(page).to_have_url(BASE + '/login')
        page.wait_for_function("typeof window.signIn === 'function'")
        page.evaluate('window.signIn()')
        page.goto(BASE + PROJECT)
        expect(keyword).to_have_value('')
        new.click()
        expect(name).to_have_value('另一标签页退出后保留.docx')

        page.goto(BASE + '/finance-management/translation')
        finance_keyword = page.locator('.finance-keyword input')
        finance_keyword.fill('切换财务页签前的查询')
        page.get_by_role('tab', name='口译', exact=True).click()
        expect(finance_keyword).to_have_count(0)
        page.get_by_role('tab', name='笔译', exact=True).click()
        expect(finance_keyword).to_have_value('')
        expect(page.get_by_role('button', name=re.compile(r'^本人（'))).to_be_visible()
        browser.close()
    print('filter close, page tabs, cross-tab logout and project draft recovery PASS')


if __name__ == '__main__':
    run()
