"""客户全称输入联想：真实笔译新增窗口，客户接口全部模拟。"""
import json,re
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];BASE='http://localhost:3000'

def run():
    source=(ROOT/'tools/verify_translation_submission_ui.py').read_text(encoding='utf8')
    scope={'urlopen':urlopen,'json':json,'re':re,'BASE':BASE,'urlparse':urlparse}
    exec('def prepare():\n'+source[source.index('    compiled='):source.index('    with sync_playwright() as p:')]+'\n    return locals()\n',scope)
    state=scope['prepare']();queries=[]
    client={'id':'client-full-name-qa','client_name':'测试客户完整名称有限公司','client_short_name':'测试简称','client_code':'C-TEST','customer_type':'企业客户','sub_clients':[]}
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/clients/':
            params=parse_qs(urlparse(route.request.url).query)
            if params.get('client_name'):queries.append(params['client_name'][0])
            route.fulfill(content_type='application/json',body=json.dumps([client]));return
        if path=='/api/clients/client-full-name-qa':route.fulfill(content_type='application/json',body=json.dumps(client));return
        state['api'](route)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1450,'height':1000});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        page.route(BASE+'/api/**',api);page.route(BASE+'/five-level-test',lambda route:route.fulfill(content_type='text/html',body=state['html']))
        page.goto(BASE+'/five-level-test');page.get_by_role('button',name='新增项目',exact=True).click()
        dialog=page.locator('.project-editor-dialog:visible');expect(dialog).to_be_visible()
        full=dialog.locator('[data-field-key="clientName"] input');full.fill('测')
        option=page.get_by_role('option').filter(has_text=client['client_name']);expect(option).to_be_visible();option.click()
        expect(full).to_have_value(client['client_name'])
        short=dialog.locator('[data-field-key="clientShortName"] input');expect(short).to_have_value(client['client_short_name'])
        assert full.get_attribute('readonly') is not None
        assert '测' in queries,queries
        # 修改简称解除关联后，全称重新可填写新客户，不被旧关联客户覆盖。
        short.fill('新客户简称');expect(full).to_have_value('')
        assert full.get_attribute('readonly') is None
        full.fill('手工录入的新客户全称');expect(full).to_have_value('手工录入的新客户全称')
        assert not errors,errors
        browser.close()
    print('PASS: actual new-project full-name keyword suggestions / selection fills full and short names / readonly linked identity / new customer remains editable')
if __name__=='__main__':run()
