"""真实工作台口译列表和共用今日安排弹窗回归；全部业务接口模拟，不写业务库。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/components/annotation/AnnotationWorkStatusDialog.vue').read().decode()
    def dep(name):
        return json.dumps(re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1))
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;
    import Group from '/src/views/schedule/components/MyProjectTaskGroup.vue';import Host from '/src/components/annotation/AnnotationWorkStatusHost.vue';import Form from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
    const router=createRouter({history:createWebHistory(),routes:[{path:'/interpretation-arrangement-test',component:{render:()=>null}}]});
    const app=createApp({render:()=>h('main',{},[h(Group,{group:'interpretation'}),h(Host)])});app.component('AppForm',Form);app.component('DraggableFormDialog',Dialog);app.use(router);app.mount('#app');</script>'''.replace('from VUE','from '+dep('vue')).replace('from ROUTER','from '+dep('vue-router'))
    state=dict(revision=0,arrangement_status='in_progress',remaining_time=None,submissions=[])
    writes=[];errors=[];unexpected=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/work-items/my-projects':
            result=dict(ready=True,total=1,items=[dict(id='ip1',project_id='ip1',project_type='interpretation',order_no='IP-TEST-001',project_name='口译今日安排测试',client_short_name='测试客户',project_status='in_progress')])
        elif path=='/api/project-arrangements/interpretation-status/ip1':
            if route.request.method=='PUT':
                values=route.request.post_data_json;writes.append(values)
                assert values['revision']==state['revision']
                state.update(values);state['revision']+=1
                result=state
            else:
                result=dict(ready=True,work_date='2026-11-02',items=[dict(id='ip1',orderNo='IP-TEST-001',projectName='口译今日安排测试',**state)])
        elif path.endswith('/annotation-status-reminder'):
            result={'remind':False}
        else:
            unexpected.append(path);result={}
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport=dict(width=1440,height=1000),service_workers='block')
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/interpretation-arrangement-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/interpretation-arrangement-test')
        page.get_by_role('button',name='今日安排',exact=True).click()
        dialog=page.locator('.annotation-work-status-dialog:visible')
        expect(dialog).to_contain_text('IP-TEST-001')
        expect(dialog.get_by_role('button',name='保存今日安排',exact=True)).to_be_visible()
        dialog.get_by_role('button',name='保存今日安排',exact=True).click()
        expect(dialog.locator('.is-error')).to_have_count(1)
        def select(label,option):
            field=dialog.locator('.el-form-item').filter(has=page.locator('label',has_text=label))
            combo=field.get_by_role('combobox')
            field.locator('.el-select__wrapper').click();list_id=combo.get_attribute('aria-controls')
            page.locator(f'[id="{list_id}"]').get_by_role('option',name=option,exact=True).click()
        select('是否今日进行','今日暂不进行')
        select('预计还需时间','1-2小时')
        dialog.get_by_role('button',name='保存今日安排',exact=True).click()
        expect(page.get_by_text('今日安排已更新',exact=True)).to_be_visible()
        assert len(writes)==1 and writes[0]['arrangement_status']=='not_today' and writes[0]['remaining_time']=='1_2h'
        page.wait_for_function("() => !document.querySelector('[class*=dialog-fade-enter-]')")
        before=dialog.bounding_box();header=dialog.locator('.el-dialog__header').bounding_box()
        x,y=header['x']+230,header['y']+15
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+55,y+30,steps=8);page.mouse.up()
        after=dialog.bounding_box();assert abs(after['x']-before['x'])+abs(after['y']-before['y'])>20
        page.mouse.move(x+55,y+30);page.mouse.down();page.mouse.move(-1800,-1800,steps=8);page.mouse.up()
        bounded=dialog.bounding_box();assert bounded['x']>=0 and bounded['y']>=0
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='今日安排',exact=True).click()
        expect(dialog).to_contain_text('今日暂不进行')
        page.wait_for_function("() => !document.querySelector('[class*=dialog-fade-enter-]')")
        reset=dialog.bounding_box();assert abs(reset['x']-before['x'])<3 and abs(reset['y']-before['y'])<3
        page.screenshot(path='scratch/interpretation-today-arrangement.png')
        page.set_viewport_size(dict(width=600,height=800))
        rect=dialog.bounding_box();assert rect['width']<=569 and rect['x']>=0
        expect(dialog.get_by_role('button',name='关闭',exact=True)).to_be_in_viewport()
        dialog.get_by_role('button',name='关闭',exact=True).click();expect(dialog).not_to_be_visible()
        assert not errors,errors
        assert not unexpected,unexpected
        browser.close()
    print('interpretation workbench Today Arrangement: shared dialog, validation, save/reopen, drag/bounds/reset and mobile PASS')


if __name__=='__main__':run()
