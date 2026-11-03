"""客户标注单价真实页面回归；全部业务请求模拟，不写业务数据库。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE + '/src/views/project/ProjectWorkspace.vue', timeout=20).read().decode()
    vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp} from VUE;import Clients from '/src/views/client/Clients.vue';import AppForm from '/src/components/common/AppForm.vue';createApp(Clients).component('AppForm',AppForm).mount('#app');</script>'''.replace('from VUE', 'from '+json.dumps(vue))
    customer = dict(id='c1', client_code='CL-TEST', client_name='标注测试客户', client_short_name='标注测试', client_manager='负责人', sub_clients=[])
    rows, writes, errors = [], [], []
    def api(route):
        path = urlparse(route.request.url).path
        method = route.request.method
        if path == '/api/clients/page': result = {'items':[customer], 'total':1}
        elif '/annotation-rates' in path:
            if method == 'POST':
                data = route.request.post_data_json; writes.append(data)
                result = dict(data, id=str(len(writes)), revision=1); rows.append(result)
            elif method == 'PUT':
                data = route.request.post_data_json; writes.append(data)
                result = next(row for row in rows if row['id'] == path.split('/')[-1]); result.update(data); result['revision'] += 1
            elif method == 'DELETE':
                rows[:] = [row for row in rows if row['id'] != path.split('/')[-1]]; result = None
            else: result = {'items':rows}
        elif path == '/api/clients/c1': result = customer
        elif '/drafts/' in path: result = {}
        else: result = {'items':[], 'total':0, 'ready':True, 'version':'1'}
        if method == 'DELETE': route.fulfill(status=204, body='')
        else: route.fulfill(content_type='application/json', body=json.dumps(result, ensure_ascii=False))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        context = browser.new_context(viewport={'width':1440,'height':950}, service_workers='block')
        context.add_init_script("localStorage.setItem('user_id','annotation-rate-ui');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['clients:read','clients:write']))")
        context.route(re.compile(r'^http://localhost:3000/api/'), api)
        context.route(BASE+'/annotation-rate-ui-test', lambda r:r.fulfill(content_type='text/html', body=html))
        page = context.new_page(); page.set_default_timeout(12000); page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/annotation-rate-ui-test')
        page.get_by_role('button', name='编辑', exact=True).click()
        outer = page.locator('.client-form-dialog:visible')
        outer.get_by_role('tab', name='财务信息', exact=True).click()
        outer.get_by_role('tab', name='标注', exact=True).click()
        panel = outer.locator('.customer-annotation-rates')
        panel.get_by_role('button', name='新增客户单价', exact=True).click()
        editor = page.locator('.customer-annotation-rate-dialog:visible')
        expect(editor).to_contain_text('CNY 人民币')
        editor.get_by_role('button', name='保存单价', exact=True).click()
        expect(editor).to_contain_text('请选择标注类型')
        assert not writes
        def choose(field, value):
            editor.locator('.el-form-item').filter(has=page.locator('label').filter(has_text=re.compile('^'+field+'$'))).locator('.el-select').click()
            page.get_by_role('option', name=value, exact=True).click()
        choose('标注类型','音频标注')
        editor.get_by_placeholder('请输入不含税单价').fill('0.123456')
        editor.get_by_placeholder('请输入含税单价').fill('0.130864')
        choose('单位','分钟')
        editor.get_by_role('button', name='保存单价', exact=True).click()
        expect(editor).to_have_count(0)
        assert writes[-1]['project_type']=='audio_annotation' and writes[-1]['unit']=='minute'
        assert writes[-1]['tax_prices']['unit_price_excl_tax']==0.123456 and writes[-1]['tax_prices']['unit_price_incl_tax']==0.130864
        expect(panel).to_contain_text('0.123456'); expect(panel).to_contain_text('分钟')
        panel.get_by_role('button', name='编辑', exact=True).click()
        expect(editor.get_by_placeholder('请输入不含税单价')).to_have_value('0.123456')
        editor.get_by_placeholder('请输入不含税单价').fill('12.5')
        choose('货币','USD 美元'); choose('单位','小时')
        # 嵌套弹窗拖动，关闭后恢复预设位置。
        before = editor.bounding_box(); header = editor.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+35,header['y']+20); page.mouse.down(); page.mouse.move(header['x']+100,header['y']+75,steps=6); page.mouse.up()
        after = editor.bounding_box(); assert abs(after['x']-before['x'])>20
        editor.get_by_role('button', name='保存单价', exact=True).click()
        expect(editor).to_have_count(0)
        assert writes[-1]['revision'] == 1 and writes[-1]['unit'] == 'hour' and writes[-1]['currency'] == 'USD'
        panel.get_by_role('button', name='新增客户单价', exact=True).click()
        page.wait_for_timeout(350)
        reopened = editor.bounding_box(); assert abs(reopened['x']-before['x'])<2
        expect(editor).to_contain_text('CNY 人民币')
        choose('标注类型','文本标注'); choose('单位','条')
        editor.get_by_placeholder('请输入不含税单价').fill('2')
        page.set_viewport_size({'width':540,'height':740})
        expect(editor.get_by_role('button', name='保存单价', exact=True)).to_be_in_viewport()
        assert editor.bounding_box()['width']<=508.5
        editor.get_by_role('button', name='保存单价', exact=True).click(); expect(editor).to_have_count(0)
        expect(panel.locator('.el-table__body-wrapper tbody tr')).to_have_count(2)
        page.set_viewport_size({'width':1440,'height':950})
        panel.get_by_role('button', name='删除', exact=True).first.click()
        page.locator('.el-message-box').get_by_role('button',name='确定',exact=True).click()
        expect(panel.locator('.el-table__body-wrapper tbody tr')).to_have_count(1)
        outer.get_by_role('button',name='取消',exact=True).click(); expect(outer).to_have_count(0)
        page.get_by_role('button',name='编辑',exact=True).click()
        outer.get_by_role('tab',name='财务信息',exact=True).click(); outer.get_by_role('tab',name='标注',exact=True).click()
        expect(panel.locator('.el-table__body-wrapper tbody tr')).to_have_count(1)
        expect(panel).to_contain_text('文本标注')
        assert not errors, errors
        browser.close()
    print('PASS annotation type dropdown, existing units, CNY default, validation, 6 decimal save, edit, multiple rates, delete, reopen, nested drag, mobile footer')


if __name__ == '__main__': run()
