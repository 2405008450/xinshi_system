"""实际结算、字数、字段设置浮窗及公共受控/非受控窗口回归；不写业务库。"""
import json
import re
from urllib.request import urlopen
from playwright.sync_api import expect, sync_playwright

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {createApp,h,ref} from VUE;
    import Translator from '/src/views/project/translation/components/TranslatorCompletionPopover.vue';
    import Matrix from '/src/components/common/WordCountMatrixPopover.vue';import Columns from '/src/components/common/TableColumnSettings.vue';
    import Window from '/src/components/common/WindowPopover.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
    const app=createApp({setup(){const people=ref([{arrangementId:'a1',translatorName:'测试译员',translatorReturnTime:'2026-10-31 19:30:00',translatorUnitPrice:1,translatorTotalPrice:10,completionRemarks:'原任务'}]),keys=ref(['name']),oneway=ref(false);window.saved=[];return()=>h('main',{style:'padding:80px min(25vw, 400px)'},[
      h(Translator,{translators:people.value,editable:true,placement:'bottom',save:async updates=>{window.saved.push(updates);people.value=updates.map(item=>({...item,translatorName:'测试译员'}));return{};}}),
      h(Matrix,{local:true}),h(Columns,{settingsKey:'window-qa',columns:[{key:'name',label:'姓名'},{key:'time',label:'时间'}],modelValue:keys.value,'onUpdate:modelValue':value=>keys.value=value,columnCount:2}),
      h(Window,{title:'单向受控窗口',visible:oneway.value,trigger:'click',width:450},{reference:()=>h('button',{onClick:()=>oneway.value=true},'单向受控'),default:()=>h('p','控制窗口正文')}),
      h(Window,{title:'非受控窗口',trigger:'click',width:450},{reference:()=>h('button','非受控'),default:()=>h('p','非受控正文')})
    ])}});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
    errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1600,'height':1000},service_workers='block')
        context.route(re.compile(r'^http://localhost:3000/api/'),lambda route:route.fulfill(content_type='application/json',body='[]'))
        context.route(BASE+'/window-popover-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/window-popover-test')

        def move_and_close(popup):
            expect(popup.locator('.app-window-popover__header')).to_be_visible()
            expect(popup.get_by_role('button',name='关闭窗口',exact=True)).to_be_visible()
            rect=popup.bounding_box();x=rect['x']+rect['width']-180;y=rect['y']+18
            page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+60,y+30,steps=10);page.mouse.up()
            moved=popup.bounding_box();assert abs(moved['x']-rect['x'])+abs(moved['y']-rect['y'])>20
            page.mouse.move(moved['x']+moved['width']-180,moved['y']+18);page.mouse.down();page.mouse.move(5000,5000,steps=10);page.mouse.up()
            bounded=popup.bounding_box();assert bounded['x']>=0 and bounded['y']>=0 and bounded['x']+bounded['width']<=1601 and bounded['y']+bounded['height']<=1001
            popup.get_by_role('button',name='关闭窗口',exact=True).click()
            expect(popup).to_have_count(0)
            return rect

        page.locator('.translator-return-trigger').click()
        popup=page.locator('.translator-completion-popover:visible')
        popup.screenshot(path='scratch/translator-popover-window.png')
        popup.locator('.el-input-number input').first.fill('9')
        popup.locator('textarea').fill('未保存草稿')
        first=move_and_close(popup)
        assert page.evaluate('window.saved.length')==0
        page.locator('.translator-return-trigger').click()
        expect(popup.locator('textarea')).to_have_value('原任务')
        assert float(popup.locator('.el-input-number input').first.input_value())==1
        reopened=popup.bounding_box();assert abs(reopened['x']-first['x'])<3 and abs(reopened['y']-first['y'])<3
        popup.locator('.el-input-number input').first.fill('2.5')
        popup.get_by_role('button',name='保存',exact=True).click()
        expect(popup).to_have_count(0)
        assert page.evaluate('window.saved[0][0].translatorUnitPrice')==2.5

        page.get_by_role('button',name='字数统计',exact=True).click()
        move_and_close(page.locator('.word-count-matrix-popper:visible'))
        page.get_by_role('button',name='字段设置',exact=True).click()
        move_and_close(page.locator('.table-column-settings-popover:visible'))
        print('settlement, matrix and column-settings checks passed',flush=True)
        for label,title in [('单向受控','单向受控窗口'),('非受控','非受控窗口')]:
            for index in range(2):
                print(f'{label}: opening {index+1}',flush=True)
                page.get_by_role('button',name=label,exact=True).click()
                common=page.locator('.app-window-popover:visible').filter(has=page.locator('.app-window-popover__title',has_text=title))
                move_and_close(common)
        page.set_viewport_size({'width':390,'height':750})
        page.locator('.translator-return-trigger').click()
        small=page.locator('.translator-completion-popover:visible')
        expect(small.get_by_role('button',name='关闭窗口',exact=True)).to_be_visible()
        box=small.bounding_box();assert box['width']<=390
        small.get_by_role('button',name='关闭窗口',exact=True).click()
        assert not errors,errors
        browser.close()
    print('settlement/word-count/field settings: drag, bounds, X, reset, discard/save, controlled reopening and mobile PASS')


if __name__=='__main__':run()
