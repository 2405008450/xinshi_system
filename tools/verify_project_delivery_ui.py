"""三类项目真实表单及邮件弹窗；接口全部模拟，不发送真实消息或邮件。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect

BASE='http://localhost:3000'
PROJECT='00000000-0000-4000-8000-000000000010'
USER='00000000-0000-4000-8000-000000000001'
OTHER='00000000-0000-4000-8000-000000000002'
MAIL='00000000-0000-4000-8000-000000000030'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    def dep(name):return re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;import I from '/src/views/project/interpretation/InterpretationProjectDetails.vue';import A from '/src/views/project/AnnotationProjects.vue';import R from '/src/views/project/RecruitmentProjects.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const module=new URLSearchParams(location.search).get('module');const app=createApp({render:()=>h({interpretation:I,annotation:A,recruitment:R}[module],{ref:vm=>window.testVm=vm})});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/project-delivery-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    posts=[];state={'fail_chat':False}
    def api(route):
        path=urlparse(route.request.url).path
        data=route.request.post_data_json if route.request.post_data else None
        if route.request.method in ('POST','PUT','PATCH'):posts.append((path,data))
        if path.endswith('/page'):result={'items':[],'total':0}
        elif path.endswith('/editor-drafts'):result={'payload':None,'revision':0}
        elif path.endswith('/business-numbers/reserve'):result={'token':str(uuid4()),'number':'TP-261110-999'}
        elif path=='/api/users/':result=[{'id':USER,'full_name':'测试甲','is_active':True,'email':'a@example.test'},{'id':OTHER,'full_name':'测试乙','is_active':True,'email':'b@example.test'}]
        elif path=='/api/project-mails/preview':
            subject=('（紧急）项目预告知：' if data.get('emergency_notice') else '')+'TEST-261110-999 项目'
            result={'subject':subject,'order_no':'TEST-261110-999','body':'已保存项目内容','body_html':'<p>已保存项目内容</p>','can_send':True,'blocking_reasons':[],'missing_fields':[],'to_users':[{'user_id':OTHER,'display_name':'测试乙','email':'b@example.test'}],'cc_users':[],'sender_mode':'system','sender_verified':True,'inline_images':[]}
        elif path=='/api/project-mails/' and route.request.method=='POST':result={'id':MAIL,'status':'sent','project_chat_error':'模拟会话暂时失败' if state['fail_chat'] else None}
        elif path=='/api/project-delivery/audience':result={'audience':[{'value':'user:'+OTHER,'label':'测试乙'}]}
        elif path.startswith('/api/project-delivery/'):result={'sent':True,'room_id':str(uuid4())}
        elif path.endswith('/'+PROJECT) and route.request.method in ('PUT','PATCH'):result={'id':PROJECT,'updated_at':'2026-11-10T12:00:00+08:00'}
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1450,'height':1000})
        page.add_init_script(f"localStorage.setItem('user_id','{USER}');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api)
        page.route(BASE+'/project-delivery-test*',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        for module,label in [('interpretation','口译'),('annotation','标注'),('recruitment','招聘')]:
            modes=['chat','urgent','mixed'] if module=='interpretation' else ['chat','urgent']
            for mode in modes:
                page.goto(BASE+'/project-delivery-test?module='+module)
                page.get_by_role('button',name='新增'+label+'项目',exact=True).click()
                dialog=page.locator({'interpretation':'.interpretation-editor-dialog:visible','annotation':'.annotation-editor-dialog:visible','recruitment':'.recruitment-editor:visible'}[module])
                footer=dialog.locator('.el-dialog__footer')
                expect(footer.get_by_role('button',name='保存并发送会话',exact=True)).to_be_visible()
                expect(footer.get_by_role('button',name='（紧急）项目预告知',exact=True)).to_be_visible()
                if module!='interpretation':expect(footer.get_by_role('button',name=re.compile('邮件'))).to_have_count(0)
                fixture=dict(id=PROJECT,orderNo='TEST-261110-999',projectName='隔离项目',clientId='00000000-0000-4000-8000-000000000020',clientName='测试客户',clientFullName='测试客户',clientShortName='测试',clientManagerId=USER,projectTypes=['translation'],taskDescription='具体任务',projectStatus='initial_follow_up',locations=['广州'],timeRanges=[{'scheduledStart':'2026-11-10T09:00:00','scheduledEnd':'2026-11-10T18:00:00','actualStart':'','actualEnd':''}],languageDirections=[{'languageIds':[USER,OTHER],'requiredCount':1}],languageItems=[{'mode':'single','sourceLanguageId':USER,'targetLanguageId':'','regions':[]}],taskDispatchedAt='2026-11-10T09:00:00',taskSubmittedAtPending=True,taskSubmittedAt='',taskImageUploadIds=[],positionTitle='招聘岗位',headcountMin=1,headcountMax=1,employmentRange=['2026-11-10','2026-12-10'],workLocation='广州',roleAssignments=[])
                page.evaluate('(data)=>Object.assign(window.testVm.$.setupState.form,data)',fixture)
                page.wait_for_timeout(350)
                page.evaluate("()=>{const s=window.testVm.$.setupState;s.form.projectName='隔离项目';s.form.contactName='测试联系人'}")
                if module=='interpretation':dialog.get_by_role('textbox',name='项目名称',exact=True).fill('隔离项目')
                start=len(posts)
                footer.get_by_role('button',name='会话补充 @',exact=True).click()
                picker=page.locator('.el-popover:visible')
                expect(picker).to_be_visible()
                picker.locator('.el-select').click()
                page.get_by_role('option',name='测试乙',exact=True).click()
                dialog.locator('.el-dialog__header').click()
                button={'chat':'保存并发送会话','urgent':'（紧急）项目预告知','mixed':'保存并发送会话和邮件'}[mode]
                footer.get_by_role('button',name=button,exact=True).click()
                try:expect(dialog).not_to_be_visible(timeout=6000)
                except AssertionError:
                    raise AssertionError((module,mode,page.locator('.el-form-item__error:visible,.el-message:visible').all_text_contents(),posts[start:]))
                assert any(path==f'/api/projects/{module}/{PROJECT}' for path,_ in posts[start:]),posts[start:]
                if module=='interpretation' and mode in ('urgent','mixed'):
                    mail=page.locator('.business-mail-dialog:visible');expect(mail).to_be_visible()
                    preview=next(data for path,data in reversed(posts) if path=='/api/project-mails/preview')
                    assert preview['emergency_notice']==(mode=='urgent')
                    state['fail_chat']=mode=='mixed'
                    mail.locator('.el-dialog__footer').get_by_role('button',name='发送邮件',exact=True).click()
                    if mode=='mixed':
                        expect(mail.get_by_role('button',name='重试会话',exact=True)).to_be_visible()
                        expect(mail.get_by_role('button',name='发送邮件',exact=True)).to_be_disabled()
                        count=sum(path=='/api/project-mails/' for path,_ in posts)
                        mail.get_by_role('button',name='重试会话',exact=True).click()
                        expect(mail).not_to_be_visible()
                        assert sum(path=='/api/project-mails/' for path,_ in posts)==count
                    else:expect(mail).not_to_be_visible()
                    sent=next(data for path,data in reversed(posts) if path=='/api/project-mails/')
                    assert sent['project_chat_audience']==['user:'+OTHER]
                    assert sent['send_project_chat']==(mode=='mixed') and sent['emergency_notice']==(mode=='urgent')
                    assert not any(path.startswith('/api/project-delivery/interpretation/') for path,_ in posts[start:])
                else:
                    calls=[data for path,data in posts[start:] if path==f'/api/project-delivery/{module}/{PROJECT}/chat']
                    assert calls and calls[-1]['emergency_notice']==(mode=='urgent'),posts[start:]
                    assert calls[-1]['audience']==['user:'+OTHER]
                    assert not any(path.startswith('/api/project-mails') for path,_ in posts[start:])
            assert not errors,errors
        browser.close()
    print('three actual forms / save-before-chat / urgent mode / interpretation mail linkage / annotation-recruitment no mail PASS')


if __name__=='__main__':run()
