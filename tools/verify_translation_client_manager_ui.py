"""列表直接调整客户经理及查看历史；模拟所有接口，禁止修改业务数据。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import expect, sync_playwright

BASE='http://localhost:3000'


def run():
    source=urlopen(BASE+'/src/components/common/AppForm.vue',timeout=30).read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',source).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive} from VUE;import Cell from '/src/views/project/translation/components/TranslationProjectFieldCell.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const state=window.testState=reactive({row:{id:'p1',orderNo:'TP-261107-007',sourceFileName:'测试.docx',clientManager:'刘家铭'},editable:true,refreshed:0});
const app=createApp({render:()=>h(Cell,{row:state.row,column:{key:'clientManager'},context:{canWriteProjects:state.editable,deleteMode:false,fetchData:()=>state.refreshed++}})});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
    detail={'id':'p1','order_no':'TP-261107-007','project_name':'测试.docx','source_file_name':'测试.docx','client_manager':'刘家铭','client_manager_id':'u1','updated_at':'2026-11-07T12:00:00+08:00'}
    writes=[];history=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/users/options':result=[{'id':'u1','display_name':'刘家铭'},{'id':'u2','display_name':'赵震锋'}]
        elif path.endswith('/history'):result={'items':history,'total':len(history)}
        elif path=='/api/projects/translation/p1':
            if route.request.method=='PUT':
                data=route.request.post_data_json;writes.append(data)
                detail.update(client_manager_id=data['client_manager_id'],client_manager='赵震锋',updated_at='2026-11-07T12:01:00+08:00')
                history.append({'id':'h1','previous_manager_name':'刘家铭','new_manager_name':'赵震锋','reason':data['client_manager_change_reason'],'actor_name':'测试操作人','changed_at':'2026-11-07T12:01:00+08:00'})
            result=detail
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1400,'height':900})
        page.add_init_script("localStorage.setItem('user_id','u1');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(BASE+'/manager-cell-test',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/manager-cell-test');page.get_by_role('button',name='刘家铭',exact=True).click()
        dialog=page.locator('.el-dialog:visible');expect(dialog).to_contain_text('客户经理与调整记录')
        page.wait_for_timeout(350);initial=dialog.bounding_box();header=dialog.locator('.el-dialog__header').bounding_box();page.mouse.move(header['x']+250,header['y']+18);page.mouse.down();page.mouse.move(header['x']+310,header['y']+58,steps=8);page.mouse.up();moved=dialog.bounding_box();assert moved['x']>initial['x']+40 and moved['y']>initial['y']+20,(initial,moved)
        select=dialog.locator('.el-select');select.click();page.get_by_role('option',name='赵震锋',exact=True).click()
        dialog.get_by_role('button',name='确认调整',exact=True).click();expect(dialog.locator('.el-form-item__error')).to_contain_text('调整原因');assert not writes
        dialog.get_by_placeholder('请说明调整客户经理的原因，保存后保留记录').fill('客户交接测试')
        dialog.get_by_role('button',name='确认调整',exact=True).click();expect(page.locator('#app').get_by_role('button',name='赵震锋',exact=True)).to_be_visible()
        assert writes==[{'client_manager_id':'u2','client_manager_change_reason':'客户交接测试','expected_updated_at':'2026-11-07T12:00:00+08:00'}],writes
        dialog.get_by_role('button',name='查看调整记录',exact=True).click()
        pop=page.locator('.project-manager-history:visible');expect(pop).to_contain_text('客户交接测试');expect(pop).to_contain_text('测试操作人');expect(pop).to_contain_text('2026/11/07')
        expect(pop).to_contain_text('刘家铭');expect(pop).to_contain_text('赵震锋')
        pop.get_by_role('button',name='关闭窗口',exact=True).click();expect(pop).not_to_be_visible();dialog.get_by_role('button',name='关闭',exact=True).click();expect(dialog).not_to_be_visible()
        page.evaluate('testState.editable=false');page.locator('#app').get_by_role('button',name='赵震锋',exact=True).click()
        expect(dialog.get_by_role('button',name='确认调整',exact=True)).to_have_count(0)
        page.wait_for_timeout(350);reopened=dialog.bounding_box();assert abs(reopened['x']-initial['x'])<2 and abs(reopened['y']-initial['y'])<2,(initial,reopened)
        expect(dialog.get_by_role('button',name='查看调整记录',exact=True)).to_be_visible()
        assert len(writes)==1 and not errors,(writes,errors)
        browser.close()
    print('list click / reason required / versioned update / audit history / read-only permissions PASS')


if __name__=='__main__':run()
