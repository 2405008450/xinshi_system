"""真实 Vue 目录存储的浏览器时钟验收；API、推送均使用合成数据。"""
import json
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


def run():
    calls, writes, errors = [], [], []
    html = '''<html><head><meta charset="utf-8"></head><body><div id="app"></div><script type="module">
import {createApp,h} from '/node_modules/.vite/deps/vue.js';
import {useAnnotationFollowed} from '/src/composables/useAnnotationFollowed.js';
createApp({setup(){const store=useAnnotationFollowed();return ()=>h('main',[
h('button',{onClick:()=>store.refresh()},'刷新目录'),h('output',{id:'unread'},String(store.mentionTotal.value))]);}}).mount('#app');
</script></body></html>'''
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True, args=['--disable-features=LocalNetworkAccessChecks'])
        context = browser.new_context(service_workers='block')
        context.add_init_script('''localStorage.setItem('token','isolated-ui');localStorage.setItem('user_id','isolated-user');
const Native=window.WebSocket;window.WebSocket=new Proxy(Native,{construct(target,args){
if(String(args[0]).includes('/api/notifications/ws')){const socket=new EventTarget();socket.readyState=0;socket.send=()=>{};socket.close=()=>{socket.readyState=3};return socket}return Reflect.construct(target,args)}});''')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.clock.install(time='2026-11-18T12:00:00+08:00')
        page.clock.pause_at('2026-11-18T12:00:00+08:00')
        page.route('**/chat-catalog-polling-check', lambda route: route.fulfill(content_type='text/html', body=html))

        def api(route):
            path = urlparse(route.request.url).path
            if not path.startswith('/api/'):
                return route.continue_()
            if route.request.method != 'GET':
                writes.append(path)
                return route.fulfill(status=405, json={'detail': '隔离验收禁止写请求'})
            if path == '/api/chat/sessions':
                calls.append(path)
                return route.fulfill(json=dict(items=[], total=0, mention_total=len(calls)))
            return route.fulfill(json=dict(items=[], ready=True, total=0, count=0))

        page.route('**/api/**', api)
        page.goto('http://localhost:3000/chat-catalog-polling-check')
        page.clock.run_for(500)
        expect(page.locator('#unread')).to_have_text('1')
        page.clock.run_for(20000)
        assert len(calls) == 1, '无事件时不应继续每 15 秒查询目录'
        page.get_by_role('button', name='刷新目录').click()
        page.clock.run_for(500)
        expect(page.locator('#unread')).to_have_text('2')
        page.clock.run_for(15000)
        assert len(calls) == 2, '刚刚刷新成功时必须跳过兜底轮询'
        page.clock.run_for(35000)
        expect(page.locator('#unread')).to_have_text('3')
        page.evaluate("Object.defineProperty(document,'visibilityState',{configurable:true,get:()=> 'hidden'})")
        page.clock.run_for(70000)
        assert len(calls) == 3, '隐藏页面不能查询目录'
        page.evaluate("Object.defineProperty(document,'visibilityState',{configurable:true,get:()=> 'visible'});window.dispatchEvent(new Event('focus'))")
        page.clock.run_for(500)
        expect(page.locator('#unread')).to_have_text('4')
        assert not errors, errors
        assert not writes, writes
        print(json.dumps(dict(passed=True, simulated_seconds=141, catalog_requests=len(calls), writes=len(writes), errors=errors)))
        browser.close()


if __name__ == '__main__':
    run()
