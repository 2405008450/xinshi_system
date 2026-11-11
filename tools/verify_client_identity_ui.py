"""公共表单客户全称回填：笔译、组合子客户、咨询字段，全部接口模拟。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive,ref} from VUE;import {ElFormItem} from '/node_modules/.vite/deps/element-plus.js';import Form from '/src/components/common/AppForm.vue';import Field from '/src/components/common/ReadonlyField.vue';
const models=reactive([{clientId:'parent',subClientId:'child',subClientName:'独立子客户',clientName:'',clientShortName:'',clientCode:''},{clientId:'parent',subClientId:'child',clientFullName:'',clientShortName:'',clientCode:''},{client_id:'parent',client_name:'',client_short_name:'',client_code:''}]);const fields=['clientName','clientFullName','client_name'],forms=[],status=ref('');
createApp({render:()=>h('div',[...models.map((model,index)=>h('section',{'data-case':index},[h(Form,{ref:el=>forms[index]=el,model,rules:{[fields[index]]:[{required:true,message:'客户全称必填'}]}},{default:()=>h(ElFormItem,{label:'客户全称',prop:fields[index]},()=>h(Field,{modelValue:model[fields[index]],source:'auto'}))}),h('span',{class:'short'},model.clientShortName||model.client_short_name)])),h('button',{onClick:async()=>{try{for(const form of forms)await form.validate();status.value='校验通过'}catch{status.value='校验失败'}}},'保存前校验'),h('p',{id:'status'},status.value)])}).mount('#app');
</script>'''.replace('from VUE','from '+json.dumps(vue))
    client={'id':'parent','client_name':'客户全称有限公司','client_short_name':'客户简称','client_code':'C001','sub_clients':[{'id':'child','client_name':'子客户全称有限公司','client_short_name':'子客户简称','sub_client_code':'SC001'}]}
    calls=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1200,'height':850});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script("localStorage.setItem('user_id','identity-qa')")
        def api(route):
            path=urlparse(route.request.url).path
            if path=='/api/clients/parent':calls.append(path);result=client
            else:result={}
            route.fulfill(content_type='application/json',body=json.dumps(result))
        page.route(BASE+'/api/**',api);page.route(BASE+'/client-identity-qa',lambda route:route.fulfill(content_type='text/html',body=html))
        page.goto(BASE+'/client-identity-qa')
        for index,full in enumerate(['客户全称有限公司','子客户全称有限公司','客户全称有限公司']):
            field=page.locator(f'section[data-case="{index}"] input');expect(field).to_have_value(full)
            assert field.get_attribute('readonly') is not None
        expect(page.locator('section[data-case="0"] .short')).to_have_text('客户简称')
        expect(page.locator('section[data-case="1"] .short')).to_have_text('子客户简称')
        page.get_by_role('button',name='保存前校验',exact=True).click();expect(page.locator('#status')).to_have_text('校验通过')
        assert calls==['/api/clients/parent'],calls
        assert not errors,errors
        browser.close()
    print('PASS: public AppForm fills full client identity / parent-vs-subclient mapping / readonly values / validation / shared request')
if __name__=='__main__':run()
