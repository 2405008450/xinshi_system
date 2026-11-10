"""真实笔译列表、删除记录和编辑窗口；全部接口模拟，不删除业务数据。"""
import json,re
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
BASE='http://localhost:3000'

def run():
    source=(ROOT/'tools/verify_translation_submission_ui.py').read_text(encoding='utf8')
    prefix=source[source.index('    compiled='):source.index('    with sync_playwright() as p:')]
    scope={'urlopen':urlopen,'json':json,'re':re,'BASE':BASE,'urlparse':urlparse}
    exec('def prepare():\n'+prefix+'\n    return locals()\n',scope)
    state=scope['prepare']();queries=[];writes=[]
    record={'id':'deleted-1','number':'TP-261110-900.001','entity_name':'删除记录测试.docx','client_name':'客户全称AA','client_short_name':'客户BB','actor_name':'测试删除人','deleted_at':'2026-11-10T23:59:59+08:00','snapshot':{'client_name':'客户全称AA','client_short_name':'客户BB','remarks':'保留的补充说明'}}
    def api(route):
        request=route.request;path=urlparse(request.url).path
        if path=='/api/business-numbers/history':
            params={key:value[0] for key,value in parse_qs(urlparse(request.url).query).items()};queries.append(params)
            route.fulfill(content_type='application/json',body=json.dumps({'items':[record],'total':1},ensure_ascii=False));return
        if request.method=='DELETE':writes.append(path)
        state['api'](route)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api)
        page.route(BASE+'/five-level-test',lambda route:route.fulfill(content_type='text/html',body=state['html']))
        page.goto(BASE+'/five-level-test')
        expect(page.get_by_role('button',name='订单删除记录',exact=True)).to_have_count(0)
        page.get_by_role('button',name='删除管理',exact=True).click()
        page.get_by_role('button',name='订单删除记录',exact=True).click()
        dialog=page.locator('.number-deletion-history-dialog:visible');expect(dialog).to_be_visible()
        expect(dialog.locator('tbody')).to_contain_text(record['number'])
        assert queries[-1]['kind']=='translation' and queries[-1]['include_children']=='true'
        assert not queries[-1].get('order_no')
        expect(dialog.locator('tbody')).to_contain_text('客户全称AA')
        order=dialog.get_by_placeholder('母订单或各级子订单号，可输入多个关键词',exact=True)
        customer=dialog.get_by_placeholder('客户全称或简称，可输入多个关键词',exact=True)
        order.fill('900 .001');customer.fill('AA BB')
        page.wait_for_timeout(550)
        assert queries[-1]['order_no']=='900 .001' and queries[-1]['client_name']=='AA BB'
        start=dialog.get_by_placeholder('开始日期',exact=True);end=dialog.get_by_placeholder('结束日期',exact=True)
        start.fill('2026-11-01');end.fill('2026-11-10');end.press('Tab')
        dialog.get_by_role('button',name='查询',exact=True).click()
        page.wait_for_timeout(150)
        assert queries[-1]['deleted_from']=='2026-11-01' and queries[-1]['deleted_to']=='2026-11-10',queries[-1]
        dialog.get_by_role('button',name='查看详情',exact=True).click()
        popover=page.locator('.el-popover:visible');expect(popover).to_contain_text('删除记录详情')
        expect(popover).to_contain_text('保留的补充说明')
        dialog.locator('.el-dialog__header').click()
        dialog.get_by_role('button',name='重置',exact=True).click();page.wait_for_timeout(150)
        assert not any(queries[-1].get(key) for key in ('order_no','client_name','deleted_from','deleted_to'))
        # 标题拖动、视口约束、关闭及重开复位。
        initial=dialog.bounding_box();header=dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+header['width']/2,header['y']+16);page.mouse.down();page.mouse.move(header['x']+header['width']/2+55,header['y']+65);page.mouse.up()
        moved=dialog.bounding_box();assert moved['x']>initial['x']+30
        page.mouse.move(moved['x']+moved['width']/2,moved['y']+16);page.mouse.down();page.mouse.move(-1000,-1000);page.mouse.up()
        bounded=dialog.bounding_box();assert bounded['x']>=-1 and bounded['y']>=-1
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='订单删除记录',exact=True).click();expect(dialog).to_be_visible()
        assert abs(dialog.bounding_box()['x']-initial['x'])<3
        dialog.get_by_role('button',name='关闭',exact=True).click()
        page.get_by_role('button',name='退出',exact=True).click()
        page.get_by_role('button',name='编辑',exact=True).first.click()
        editor=page.locator('.project-editor-dialog:visible');expect(editor).to_be_visible()
        expect(editor.get_by_role('button',name='编号删除记录',exact=True)).to_have_count(0)
        editor.get_by_role('button',name='订单删除记录',exact=True).click();expect(dialog).to_be_visible()
        assert queries[-1].get('order_no')==state['root']['order_no']
        assert not writes and not errors,(writes,errors)
        browser.close()
    print('PASS: delete-management entry / all levels / customer and order search / inclusive date range / reset / details / drag and reopen / editor label / no deletion')

if __name__=='__main__':run()
