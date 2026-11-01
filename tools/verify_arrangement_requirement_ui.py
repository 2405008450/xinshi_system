"""真实部门面板、下级订单安排、今日任务与通知回复联调；接口全部模拟。"""
import json
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import expect,sync_playwright

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=20).read().decode()
    dep=lambda name:re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {createApp,h,ref} from VUE;import {createRouter,createWebHistory} from ROUTER;import Personnel from '/src/components/common/ArrangementPersonnel.vue';import Table from '/src/views/project/translation/components/ProjectArrangementTable.vue';import Today from '/src/views/schedule/components/TodayTasks.vue';import Bell from '/src/components/NotificationBell.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
    const app=createApp({setup(){const selected=ref([{id:'qa1',name:'甲'}]);return()=>h('main',{},[h(Bell),h('div',{style:'display:grid;grid-template-columns:320px minmax(0,1fr);gap:12px'},[h(Personnel,{departmentVisibility:true,modelValue:selected.value,'onUpdate:modelValue':value=>selected.value=value}),h(Table,{projects:[{id:'root',orderNo:'TP-ORDER-001',sourceFileName:'母订单.docx',projectStatus:'confirmed',customerRequirementProfessional:'法律术语统一',customerRequirementSpecial:'保留原格式'}],people:selected.value,canWrite:true})]),h(Today,{day:'2026-10-31'})])}});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/arrangement-requirement-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(dep('vue'))).replace('from ROUTER','from '+json.dumps(dep('vue-router')))
    directory={'items':[{'id':'project','name':'项目部'},{'id':'hr','name':'HR部'},{'id':'empty','name':'空部门'}],'people':[{'id':'qa1','name':'甲','username':'jia','active':True,'departments':[{'id':'project','name':'项目部'}]},{'id':'p2','name':'乙','username':'yi','active':True,'departments':[{'id':'hr','name':'HR部'}]}]}
    third={'id':'third','order_no':'TP-ORDER-001.001.001','project_name':'三级订单.xlsx','level':3,'status':'pending_confirmation','children':[]}
    child={'id':'child','order_no':'TP-ORDER-001.001','project_name':'子订单.pdf','level':2,'status':'confirmed','children':[third]}
    tree={'items':[{'id':'root','order_no':'TP-ORDER-001','project_name':'母订单.docx','level':1,'status':'confirmed','children':[child]}],'ready':True}
    task={'id':'t1','assignee_id':'qa1','assignee_name':'甲','project_id':'root','order_no':third['order_no'],'project_name':third['project_name'],'work_date':'2026-10-31','content':'翻译','status':'pending','revision':1,'estimated_minutes':0,'actual_minutes':0,'execution_sequence':[],'customer_requirement_professional':'法律术语统一','customer_requirement_special':'保留原格式'}
    requirement={'id':'req1','project_id':'root','order_no':'TP-ORDER-001','project_name':'母订单.docx','original_text':'需求原文','translated_text':'Requirement','chargeable':False,'previous_status':'confirmed','saved_status':'simple_requirement','current_status':'simple_requirement','actor_name':'发送人','created_at':'2026-10-31T10:00:00+08:00','can_reply':True,'recipients':[{'user_id':'qa1','user_name':'甲','received_at':None,'reply':None}]}
    notice={'id':'n1','title':'简单需求通知测试','content':'请回复收到','notification_type':'translation_simple_requirement','related_entity_id':'req1','related_project_id':'root','related_project_type':'translation','is_read':False,'created_at':'2026-10-31T10:00:00+08:00'}
    assigned=[];posts=[];replies=[];errors=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/departments/organization':result=directory
        elif path=='/api/project-arrangements/directory':result={'ready':True}
        elif path=='/api/project-arrangements/project/root/orders':result=tree
        elif path=='/api/project-arrangements/project/root/detail':result={'ready':True,'tasks':assigned,'history':[],'history_total':0,'revision':0,'common_instruction':'','instruction_revision':0}
        elif path=='/api/project-arrangements/project/root':
            body=route.request.post_data_json;posts.append(body)
            for uid in body['target_order_ids']:
                node=child if uid=='child' else third
                assigned.append({**task,'id':uid,'order_no':node['order_no'],'project_name':node['project_name'],'order_level':node['level']})
            result=assigned
        elif path=='/api/project-arrangements':result={'items':[task],'total':1,'ready':True}
        elif path=='/api/translation-simple-requirements/req1/received':
            replies.append(route.request.post_data_json);requirement['recipients'][0].update(received_at='2026-10-31T11:00:00+08:00',reply=replies[-1]['reply']);requirement['can_reply']=False;result=requirement
        elif path=='/api/translation-simple-requirements/req1':result=requirement
        elif path=='/api/notifications/':result=[notice]
        elif path.endswith('/unread-count'):result={'count':1}
        elif path=='/api/notifications/n1/read':notice['is_read']=True;result=notice
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True);context=browser.new_context(viewport={'width':1600,'height':1100},service_workers='block')
        context.add_init_script("if(!localStorage.getItem('user_id')){localStorage.setItem('user_id','qa1');localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['projects:read','projects:write','reports:read']));}")
        context.route(re.compile(r'^http://localhost:3000/api/'),api);context.route(BASE+'/arrangement-requirement-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.set_default_timeout(12000);page.on('pageerror',lambda error:errors.append(error.stack));page.goto(BASE+'/arrangement-requirement-test')
        left=page.locator('.arrangement-personnel');left.get_by_role('button',name='显示部门',exact=True).click();picker=page.locator('.app-window-popover:visible').filter(has_text='显示部门')
        expect(picker).to_contain_text('空部门');picker.get_by_role('button',name='清空',exact=True).click();picker.locator('label.el-checkbox').filter(has_text=re.compile('^项目部$')).click();picker.get_by_role('button',name='确定',exact=True).click()
        expect(left).not_to_contain_text('HR部');page.reload();expect(left).not_to_contain_text('HR部')
        left.locator('.el-radio-button').filter(has_text='全体人员').click();expect(left.locator('.person')).to_have_count(1)
        left.get_by_role('button',name=re.compile('显示部门')).click();picker=page.locator('.app-window-popover:visible').filter(has_text='显示部门');picker.get_by_role('button',name='全选',exact=True).click();picker.get_by_role('button',name='取消',exact=True).click();expect(left.locator('.person')).to_have_count(1)
        table=page.locator('.arrangement-projects');table.get_by_role('button',name='安排',exact=True).click();expect(table.locator('.arrangement-order-picker')).to_contain_text('子订单.pdf')
        def node_content(number):return table.locator('.el-tree-node__content').filter(has=page.locator('.target-order-name',has_text=re.compile('^'+re.escape(number)+' ·')))
        node_content('TP-ORDER-001').locator('label.el-checkbox').click();node_content(child['order_no']).locator('label.el-checkbox').click();node_content(child['order_no']).locator('.el-tree-node__expand-icon').click();node_content(third['order_no']).locator('label.el-checkbox').click()
        table.locator('.project-assignees > .assignment-line textarea').fill('核对术语');table.get_by_role('button',name='保存安排',exact=True).click();expect(table.locator('.plan-current-tasks .assignment-line')).to_have_count(2)
        assert set(posts[0]['target_order_ids'])=={'child','third'}
        table.get_by_role('button',name='客户要求',exact=True).click();requirements=page.locator('.app-window-popover:visible').filter(has_text='客户专业要求');expect(requirements).to_contain_text('法律术语统一');expect(requirements).to_contain_text('保留原格式');requirements.get_by_role('button',name='关闭窗口',exact=True).click();expect(requirements).not_to_be_visible()
        today=page.locator('.today-tasks');expect(today).to_contain_text(third['order_no']);today.get_by_role('button',name='客户要求',exact=True).click();requirements=page.locator('.app-window-popover:visible').filter(has_text='客户专业要求');expect(requirements).to_contain_text('法律术语统一');requirements.get_by_role('button',name='关闭窗口',exact=True).click();expect(requirements).not_to_be_visible()
        page.get_by_role('button',name='系统通知',exact=True).click();page.get_by_role('button').filter(has_text='简单需求通知测试').click();dialog=page.locator('.el-dialog:visible').filter(has_text='简单需求 · 收到及已完成回执');expect(dialog).to_contain_text('需求原文');expect(dialog).to_contain_text('不收费')
        rect=dialog.bounding_box();header=dialog.locator('.el-dialog__header').bounding_box();page.mouse.move(header['x']+250,header['y']+15);page.mouse.down();page.mouse.move(header['x']+300,header['y']+45,steps=8);page.mouse.up();moved=dialog.bounding_box();assert abs(moved['x']-rect['x'])+abs(moved['y']-rect['y'])>20
        dialog.get_by_label('收到回复',exact=True).fill('收到，已确认');dialog.get_by_role('button',name='回复收到',exact=True).click();expect(dialog).to_contain_text('收到，已确认');expect(dialog.get_by_role('button',name='回复收到',exact=True)).to_have_count(0);assert replies==[{'reply':'收到，已确认'}]
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        page.evaluate("localStorage.setItem('user_id','another-user')");page.reload();expect(left).to_contain_text('HR部')
        assert not errors,errors;page.screenshot(path='scratch/arrangement-order-requirements.png');browser.close()
    print('department selection persistence/isolation, child/third batch arrangement, both customer requirement viewers and real notification reply dialog PASS')


if __name__=='__main__':run()
