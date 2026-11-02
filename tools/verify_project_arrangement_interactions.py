"""模拟接口验证安排拖拽的 HTTP 兼容、移除确认及左右独立滚动。"""
import json
import re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE+'/src/views/project/ProjectWorkspace.vue', timeout=20).read().decode()
    vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {createApp,h,ref} from VUE;
    import Layout from '/src/views/project/translation/components/ProjectArrangementLayout.vue';
    import Table from '/src/views/project/translation/components/ProjectArrangementTable.vue';
    const projects=Array.from({length:24},(_,i)=>({id:'root'+i,orderNo:'TP-TEST-'+i,sourceFileName:'测试.docx'}));
    createApp({setup(){const selected=ref([]);return()=>h(Layout,{enabled:true,canWrite:true,modelValue:selected.value,'onUpdate:modelValue':v=>selected.value=v},{default:()=>h(Table,{projects,people:selected.value,canWrite:true,columns:[{key:'orderNo',label:'订单号'},{key:'sourceFileName',label:'项目名称'}]})})}}).mount('#app');</script>'''.replace('from VUE', 'from '+json.dumps(vue))
    tasks = [dict(id='task1',assignee_id='qa1',assignee_name='甲',order_no='TP-TEST-0',content='已保存任务',status='pending',revision=1,work_date='2026-11-01')]
    deletes, saves, errors = [], [], []

    def api(route):
        path = urlparse(route.request.url).path
        if path == '/api/departments/organization':
            result = {'items':[{'id':'dept','name':'项目部'}], 'people':[{'id':'qa1','name':'甲','active':True,'departments':[{'id':'dept','name':'项目部'}]}]}
        elif path.endswith('/directory'):
            result = {'ready':True}
        elif path.endswith('/orders'):
            result = {'ready':True,'items':[{'id':'root0','order_no':'TP-TEST-0','project_name':'测试.docx','level':1,'children':[]}]}
        elif path.endswith('/detail') or route.request.method == 'DELETE':
            if route.request.method == 'DELETE':
                deletes.append(route.request.post_data_json)
                tasks.clear()
            result = {'ready':True,'tasks':tasks,'history':[],'history_total':0,'revision':1,'common_instruction':'','instruction_revision':0}
        elif route.request.method == 'POST':
            saves.append(route.request.post_data_json)
            result = []
        else:
            result = {}
        route.fulfill(content_type='application/json', body=json.dumps(result))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        context = browser.new_context(viewport={'width':1400,'height':900})
        context.add_init_script("Object.defineProperty(crypto,'randomUUID',{value:undefined,configurable:true}); localStorage.setItem('user_id','arrangement-ui-test')")
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/arrangement-interactions-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page = context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/arrangement-interactions-test')
        left = page.locator('.arrangement-personnel')
        right = page.locator('.project-arrangement-main')
        expect(left.locator('.person')).to_have_count(1)
        assert page.evaluate('typeof crypto.randomUUID') == 'undefined'
        left.locator('.person').drag_to(page.locator('.arrangement-project').first.locator('.project-summary'))
        draft = page.locator('.project-assignees > .assignment-line')
        expect(draft).to_have_count(1)
        expect(page.locator('.el-message--warning')).to_have_count(0)
        left.locator('.person').drag_to(page.locator('.arrangement-project').first.locator('.project-summary'))
        expect(draft).to_have_count(1)
        draft.locator('textarea').fill('测试拖拽任务')
        page.get_by_role('button',name='保存安排',exact=True).click()
        expect(draft).to_have_count(0)
        assert len(saves)==1 and saves[0]['items'][0]['assignee_id']=='qa1'
        remove = page.get_by_role('button',name='移除甲的安排',exact=True)
        remove.click()
        page.get_by_role('button',name='取消',exact=True).click()
        expect(remove).to_be_visible()
        assert not deletes
        remove.click()
        page.get_by_role('button',name='确认移除',exact=True).click()
        expect(remove).to_have_count(0)
        assert deletes == [{'revision':1}]
        right.evaluate('(el)=>{el.scrollTop=0}')
        before = left.bounding_box()
        y = page.evaluate('scrollY')
        right.hover()
        page.mouse.wheel(0,700)
        page.wait_for_function("document.querySelector('.project-arrangement-main').scrollTop > 100")
        assert page.evaluate('scrollY') == y
        assert left.bounding_box()['y'] == before['y']
        assert not errors, errors
        browser.close()
    print('HTTP randomUUID fallback, personnel drop/dedup/save, removal cancel/confirm, independent right scroll PASS')


if __name__ == '__main__':
    run()
