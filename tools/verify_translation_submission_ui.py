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
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1280,'height':850})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(BASE+'/five-level-test',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda err:errors.append(str(err)));page.goto(BASE+'/five-level-test')
        page.get_by_role('button',name='展开子订单',exact=True).first.click()
        page.get_by_role('button',name='进入子订单管理页',exact=True).click()
        dialog=page.locator('.project-suborder-manager-dialog:visible');expect(dialog).to_be_visible()
        initial=dialog.bounding_box()
        header=dialog.locator('.el-dialog__header').first.bounding_box()
        page.mouse.move(header['x']+450,header['y']+16);page.mouse.down();page.mouse.move(header['x']+440,header['y']+36,steps=5);page.mouse.up()
        moved=dialog.bounding_box()
        assert abs(moved['y']-initial['y'])>5 and moved['x']>=0 and moved['y']>=0
        table=dialog.locator('.suborder-management-table')
        body=table.locator('.el-scrollbar__wrap')
        sizes=body.evaluate('(el)=>({height:el.clientHeight,scrollHeight:el.scrollHeight,width:el.clientWidth,scrollWidth:el.scrollWidth})')
        assert sizes['scrollHeight']>sizes['height'] and sizes['scrollWidth']>sizes['width'],sizes
        heading=table.locator('.el-table__header-wrapper')
        initial_heading=heading.bounding_box()
        body.evaluate('(el)=>{el.scrollTop=400;el.scrollLeft=120}')
        assert abs(heading.bounding_box()['y']-initial_heading['y'])<1
        horizontal=table.locator('.el-scrollbar__bar.is-horizontal')
        vertical=table.locator('.el-scrollbar__bar.is-vertical')
        expect(horizontal).to_be_visible();expect(vertical).to_be_visible()
        bottom=horizontal.bounding_box()['y']+horizontal.bounding_box()['height']
        card=dialog.locator('.suborder-management').bounding_box()
        assert abs(card['y']+card['height']-bottom)<5,(card,horizontal.bounding_box())
        assert bottom<=850 and heading.bounding_box()['y']>=0
        page.set_viewport_size({'width':1024,'height':700})
        expect(horizontal).to_be_visible();expect(vertical).to_be_visible()
        resized=dialog.bounding_box()
        assert horizontal.bounding_box()['y']+horizontal.bounding_box()['height']<=700
        page.set_viewport_size({'width':1280,'height':850})
        grid=dialog.locator('.suborder-statistics-grid')
        expect(grid.locator('thead th').first).to_have_text('序号')
        expect(grid.locator('thead th').nth(3)).to_have_text('相对路径')
        expect(grid.locator('tbody tr').nth(3).locator('td').nth(3)).to_have_text('客户项目'+chr(92)+('很长的共享资料路径'+chr(92))*18+'末级文件.xlsx')
        expect(grid.locator('tbody tr').nth(0).locator('td').first).to_have_text('1')
        expect(grid.locator('tbody tr').nth(4).locator('td').first).to_have_text('5')
        splitter=dialog.get_by_role('separator',name='调整统计填写区与子订单列表高度',exact=True)
        top=dialog.locator('.vertical-split-top');bottom_panel=dialog.locator('.vertical-split-bottom')
        before_top=top.bounding_box()['height'];before_bottom=bottom_panel.bounding_box()['height']
        handle=splitter.bounding_box();x=handle['x']+handle['width']/2;y=handle['y']+handle['height']/2
        page.mouse.move(x,y);page.mouse.down();page.mouse.move(x,y+60,steps=8);page.mouse.up()
        assert top.bounding_box()['height']>before_top+40
        assert bottom_panel.bounding_box()['height']<before_bottom-40
        splitter.focus();splitter.press('ArrowUp')
        grid.locator('input[data-row="3"][data-col="0"]').fill('50')
        top_toggle=dialog.get_by_title('折叠统计填写区',exact=True)
        top_toggle.click();expect(grid).not_to_be_visible();expect(dialog.locator('.suborder-list-region')).to_be_visible()
        dialog.get_by_title('展开统计填写区',exact=True).click();expect(grid).to_be_visible()
        expect(grid.locator('input[data-row="3"][data-col="0"]')).to_have_value('50')
        dialog.get_by_title('折叠子订单列表',exact=True).click()
        expect(dialog.locator('.suborder-list-region')).not_to_be_visible();expect(grid).to_be_visible()
        dialog.get_by_title('展开子订单列表',exact=True).click()
        expect(dialog.locator('.suborder-list-region')).to_be_visible()

        expect(grid.locator('input[data-row="0"][data-col="0"]')).to_have_attribute('readonly','')
        cell=grid.locator('input[data-row="3"][data-col="0"]')
        cell.focus()
        cell.press('ArrowRight')
        expect(grid.locator('input[data-row="3"][data-col="1"]')).to_be_focused()
        page.keyboard.press('ArrowDown')
        expect(grid.locator('input[data-row="4"][data-col="1"]')).to_be_focused()
        page.keyboard.press('ArrowLeft')
        expect(grid.locator('input[data-row="4"][data-col="0"]')).to_be_focused()
        page.keyboard.press('ArrowUp')
        expect(cell).to_be_focused()
        cell.press('ArrowLeft')
        expect(cell).to_be_focused()

        cell.evaluate("el=>{const data=new DataTransfer();data.setData('text/plain','100\\t90\\t80\\t70\\n200\\t190\\t180\\t170');el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}))}")
        expect(cell).to_have_value('100');expect(grid.locator('input[data-row="4"][data-col="1"]')).to_have_value('190')
        cell.press('Enter');expect(grid.locator('input[data-row="4"][data-col="0"]')).to_be_focused()
        grid.get_by_role('button',name='保存统计（2 单）',exact=True).click()
        expect(grid.get_by_role('button',name='保存统计（0 单）',exact=True)).to_be_disabled()
        assert len(patches)==2,patches
        assert next(change['value'] for change in patches[0][1]['changes'] if change['dimension']=='customer' and change['metric_type']=='words')==90
        expect(dialog).to_contain_text(r'D:\客户项目')
        dialog.get_by_role('button',name='目录导入记录',exact=True).click()
        expect(page.locator('.folder-import-records:visible')).to_contain_text(r'D:\客户项目\空目录')
        expect(page.locator('.folder-import-records:visible')).to_contain_text('测试人员')
        dialog.get_by_role('button',name='目录导入记录',exact=True).click()
        with page.expect_download() as download:dialog.get_by_role('button',name='导出层级Excel',exact=True).click()
        assert download.value.suggested_filename.endswith('.xlsx')
        dialog.get_by_role('button',name='关闭窗口',exact=True).first.click();expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='进入子订单管理页',exact=True).click();expect(dialog).to_be_visible()

        dialog.locator('.suborder-management-table').get_by_role('button',name='编辑',exact=True).first.click()
        editor=page.locator('.suborder-editor-dialog:visible')
        extras=editor.locator('.order-inherited-extras')
        expect(extras).to_be_visible()
        expect(extras.locator('.el-form-item').filter(has_text='客户专业要求').locator('textarea')).to_have_value('子专业要求')
        expect(extras.locator('.inheritance-label')).to_have_count(4)
        extras.locator('.el-form-item').filter(has_text='客户特殊要求').locator('textarea').fill('手工调整要求')
        progress=editor.locator('.suborder-progress-collapse')
        expect(progress.locator('.el-collapse-item__wrap')).not_to_be_visible()
        progress.get_by_role('button',name='进度跟踪',exact=True).click()
        expect(progress.locator('.el-collapse-item__wrap')).to_be_visible()
        progress.locator('input').first.fill('30')
        expect(editor.locator('.el-form-item').filter(has_text='网络文件路径').locator('input')).to_be_visible()
        editor.get_by_role('button',name='取消',exact=True).click()
        expect(editor).not_to_be_visible()
        dialog.locator('.suborder-management-table').get_by_role('button',name='编辑',exact=True).first.click()
        editor=page.locator('.suborder-editor-dialog:visible')
        expect(editor.locator('.suborder-progress-collapse .el-collapse-item__wrap')).not_to_be_visible()
        editor.get_by_role('button',name='取消',exact=True).click()

        dialog.get_by_role('button',name='关闭窗口',exact=True).first.click()
        page.get_by_role('button',name='编辑',exact=True).first.click()
        main=page.locator('.project-editor-dialog:visible')
        expect(main).to_be_visible()
        professional=main.locator('.el-form-item').filter(has=page.locator('[data-field-key="nonexistent"]')) if False else main.locator('[data-field-key="customerRequirementProfessional"]')
        diff=professional.locator('.field-difference')
        expect(diff.locator('summary')).to_contain_text('4 个下级订单')
        expect(diff.locator('.difference-item').first).not_to_be_visible()
        diff.locator('summary').click()
        expect(diff.locator('.difference-item')).to_have_count(4)
        expect(diff.locator('.difference-item').first).to_be_visible()
        direction=main.locator('[data-field-key="languagePair"]').locator('.field-difference')
        expect(direction).to_contain_text('英语→中文')
        expect(direction).not_to_contain_text(number)
        main.get_by_role('button',name='保存',exact=True).click()
        expect(page.locator('.project-suborder-manager-dialog:visible')).to_be_visible()
        assert not project_writes,project_writes
        page.locator('.project-suborder-manager-dialog:visible').get_by_role('button',name='关闭窗口',exact=True).first.click()
        main.get_by_role('button',name='（紧急）项目预告知',exact=True).click()
        expect(main).to_be_visible()
        assert project_writes and project_writes[-1]['submission_mode']=='emergency_notice',project_writes
        assert project_writes[-1]['sub_orders_reviewed'] is False
        expect(page.locator('.business-mail-dialog:visible')).to_be_visible()
        composer=page.locator('.business-mail-dialog:visible')
        composer.get_by_role('button',name='发送邮件',exact=True).click()
        expect(composer).not_to_be_visible()
        assert len(mail_writes)==1 and mail_writes[-1]['send_translation_chat'] is False
        assert not chat_writes
        main.get_by_role('button',name=re.compile(r'^保存并发送会话(?:（.*）)?$')).click()
        expect(main.get_by_role('button',name='保存并发送会话（1次）',exact=True)).to_be_visible()
        assert len(chat_writes)==1
        main.get_by_role('button',name=re.compile(r'^保存并发送会话和邮件')).click()
        composer=page.locator('.business-mail-dialog:visible');expect(composer).to_be_visible()
        assert len(chat_writes)==1
        composer.get_by_role('button',name='发送邮件',exact=True).click()
        expect(composer).not_to_be_visible()
        assert len(mail_writes)==2 and mail_writes[-1]['send_translation_chat'] is True
        expect(main.get_by_role('button',name='保存并发送邮件（2次）',exact=True)).to_be_visible()
        expect(main.get_by_role('button',name='保存并发送会话（2次）',exact=True)).to_be_visible()



        assert not errors,errors;browser.close()
    print('preflight gate / emergency mail only / keep editor open / conversation only / mail-and-conversation opt-in / successful counters / repeat sends / mocked delivery PASS')
if __name__=='__main__':run()
