"""按账号草稿的切换、异步隔离和正式保存清理；接口全部模拟。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'


def run():
    source = urlopen(BASE+'/src/components/common/AppForm.vue', timeout=30).read().decode()
    vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', source).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><div id="app"></div><script type="module">
import {createApp,h,reactive} from VUE;import {useFormDraft} from '/src/composables/useFormDraft.js';import {flushCloudDrafts} from '/src/utils/cloudDrafts.js';
createApp({setup(){const form=reactive({name:''});const d=useFormDraft({namespace:'account-policy',form,requireUserId:true,createDraftVersion:'account-v2',retentionMs:null,createDefault:()=>({name:''})});
window.testDraft={form,...d,flushCloudDrafts};return()=>h('div',{},[h('input',{'aria-label':'内容',value:form.name,onInput:e=>form.name=e.target.value}),
h('button',{onClick:()=>{d.pauseDraft();form.name='';d.beginDraft('create')}},'新增'),h('button',{onClick:d.clearDraft},'正式保存成功')])}}).mount('#app');</script>'''.replace('from VUE', 'from '+json.dumps(vue))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge');page = browser.new_page()
        page.add_init_script("""localStorage.setItem('user_id','qa');localStorage.setItem('token','token-qa');for(const id of ['qa','qb'])localStorage.setItem('form-drafts:account-policy:'+id,JSON.stringify({create:{ownerId:id,version:'account-v2',savedAt:'2020-01-01T00:00:00+08:00',form:{name:id+'原有草稿'}}}));""")
        delayed = [];writes = []
        def api(route):
            if route.request.method == 'GET':
                if route.request.headers.get('authorization') == 'Bearer token-qa': delayed.append(route)
                elif route.request.headers.get('authorization') == 'Bearer token-cloud': route.fulfill(content_type='application/json',body=json.dumps({'payload':{'ownerId':'cloud','version':'account-v2','savedAt':'2026-11-07T12:00:00+08:00','form':{'name':'本账号云端未保存内容'}},'revision':1,'updated_at':'2026-11-07T12:00:00+08:00'}))
                elif route.request.headers.get('authorization') == 'Bearer token-qc': route.fulfill(content_type='application/json',body=json.dumps({'payload':{'form':{'id':'old-saved-project','name':'来源不明云端旧内容'}},'revision':99,'updated_at':'2026-11-07T12:00:00+08:00'}))
                else: route.fulfill(content_type='application/json', body='{"payload":null,"revision":0}')
            else:
                payload = route.request.post_data_json
                writes.append((route.request.headers.get('authorization'), payload))
                result = [{**item, 'revision': item['revision']+1, 'updated_at':'2026-11-07T12:00:00+08:00'} for item in payload['drafts']]
                route.fulfill(content_type='application/json', body=json.dumps(result))
        page.route(re.compile(r'^http://localhost:3000/api/'), api)
        page.route(BASE+'/account-draft-test',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/account-draft-test');page.get_by_role('button',name='新增',exact=True).click()
        field=page.get_by_role('textbox',name='内容');expect(field).to_have_value('qa原有草稿')
        field.fill('甲刚刚填写');page.evaluate("window.dispatchEvent(new Event('pagehide'))")
        assert page.evaluate("JSON.parse(localStorage.getItem('form-drafts:account-policy:qa')).create.form.name")=='甲刚刚填写'
        # 同一个已挂载组件内换账号，旧表单不能写进任一账号的草稿。
        page.evaluate("localStorage.setItem('user_id','qb');localStorage.setItem('token','token-qb')")
        field.fill('不可串入任何账号');page.wait_for_timeout(500)
        assert page.evaluate("JSON.parse(localStorage.getItem('form-drafts:account-policy:qa')).create.form.name")=='甲刚刚填写'
        assert page.evaluate("JSON.parse(localStorage.getItem('form-drafts:account-policy:qb')).create.form.name")=='qb原有草稿'
        page.get_by_role('button',name='新增',exact=True).click();expect(field).to_have_value('qb原有草稿')
        for route in delayed:route.fulfill(content_type='application/json',body=json.dumps({'payload':{'form':{'name':'迟到的甲账号云端内容'}},'revision':1,'updated_at':'2026-11-07T12:00:00+08:00'}))
        page.wait_for_timeout(200);expect(field).to_have_value('qb原有草稿')
        field.fill('乙待正式保存');page.evaluate('testDraft.flushDraft()')
        page.get_by_role('button',name='正式保存成功',exact=True).click();page.evaluate('testDraft.flushCloudDrafts()')
        assert page.evaluate("JSON.parse(localStorage.getItem('form-drafts:account-policy:qb')||'{}').create??null") is None
        assert page.evaluate("JSON.parse(localStorage.getItem('form-drafts:account-policy:qa')).create.form.name")=='甲刚刚填写'
        assert writes and all(owner=='Bearer token-qb' for owner,_ in writes),writes
        assert any(item['payload'] is None for _,batch in writes for item in batch['drafts'])
        # 退出前同步保存最后一次输入，未认证状态不创建匿名草稿。
        page.get_by_role('button',name='新增',exact=True).click();field.fill('乙退出前最后输入')
        page.evaluate("window.dispatchEvent(new Event('auth-session-clearing'));localStorage.removeItem('user_id');localStorage.removeItem('user_name')")
        assert page.evaluate("JSON.parse(localStorage.getItem('form-drafts:account-policy:qb')).create.form.name")=='乙退出前最后输入'
        page.get_by_role('button',name='新增',exact=True).click();field.fill('未认证输入');page.wait_for_timeout(500)
        assert page.evaluate("localStorage.getItem('form-drafts:account-policy:anonymous')") is None
        page.evaluate("localStorage.setItem('user_id','qc');localStorage.setItem('token','token-qc');localStorage.setItem('form-drafts:account-policy:qc',JSON.stringify({create:{ownerId:'qa',version:'account-v2',form:{name:'其他账号旧内容'}}}))")
        page.get_by_role('button',name='新增',exact=True).click();expect(field).to_have_value('');page.wait_for_timeout(300);expect(field).to_have_value('')
        page.evaluate("localStorage.setItem('user_id','cloud');localStorage.setItem('token','token-cloud')")
        page.get_by_role('button',name='新增',exact=True).click();expect(field).to_have_value('本账号云端未保存内容')
        assert page.evaluate("JSON.parse(localStorage.getItem('form-drafts:account-policy:cloud')).create.ownerId")=='cloud'
        assert not errors,errors
        browser.close()
    print('account isolation, delayed response, immediate close/logout, clear-after-save and no anonymous drafts PASS')


if __name__=='__main__':run()
