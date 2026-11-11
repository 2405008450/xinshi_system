"""保存前子订单窗口：实际组件的分隔、折叠、独立滚动和未保存输入保留；接口均模拟。"""
import json,re
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
import {createApp,h,ref,reactive} from VUE;import Pending from '/src/views/project/translation/components/PendingSubOrderManager.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const visible=ref(false),form=reactive({orderNo:'TP-261109-999',projectName:'测试母订单',initialSubOrderNamesText:Array.from({length:25},(_,i)=>`测试文件${i+1}.docx`).join('\\n'),languagePair:'中文→英语',pendingSubOrderDetails:{},customerRequirementProfessional:'测试专业要求',customerRequirementSpecial:'无'});window.testForm=form;
const app=createApp({render:()=>h('div',[h('button',{onClick:()=>visible.value=true},'打开测试窗口'),h(Pending,{modelValue:visible.value,'onUpdate:modelValue':v=>visible.value=v,form})])});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue')))
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script("localStorage.setItem('user_id','split-qa')")
 page.route(re.compile(r'^http://localhost:3000/api/'),lambda r:r.fulfill(content_type='application/json',body='[]'))
 page.route(BASE+'/pending-split-qa',lambda r:r.fulfill(content_type='text/html',body=html))
 page.goto(BASE+'/pending-split-qa');page.get_by_role('button',name='打开测试窗口').click()
 dialog=page.locator('.pending-suborder-manager:visible');expect(dialog).to_be_visible()
 top=dialog.locator('.vertical-split-top');bottom=dialog.locator('.vertical-split-bottom');handle=dialog.get_by_role('separator')
 expect(top).to_be_visible();expect(bottom).to_be_visible()
 assert dialog.locator('tbody tr').count()==25
 footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=1000
 before=top.bounding_box()['height'];box=handle.bounding_box();page.mouse.move(box['x']+box['width']/2,box['y']+15);page.mouse.down();page.mouse.move(box['x']+box['width']/2,box['y']+90,steps=8);page.mouse.up()
 assert top.bounding_box()['height']>before+45
 handle.press('ArrowUp');assert top.bounding_box()['height']<before+75
 scroll=top.locator('.statistics-scroll');assert scroll.evaluate('el=>el.scrollHeight>el.clientHeight')
 head=top.locator('thead th').first;head_y=head.bounding_box()['y'];scroll.evaluate('el=>el.scrollTop=400');assert abs(head.bounding_box()['y']-head_y)<2
 scroll.evaluate('el=>el.scrollTop=0');top.locator('tbody input').first.fill('123')
 professional=bottom.locator('.el-form-item').filter(has=page.get_by_text('客户专业要求',exact=True)).locator('textarea');professional.fill('分区折叠后保留的要求')
 dialog.get_by_title('折叠统计填写区',exact=True).click();expect(top).not_to_be_visible();expect(bottom).to_be_visible()
 dialog.get_by_title('展开统计填写区',exact=True).click();expect(top).to_be_visible();expect(top.locator('tbody input').first).to_have_value('123')
 dialog.get_by_title('折叠子订单编辑区',exact=True).click();expect(bottom).not_to_be_visible()
 search=dialog.get_by_placeholder('搜索字段，如客户交稿时间');search.fill('客户专业要求')
 page.get_by_role('option').filter(has_text='客户专业要求').first.click();expect(bottom).to_be_visible();expect(professional).to_have_value('分区折叠后保留的要求')
 editor=bottom.locator('.pending-suborder-editor');assert editor.evaluate('el=>el.scrollHeight>el.clientHeight')
 footer_before_scroll=dialog.locator('.el-dialog__footer').bounding_box();editor.evaluate('el=>el.scrollTop=el.scrollHeight');footer_after_scroll=dialog.locator('.el-dialog__footer').bounding_box();assert abs(footer_before_scroll['y']-footer_after_scroll['y'])<1,(footer_before_scroll,footer_after_scroll);assert footer_after_scroll['y']+footer_after_scroll['height']<=1000
 dialog.get_by_role('button',name='返回母订单',exact=True).click();expect(dialog).not_to_be_visible()
 assert page.evaluate('Object.values(testForm.pendingSubOrderDetails)[0].wordCountMatrix.company.words')==123
 page.get_by_role('button',name='打开测试窗口').click();expect(top).to_be_visible();expect(bottom).to_be_visible();expect(professional).to_have_value('分区折叠后保留的要求')
 # Dialog title remains draggable, controls remain within viewport.
 start=dialog.bounding_box();title=dialog.locator('.dialog-field-search-header__title').bounding_box();page.mouse.move(title['x']+20,title['y']+10);page.mouse.down();page.mouse.move(title['x']+30,title['y']+25,steps=5);page.mouse.up();assert dialog.bounding_box()['y']>=0;assert abs(dialog.bounding_box()['y']-start['y'])>5
 dialog.screenshot(path=str(ROOT/'scratch/pending-suborder-split.png'))
 page.set_viewport_size({'width':900,'height':700});page.wait_for_timeout(200)
 small_footer=dialog.locator('.el-dialog__footer').bounding_box();assert small_footer['y']+small_footer['height']<=700
 assert not errors,errors
 browser.close()
print('pending child manager split drag / collapse both / independent scroll / sticky table header / fixed footer / field search reveal / inputs preserved and reopen PASS')
