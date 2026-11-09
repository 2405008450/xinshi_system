"""真实管理弹窗：少于10条可打开、四级路径、Excel粘贴及统计保存，全部接口模拟。"""
import json,re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><div id="app"></div><script type="module">
import {createApp,h} from VUE;import {createRouter,createWebHistory} from ROUTER;import Projects from '/src/views/project/translation/ProjectDetails.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';const app=createApp({render:()=>h(Projects)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/five-level-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    number='TP-261107-971'
    rows=[]
    for i,(suffix,name,folder) in enumerate([('.001','一级资料',True),('.001.001','二级资料',True),('.001.001.001','三级资料',True),('.001.001.001.001','末级文件.xlsx',False),('.002','根文件.pdf',False)]):
        rows.append({'id':'s'+str(i),'parent_project_id':'p1','sub_order_no':number+suffix,'sub_project_name':name,'status':'pending_confirmation','folder_info':{'files':[]} if folder else None,'network_file_path':'D:\\客户项目\\'+('很长的共享资料路径\\'*18)+name,'word_count_matrix':{'company':{'words':None},'customer':{'words':None}},'word_count_matrix_source':'suborder_aggregate' if folder else 'suborder'})
    root={'id':'p1','order_no':number,'project_name':'客户项目','source_file_name':'客户项目','project_status':'confirmed','network_file_path':r'D:\客户项目','sub_orders':rows,'word_count_matrix':{'company':{'words':None}},'word_count_sub_order_count':2}
    root.update({'service_content':'翻译','customer_requirement_professional':'母专业要求','customer_requirement_special':'母特殊要求','remarks':'母补充说明','file_type_secondary':'合同','child_field_differences':{'customer_requirement_professional':{'count':4,'items':[{'order_no':number+'.00'+str(i),'value':'下级专业要求'+str(i),'includes_descendants':False} for i in range(1,5)]},'language_pair':{'count':1,'items':[{'order_no':number+'.001','value':'英语→中文','includes_descendants':False}]}}})
    for row in rows:
        row.update({'service_content':'翻译','customer_requirement_professional':'子专业要求','customer_requirement_special':'子特殊要求','remarks':'子补充说明','inherited_fields':['service_content','customer_requirement_professional','customer_requirement_special','remarks'],'child_field_differences':{}})
    root.update({'client_name':'系统开发测试有限公司','client_short_name':'系统开发测试','contact_name':'测试联系人','customer_type':'企业客户','statement_required':True,'customer_reception_time':'2026-11-08 09:00:00','customer_deadline_time':'2026-11-09 18:00:00','language_pair':'中文→英语','original_storage_path':r'D:\客户项目'})
    patches=[];project_writes=[];chat_writes=[];mail_writes=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/translation-delivery/p1/counts':data={'mail_count':len(mail_writes),'chat_count':len(chat_writes)+sum(bool(m.get('send_translation_chat')) for m in mail_writes)}
        elif path=='/api/translation-delivery/p1/chat':
            chat_writes.append(route.request.post_data_json);data={'mail_count':len(mail_writes),'chat_count':len(chat_writes)+sum(bool(m.get('send_translation_chat')) for m in mail_writes),'warnings':[]}
        elif path=='/api/project-mails/preview':data={'subject':'TP-261107-971 项目预告知','body':'完整邮件内容','body_html':'<p>完整邮件内容</p>','can_send':True,'blocking_reasons':[],'to_users':[{'user_id':'qa','display_name':'测试人员','email':'qa@example.test'}],'cc_users':[],'inline_images':[],'missing_fields':[],'sender_mode':'system','sender_verified':True}
        elif path=='/api/project-mails/' and route.request.method=='POST':
            mail_writes.append(route.request.post_data_json);data={'id':'mail'+str(len(mail_writes)),'status':'sent'}
        elif path=='/api/users/':data=[{'id':'qa','full_name':'测试人员','is_active':True,'email':'qa@example.test'},{'id':'u2','full_name':'其他人员','is_active':True,'email':'other@example.test'}]
        elif path=='/api/projects/translation/p1' and route.request.method in ('PUT','PATCH'):
            project_writes.append(route.request.post_data_json);data=root
        elif path.startswith('/api/project-files/project/'):data=[{'id':'f1','storage_path':r'D:\客户项目'}]
        elif path=='/api/project-files/f1':data={'id':'f1','storage_path':r'D:\客户项目'}
        elif path=='/api/business-mails/preview':data={'subject':'项目预告知','body':'测试预览','can_send':False,'blocking_reasons':['本测试不发送邮件']}
        elif path=='/api/projects/translation/page':data={'items':[root],'total':1}
        elif path=='/api/projects/translation/p1':data=root
        elif path=='/api/sub-orders/project/p1':data=rows
        elif path.endswith('/folder-import-records'):data={'items':[{'id':'log1','actor_name':'测试人员','created_at':'2026-11-07T22:00:00+08:00','root_path':r'D:\客户项目','empty_folders':['客户项目/空目录'],'created_count':5,'empty_detection_complete':True}]}
        elif path.startswith('/api/word-count-matrices/suborder/') and route.request.method=='PATCH':
            ident=path.rsplit('/',1)[1];payload=route.request.post_data_json;patches.append((ident,payload))
            row=next(row for row in rows if row['id']==ident)
            for change in payload['changes']:row['word_count_matrix'].setdefault(change['dimension'],{})[change['metric_type']]=change['value']
            data={}
        elif path.endswith('/export'):route.fulfill(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',body=b'mocked-xlsx');return
        elif path.endswith('/editor-drafts'):data={'payload':None,'revision':0}
        elif path.endswith('/page'):data={'items':[],'total':0}
        else:data=[]
        route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
    rows.clear()
    root.update({'project_name':'原文件.docx','source_file_name':'原文件.docx','sub_orders':[],'word_count_matrix':{'company':{'words':100}},'word_count_sub_order_count':0})
    writes=[]
    def mocks(route):
        path=urlparse(route.request.url).path
        if path.endswith('/business-numbers/reserve'):
            route.fulfill(content_type='application/json',body=json.dumps({'token':'00000000-0000-4000-8000-000000000099','number':number+'.001'}));return
        if path=='/api/sub-orders/' and route.request.method=='POST':
            payload=route.request.post_data_json;writes.append(payload)
            review={'required':True,'original_name':'原文件.docx','first_sub_order_id':'original-child','created_at':'2026-11-08T22:00:00+08:00'}
            root.update({'project_name':'原文件','source_file_name':'原文件','mother_split_review':review})
            first={'id':'original-child','sub_order_no':number+'.001','sub_project_name':'原文件.docx','parent_project_id':'p1','word_count_matrix':{'company':{'words':100}},'mother_split_review':review}
            second={'id':'new-child','sub_order_no':number+'.002','sub_project_name':payload['sub_project_name'],'parent_project_id':'p1','word_count_matrix':payload['word_count_matrix'],'mother_split_review':review}
            rows.extend([first,second]);route.fulfill(content_type='application/json',body=json.dumps(second));return
        api(route)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':950})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),mocks);page.route(BASE+'/five-level-test',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/five-level-test')
        page.get_by_role('button',name='编辑',exact=True).first.click()
        dialog=page.locator('.project-editor-dialog:visible')
        expect(dialog.get_by_role('tab',name='编辑母订单',exact=True)).to_be_visible()
        dialog.get_by_role('tab',name='补充子订单',exact=True).click();dialog.get_by_role('button',name='小量新增',exact=True).click()
        child=page.locator('.suborder-editor-dialog:visible')
        child.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text='文件名称')).locator('input').first.fill('第二个.pdf')
        expect(child.locator('.word-count-inline')).to_be_visible()
        child.locator('.word-count-inline input[aria-label="我司统计 字数"]').fill('20')
        child.get_by_role('button',name='保存',exact=True).click();expect(child).not_to_be_visible()
        assert writes[0]['word_count_matrix']['company']['words']==20 and writes[0]['preserve_original_file'] is True,writes
        expect(dialog.get_by_role('tab',name='编辑母订单',exact=True)).to_have_attribute('aria-selected','true')
        expect(dialog).to_contain_text('母订单信息需要调整')
        expect(dialog.locator('[data-field-key="sourceFileName"] input')).to_have_value('原文件')
        dialog.get_by_role('tab',name='补充子订单',exact=True).click()
        dialog.get_by_role('button',name='查看全部子订单',exact=True).click()
        manager=page.locator('.project-suborder-manager-dialog:visible')
        manager.get_by_role('button',name='小量新增',exact=True).click()
        expect(child.locator('.word-count-inline')).to_be_visible()
        child.locator('.word-count-inline input[aria-label="客户统计 页数"]').fill('2')
        child.get_by_role('button',name='取消',exact=True).click();expect(child).not_to_be_visible()
        manager.get_by_role('button',name='关闭窗口',exact=True).click();expect(manager).not_to_be_visible()
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='新增项目',exact=True).click()
        dialog.get_by_role('button',name='（紧急）项目预告知',exact=True).click()
        expect(page.locator('.el-message').filter(has_text='尚未保存或发送').first).to_be_visible(timeout=15000)
        assert not mail_writes,mail_writes
        assert not errors,errors
        browser.close()
    print('inline small-create statistics / preserve flag / shifted second child / mother review navigation / clear blocked emergency feedback / no mail sent PASS')

if __name__=='__main__':run()
