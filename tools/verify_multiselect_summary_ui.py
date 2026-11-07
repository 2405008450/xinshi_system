"""统一多选下拉验收：普通/远程/虚拟列表/级联及复选浮窗，无业务接口。"""
import json
import re
from urllib.request import urlopen
from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'


def run():
    source = urlopen(BASE+'/src/components/common/searchableControls.js', timeout=30).read().decode()
    dep = lambda name: re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)', source).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive} from VUE;import {ElOption,ElCheckbox} from ELEMENT;
import {SearchSelect,SearchSelectV2,SearchCascader} from '/src/components/common/searchableControls.js';
import {SelectionCheckboxGroup} from '/src/components/common/selectionCheckboxGroup.js';import WindowPopover from '/src/components/common/WindowPopover.vue';
const options=[{value:'alpha-id',label:'阿尔法'},{value:'beta-id',label:'贝塔'},{value:'gamma-id',label:'伽马'},{value:'delta-id',label:'德尔塔'},{value:'epsilon-id',label:'伊普西龙'},{value:'zeta-id',label:'泽塔'}];
const s=window.testState=reactive({normal:[],remote:[],virtual:[],cascade:[],checks:[],small:[],smallOptions:options.slice(0,5),smallVirtual:[],smallCascade:[],smallChecks:[],smallVisible:false,remoteOptions:options,filter:'',visible:false,confirmed:0});
const native=(key,extra={})=>h(SearchSelect,{id:key,popperClass:'test-'+key,multiple:true,filterable:true,collapseTags:true,modelValue:s[key],'onUpdate:modelValue':v=>s[key]=v,style:{width:'260px'},...extra},{default:()=> (key==='remote'?s.remoteOptions:key==='small'?s.smallOptions:options).map(o=>h(ElOption,{key:o.value,...o}))});
createApp({render:()=>h('main',{style:{padding:'16px',display:'grid',gap:'20px'}},[
h('div',{},['普通',native('normal')]),h('div',{},['远程',native('remote',{remote:true,remoteMethod:q=>{s.remoteOptions=q?options.filter(o=>o.label.includes(q)):options}})]),
h('div',{},['虚拟',h(SearchSelectV2,{id:'virtual',popperClass:'test-virtual',multiple:true,filterable:true,options,modelValue:s.virtual,'onUpdate:modelValue':v=>s.virtual=v,style:{width:'260px'}})]),
h('div',{},['级联',h(SearchCascader,{id:'cascade',options:[{value:'dept',label:'项目部',children:options}],props:{multiple:true,emitPath:false},modelValue:s.cascade,'onUpdate:modelValue':v=>s.cascade=v,style:{width:'260px'}})]),
h(WindowPopover,{title:'复选浮窗',width:300,trigger:'click',visible:s.visible,'onUpdate:visible':v=>s.visible=v},{reference:()=>h('button',{id:'open-checks',onClick:()=>s.visible=!s.visible},'复选浮窗'),default:()=>[
h('input',{id:'filter-checks',value:s.filter,onInput:e=>s.filter=e.target.value}),
h(SelectionCheckboxGroup,{modelValue:s.checks,'onUpdate:modelValue':v=>s.checks=v},{default:()=>options.filter(o=>o.label.includes(s.filter)).map(o=>h(ElCheckbox,{value:o.value,key:o.value},{default:()=>o.label}))}),
h('button',{onClick:()=>{s.confirmed++;s.visible=false}},'确定')]}),
h(SearchSelect,{id:'single',modelValue:'alpha-id',style:{width:'260px'}},{default:()=>options.map(o=>h(ElOption,o))}),
h('div',{},['小下拉',native('small')]),h(SearchSelectV2,{id:'smallVirtual',popperClass:'test-smallVirtual',multiple:true,options:options.slice(0,5),modelValue:s.smallVirtual,'onUpdate:modelValue':v=>s.smallVirtual=v,style:{width:'260px'}}),
h(SearchCascader,{id:'smallCascade',popperClass:'test-smallCascade',options:[{value:'small-dept',label:'小部门',children:options.slice(0,5)}],props:{multiple:true,emitPath:false},modelValue:s.smallCascade,'onUpdate:modelValue':v=>s.smallCascade=v,style:{width:'260px'}}),
h(WindowPopover,{title:'小复选浮窗',width:300,trigger:'click',visible:s.smallVisible,'onUpdate:visible':v=>s.smallVisible=v},{reference:()=>h('button',{id:'open-small-checks',onClick:()=>s.smallVisible=!s.smallVisible},'小复选浮窗'),default:()=>h(SelectionCheckboxGroup,{modelValue:s.smallChecks,'onUpdate:modelValue':v=>s.smallChecks=v},{default:()=>options.slice(0,5).map(o=>h(ElCheckbox,{value:o.value,key:o.value},{default:()=>o.label}))})})])}).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ELEMENT','from '+json.dumps(dep('element-plus')))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1000,'height':850})
        errors=[];page.on('pageerror',lambda error: (errors.append(str(error)), print(str(error)[:250], flush=True)))
        page.route('**/multiselect-summary-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page.goto(BASE+'/multiselect-summary-test')
        for key in ['normal','remote','virtual']:
            print('testing', key, flush=True)
            page.locator('#'+key).click()
            pop=page.locator('.test-'+key+':visible')
            pop.get_by_role('option',name='阿尔法',exact=True).click()
            pop.get_by_role('option',name='贝塔',exact=True).click()
            summary=pop.locator('.multi-select-summary')
            expect(summary).to_contain_text('已选 2 项')
            expect(summary.get_by_role('listitem')).to_have_text(['阿尔法','贝塔'])
            page.locator('#'+key).fill('不存在')
            expect(summary.get_by_role('listitem')).to_have_text(['阿尔法','贝塔'])
            summary.get_by_role('button',name='确认',exact=True).click()
            expect(pop).to_have_count(0)
            page.locator('#'+key).click();pop=page.locator('.test-'+key+':visible')
            expect(pop.locator('.multi-select-summary')).to_contain_text('已选 2 项')
            pop.locator('.multi-select-summary').get_by_role('button',name='确认',exact=True).click()
            expect(pop).to_have_count(0)
        page.locator('.el-cascader').first.click()
        pop=page.locator('.el-cascader__dropdown:visible')
        pop.get_by_text('项目部',exact=True).click()
        pop.get_by_text('阿尔法',exact=True).locator('..').locator('.el-checkbox').click()
        expect(pop.locator('.multi-select-summary')).to_contain_text('项目部 / 阿尔法')
        pop.locator('.multi-select-summary').get_by_role('button',name='确认',exact=True).click()
        expect(pop).to_have_count(0)
        page.locator('#open-checks').click()
        pop=page.locator('.el-popover:visible')
        pop.get_by_text('阿尔法',exact=True).click();pop.get_by_text('贝塔',exact=True).first.click()
        expect(pop.locator('.multi-select-summary').get_by_role('listitem')).to_have_text(['阿尔法','贝塔'])
        page.locator('#filter-checks').fill('伽马')
        expect(pop.locator('.multi-select-summary').get_by_role('listitem')).to_have_text(['阿尔法','贝塔'])
        pop.locator('.multi-select-summary').get_by_role('button',name='确认',exact=True).click()
        expect(pop).to_have_count(0)
        assert page.evaluate('testState.confirmed')==1
        page.locator('.el-select:has(#single)').click()
        expect(page.locator('.el-select__popper:visible .multi-select-summary')).to_have_count(0)
        page.keyboard.press('Escape')
        for key in ['small','smallVirtual','smallCascade']:
            (page.locator('.el-cascader').nth(1) if key=='smallCascade' else page.locator('.el-select:has(#'+key+')')).click()
            pop=page.locator('.test-'+key+':visible')
            summary=pop.locator('.multi-select-summary')
            expect(summary).to_have_attribute('data-option-count','5')
            expect(summary.locator('.multi-select-summary__count')).to_have_count(0)
            expect(summary.get_by_role('list')).to_have_count(0)
            summary.get_by_role('button',name='确认',exact=True).click();expect(pop).to_have_count(0)
        page.locator('#open-small-checks').click();pop=page.locator('.el-popover:visible')
        expect(pop.locator('.multi-select-summary')).to_have_attribute('data-option-count','5')
        expect(pop.locator('.multi-select-summary__count')).to_have_count(0)
        pop.get_by_text('阿尔法',exact=True).click()
        expect(pop.locator('.multi-select-summary__count')).to_have_count(0)
        pop.locator('.multi-select-summary').get_by_role('button',name='确认',exact=True).click();expect(pop).to_have_count(0)
        page.evaluate("testState.smallOptions=[]")
        page.locator('#small').click();pop=page.locator('.test-small:visible')
        expect(pop.locator('.multi-select-summary__count')).to_have_count(0)
        page.keyboard.press('Escape')
        page.set_viewport_size({'width':390,'height':700})
        page.evaluate("testState.normal=['alpha-id','beta-id','gamma-id']")
        page.locator('#normal').click()
        summary=page.locator('.test-normal:visible .multi-select-summary')
        expect(summary.get_by_role('listitem')).to_have_count(3)
        rect=summary.bounding_box();assert rect['x']>=0 and rect['x']+rect['width']<=391,rect
        summary.get_by_role('button',name='确认',exact=True).click()
        assert not errors,errors
        browser.close()
    print('normal / remote / select-v2 / cascader / custom checkbox popover PASS; <=5 no selected area, >5 retains summary, confirmation retained, single-select unchanged')


if __name__=='__main__':run()
