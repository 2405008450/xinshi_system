"""真实管理弹窗：少于10条可打开、四级路径、Excel粘贴及统计保存，全部接口模拟。"""
import json,re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><link rel="stylesheet" href="/src/styles/common.css"><style>html,body,#app{height:100%;margin:0}#app{display:flex;flex-direction:column}</style><div id="app"></div><script type="module">
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
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':950})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        def mocks(route):
            if '/business-numbers/reserve' in route.request.url:
                route.fulfill(content_type='application/json',body=json.dumps({'token':'00000000-0000-4000-8000-000000000099','number':'TP-261108-999'}));return
            api(route)
        page.route(re.compile(r'^http://localhost:3000/api/'),mocks);page.route(BASE+'/five-level-test',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda err:errors.append(str(err)));page.goto(BASE+'/five-level-test')
        page.get_by_role('button',name='新增项目',exact=True).click()
        dialog=page.locator('.project-editor-dialog:visible')
        if not dialog.count():dialog=page.locator('.el-dialog:visible').first
        tabs=dialog.get_by_role('tab')
        expect(tabs).to_have_text(['新增母订单','新增母子订单','补充子订单','项目文件','进度跟踪'])
        dialog.get_by_role('tab',name='新增母子订单',exact=True).click()
        expect(dialog.get_by_role('button',name='读取路径',exact=True)).to_be_visible()
        expect(dialog.get_by_role('button',name='按数量批量新增',exact=True)).not_to_be_visible()
        summary=dialog.locator('[data-field-key="wordCountSummary"]:visible')
        expect(summary).to_contain_text('此处暂不填写')
        expect(summary).not_to_have_class(re.compile(r'\bis-required\b'))
        expect(summary.get_by_role('button',name='展开字数统计',exact=True)).to_have_count(0)
        expect(dialog.get_by_text('预告知：其余必填项须完成，可跳过字数与汇总',exact=True)).to_be_visible()
        summary.get_by_role('button',name='打开子订单管理（填写字数并汇总）',exact=True).click()
        pending=page.locator('.pending-suborder-manager:visible');expect(pending).to_be_visible()
        pending.get_by_role('button',name='返回母订单',exact=True).click();expect(pending).not_to_be_visible()
        assert not project_writes,project_writes
        dialog.get_by_role('tab',name='新增母订单',exact=True).click()
        expect(dialog.locator('[data-field-key="wordCountSummary"]:visible').get_by_role('button',name='展开字数统计',exact=True)).to_be_visible()
        dialog.get_by_role('tab',name='新增母子订单',exact=True).click()
        dialog.get_by_role('tab',name='补充子订单',exact=True).click()
        expect(dialog.get_by_role('button',name='读取路径',exact=True)).not_to_be_visible()
        for label in ['小量新增','按数量批量新增','按文件名导入']:expect(dialog.get_by_role('button',name=label,exact=True)).to_be_visible()
        dialog.get_by_role('button',name='小量新增',exact=True).click()
        child=page.locator('.suborder-editor-dialog:visible')
        child.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text='文件名称')).locator('input').first.fill('local-child.docx')
        child.get_by_role('button',name='保存',exact=True).click();expect(child).not_to_be_visible()
        expect(dialog).to_contain_text('local-child.docx')
        dialog.get_by_role('button',name='按数量批量新增',exact=True).click()
        batch=page.locator('.suborder-batch-create-dialog:visible');expect(batch.get_by_role('tab')).to_have_count(0)
        batch.get_by_role('button',name='取消',exact=True).click()
        dialog.get_by_role('button',name='按文件名导入',exact=True).click()
        expect(batch).to_contain_text('复制/文件导入');batch.get_by_role('button',name='取消',exact=True).click()
        dialog.get_by_role('button',name='复用项目信息',exact=True).click()
        reuse=page.locator('.el-dialog:visible').filter(has=page.get_by_text('目前只支持复用母订单（无论是否包含子订单）的信息。',exact=True))
        expect(reuse).to_be_visible()
        page.wait_for_timeout(350)
        initial=reuse.bounding_box();header=reuse.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+350,header['y']+15);page.mouse.down();page.mouse.move(header['x']+370,header['y']+45,steps=5);page.mouse.up()
        moved=reuse.bounding_box();assert moved['y']>initial['y']+10 and moved['x']>=0 and moved['y']>=0
        reuse.get_by_role('button',name='关闭窗口',exact=True).click();expect(reuse).not_to_be_visible()
        dialog.get_by_role('button',name='复用项目信息',exact=True).click();expect(reuse).to_be_visible()
        page.wait_for_timeout(350)
        assert abs(reuse.bounding_box()['y']-initial['y'])<2,(initial,reuse.bounding_box())

        reuse.get_by_placeholder('订单号、客户名称、项目名称、翻译方向、客户经理、客户类型；支持多个关键词',exact=True).fill('中文 测试')
        reuse.get_by_role('button',name='查询',exact=True).click()
        reuse.get_by_role('radio',name='选择TP-261107-971',exact=True).locator('xpath=ancestor::label[1]').click()
        reuse.get_by_role('button',name='复用信息',exact=True).click();expect(reuse).not_to_be_visible()
        expect(dialog.get_by_role('tab',name='新增母订单',exact=True)).to_have_attribute('aria-selected','true')
        expect(dialog).to_contain_text('TP-261108-999')
        dialog.get_by_role('tab',name='补充子订单',exact=True).click();expect(dialog).to_contain_text('local-child.docx')
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='编辑',exact=True).first.click()
        expect(dialog).to_be_visible();dialog.get_by_role('tab',name='补充子订单',exact=True).click()
        expect(dialog.get_by_role('button',name='读取路径',exact=True)).to_have_count(0)
        for label in ['小量新增','按数量批量新增','按文件名导入']:expect(dialog.get_by_role('button',name=label,exact=True)).to_be_visible()
        assert not project_writes,project_writes
        assert not errors,errors
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        # 提取根路径返回后，即使尚无文件路径记录，也应回填原文路径。
        imports=[]
        def folder_import(route):
            imports.append(route.request.post_data_json)
            route.fulfill(content_type='application/json',body=json.dumps({'project_id':'p2','order_no':number,'project_name':'提取根目录','created_root':True,'created_count':1,'skipped_count':0}))
        page.route('**/api/sub-orders/folders/import',folder_import)
        page.route('**/api/project-files/project/p2**',lambda route:route.fulfill(content_type='application/json',body='[]'))
        page.route('**/api/projects/translation/p2',lambda route:route.fulfill(content_type='application/json',body=json.dumps({**root,'id':'p2'})))
        page.route('**/api/sub-orders/project/p2',lambda route:route.fulfill(content_type='application/json',body=json.dumps(rows)))
        page.evaluate("window.xinshiDesktop={chooseTranslationFolder:async()=>({rootPath:'E:\\\\提取根目录',entries:[{relativePath:'提取根目录',files:['test.pdf']}]})}")
        page.get_by_role('button',name='新增项目',exact=True).click()
        dialog.get_by_role('tab',name='新增母子订单',exact=True).click()
        dialog.get_by_role('button',name='读取路径',exact=True).click()
        batch=page.locator('.suborder-batch-create-dialog:visible')
        batch.get_by_role('tab',name='本地',exact=True).click()
        batch.get_by_role('button',name='选择本地文件夹',exact=True).click()
        batch.get_by_role('button',name='应用到新增表单',exact=True).click();expect(batch).not_to_be_visible()
        source=dialog.locator('[data-field-key="originalStoragePath"]:visible input')
        expect(source).to_have_value('E:\\提取根目录')
        assert not imports, '新增表单尚未保存，不应提前写入目录订单'
        dialog.get_by_role('tab',name='项目文件',exact=True).click()
        dialog.get_by_role('tab',name='新增母子订单',exact=True).click()
        expect(source).to_have_value('E:\\提取根目录')
        special=dialog.locator('[data-field-key="customerRequirementSpecial"] textarea')
        special.fill('未保存的特殊要求')
        dialog.get_by_role('tab',name='进度跟踪',exact=True).click()
        progress=dialog.locator('[data-field-key="translatorDeliveryProgress"] input')
        progress.fill('35');progress.press('Tab')
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='新增项目',exact=True).click()
        expect(dialog.get_by_role('tab',name='进度跟踪',exact=True)).to_have_attribute('aria-selected','true')
        expect(progress).to_have_value('35')
        dialog.get_by_role('tab',name='新增母子订单',exact=True).click()
        expect(special).to_have_value('未保存的特殊要求');expect(source).to_have_value('E:\\提取根目录')
        expect(page.get_by_text(re.compile('已恢复.*草稿|是否恢复草稿'))).to_have_count(0)
        for width,height in [(1440,950),(700,850)]:
            page.set_viewport_size({'width':width,'height':height})
            footer=dialog.locator('.el-dialog__footer');expect(footer).to_be_visible()
            body=dialog.locator('.editor-body');body.evaluate('(el)=>el.scrollTop=el.scrollHeight')
            box=footer.bounding_box()
            assert box['y']>=0 and box['y']+box['height']<=height+1,box
            assert dialog.bounding_box()['width']<=width+1
        assert not errors,errors
        browser.close()
    print('new tabs / path-only combined creation / shared child entries / pending small child / quantity-only / file import / editing no path PASS')

if __name__=='__main__':run()
