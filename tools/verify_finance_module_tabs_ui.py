"""真实财务页签、项目入口、保存与弹窗交互；业务接口全部模拟，不写业务库。"""
import json,re
from urllib.parse import urlparse,parse_qs
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    code=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue').read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',code).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h,ref} from VUE;import {createRouter,createWebHistory,RouterView} from ROUTER;import Workspace from '/src/views/project/ProjectWorkspace.vue';import Annotation from '/src/views/project/AnnotationWorkspace.vue';import Translation from '/src/views/project/translation/CustomerFinance.vue';import AppForm from '/src/components/common/AppForm.vue';const Harness={setup(){const editor=ref();const target={customerChargeItems:[],languagePair:'英语→简中',wordCountMatrix:{customer:{words:100}}};return()=>h('div',[h('button',{onClick:()=>editor.value.openForForm(target,{clientId:'c1',languagePair:'英语→简中'})},'打开笔译财务'),h(Translation,{ref:editor,editorOnly:true})])}};createApp({render:()=>h(RouterView)}).component('AppForm',AppForm).use(createRouter({history:createWebHistory(),routes:[{path:'/finance-tabs-translation-test',component:Harness},{path:'/finance-tabs-annotation-test',name:'AnnotationProjectDetails',component:Annotation},{path:'/finance-tabs-recruitment-test',component:Workspace,props:{module:'recruitment'}},{path:'/finance-tabs-interpretation-test',component:Workspace,props:{module:'interpretation'}}]})).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    tax=dict(unit_price_excl_tax='10.123456',unit_price_incl_tax='10.730864',total_excl_tax='100.01',total_incl_tax='106.01')
    projects={module:dict(id=module+'1',module=module,order_no=module+'-TEST',project_name=module+'项目',client_id='c1',client_name='客户一',project_status='project_in_progress',project_types=['audio_annotation'],version='v1',prices=[dict(id='price1',project_type='audio_annotation',amount='10.123456',currency='CNY',unit='条',tax_prices=tax)],tax_prices=tax,currency='CNY',legacy_amount='100',totals_excl_tax={'CNY':'100.01'},totals_incl_tax={'CNY':'106.01'}) for module in ('annotation','recruitment')}
    calls=[];writes=[];errors=[]
    def api(route):
        request=route.request;parsed=urlparse(request.url);path=parsed.path;calls.append((path,parse_qs(parsed.query)))
        if '/project-customer-finance/' in path:
            module=path.split('/')[3];row=projects[module]
            if path.endswith('/page'):result=dict(items=[row],total=25,totals_excl_tax={'CNY':'100.01'},totals_incl_tax={'CNY':'106.01'})
            elif path.endswith('/history'):result={'items':[],'total':0}
            elif request.method=='PUT':
                body=request.post_data_json;writes.append((module,body));row.update(body);row['version']='v2';result=row
            else:result=row
        elif path=='/api/interpretation-customer-finance/page':result={'items':[dict(id='oral1',order_no='IP-TEST',project_name='口译项目',client_short_name='客户一',directions=[],payload={},totals_excl_tax={},totals_incl_tax={})],'total':1}
        elif path=='/api/interpretation-customer-finance/project/oral1':result=dict(ready=True,order_no='IP-TEST',project_name='口译项目',client_id='c1',client_short_name='客户一',directions=[],payload={'rates':[]},revision=1)
        elif path.endswith('/history'):result={'items':[],'total':0}
        elif path.endswith('/page'):result={'items':[],'total':0}
        elif path=='/api/customer-translation-rates/c1':result={'items':[],'version':'1'}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1600,'height':1000})
        context.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['*']))")
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(re.compile(r'^http://localhost:3000/finance-tabs-.*-test(?:\?.*)?$'),lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:(errors.append(str(e)),print('PAGE ERROR:',str(e),flush=True)))
        page.goto(BASE+'/finance-tabs-translation-test');page.get_by_role('button',name='打开笔译财务',exact=True).click()
        dialog=page.locator('.customer-finance-dialog:visible');expect(dialog.get_by_role('tab',name='笔译财务',exact=True)).to_have_attribute('aria-selected','true')
        dialog.locator('.el-radio').filter(has_text='固定收费').click();dialog.get_by_placeholder('请输入不含税固定收费').fill('1234')
        for module,label in [('interpretation','口译财务'),('annotation','标注财务'),('recruitment','招聘财务')]:
            dialog.get_by_role('tab',name=label,exact=True).click();expect(dialog.get_by_role('button',name='保存',exact=True)).to_have_count(0)
            expect(dialog.get_by_text('财务管理（客户）'+(' · 标注' if module=='annotation' else ' · 招聘' if module=='recruitment' else ''),exact=True)).to_be_visible()
            page.wait_for_timeout(150)
            assert any(module in path and query.get('client_id')==['c1'] and query.get('only_mine')!=['true'] for path,query in calls),(module,calls)
        dialog.get_by_role('tab',name='笔译财务',exact=True).click();expect(dialog.get_by_placeholder('请输入不含税固定收费')).to_have_value(re.compile('^1234'))
        dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).to_have_count(0)
        for module,label in [('annotation','标注财务'),('recruitment','招聘财务')]:
            page.goto(BASE+f'/finance-tabs-{module}-test?section=customer-finance')
            expect(page.get_by_role('tab',name='财务管理（客户）',exact=True)).to_have_attribute('aria-selected','true')
            page.get_by_role('button',name='查看详情',exact=True).click();expect(page.locator('.el-popover:visible')).to_contain_text(module+'-TEST');page.mouse.click(5,5)
            page.get_by_role('button',name='编辑财务',exact=True).click();editor=page.locator('.project-customer-finance-editor:visible')
            expect(editor.get_by_role('tab',name=label,exact=True)).to_have_attribute('aria-selected','true')
            editor.get_by_placeholder('请输入不含税单价',exact=True).fill('20.123456')
            editor.get_by_placeholder('请输入含税总价',exact=True).fill('212.34')
            editor.get_by_role('tab',name='笔译财务',exact=True).click();expect(editor.locator(':scope > .el-dialog__footer').get_by_role('button',name='保存',exact=True)).to_have_count(0)
            editor.get_by_role('tab',name=label,exact=True).click();expect(editor.get_by_placeholder('请输入不含税单价',exact=True)).to_have_value('20.123456')
            editor.get_by_role('button',name='保存',exact=True).click();expect(page.get_by_text('客户财务已保存并记录',exact=True)).to_be_visible()
            body=writes[-1][1];values=body['prices'][0]['tax_prices'] if module=='annotation' else body['tax_prices']
            assert values['unit_price_excl_tax']==20.123456 and values['total_incl_tax']==212.34
            rect=editor.bounding_box();header=editor.locator(':scope > .el-dialog__header');box=header.bounding_box()
            page.mouse.move(box['x']+box['width']-150,box['y']+15);page.mouse.down();page.mouse.move(box['x']+box['width']-230,box['y']+80,steps=8);page.mouse.up()
            moved=editor.bounding_box();assert abs(moved['x']-rect['x'])>20 or abs(moved['y']-rect['y'])>20
            page.set_viewport_size({'width':560,'height':760});expect(editor.get_by_role('button',name='保存',exact=True)).to_be_in_viewport()
            editor.locator(':scope > .el-dialog__body').evaluate('(node)=>node.scrollTop=node.scrollHeight');expect(editor.get_by_role('button',name='保存',exact=True)).to_be_in_viewport()
            editor.get_by_role('button',name='关闭',exact=True).click();expect(editor).to_have_count(0);page.set_viewport_size({'width':1600,'height':1000})
            page.get_by_role('button',name='编辑财务',exact=True).click();expect(editor).to_be_visible();reopened=editor.bounding_box();assert abs(reopened['x']-rect['x'])<3
            editor.get_by_role('button',name='关闭窗口',exact=True).click();expect(editor).to_have_count(0)
        page.goto(BASE+'/finance-tabs-interpretation-test?section=customer-finance');page.get_by_role('button',name='编辑收费 / 调整记录',exact=True).click()
        oral=page.locator('.interpretation-finance-dialog:visible');expect(oral.get_by_role('tab',name='口译财务',exact=True)).to_have_attribute('aria-selected','true')
        assert not errors,errors;browser.close()
    print('PASS four finance tabs, same-client scope, draft retained, annotation/recruitment workspace entries, tax save, details popover, drag/reopen, mobile fixed footer, interpretation default tab')

if __name__=='__main__':run()
