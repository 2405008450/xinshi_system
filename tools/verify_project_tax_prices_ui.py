"""标注、招聘新增/编辑真实页面税口径与长表单回归；所有业务请求模拟。"""
import json,re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    code=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',code).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Annotation from '/src/views/project/AnnotationProjects.vue';import Recruitment from '/src/views/project/RecruitmentProjects.vue';import AppForm from '/src/components/common/AppForm.vue';createApp({render:()=>h(RouterView)}).component('AppForm',AppForm).use(createRouter({history:createWebHistory(),routes:[{path:'/tax-annotation-new-test',component:Annotation,props:{createOnly:true,embedded:true}},{path:'/tax-annotation-edit-test',component:Annotation,props:{editorOnly:true,editorProjectId:'a1',embedded:true}},{path:'/tax-recruitment-new-test',component:Recruitment},{path:'/tax-recruitment-edit-test',component:Recruitment}]})).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    tax=dict(unit_price_excl_tax='10.123456',unit_price_incl_tax='10.730864',total_excl_tax='100.01',total_incl_tax='106.01')
    annotation=dict(id='a1',order_no='AP-TAX',project_name='标注税口径',project_types=['audio_annotation'],project_status='initial_consultation',language_items=[],assignees=[],role_assignments=[],custom_values={},price_items=[dict(id='price1',project_type='audio_annotation',amount='10.123456',currency='CNY',unit='条',tax_prices=tax)])
    recruitment=dict(id='r1',order_no='RP-TAX',project_name='招聘税口径',position_title='工程师',project_status='pending_setup',language_directions=[],role_assignments=[],service_fee_type='fixed',service_fee_currency='CNY',service_fee_amount='100',tax_prices=tax)
    errors=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/projects/annotation/a1':result=annotation
        elif path=='/api/projects/recruitment/r1':result=recruitment
        elif path=='/api/projects/languages':result=[dict(id='en',label='英语'),dict(id='zh',label='简中')]
        elif path.endswith('/page'):result={'items':[],'total':0}
        elif '/drafts/' in path:result={}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge')
        for module in ('annotation','recruitment'):
            for mode in ('new','edit'):
                context=browser.new_context(viewport={'width':1500,'height':1000})
                context.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['*']))")
                context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/tax-*-test*',lambda r:r.fulfill(content_type='text/html',body=html))
                page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(BASE+f'/tax-{module}-{mode}-test'+('?projectId=r1&openEditor=1' if module=='recruitment' and mode=='edit' else ''))
                if module=='recruitment' and mode=='new':page.get_by_role('button',name='新增招聘项目',exact=True).click()
                dialog=page.locator('.el-dialog:visible').first;expect(dialog).to_be_visible()
                if module=='annotation' and mode=='new':
                    for header in dialog.locator('.el-collapse-item:not(.is-active) > .el-collapse-item__header').all():
                        if header.is_visible():header.click()
                    dialog.get_by_role('button',name='添加报价',exact=True).click()
                search=dialog.locator('.dialog-field-search-header input').first;search.fill('含税总价')
                page.locator('.el-autocomplete-suggestion:visible li').filter(has=page.locator('.project-field-search-option > span:first-child').filter(has_text=re.compile('^含税总价$'))).first.click()
                for placeholder in ('请输入不含税单价','请输入含税单价','请输入不含税总价','请输入含税总价'):
                    expect(dialog.get_by_placeholder(placeholder).first).to_be_visible()
                if mode=='edit':
                    expect(dialog.get_by_placeholder('请输入含税总价').first).to_have_value(re.compile('^106.01'))
                    expect(dialog.get_by_placeholder('请输入不含税单价').first).to_have_value('10.123456')
                dialog.get_by_placeholder('请输入不含税单价').first.fill('12.123456')
                dialog.get_by_placeholder('请输入含税单价').first.fill('12.850863')
                dialog.get_by_placeholder('请输入不含税总价').first.fill('120.01')
                dialog.get_by_placeholder('请输入含税总价').first.fill('127.21')
                page.set_viewport_size({'width':560,'height':760})
                expect(dialog.locator('.el-dialog__footer')).to_be_in_viewport()
                assert dialog.bounding_box()['width']<=528.5
                context.close()
        assert not errors,errors;browser.close()
    print('PASS real annotation and recruitment create/edit tax fields, persisted-value display, field search, mobile and fixed footer')

if __name__=='__main__':run()
