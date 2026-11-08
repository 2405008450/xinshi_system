"""新增项目按账号静默恢复、不串号及母订单文件名例外；全部接口模拟。"""
import json,re
from uuid import uuid4
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=20).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Workspace from '/src/views/project/ProjectWorkspace.vue';import AppForm from '/src/components/common/AppForm.vue';import {installAutoDrafts} from '/src/utils/autoDrafts.js';import Dialog from '/src/components/common/DraggableFormDialog.vue';const app=createApp({render:()=>h(RouterView)});installAutoDrafts(app);app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/new-project-draft-test',component:Workspace,props:{module:'translation'}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    number_counter=0
    def api(route):
        nonlocal number_counter
        path=urlparse(route.request.url).path
        if path=='/api/projects/translation/page':result={'items':[],'total':0}
        elif path=='/api/business-numbers/reserve':
            number_counter+=1
            prefix='CL' if route.request.post_data_json['kind']=='client' else 'TP'
            result={'token':str(uuid4()),'number':f'{prefix}-261107-{number_counter:03d}'}
        elif path.startswith('/api/business-numbers/'):result={'ok':True}
        elif path.endswith('/next-order-no'):result={'order_no':'TP-261102-999'}
        elif path=='/api/editor-drafts':result={'payload':None,'revision':0}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1500,'height':1000})
        context.add_init_script("if(!localStorage.getItem('qa-draft-seeded')){localStorage.setItem('qa-draft-seeded','1');localStorage.setItem('user_id','qa');localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write','project_files:read','project_files:write']));localStorage.setItem('form-drafts:translation-project:qa',JSON.stringify({create:{ownerId:'qa',version:'translation-create-account-v2',savedAt:new Date().toISOString(),form:{id:'',orderNo:'TP-OLD-001',sourceFileName:'旧草稿.docx',clientShortName:'旧客户',customerReceptionTime:'2026-10-29 11:15',customerDeadlineTime:'2026-10-30 11:00',wordCountMatrix:{company:{documents:3}}}}}));}")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/new-project-draft-test',lambda r:r.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(18000);errors=[];page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/new-project-draft-test')
        page.get_by_role('button',name='新增项目',exact=True).click();dialog=page.locator('.project-editor-dialog:visible')
        order_field=dialog.get_by_role('textbox',name='订单号',exact=True)
        expect(order_field).to_have_value(re.compile(r'^TP-261107-'))
        initial_number=order_field.input_value()
        expect(dialog).to_have_attribute('data-auto-draft','off')
        expect(dialog).to_have_class(re.compile('is-maximized'))
        page.wait_for_function("()=>{const e=document.querySelector('.project-editor-dialog.is-maximized');if(!e)return false;const r=e.getBoundingClientRect();return Math.abs(r.x)<1&&Math.abs(r.y)<1&&Math.abs(r.width-innerWidth)<2&&Math.abs(r.height-innerHeight)<2}")
        rect=dialog.bounding_box();assert abs(rect['x'])<1 and abs(rect['y'])<1 and abs(rect['width']-1500)<2 and abs(rect['height']-1000)<2,rect
        footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=1001
        dialog.get_by_role('button',name='还原窗口',exact=True).click();expect(dialog).not_to_have_class(re.compile('is-maximized'))
        assert dialog.bounding_box()['width']<1500
        dialog.get_by_role('button',name='最大化窗口',exact=True).click();expect(dialog).to_have_class(re.compile('is-maximized'))
        for level in [0.8,0.9,1.1,1.25,1]:
            dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
            page.evaluate("async level=>{const m=await import('/src/composables/useUiZoom.js');m.applyUiZoom(level)}",level)
            page.get_by_role('button',name='新增项目',exact=True).click()
            expect(dialog).to_have_class(re.compile('is-maximized'))
            page.wait_for_function("()=>{const e=document.querySelector('.project-editor-dialog.is-maximized');if(!e)return false;const r=e.getBoundingClientRect();return Math.abs(r.x)<1&&Math.abs(r.y)<1&&Math.abs(r.width-innerWidth)<2&&Math.abs(r.height-innerHeight)<2}")
            assert not dialog.evaluate("e=>!!e.closest('#app')")
            footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=1001
        expect(dialog.get_by_role('button',name='恢复草稿',exact=True)).to_have_count(0)
        name=dialog.locator('[data-field-key="sourceFileName"] input.el-input__inner')
        expect(name).to_have_value('旧草稿.docx');expect(dialog.locator('[data-field-key="clientShortName"] input.el-input__inner')).to_have_value('旧客户')
        name.fill('本次未保存.docx')
        page.wait_for_timeout(500)
        parent_mode=dialog.locator('.el-checkbox').filter(has_text='同时创建子订单（母订单名称可不带扩展名）');expect(parent_mode).to_be_visible()
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='新增项目',exact=True).click();expect(name).to_have_value('本次未保存.docx');expect(dialog.locator('[data-field-key="clientShortName"] input.el-input__inner')).to_have_value('旧客户');expect(dialog.get_by_role('button',name='恢复草稿',exact=True)).to_have_count(0)
        parent_mode.click();name.fill('母订单名称')
        children=dialog.locator('.el-form-item').filter(has_text='子订单文件名称').locator('textarea');children.fill('文件甲.docx\n文件乙.pdf');children.press('Tab')
        expect(dialog.locator('[data-field-key="sourceFileName"] .el-form-item__error')).to_have_count(0)
        dialog.get_by_role('tab',name='项目文件',exact=True).click()
        path_field=dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=re.compile('^译文路径$'))).locator('input')
        path_field.fill('\\\\Win-server\\测试\\译文')
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.reload();page.get_by_role('button',name='新增项目',exact=True).click()
        expect(name).to_have_value('母订单名称');expect(children).to_have_value('文件甲.docx\n文件乙.pdf')
        dialog.get_by_role('tab',name='项目文件',exact=True).click();expect(path_field).to_have_value('\\\\Win-server\\测试\\译文')
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='新增项目',exact=True).click()
        dialog.get_by_role('button',name='展开字数统计',exact=True).click()
        matrix=page.locator('.word-count-matrix-popper:visible')
        matrix.get_by_role('spinbutton',name='我司统计-份数',exact=True).fill('');matrix.get_by_role('spinbutton',name='我司统计-份数',exact=True).press('Tab')
        matrix.get_by_role('spinbutton',name='我司统计-字数',exact=True).fill('4567')
        matrix.get_by_role('spinbutton',name='客户统计-字数',exact=True).fill('987')
        matrix.get_by_role('spinbutton',name='预统计-页数',exact=True).fill('0')
        matrix.get_by_role('button',name='关闭',exact=True).click();expect(matrix).not_to_be_visible()
        expect(dialog.locator('[data-field-key="wordCountSummary"]')).to_contain_text('4,567')
        expect(dialog.locator('[data-field-key="wordCountSummary"]')).to_contain_text('未保存修改')
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.reload();page.get_by_role('button',name='新增项目',exact=True).click()
        dialog.get_by_role('button',name='展开字数统计',exact=True).click()
        expect(matrix.get_by_role('spinbutton',name='我司统计-字数',exact=True)).to_have_value('4567')
        expect(matrix.get_by_role('spinbutton',name='客户统计-字数',exact=True)).to_have_value('987')
        expect(matrix.get_by_role('spinbutton',name='预统计-页数',exact=True)).to_have_value('0')
        matrix.get_by_role('button',name='保存',exact=True).click();expect(matrix).not_to_be_visible()
        expect(dialog.locator('[data-field-key="wordCountSummary"]')).not_to_contain_text('未保存修改')
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.evaluate("localStorage.setItem('user_id','qb')")
        page.get_by_role('button',name='新增项目',exact=True).click();expect(name).to_have_value('')
        name.fill('乙账号独有.pdf');dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.evaluate("localStorage.setItem('user_id','qa')")
        page.get_by_role('button',name='新增项目',exact=True).click();expect(name).to_have_value('母订单名称')
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.evaluate("localStorage.setItem('user_id','qb')")
        page.get_by_role('button',name='新增项目',exact=True).click();expect(name).to_have_value('乙账号独有.pdf')
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.evaluate("localStorage.setItem('user_id','qc');localStorage.setItem('form-drafts:translation-project:qc',JSON.stringify({create:{savedAt:new Date().toISOString(),form:{id:'saved-old-project',sourceFileName:'归属不明旧项目.docx',emailSubjectPreview:'TP-261029-004 旧主题'}}}))")
        page.get_by_role('button',name='新增项目',exact=True).click();expect(name).to_have_value('')
        expect(dialog.locator('[data-field-key="clientShortName"] input.el-input__inner')).to_have_value('')
        assert not errors,errors;browser.close()
    print('account-isolated silent create recovery, reserved fresh order number, refresh, file paths, sub-orders and fullscreen PASS')


if __name__=='__main__':run()
