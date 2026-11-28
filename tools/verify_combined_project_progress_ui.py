"""四类项目共用进度录入，无模式切换即可修改状态和说明；业务接口全部拦截。"""
import json
import re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect

BASE='http://localhost:3000'


def run():
    source=urlopen(BASE+'/src/main.js').read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',source).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {createApp,h,reactive} from VUE;import Entry from '/src/components/common/ProjectProgressEntryForm.vue';import {getProjectStatusOptions} from '/src/utils/projectStatus.js';
    const types=['translation','interpretation','annotation','recruitment'];const values=reactive(Object.fromEntries(types.map(type=>[type,{projectStatus:getProjectStatusOptions(type)[0].value,effectiveOn:'2026-11-28T17:23:00',changeNote:''}])));window.submissions=[];
    createApp({render:()=>h('main',{},types.map(type=>h('section',{'data-type':type,style:'padding:20px;border:1px solid #ddd'},[h(Entry,{modelValue:values[type],statuses:getProjectStatusOptions(type),'onUpdate:modelValue':value=>values[type]=value,onSubmit:()=>window.submissions.push({type,...values[type]})})])))}).mount('#app')</script>'''.replace('VUE',json.dumps(vue))
    errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1400,'height':1050},service_workers='block')
        context.route(re.compile(r'^http://localhost:3000/api/'),lambda r:r.fulfill(content_type='application/json',body='{}'))
        context.route(BASE+'/combined-progress-test',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/combined-progress-test')
        for index,kind in enumerate(['translation','interpretation','annotation','recruitment']):
            panel=page.locator(f'[data-type="{kind}"]')
            expect(panel.get_by_role('radio')).to_have_count(0)
            panel.locator('textarea').fill(kind+'状态变更说明')
            panel.locator('.el-select').click()
            list_id=panel.locator('.el-select').get_by_role('combobox').get_attribute('aria-controls')
            page.locator('[id="'+list_id+'"]').get_by_role('option',name='项目取消' if kind=='recruitment' else '已取消',exact=True).click()
            expect(panel.locator('textarea')).to_have_value(kind+'状态变更说明')
            panel.get_by_role('button',name='保存项目进度',exact=True).click()
            page.wait_for_function('(n)=>window.submissions.length===n',arg=index*2+1)
            first=page.evaluate('window.submissions.at(-1)')
            assert first['projectStatus']=='cancelled' and first['changeNote']==kind+'状态变更说明'
            panel.locator('textarea').fill(kind+'状态不变追加说明')
            panel.get_by_role('button',name='保存项目进度',exact=True).click()
            page.wait_for_function('(n)=>window.submissions.length===n',arg=index*2+2)
            second=page.evaluate('window.submissions.at(-1)')
            assert second['projectStatus']=='cancelled' and second['changeNote']==kind+'状态不变追加说明'
        assert not errors,errors
        browser.close()
    print('PASS: 四类项目同一表单修改状态与说明、保留已填说明、状态不变追加进度')


if __name__=='__main__':run()
