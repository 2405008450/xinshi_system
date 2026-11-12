"""真实统计组件回归：隔离旧草稿、四级只读汇总、粘贴与保存；不访问业务库。"""
import json
import re
from urllib.request import urlopen
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'

def run():
    compiled = urlopen(BASE + '/src/views/project/ProjectWorkspace.vue', timeout=30).read().decode()
    vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
    rows = [
        {'id': 'p1', 'subOrderNo': 'TP-261109-001.001', 'wordCountMatrix': {'company': {'words': 999}}},
        {'id': 'p2', 'subOrderNo': 'TP-261109-001.001.001', 'wordCountMatrix': {}},
        {'id': 'p3', 'subOrderNo': 'TP-261109-001.001.001.001', 'wordCountMatrix': {}},
        {'id': 'leaf', 'subOrderNo': 'TP-261109-001.001.001.001.001', 'wordCountMatrix': {'company': {'words': 3430}, 'customer': {'pages': 2}}},
        {'id': 'zero', 'subOrderNo': 'TP-261109-001.002', 'wordCountMatrix': {'company': {'words': 0}}},
    ]
    html = '''<!doctype html><meta charset="UTF-8"><title>统计回归</title>
<link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div>
<script type="module">
import {createApp,h,reactive} from VUE;
import Grid from '/src/views/project/translation/components/SubOrderStatisticsGrid.vue';
import {installAutoDrafts} from '/src/utils/autoDrafts.js';
import {createAutoDraftStore,draftHash} from '/src/utils/autoDraftStore.js';
const rows=reactive(ROWS);window.testRows=rows;window.saved=0;
// 模拟旧版单元格遗留草稿：点击/聚焦曾把 3430 覆盖成 111。
const identity='/statistics-regression|统计回归|control|new||TP-261109-001.001.001.001.001 我司统计:12';
createAutoDraftStore({storage:localStorage,owner:'statistics-qa'}).save({id:draftHash(identity)+':'+identity,identity,data:'111'});
const app=createApp({render:()=>h(Grid,{rows,editable:true,onSaved:()=>window.saved++})});installAutoDrafts(app);app.mount('#app');
</script>'''.replace('from VUE', 'from '+json.dumps(vue)).replace('reactive(ROWS)', 'reactive('+json.dumps(rows)+')')
    writes=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge')
        page=browser.new_page(viewport={'width':1600,'height':950})
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script("localStorage.setItem('user_id','statistics-qa')")
        def api(route):
            if route.request.method=='PATCH':
                writes.append((route.request.url,route.request.post_data_json))
                page.evaluate('''({id,changes})=>{const row=window.testRows.find(row=>row.id===id);for(const cell of changes){const key=cell.dimension==='translator_estimate'?'translatorEstimate':cell.dimension;row.wordCountMatrix[key]??={};row.wordCountMatrix[key][cell.metric_type]=cell.value}}''', {'id':route.request.url.rsplit('/',1)[-1], 'changes':route.request.post_data_json['changes']})
            route.fulfill(content_type='application/json',body='{}')
        page.route(BASE+'/api/**',api)
        page.route(BASE+'/statistics-regression',lambda route:route.fulfill(content_type='text/html',body=html))
        page.goto(BASE+'/statistics-regression')
        table=page.locator('tbody tr')
        parents=table.nth(0).locator('input')
        expect(parents.nth(0)).to_have_value('3430')
        expect(page.locator('select').nth(1)).to_have_value('pages')
        expect(parents.nth(1)).to_have_value('2')
        # 页数已填写时锁定客户字数，清空页数后才可切换。
        page.locator('select').nth(1).select_option('words')
        customer = table.nth(3).locator('input').nth(1)
        expect(customer).to_be_disabled()
        for index in range(3):
            expect(table.nth(index).locator('input').nth(0)).to_have_value('3430')
            assert table.nth(index).locator('input').nth(0).get_attribute('readonly') is not None
            expect(table.nth(index)).to_contain_text('下级汇总')
        leaf=table.nth(3).locator('input').nth(0)
        # 按实际 DOM 位置重新生成遗留草稿的索引（只读组件也有输入框）。
        page.evaluate('''async()=>{const {createAutoDraftStore,draftHash}=await import('/src/utils/autoDraftStore.js');const el=document.querySelectorAll('tbody tr')[3].querySelector('input');const index=[...document.querySelectorAll('input,textarea,[contenteditable="true"]')].indexOf(el);const identity='/statistics-regression|统计回归|control|new||'+el.getAttribute('aria-label')+':'+index;createAutoDraftStore({storage:localStorage,owner:'statistics-qa'}).save({id:draftHash(identity)+':'+identity,identity,data:'111'})}''')
        leaf.click();expect(leaf).to_have_value('3430')
        page.locator('select').nth(0).select_option('pages');page.locator('select').nth(0).select_option('words')
        expect(leaf).to_have_value('3430')
        expect(page.get_by_role('button',name='保存统计（0 单）')).to_be_disabled()
        page.locator('select').nth(1).select_option('pages')
        customer.fill('')
        page.locator('select').nth(1).select_option('words')
        expect(customer).to_be_enabled()
        leaf.fill('4000')
        for index in range(3):expect(table.nth(index).locator('input').nth(0)).to_have_value('4000')
        leaf.fill('')
        for index in range(3):expect(table.nth(index).locator('input').nth(0)).to_have_value('')
        leaf.evaluate("el=>el.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:(()=>{const d=new DataTransfer();d.setData('text/plain','12\\t34\\n56\\t78');return d})()}))")
        expect(leaf).to_have_value('12')
        for index in range(3):expect(table.nth(index).locator('input').nth(0)).to_have_value('12')
        expect(table.nth(4).locator('input').nth(0)).to_have_value('56')
        # 父级粘贴不会创建修改，仍然只能从叶子汇总。
        parents.nth(0).evaluate("el=>el.dispatchEvent(new InputEvent('input',{bubbles:true}))")
        page.get_by_role('button',name='保存统计（2 单）').click()
        expect(page.get_by_role('button',name='保存统计（0 单）')).to_be_disabled()
        assert len(writes)==2 and all(url.rsplit('/',1)[-1] in ('leaf','zero') for url,_ in writes),writes
        expect(leaf).to_have_value('12')
        leaf.click();expect(leaf).to_have_value('12')
        page.locator('select').nth(1).select_option('pages')
        for index in range(3):expect(table.nth(index).locator('input').nth(1)).to_have_value('')
        assert not errors,errors
        browser.close()
    print('PASS: stale draft isolation / click unchanged / four-level readonly rollup / clear and zero / paste / leaf-only save')

if __name__=='__main__':run()
