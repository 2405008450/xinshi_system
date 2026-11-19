"""隔离数据验证公共筛选：确认、关闭、恢复生效项、清除及切换页面。"""
import json
import re
from urllib.request import urlopen
from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE + '/src/views/project/ProjectWorkspace.vue', timeout=20).read().decode()
    vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled)[1]
    html = '''<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="/node_modules/element-plus/dist/index.css">
<div id="app"></div><script type="module">
import {createApp,h,reactive,ref} from VUE;
import Advanced from '/src/components/common/AdvancedFilterPopover.vue';
import Compact from '/src/components/common/CompactFilterGrid.vue';
import Header from '/src/components/common/ConfiguredColumnHeaderFilter.vue';
import Window from '/src/components/common/WindowPopover.vue';
import Control from '/src/components/common/ListFilterControl.vue';
const fields=[{key:'name',label:'名称',type:'text'},
 {key:'status',label:'状态',type:'select',options:[{value:'a',label:'甲'},{value:'b',label:'乙'}]}];
const app=createApp({setup(){
 const form=reactive({name:'',status:[]}),visible=ref(false),header=ref([]),custom=ref(''),customVisible=ref(false);
 const query=ref({name:'',status:[]}),switched=ref(false),client=ref('802c34ab-798a-46f2-ab7f-e15ecbe00001');
 const apply=()=>query.value=JSON.parse(JSON.stringify(form));
 const reset=()=>{Object.assign(form,{name:'',status:[]});apply()};
 window.fixture={form,query,header,custom};
 return()=>h('div',{style:'padding:30px'},[
  h('button',{onClick:()=>{switched.value=!switched.value;reset();header.value=[];custom.value=''}},'切换窗口'),
  !switched.value?h(Advanced,{visible:visible.value,'onUpdate:visible':v=>visible.value=v,
    count:form.status.length+(form.name?1:0),onReset:reset,onClear:reset},
    ()=>h(Compact,{fields,model:form,onUpdate:(k,v)=>form[k]=v,onEnter:apply,onChange:apply,onTextInput:apply})):null,
  h('output',{'aria-label':'筛选结果'},JSON.stringify(query.value)),
  h(Header,{definition:fields[1],modelValue:header.value,'onUpdate:modelValue':v=>header.value=v}),
  h('output',{'aria-label':'表头筛选结果'},JSON.stringify(header.value)),
  h(Window,{visible:customVisible.value,'onUpdate:visible':v=>customVisible.value=v,title:'自定义筛选'},
   {reference:()=>h('button',{},'自定义入口'),default:()=>h(Control,{definition:fields[0],modelValue:custom.value,'onUpdate:modelValue':v=>custom.value=v})}),
  h('output',{'aria-label':'自定义结果'},custom.value)
  ,h(Control,{definition:{key:'client_short_name',type:'text',autocomplete:'client'},modelValue:client.value,'onUpdate:modelValue':v=>client.value=v})
  ,h('output',{'aria-label':'客户简称值'},client.value)
 ])}});app.mount('#app');
</script>'''.replace('from VUE', 'from ' + json.dumps(vue))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        page = browser.new_page(viewport={'width': 1400, 'height': 950})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route(BASE + '/api/**', lambda r: r.fulfill(json={
            'id':'802c34ab-798a-46f2-ab7f-e15ecbe00001','client_short_name':'甲客户','client_name':'甲方公司',
        } if '/clients/802c34ab-' in r.request.url else []))
        page.route(BASE + '/filter-retention-check', lambda r: r.fulfill(content_type='text/html', body=html))
        page.goto(BASE + '/filter-retention-check')
        expect(page.get_by_label('客户简称值')).to_have_text('甲客户')
        advanced = page.get_by_role('button', name=re.compile('^高级筛选'))
        popup = page.locator('.common-advanced-filter-popover:visible')
        result = page.get_by_label('筛选结果', exact=True)
        advanced.click()
        field = popup.get_by_placeholder('筛选名称', exact=True)
        field.fill('已应用条件')
        popup.get_by_role('button', name='确定', exact=True).click()
        expect(popup).to_be_hidden()
        expect(result).to_contain_text('已应用条件')
        advanced.click()
        expect(field).to_have_value('已应用条件')
        field.fill('未确认修改')
        popup.get_by_role('button', name='关闭', exact=True).click()
        expect(result).to_contain_text('已应用条件')
        advanced.click()
        expect(field).to_have_value('已应用条件')
        popup.get_by_role('button', name='取消筛选', exact=True).click()
        expect(result).not_to_contain_text('已应用条件')
        advanced.click()
        expect(field).to_have_value('')
        popup.get_by_role('button', name='关闭', exact=True).click()

        trigger = page.get_by_role('button', name='状态筛选', exact=True)
        header = page.locator('.column-header-filter-popover:visible')
        trigger.click()
        header.locator('label.el-checkbox').filter(has_text='甲').click()
        header.get_by_role('button', name='确定', exact=True).click()
        expect(page.get_by_label('表头筛选结果')).to_have_text('["a"]')
        trigger.click()
        expect(header.get_by_role('checkbox', name='甲', exact=True)).to_be_checked()
        header.get_by_role('button', name='取消筛选', exact=True).click()
        expect(page.get_by_label('表头筛选结果')).to_have_text('[]')
        header.get_by_role('button', name='取消', exact=True).click()

        page.get_by_role('button', name='自定义入口').click()
        custom = page.locator('.app-window-popover:visible').filter(has_text='自定义筛选')
        custom.get_by_placeholder('筛选名称').fill('自定义保留')
        custom.get_by_role('button', name='确定', exact=True).click()
        expect(page.get_by_label('自定义结果')).to_have_text('自定义保留')
        page.get_by_role('button', name='自定义入口').click()
        expect(custom.get_by_placeholder('筛选名称')).to_have_value('自定义保留')
        custom.get_by_role('button', name='取消筛选', exact=True).click()
        expect(page.get_by_label('自定义结果')).to_have_text('')
        page.get_by_role('button', name='切换窗口').click()
        page.get_by_role('button', name='切换窗口').click()
        advanced.click()
        expect(field).to_have_value('')
        assert not errors, errors
        browser.close()
    print('advanced/header/custom filters: retain applied values and results, discard unconfirmed changes, clear together PASS')


if __name__ == '__main__':
    run()
