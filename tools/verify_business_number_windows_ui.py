"""实际公共弹窗/表单/草稿组件验收；所有业务接口模拟，不写业务数据库。"""
import json
import re
from uuid import uuid4
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect

BASE='http://localhost:3000'
def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive,ref} from VUE;import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';import api from '/src/api/index.js';import {useFormDraft} from '/src/composables/useFormDraft.js';
createApp({setup(){const form=reactive({id:'',orderNo:'',projectName:''}),visible=ref(false),formRef=ref(null);const {beginDraft,pauseDraft,clearDraft}=useFormDraft({namespace:'number-qa',form,createDefault:()=>({id:'',orderNo:'',projectName:''}),requireUserId:true,formRef});async function open(){Object.assign(form,{id:'',orderNo:'',projectName:''});visible.value=true;await beginDraft('create')}async function save(){if(!await formRef.value.validate().catch(()=>false))return;await api.post('/projects/translation/',{orderNo:form.orderNo,projectName:form.projectName});clearDraft();visible.value=false}return()=>h('div',{},[h('button',{onClick:open},'新增'),h(Dialog,{modelValue:visible.value,'onUpdate:modelValue':v=>visible.value=v,onClosed:pauseDraft,title:'编号验收'},{default:()=>h(AppForm,{ref:formRef,model:form,numberScope:'translation',numberField:'orderNo',numberActive:visible.value&&!form.id},{default:()=>[h('input',{'aria-label':'编号',readonly:true,value:form.orderNo}),h('input',{'aria-label':'内容',value:form.projectName,onInput:e=>form.projectName=e.target.value})]}),footer:()=>[h('button',{onClick:()=>visible.value=false},'关闭'),h('button',{onClick:save},'保存')]})])}}).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue')))
    leases={};creates=[];counter=0
    def api_route(route):
        nonlocal counter
        path=route.request.url.split('/api',1)[1]
        body=route.request.post_data_json if route.request.method in ('POST','PUT','PATCH') and route.request.post_data else {}
        if path.startswith('/business-numbers/history'):
            data={'items':[{'id':'deleted-one','number':'TP-261107-001','entity_id':'previous-entity','entity_name':'原删除项目','actor_name':'测试管理员','deleted_at':'2026-11-07T17:00:00+08:00','snapshot':{'project_name':'原删除项目','client_short_name':'原客户','remarks':'删除前备注'}}],'total':1}
        elif path=='/business-numbers/reserve':
            freed=next((item for item in leases.values() if item['state']=='released'),None)
            if freed:
                number=freed['number'];freed['state']='retired'
            else:
                counter+=1;number=f'TP-261107-{counter:03d}'
            token=str(uuid4())
            leases[token]={'state':'active','number':number};data={'token':token,'number':number}
        elif '/business-numbers/' in path:
            token=path.split('/')[2]
            if path.endswith('/release') and leases[token]['state']=='active':leases[token]['state']='released'
            data={'ok':True}
        elif path=='/projects/translation/':
            tokens=json.loads(route.request.headers.get('x-business-number-leases','[]'));assert len(tokens)==1,tokens
            assert leases[tokens[0]]['number']==body['orderNo'];leases[tokens[0]]['state']='used';creates.append(body);data={'id':str(uuid4()),**body}
        elif 'editor-drafts' in path:data={'payload':None,'revision':0}
        else:data=[]
        route.fulfill(content_type='application/json',body=json.dumps(data))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1100,'height':800})
        context.add_init_script("localStorage.setItem('user_id','account-a');localStorage.setItem('token','test-only')")
        context.route(re.compile(r'^http://localhost:3000/api/'),api_route)
        context.route(BASE+'/number-qa',lambda route:route.fulfill(content_type='text/html',body=html))
        a=context.new_page();b=context.new_page();errors=[]
        for page in (a,b):page.on('pageerror',lambda error:errors.append(str(error)));page.goto(BASE+'/number-qa')
        def opened(page):
            page.get_by_role('button',name='新增',exact=True).click();field=page.get_by_role('textbox',name='编号',exact=True);expect(field).to_have_value(re.compile(r'^TP-'));return field.input_value()
        one=opened(a);two=opened(b);assert one!=two
        a.get_by_role('button',name='编号删除记录',exact=True).click()
        history=a.locator('.el-dialog:visible').filter(has_text='同一编号重新使用后')
        expect(history).to_contain_text('原删除项目')
        before=history.bounding_box();header=history.locator('.el-dialog__header').bounding_box()
        a.mouse.move(header['x']+header['width']*.55,header['y']+18);a.mouse.down();a.mouse.move(header['x']+header['width']*.55,header['y']+48,steps=8);a.mouse.up()
        after=history.bounding_box();assert after['y']>before['y']+5 and after['y']>=0
        history.get_by_role('button',name='查看详情',exact=True).click();expect(a.locator('.number-history-details:visible')).to_contain_text('删除前备注')
        history.get_by_role('button',name='关闭',exact=True).click();expect(history).not_to_be_visible()
        a.get_by_role('button',name='编号删除记录',exact=True).click();expect(history).to_be_visible();assert abs(history.bounding_box()['y']-before['y'])<3
        history.get_by_role('button',name='关闭',exact=True).click();expect(history).not_to_be_visible()
        a.get_by_role('textbox',name='内容',exact=True).fill('本账号未保存内容');a.get_by_role('button',name='关闭',exact=True).click();expect(a.locator('.el-dialog:visible')).to_have_count(0)
        three=opened(a);assert three==one and three!=two;expect(a.get_by_role('textbox',name='内容',exact=True)).to_have_value('本账号未保存内容')
        a.get_by_role('button',name='保存',exact=True).click();expect(a.locator('.el-dialog:visible')).to_have_count(0);assert creates[-1]['orderNo']==three
        four=opened(a);assert four not in (one,two,three)
        expect(a.get_by_role('textbox',name='内容',exact=True)).to_have_value('')
        other=browser.new_context(viewport={'width':1100,'height':800});other.add_init_script("localStorage.setItem('user_id','account-b');localStorage.setItem('token','test-only')")
        other.route(re.compile(r'^http://localhost:3000/api/'),api_route);other.route(BASE+'/number-qa',lambda route:route.fulfill(content_type='text/html',body=html))
        c=other.new_page();c.goto(BASE+'/number-qa');five=opened(c);assert len({one,two,three,four,five})==4
        expect(c.get_by_role('textbox',name='内容',exact=True)).to_have_value('')
        assert not errors,errors
        assert any(item['number']==one and item['state']=='retired' for item in leases.values())
        browser.close()
    print('actual AppForm/Dialog: concurrent windows / released number reuse / own draft only / deletion history details and dragging/reset PASS')
if __name__=='__main__':run()
