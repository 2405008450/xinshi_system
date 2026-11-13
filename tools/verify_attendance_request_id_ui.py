"""模拟旧浏览器验证请假；拦截全部业务接口，不写业务数据库。"""
import json
import re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'
compiled = urlopen(BASE + '/src/components/common/AppForm.vue').read().decode()
vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h,ref} from VUE;import Panel from '/src/views/schedule/components/AttendanceLeaveDialog.vue';const open=ref(false);createApp({setup:()=>()=>h('div',[h('button',{onClick:()=>open.value=true},'打开请假'),h(Panel,{modelValue:open.value,'onUpdate:modelValue':v=>open.value=v})])}).mount('#app');</script>'''.replace('VUE', json.dumps(vue))

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='msedge', headless=True)
    for mode in ('noRandomUUID', 'noCrypto'):
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        errors, writes, previews = [], [], []
        page.on('pageerror', lambda error: (errors.append(str(error)), print(str(error), flush=True)))
        page.add_init_script("Object.defineProperty(window,'crypto',{value:undefined})" if mode == 'noCrypto' else "Object.defineProperty(crypto,'randomUUID',{value:undefined})")
        def api(route):
            path = route.request.url.split('?')[0]
            if path.endswith('/leave/preview'):
                previews.append(route.request.post_data_json)
                result = {'days': [], 'minutes': 480, 'note': '已扣除休息时间'}
            elif path.endswith('/leave'):
                writes.append(route.request.post_data_json)
                if len(writes) == 1:
                    route.fulfill(status=422, content_type='application/json', body=json.dumps({'detail': [{'loc': ['body', 'client_id'], 'type': 'uuid_parsing', 'msg': '标识格式不正确'}]}))
                    return
                result = {'message': '请假记录已保存，全员通知已生成'}
            else:
                result = {}
            route.fulfill(content_type='application/json', body=json.dumps(result))
        page.route(BASE + '/api/**', api)
        page.route('**/__verify_leave', lambda route: route.fulfill(content_type='text/html', body=html))
        page.goto(BASE + '/__verify_leave')
        page.wait_for_function("document.querySelector('#app button')", timeout=10000)
        page.get_by_role('button', name='打开请假').click()
        dialog = page.get_by_role('dialog', name='请假', exact=True)
        panel = dialog.locator('.el-dialog')
        expect(panel).to_be_visible()
        initial = panel.bounding_box()
        handle = panel.locator('.dialog-field-search-header__title').bounding_box()
        page.mouse.move(handle['x']+15, handle['y']+10)
        page.mouse.down()
        page.mouse.move(handle['x']+75, handle['y']+50, steps=8)
        page.mouse.up()
        assert panel.bounding_box()['x'] > initial['x']+20
        handle = panel.locator('.dialog-field-search-header__title').bounding_box()
        page.mouse.move(handle['x']+15, handle['y']+10)
        page.mouse.down()
        page.mouse.move(-500, -500, steps=8)
        page.mouse.up()
        assert panel.bounding_box()['x'] >= -1 and panel.bounding_box()['y'] >= -1
        dialog.get_by_role('button', name='关闭窗口', exact=True).click()
        page.get_by_role('button', name='打开请假').click()
        expect(panel).to_be_visible()
        assert abs(panel.bounding_box()['x']-initial['x']) < 2
        items = dialog.locator('.el-form-item')
        for index, value in ((0, '2026-11-13 09:00:00'), (1, '2026-11-13 18:30:00')):
            control = items.nth(index).locator('input')
            control.fill(value)
            control.press('Enter')
            control.press('Tab')
        items.nth(2).locator('textarea').fill('兼容性验收')
        expect(dialog).to_contain_text('请假时长：')
        assert previews and previews[-1]['start_at'].endswith('+08:00')
        page.set_viewport_size({'width': 390, 'height': 700})
        footer = dialog.locator('.el-dialog__footer').bounding_box()
        assert footer['y'] >= 0 and footer['y']+footer['height'] <= 700
        save = dialog.get_by_role('button', name='保存并通知全体')
        save.click()
        expect(page.get_by_text('申请提交校验失败，请保留填写内容并刷新页面后重试', exact=True)).to_be_visible()
        expect(dialog).to_be_visible()
        expect(items.nth(2).locator('textarea')).to_have_value('兼容性验收')
        save.click()
        expect(dialog).not_to_be_visible()
        assert len(writes) == 2 and writes[0]['client_id'] == writes[1]['client_id']
        assert re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', writes[0]['client_id'])
        assert not errors, errors
        page.close()
    browser.close()
print('PASS: legacy browser preview, UUID, error message, retry, dialog and mobile footer')
