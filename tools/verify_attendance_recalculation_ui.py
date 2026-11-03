"""隔离前端联调：临时 Vite、拦截全部 API、模拟通知，不启动后端或访问业务库。"""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
from urllib.request import urlopen
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PORT = 3317
BASE = f'http://127.0.0.1:{PORT}'

HTML = '''<!doctype html><meta charset="UTF-8">
<link rel="stylesheet" href="/node_modules/element-plus/dist/index.css">
<div id="app"></div><script type="module">
import {createApp,h} from VUE;
import Attendance from '/src/views/schedule/components/AttendanceOverview.vue';
import Annual from '/src/views/schedule/components/AnnualLeavePanel.vue';
import Policy from '/src/views/schedule/components/AttendancePolicyPanel.vue';
import AppForm from '/src/components/common/AppForm.vue';
import Dialog from '/src/components/common/DraggableFormDialog.vue';
import {ensureConnected,closeSocket} from '/src/utils/realtimeSocket.js';
window.app=createApp({render:()=>h('main',[h(Attendance),h(Annual),h(Policy)])});
app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);
app.mount('#app');ensureConnected();window.stopTest=()=>{app.unmount();closeSocket()};
</script>'''


def main():
    # 固定专用端口被占用时停止，不能复用或重启其他服务。
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', PORT))
    env = {**os.environ, 'VITE_API_PROXY_TARGET': 'http://127.0.0.1:1'}
    (ROOT / '.tmp').mkdir(exist_ok=True)
    with open(ROOT / '.tmp' / 'attendance-recalculation-vite.log', 'w', encoding='utf-8') as log:
        process = subprocess.Popen(
            ['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', str(PORT), '--strictPort'],
            cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    compiled = urlopen(BASE + '/src/components/common/AppForm.vue', timeout=1).read().decode()
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('隔离 Vite 启动失败，请查看 .tmp/attendance-recalculation-vite.log')
                    time.sleep(.2)
            vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
            html = HTML.replace('from VUE', f'from {json.dumps(vue)}')
            run_browser(html)
        finally:
            process.terminate()
            process.wait(timeout=10)


def run_browser(html):
    state = {'late': 14.1, 'hold': False}
    reads, writes, errors, held = [], [], [], []

    def api(route):
        path = urlparse(route.request.url).path
        reads.append(path)
        if route.request.method != 'GET':
            writes.append(path)
            route.abort()
            return
        late = state['late']
        shift = {'code': 'early', 'label': '早班' if late == 0 else '早早班', 'periods': ['09:00–12:00', '13:30–18:30']}
        row = {'id': 'clock-1', 'day': '2026-11-02', 'name': '本人', 'shift': shift, 'check_in': '2026-11-02T08:59:06+08:00', 'check_out': '2026-11-02T18:54:32+08:00', 'late_minutes': late, 'leave_minutes': late, 'leaves': []}
        if path.endswith('/today'):
            result = {'shift': shift, 'record': row, 'sessions': [row], 'leaves': []}
        elif '/annual-leave' in path:
            result = {'people': [{'name': '本人', 'entries': [], 'used_days': late / 480, 'annual_leave_days': 1, 'remaining_days': 1 - late / 480}]}
        elif '/policy' in path:
            result = {'balances': [], 'monthly_policy': []}
        else:
            result = {'records': [row], 'people': [], 'total': 1, 'leaves': [], 'totals': {'late_minutes': late, 'leave_minutes': late, 'late_leave_minutes': late}, 'departments': []}
        if path.endswith('/mine') and state['hold']:
            state['hold'] = False
            held.append((route, result))
        else:
            route.fulfill(content_type='application/json', body=json.dumps(result, ensure_ascii=False))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, service_workers='block')
        context.add_init_script('''
          localStorage.setItem('token','isolated-test-only');
          const NativeSocket=window.WebSocket;
          class TestSocket {
            static OPEN=1; static CONNECTING=0; readyState=1;
            constructor(url,protocols){if(!url.includes('/notifications/ws'))return new NativeSocket(url,protocols);window.testSocket=this;queueMicrotask(()=>this.onopen?.())}
            send(){} close(){this.readyState=3}
          }
          window.WebSocket=TestSocket;
        ''')
        context.route(re.compile(r'^' + re.escape(BASE) + r'/api/'), api)
        context.route(BASE + '/attendance-recalculation-check', lambda route: route.fulfill(content_type='text/html', body=html))
        page = context.new_page()
        page.on('pageerror', lambda error: (errors.append(str(error)), print('页面错误:', error, flush=True)))
        page.goto(BASE + '/attendance-recalculation-check')
        section = page.locator('.attendance-overview')
        section.locator('.el-collapse-item__header').filter(has_text=re.compile('^考勤与加班统计$')).click()
        section.get_by_role('tab', name='每日明细', exact=True).click()
        record = section.get_by_role('row').filter(has_text='2026-11-02').first
        expect(record).to_contain_text('14.1分钟')
        before = {path: reads.count(path) for path in ('/api/attendance/mine', '/api/attendance/today', '/api/attendance/annual-leave', '/api/attendance/policy')}
        state['late'] = 0
        notify = "testSocket.onmessage({data:JSON.stringify({type:'attendance_schedule_changed'})})"
        page.evaluate(notify)
        expect(record).not_to_contain_text('14.1分钟')
        expect(record).to_contain_text('早班')
        expect(record).to_contain_text('0分钟')
        for path, count in before.items():
            assert reads.count(path) > count, (path, reads)
        # 保持旧请求悬挂，连续通知后让新结果先到，旧响应不能覆盖。
        state['hold'] = True
        page.evaluate(notify)
        deadline = time.monotonic() + 5
        while not held and time.monotonic() < deadline:
            page.wait_for_timeout(25)
        assert held
        state['late'] = 7
        page.evaluate(notify)
        expect(record).to_contain_text('7分钟')
        old_route, old_result = held.pop()
        old_route.fulfill(content_type='application/json', body=json.dumps(old_result))
        expect(record).to_contain_text('7分钟')
        page.set_viewport_size({'width': 650, 'height': 800})
        expect(record).to_contain_text('7分钟')
        page.evaluate('stopTest()')
        count = len(reads)
        page.evaluate(notify)
        page.wait_for_timeout(100)
        assert len(reads) == count and not writes and not errors, (writes, errors)
        print(json.dumps({'realtime_refresh_all_panels': True, 'stale_response_protected': True, 'unmount_cleanup': True, 'small_viewport': True, 'business_writes': writes, 'page_errors': errors}))
        browser.close()


if __name__ == '__main__':
    main()
