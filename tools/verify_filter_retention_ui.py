"""筛选关闭保留回归验收：本机前端、全量业务接口拦截，不连接数据库。"""
import json
import re
import functools
import http.server
import threading
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://127.0.0.1:3000'


def verify_talent_and_grouped_filters():
    requests, errors = [], []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def handle(self):
            try:
                super().handle()
            except ConnectionError:
                pass  # 页面切换时可能中断尚未完成的静态资源连接。

        def log_message(self, *args):
            pass

        def do_GET(self):
            if not Path(self.translate_path(self.path)).is_file() and not Path(self.path).suffix:
                self.path = '/index.html'
            super().do_GET()

    root = Path(__file__).resolve().parents[1]
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(root / 'frontend/dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def api(route):
        path = urlparse(route.request.url).path.removeprefix('/api').rstrip('/')
        result = []
        if path == '/auth/session':
            result = dict(user_id='filter-ui-test', username='筛选验收', roles=['admin'], permissions=['*'])
        elif path == '/talents/page':
            requests.append(route.request.url)
            result = dict(items=[], total=0)
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport=dict(width=1440, height=1000))
        context.add_init_script("localStorage.setItem('token','isolated-filter-ui-test')")
        context.route(re.compile(r'^http://127\.0\.0\.1:\d+/api/'), api)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_port}/resource-management/talents')
        trigger = page.get_by_role('button', name='状态筛选', exact=True)
        try:
            expect(trigger).to_be_visible(timeout=20000)
        except AssertionError:
            print(page.locator('body').inner_text()[:2500], errors, flush=True)
            raise
        panel = page.locator('.column-header-filter-popover:visible')

        def open_status():
            trigger.click()
            expect(panel).to_be_visible()

        def check_selected(labels):
            expect(panel.locator('.el-checkbox input:checked')).to_have_count(len(labels))
            for label in labels:
                expect(panel.get_by_role('checkbox', name=label, exact=True)).to_be_checked()

        def close_window():
            panel.get_by_role('button', name='关闭窗口', exact=True).click()
            expect(panel).to_have_count(0)

        open_status()
        panel.get_by_text('备用', exact=True).click()
        panel.get_by_text('活跃', exact=True).click()
        panel.get_by_role('button', name='确定', exact=True).click()
        expect(panel).to_have_count(0)
        expect(trigger).to_have_class(re.compile('is-active'))
        page.wait_for_timeout(500)
        assert requests and 'standby' in requests[-1] and 'active' in requests[-1], requests
        request_count = len(requests)
        open_status()
        check_selected(['备用', '活跃'])
        close_window()
        page.wait_for_timeout(500)
        assert len(requests) == request_count, '关闭不应触发清空查询'
        open_status()
        check_selected(['备用', '活跃'])
        panel.get_by_text('休眠', exact=True).click()
        panel.get_by_role('button', name='取消', exact=True).click()
        open_status()
        check_selected(['备用', '活跃'])
        panel.get_by_text('休眠', exact=True).click()
        page.locator('.page-title').click()
        expect(panel).to_have_count(0)
        open_status()
        check_selected(['备用', '活跃'])
        # 清空仍是临时选择；取消后恢复，确定后才清除正式条件。
        panel.get_by_role('button', name='清空', exact=True).click()
        panel.get_by_role('button', name='取消', exact=True).click()
        open_status()
        check_selected(['备用', '活跃'])
        panel.get_by_role('button', name='确定', exact=True).click()
        expect(panel).to_have_count(0)
        open_status()
        panel.get_by_role('button', name='清空', exact=True).click()
        panel.get_by_role('button', name='确定', exact=True).click()
        expect(trigger).not_to_have_class(re.compile('is-active'))
        print('人才总库：确认应用、关闭保留、取消/外部点击放弃草稿、明确清空 PASS', flush=True)

        # 挂载真实公共组件，覆盖组合筛选及独立时间/排除状态控件。
        source = urlopen(BASE + '/src/components/common/searchableControls.js').read().decode()
        vue_url = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', source).group(1)
        html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive} from VUE;
import Configured from '/src/components/common/ConfiguredColumnHeaderFilter.vue';
import Advanced from '/src/components/common/AdvancedFilterPopover.vue';
import Control from '/src/components/common/ListFilterControl.vue';
import Arrangement from '/src/views/project/translation/components/ArrangementFilterToolbar.vue';
const s=window.testState=reactive({status:['a'],text:'原条件',advanced:false,resets:0,queries:0,excluded:['a'],reception:['2026-11-01','2026-11-18'],deadline:[]});
const options=Array.from({length:30},(_,i)=>({label:'选项'+i,value:i===0?'a':String(i)}));
createApp({render:()=>h('main',{style:{padding:'40px',display:'grid',gap:'20px'}},[
h('button',{id:'outside'},'外部'),
h(Configured,{definition:{type:'group',label:'组合',fields:[{key:'status',label:'状态',type:'select',options},{key:'text',label:'文本',type:'text'}]},model:s,'onUpdate-field':(key,value)=>s[key]=value,onEnter:()=>s.queries++}),
h(Advanced,{visible:s.advanced,'onUpdate:visible':v=>s.advanced=v,count:1,onReset:()=>s.resets++,onClear:()=>s.text=''},{default:()=>h(Control,{definition:{type:'text',label:'Advanced text',placeholder:'Advanced text'},modelValue:s.text,'onUpdate:modelValue':v=>s.text=v,onEnter:()=>s.queries++})}),
h(Arrangement,{excluded:s.excluded,statuses:options,reception:s.reception,deadline:s.deadline,'onUpdate:excluded':v=>s.excluded=v,'onUpdate:reception':v=>s.reception=v,'onUpdate:deadline':v=>s.deadline=v})
])}).mount('#app');</script>'''.replace('from VUE', 'from ' + json.dumps(vue_url))
        page.route('**/filter-retention-test', lambda route: route.fulfill(content_type='text/html', body=html))
        page.goto(BASE + '/filter-retention-test')
        group_trigger = page.get_by_role('button', name='组合筛选', exact=True)
        try:
            expect(group_trigger).to_be_visible()
        except AssertionError:
            print(page.locator('body').inner_text()[:2500], errors, flush=True)
            raise
        group_trigger.click()
        group = page.locator('.column-header-filter-popover:visible')
        group.get_by_text('选项1', exact=True).click()
        group.get_by_role('button', name='确定', exact=True).click()
        expect(group).to_have_count(0)
        assert page.evaluate('testState.status') == ['a', '1']
        page.get_by_role('button', name='组合筛选', exact=True).click()
        group.get_by_text('选项2', exact=True).click()
        group.get_by_role('button', name='取消', exact=True).click()
        assert page.evaluate('testState.status') == ['a', '1']
        assert page.evaluate('testState.text') == '原条件'
        page.get_by_role('button', name=re.compile('高级筛选')).click()
        advanced = page.locator('.common-advanced-filter-popover:visible')
        advanced.get_by_placeholder('Advanced text').fill('保留高级条件')
        advanced.get_by_role('button', name='确定', exact=True).click()
        page.get_by_role('button', name=re.compile('^高级筛选')).click()
        advanced.get_by_role('button', name='关闭', exact=True).click()
        assert page.evaluate('testState.resets') == 0
        page.get_by_role('button', name=re.compile('高级筛选')).click()
        expect(advanced.get_by_placeholder('Advanced text')).to_have_value('保留高级条件')
        advanced.get_by_role('button', name='取消筛选', exact=True).click()
        assert page.evaluate('testState.resets') == 1
        page.locator('#outside').click()
        assert page.evaluate('testState.resets') == 1
        page.get_by_role('button', name=re.compile('时间筛选')).click()
        time_panel = page.locator('.arrangement-filter-popover:visible')
        expect(time_panel).to_be_visible()
        page.locator('#outside').click()
        assert page.evaluate('testState.reception') == ['2026-11-01', '2026-11-18']
        page.get_by_role('button', name=re.compile('时间筛选')).click()
        time_panel.get_by_role('button', name='清空时间条件', exact=True).click()
        assert page.evaluate('testState.reception') == []
        page.locator('#outside').click()
        page.get_by_role('button', name=re.compile('^排除状态')).click()
        exclusion = page.locator('.project-status-exclusion-popover:visible')
        exclusion.get_by_text('选项1', exact=True).click()
        page.locator('#outside').click()
        assert page.evaluate('testState.excluded') == ['a', '1']
        page.get_by_role('button', name=re.compile('^排除状态')).click()
        expect(exclusion.get_by_role('checkbox', name='选项1', exact=True)).to_be_checked()
        exclusion.get_by_role('button', name='取消全部', exact=True).click()
        assert page.evaluate('testState.excluded') == []
        assert not errors, errors
        print('组合筛选、高级筛选关闭/重置、时间筛选重开/清空、排除状态保留 PASS', flush=True)
        browser.close()
    server.shutdown()


def verify_filter_drafts():
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
        browser = p.chromium.launch(channel='msedge', headless=True)
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
        field.fill('等待清空的条件')
        popup.get_by_role('button', name='确定', exact=True).click()
        advanced.click()
        field.fill('同时清空未确认的输入')
        popup.get_by_role('button', name='清空高级条件', exact=True).click()
        expect(field).to_have_value('')
        expect(result).not_to_contain_text('等待清空的条件')
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
    verify_talent_and_grouped_filters()
    verify_filter_drafts()
