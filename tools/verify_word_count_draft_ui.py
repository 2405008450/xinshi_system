"""统计矩阵完整回显、账号隔离、未提交恢复与外层提交；所有业务接口模拟。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import expect, sync_playwright

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/components/common/AppForm.vue',timeout=30).read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive,ref} from VUE;import Matrix from '/src/components/common/WordCountMatrixPopover.vue';import {installAutoDrafts} from '/src/utils/autoDrafts.js';import {formatWordCountMatrix} from '/src/utils/wordCountMatrix.js';
const s=window.testState=reactive({matrix:{company:{words:9999}},pending:null,local:false,mounted:true});window.matrixRef=ref();
const app=createApp({render:()=>h('div',{},[h('div',{id:'summary'},formatWordCountMatrix(s.pending?.ownerId===localStorage.getItem('user_id')?s.pending.matrix:s.matrix)),s.mounted?h(Matrix,{ref:window.matrixRef,entityType:'project',entityId:s.local?'':'p1',local:s.local,modelValue:s.matrix,pendingDraft:s.local?s.pending:undefined,draftScope:'matrix-test','onUpdate:modelValue':v=>s.matrix=v,'onUpdate:pendingDraft':v=>s.pending=v}):null])});installAutoDrafts(app);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
    saved={'entity_type':'project','entity_id':'p1','company':{'words':2345},'customer':{'characters_no_spaces':2200},'preliminary':{'pages':4,'foreign_words':800},'translator_estimate':{'words':2300},'translators':[{'arrangement_id':'a1','translator_id':'t1','translator_name':'测试译员','planned':{'words':2000},'actual':{'words':1900}}]}
    writes=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path.startswith('/api/word-count-matrices/'):
            if route.request.method=='PATCH':
                changes=route.request.post_data_json['changes'];writes.extend(changes)
                for change in changes:saved[change['dimension']][change['metric_type']]=change['value']
            result=saved
        elif path=='/api/editor-drafts':result={'payload':None,'revision':0}
        elif path=='/api/editor-drafts/batch':result=[{**item,'revision':item['revision']+1,'updated_at':'2026-11-07T18:00:00+08:00'} for item in route.request.post_data_json['drafts']]
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1500,'height':1000})
        context.add_init_script("if(!localStorage.getItem('matrix-test-seeded')){localStorage.setItem('matrix-test-seeded','1');localStorage.setItem('user_id','qa');localStorage.setItem('token','qa')}")
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/matrix-draft-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/matrix-draft-test')
        pop=page.locator('.word-count-matrix-popper:visible');opener=page.get_by_role('button',name='字数统计',exact=True)
        def open_box():opener.click();expect(pop).to_be_visible()
        def field(name):return pop.get_by_role('spinbutton',name=name,exact=True)
        def close_box():pop.get_by_role('button',name='关闭',exact=True).click();expect(pop).not_to_be_visible()
        def switch(user):page.evaluate("user=>{localStorage.setItem('user_id',user);localStorage.setItem('token',user)}",user)
        open_box();expect(field('我司统计-字数')).to_have_value('2345');expect(field('客户统计-字符数（不计空格）')).to_have_value('2200')
        expect(field('预统计-页数')).to_have_value('4');expect(field('预统计-外文字数')).to_have_value('800')
        expect(field('译员预定（项目预估）-字数')).to_have_value('2300');expect(field('测试译员 · 预定-字数')).to_have_value('2000');expect(field('测试译员 · 实际-字数')).to_have_value('1900')
        expect(page.locator('#summary')).to_contain_text('2,345');expect(pop.locator('.word-count-matrix')).to_have_attribute('data-auto-draft','off')
        field('我司统计-字数').fill('2000');close_box();assert not writes
        page.reload();open_box();expect(field('我司统计-字数')).to_have_value('2000');expect(pop).to_contain_text('未保存修改');close_box()
        switch('qb');open_box();expect(field('我司统计-字数')).to_have_value('2345');field('我司统计-字数').fill('2100');close_box()
        switch('qa');open_box();expect(field('我司统计-字数')).to_have_value('2000');pop.get_by_role('button',name='保存',exact=True).click();expect(pop).not_to_be_visible()
        assert writes==[{'scope':'entity','dimension':'company','metric_type':'words','value':2000,'arrangement_id':None}],writes
        open_box();expect(field('我司统计-字数')).to_have_value('2000');expect(pop).not_to_contain_text('未保存修改');close_box()
        switch('qb');open_box();expect(field('我司统计-字数')).to_have_value('2100');close_box()
        switch('qc');open_box();expect(field('我司统计-字数')).to_have_value('2000');close_box()
        # 新建项目由外层账号草稿携带未保存的整个矩阵，不留下独立的旧项目缓存。
        switch('qa');page.evaluate("testState.local=true;testState.pending=null;testState.matrix={company:{words:3100}}")
        open_box();expect(field('我司统计-字数')).to_have_value('3100');field('我司统计-字数').fill('3200');close_box()
        assert page.evaluate('testState.matrix.company.words')==3100
        assert page.evaluate('testState.pending.ownerId')=='qa'
        expect(page.locator('#summary')).to_contain_text('3,200')
        page.evaluate('testState.mounted=false');page.wait_for_timeout(50);page.evaluate('testState.mounted=true')
        open_box();expect(field('我司统计-字数')).to_have_value('3200');close_box()
        assert page.evaluate('matrixRef.value.prepareSubmit()') is True
        assert page.evaluate('testState.matrix.company.words')==3200
        open_box();pop.get_by_role('button',name='保存',exact=True).click();expect(pop).not_to_be_visible()
        assert page.evaluate('testState.pending') is None
        assert len(writes)==1 and not errors,(writes,errors)
        browser.close()
    print('full saved matrix, private pending changes, refresh/account isolation, save clearing and outer submission PASS')


if __name__=='__main__':run()
