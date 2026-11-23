"""公共复制菜单浏览器回归，剪贴板与接口完全隔离。"""
import json
import re
from urllib.request import urlopen
from playwright.sync_api import expect, sync_playwright

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/components/common/screenshotDisplays.js',timeout=20).read().decode()
    def dep(name):
        return json.dumps(re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled)[1])
    html='''<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="/node_modules/element-plus/dist/index.css">
<div id="app"></div><script type="module">
import {createApp,h} from VUE;
import {ElTable,ElDescriptions,ElDescriptionsItem} from EP;
import {ScreenshotTableColumn as Column} from '/src/components/common/screenshotDisplays.js';
import Menu from '/src/components/common/FieldCopyContextMenu.vue';
import Inline from '/src/components/common/InlineTextField.vue';
const rows=[{id:'qa',client_short_name:'甲客户 · 子客户乙',projectName:'这是一段非常长的项目名称，用于验证省略号显示时复制完整字段内容',orderNo:'TP-261122-001',status:'进行中'}];
const app=createApp({render:()=>h('div',{style:'padding:25px'},[
 h(Menu),
 h(ElTable,{data:rows,border:true},()=>[
  h(Column,{prop:'client_short_name',label:'客户简称',width:150}),
  h(Column,{prop:'projectName',label:'项目名称',width:180,showOverflowTooltip:true},{default:({row})=>h('button',{class:'project-link',onClick:()=>window.projectClicked=true},row.projectName)}),
  h(Column,{prop:'orderNo',label:'订单号',width:180}),
  h(Column,{prop:'status',label:'状态',width:100}),
 ]),
 h(ElDescriptions,{border:true},()=>h(ElDescriptionsItem,{label:'项目名称'},()=>h('span',{id:'detail-name'},'详情项目完整名称'))),
 h('div',{class:'el-form-item'},[
  h('label',{class:'el-form-item__label'},'订单号'),
  h('div',{class:'el-form-item__content'},h('input',{id:'order-input',value:'AP-261122-009',readonly:true})),
 ]),
 h('p',{id:'unrelated'},'其他区域选中的文字'),
 h(Inline,{modelValue:'行内项目名称',label:'项目名称',editable:false}),
 h('div',{'data-field-copy':'off'},h('span',{'data-field-copy':'true',id:'excluded'},'不接管区域')),
])});app.mount('#app');
</script>'''.replace('from VUE','from '+dep('vue')).replace('from EP','from '+dep('element-plus'))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge')
        page=browser.new_page(viewport={'width':1200,'height':850})
        page.add_init_script("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>{window.copied=value}}})")
        page.route(BASE+'/api/**',lambda route:route.fulfill(json=[]))
        page.route(BASE+'/field-copy-check',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/field-copy-check')
        menu=page.get_by_role('menu',name='字段复制菜单')
        async_copy=page.get_by_role('menuitem',name='复制',exact=True)
        project=page.locator('.project-link')
        expect(project).to_be_visible()
        project.click()
        assert page.evaluate('window.projectClicked') is True
        for locator,value in [
            (project,'这是一段非常长的项目名称，用于验证省略号显示时复制完整字段内容'),
            (page.locator('.client-management-link'),'甲客户 · 子客户乙'),
            (page.get_by_text('TP-261122-001',exact=True),'TP-261122-001'),
            (page.locator('#detail-name'),'详情项目完整名称'),
            (page.locator('#order-input'),'AP-261122-009'),
            (page.get_by_text('行内项目名称',exact=True),'行内项目名称'),
        ]:
            page.evaluate('window.getSelection().removeAllRanges()')
            locator.click(button='right')
            expect(menu).to_be_visible()
            async_copy.click()
            assert page.evaluate('window.copied')==value
        project.evaluate("""el=>{
          const range=document.createRange();range.setStart(el.firstChild,5);range.setEnd(el.firstChild,12);
          const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
        }""")
        selected=page.evaluate('window.getSelection().toString()')
        project.click(button='right')
        expect(menu).to_contain_text('复制选中内容')
        async_copy.click()
        assert page.evaluate('window.copied')==selected
        field=page.locator('#order-input')
        field.evaluate('el=>{el.focus();el.setSelectionRange(3,9)}')
        field.click(button='right')
        expect(menu).to_contain_text('复制选中内容')
        async_copy.click()
        assert page.evaluate('window.copied')=='261122'
        page.get_by_text('进行中',exact=True).click(button='right')
        expect(menu).to_be_hidden()
        page.keyboard.press('Escape')
        page.locator('#excluded').click(button='right')
        expect(menu).to_be_hidden()
        assert not errors,errors
        browser.close()
    print('field copy: full cells, truncated text, details, readonly input, selected text and left-click behavior PASS')


if __name__=='__main__':
    run()
