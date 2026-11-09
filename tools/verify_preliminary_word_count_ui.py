"""预统计显示顺序、保存与重新读取；模拟接口，不写业务库。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=20).read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h,ref} from VUE;import Matrix from '/src/components/common/WordCountMatrixPopover.vue';const model=ref({});createApp({render:()=>h(Matrix,{entityType:'project',entityId:'p1',modelValue:model.value,'onUpdate:modelValue':v=>model.value=v})}).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
    state={'entity_type':'project','entity_id':'p1','company':{'words':10},'customer':{'words':20},'preliminary':{},'translator_estimate':{},'translators':[]};writes=[]
    def api(route):
        if route.request.method=='PATCH':
            changes=route.request.post_data_json['changes'];writes.extend(changes)
            for change in changes:state[change['dimension']][change['metric_type']]=change['value']
        route.fulfill(content_type='application/json',body=json.dumps(state,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1400,'height':950})
        context.route(BASE+'/preliminary-matrix-test',lambda r:r.fulfill(content_type='text/html',body=html));context.route(BASE+'/api/word-count-matrices/**',api)
        page=context.new_page();page.set_default_timeout(15000);page.goto(BASE+'/preliminary-matrix-test');page.get_by_role('button',name='字数统计',exact=True).click()
        popup=page.locator('.word-count-matrix-popper:visible');labels=popup.locator('tbody th > span');expect(labels).to_have_text(['我司统计','客户统计','预统计','译员预定（项目预估）'],use_inner_text=False)
        popup.get_by_role('spinbutton',name='预统计-页数',exact=True).fill('99');popup.get_by_role('button',name='保存',exact=True).click();expect(popup).not_to_be_visible()
        assert writes==[{'scope':'entity','dimension':'preliminary','metric_type':'pages','value':99,'arrangement_id':None}]
        page.get_by_role('button',name='字数统计',exact=True).click();expect(popup.get_by_role('spinbutton',name='预统计-页数',exact=True)).to_have_value('99');expect(popup.get_by_role('spinbutton',name='客户统计-字数',exact=True)).to_have_value('20')
        popup.get_by_role('button',name='关闭',exact=True).click()
        state['source']='project';state['sub_order_count']=2;state['customer']['words']=127
        page.get_by_role('button',name='字数统计',exact=True).click()
        expect(popup).to_contain_text('母订单与各级子订单独立填报')
        expect(popup.get_by_role('spinbutton',name='客户统计-字数',exact=True)).to_have_value('127')
        expect(popup.get_by_role('spinbutton',name='客户统计-字数',exact=True)).to_be_enabled()
        expect(popup.get_by_role('spinbutton',name='预统计-页数',exact=True)).to_be_enabled()
        popup.get_by_role('spinbutton',name='客户统计-字数',exact=True).fill('128')
        popup.get_by_role('button',name='保存',exact=True).click()
        assert len(writes)==2 and writes[-1]['value']==128
        browser.close()
    print('statistics labels, preliminary placement, independent PATCH and reopening persistence PASS')


if __name__=='__main__':run()
