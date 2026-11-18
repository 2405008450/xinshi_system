"""在本机 Vite 页面挂载真实组件，全部 API 使用合成数据，不连接业务后端。"""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright


def run():
    output = Path(__file__).resolve().parents[1] / 'outputs/chat-session-activity-ui'
    output.mkdir(parents=True, exist_ok=True)
    requests, writes, errors = [], [], []
    html = '''<html><head><meta charset="utf-8"></head><body style="margin:0"><div id="app"></div>
<script type="module">
import {createApp,h,ref} from '/node_modules/.vite/deps/vue.js';
import ElementPlus from '/node_modules/.vite/deps/element-plus.js';
import {createRouter,createMemoryHistory} from '/node_modules/.vite/deps/vue-router.js';
import '/node_modules/element-plus/dist/index.css';
import ChatWorkspace from '/src/components/chat/ChatWorkspace.vue';
const rows=[{key:'annotation:recent',projectType:'annotation',projectId:'recent',title:'近期合成项目',subtitle:'AP-261118-001',unread:0,mentionUnread:0,lastMessage:{preview:'近期消息',senderName:'测试',createdAt:'2026-11-18T12:00:00+08:00'}}];
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/:pathMatch(.*)*',component:{render:()=>null}}]});
const width=ref(window.innerWidth);window.addEventListener('resize',()=>{width.value=window.innerWidth});
createApp({render(){return h(ChatWorkspace,{style:'width:100vw;height:100vh',sessions:rows,searchSessions:rows,active:true,sidebarOpen:true,maximized:true,mobile:width.value<640,narrow:width.value<640,title:'沟通',onOpen:row=>{window.selectedHistory=row}})}}).use(ElementPlus).use(router).mount('#app');
</script></body></html>'''
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True, args=['--disable-features=LocalNetworkAccessChecks'])
        context = browser.new_context(viewport={'width': 1280, 'height': 900}, timezone_id='America/Los_Angeles', service_workers='block')
        context.add_init_script("""localStorage.setItem('token','isolated-ui');localStorage.setItem('user_id','isolated-user');localStorage.setItem('user_roles','[]');
const NativeWebSocket=window.WebSocket;
window.WebSocket=new Proxy(NativeWebSocket,{construct(target,args){
 if(String(args[0]).includes('/api/notifications/ws')){const socket=new EventTarget();socket.readyState=0;socket.send=()=>{};socket.close=()=>{socket.readyState=3};return socket}
 return Reflect.construct(target,args);
}});""")
        page = context.new_page()
        page.set_default_timeout(15000)
        page.on('pageerror', lambda error: (errors.append(str(error)), print('PAGE_ERROR', str(error))))
        page.on('console', lambda message: print('CONSOLE', message.text) if message.type == 'error' else None)
        page.route('**/chat-session-activity-check', lambda route: route.fulfill(content_type='text/html', body=html))

        def api(route):
            request = route.request
            parsed = urlparse(request.url)
            if not parsed.path.startswith('/api/'):
                return route.continue_()
            if request.method != 'GET':
                writes.append(parsed.path)
                return route.fulfill(status=405, json={'detail': '隔离验收禁止写请求'})
            if parsed.path == '/api/chat/sessions/history':
                params = parse_qs(parsed.query)
                requests.append(params)
                offset = int(params.get('offset', ['0'])[0])
                keyword = params.get('keyword', [''])[0]
                count = 1 if keyword else 65
                rows = [dict(key=f'annotation:history-{index}', kind='annotation', project_id=f'history-{index}',
                             title=f'{keyword or "历史项目"} {index}', subtitle=f'AP-250101-{index:03}', member_count=3)
                        for index in range(offset, min(offset + 30, count))]
                return route.fulfill(json=dict(items=rows, total=count, has_more=offset + len(rows) < count))
            return route.fulfill(json=dict(items=[], total=0, count=0, ready=True, hierarchy_ready=False, can_manage=False))

        page.route('**/api/**', api)
        page.goto('http://localhost:3000/chat-session-activity-check')
        page.wait_for_timeout(2000)
        if errors:
            raise AssertionError(errors)
        history = page.get_by_role('button', name='历史会话', exact=True)
        if not history.count():
            print('BODY', page.locator('body').inner_text()[:2000])
            page.screenshot(path=str(output / 'failure.png'), full_page=True)
        expect(history).to_be_visible()
        assert not requests, '默认目录不能预加载历史会话'
        history.click()
        expect(page.locator('.chat-history__item')).to_have_count(30)
        print('UI: opened history', flush=True)
        page.get_by_role('button', name='Go to next page').click()
        expect(page.locator('.chat-history__item').first).to_contain_text('历史项目 30')
        page.locator('.chat-history__item').first.click()
        assert page.evaluate('window.selectedHistory.projectId') == 'history-30'
        print('UI: paged and opened conversation', flush=True)
        page.get_by_role('button', name='返回近期会话', exact=True).click()
        expect(page.locator('.chat-history')).to_have_count(0)
        field = page.locator('.chat-workspace__search .el-input__inner')
        before = len(requests)
        field.fill('历史目标')
        page.wait_for_timeout(150)
        assert len(requests) == before, '搜索应防抖'
        expect(page.locator('.chat-history__item')).to_have_count(1)
        print('UI: searched history', flush=True)
        assert requests[-1].get('offset') == ['0']
        assert field.bounding_box()['width'] >= 35, '窄侧栏必须保留可编辑的搜索输入区'
        field.fill('')
        expect(page.locator('.chat-history')).to_have_count(0)
        print('UI: cleared search', flush=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.get_by_role('button', name='历史会话', exact=True).click()
        expect(page.locator('.chat-history__item')).to_have_count(30)
        print('UI: mobile history', flush=True)
        assert page.locator('.chat-history').evaluate('(el)=>el.scrollWidth <= el.clientWidth+1')
        page.screenshot(path=str(output / 'mobile.png'), full_page=True)
        assert not writes, writes
        assert not errors, errors
        print(json.dumps({'passed': True, 'history_requests': len(requests), 'writes': len(writes), 'errors': errors}, ensure_ascii=False))
        browser.close()


if __name__ == '__main__':
    run()
