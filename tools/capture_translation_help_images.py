"""帮助配图：独立浏览器、真实业务组件、纯测试数据，所有业务接口均模拟。"""
from pathlib import Path
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
ROOT=Path(__file__).resolve().parents[1]

def run():
    # 复用已有验收脚本中的组件挂载与模拟接口，截取前不执行任何发送操作。
    source=(ROOT/'tools/verify_translation_submission_ui.py').read_text(encoding='utf8')
    setup=source[source.index('    compiled='):source.index('    with sync_playwright() as p:')]
    namespace={'urlopen':urlopen,'re':re,'json':json,'BASE':BASE,'urlparse':__import__('urllib.parse',fromlist=['urlparse']).urlparse}
    exec('def prepare():\n'+setup+'\n    return locals()\n',namespace)
    state=namespace['prepare']();api=state['api'];html=state['html']
    html=html.replace('<link rel="stylesheet" href="/src/styles/common.css">','<link rel="stylesheet" href="/src/styles/theme.css"><link rel="stylesheet" href="/src/styles/common.css"><link rel="stylesheet" href="/src/styles/projectSubOrders.css">')
    html=html.replace('import {createApp,h} from',"import AppStyles from '/src/App.vue';import {createApp,h} from")
    state['root']['child_field_differences']={}
    def mocks(route):
        if '/projects/languages' in route.request.url:
            route.fulfill(content_type='application/json',body=json.dumps([{'id':'zh','label':'中文'},{'id':'en','label':'英语'}]));return
        if '/business-numbers/reserve' in route.request.url:
            route.fulfill(content_type='application/json',body=json.dumps({'token':'00000000-0000-4000-8000-000000000099','number':'TP-261108-999'}));return
        api(route)
    output=ROOT/'frontend/public/help/translation';output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1360,'height':1050},device_scale_factor=1)
        page.add_init_script("localStorage.setItem('user_id','help-example');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\",\"project_files:read\",\"project_files:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),mocks)
        page.route(BASE+'/five-level-test',lambda r:r.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/five-level-test');page.get_by_role('button',name='新增项目',exact=True).click()
        editor=page.locator('.project-editor-dialog:visible');expect(editor).to_be_visible();page.wait_for_timeout(350)
        editor.locator('[data-field-key="sourceFileName"] input').fill('合同.docx')
        editor.locator('[data-field-key="clientName"] input').fill('示例客户有限公司')
        box=editor.bounding_box();page.screenshot(path=str(output/'create-entry.png'),clip={'x':box['x'],'y':box['y'],'width':box['width'],'height':min(640,box['height'])})
        editor.locator('.el-dialog__footer').screenshot(path=str(output/'send-actions.png'))
        editor.get_by_role('tab',name='新增母子订单',exact=True).click();editor.get_by_role('button',name='读取路径',exact=True).click()
        batch=page.locator('.suborder-batch-create-dialog:visible');batch.get_by_role('tab',name='本地',exact=True).click()
        page.evaluate("window.xinshiDesktop={chooseTranslationFolder:async()=>({rootPath:'D:\\\\示例项目\\\\合同资料',entries:[{relativePath:'合同资料',files:['合同.docx']},{relativePath:'合同资料/财务',files:['报价.xlsx']},{relativePath:'合同资料/财务/附件',files:[]},{relativePath:'合同资料/财务/附件/证明',files:['证明.pdf']},{relativePath:'合同资料/空文件夹',files:[]}]})}")
        batch.get_by_role('button',name='选择本地文件夹',exact=True).click();expect(batch).to_contain_text('证明.pdf');page.wait_for_timeout(350)
        batch.screenshot(path=str(output/'folder-preview.png'))
        batch.get_by_role('button',name='取消',exact=True).click()
        editor.get_by_role('tab',name='补充子订单',exact=True).click();editor.get_by_role('button',name='小量新增',exact=True).click()
        child=page.locator('.suborder-editor-dialog:visible');grid=child.locator('.word-count-inline');expect(grid).to_be_visible()
        grid.locator('input[aria-label="我司统计 字数"]').fill('1800');grid.locator('input[aria-label="客户统计 字数"]').fill('1750');grid.locator('input[aria-label="预统计 字数"]').fill('1700')
        grid.screenshot(path=str(output/'statistics.png'))
        assert not state['mail_writes'] and not state['chat_writes'] and not state['project_writes']
        assert not errors,errors
        browser.close()
    print('4 help screenshots captured from real components; mocked data; no project/mail/chat writes')

if __name__=='__main__':run()
