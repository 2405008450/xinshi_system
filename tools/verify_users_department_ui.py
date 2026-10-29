"""从真实 Users 列表点击所属部门；仅使用隔离接口，不修改业务数据。"""
import json
import re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    person={'id':'person-1','username':'pm-test','full_name':'测试人员','department':None,'is_active':True,'roles':[]}
    organization={'ready':True,'membershipReady':True,'canManage':True,'aliases':{},'items':[{'id':'project','name':'项目部','revision':1,'userCount':0},{'id':'hr','name':'HR部','revision':1,'userCount':0}],
                  'people':[{'id':'person-1','name':'测试人员','username':'pm-test','active':True,'primaryDepartment':None,'departments':[]}]}
    writes=[];errors=[]
    html=f'''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {{createApp,h}} from {json.dumps(vue)};
    import Users from '/src/views/system/Users.vue';
    import AppForm from '/src/components/common/AppForm.vue';
    import Dialog from '/src/components/common/DraggableFormDialog.vue';
    const app=createApp({{render:()=>h(Users)}});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.mount('#app');</script>'''
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/users/page':result={'items':[person],'total':1}
        elif path=='/api/departments/organization':result=organization
        elif path=='/api/departments/people/person-1/memberships' and route.request.method=='PUT':
            body=route.request.post_data_json;writes.append(body)
            selected=[d for d in organization['items'] if d['id'] in body['department_ids']]
            person['department']=next((d['name'] for d in selected if d['id']==body['primary_department_id']),None)
            organization['people'][0]['departments']=[{'id':d['id'],'name':d['name'],'position':''} for d in selected]
            organization['people'][0]['primaryDepartment']=person['department'];result=organization
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1600,'height':1000},service_workers='block')
        context.add_init_script("localStorage.setItem('user_roles',JSON.stringify(['超级管理员']));localStorage.setItem('user_permissions',JSON.stringify(['system:users:read','system:users:write']));localStorage.setItem('user_id','qa')")
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/users-department-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/users-department-test')
        cell=page.get_by_role('button',name='调整测试人员的所属部门',exact=True)
        expect(cell).to_be_visible()
        cell.get_by_text('未分部门',exact=True).click()
        dialog=page.locator('.user-department-dialog.el-dialog')
        expect(dialog).to_be_visible()
        expect(page.get_by_text('用户邮件资料',exact=True)).not_to_be_visible()
        dialog.get_by_role('combobox').first.click();page.get_by_role('option',name='项目部',exact=True).click()
        dialog.get_by_role('combobox').first.press('Escape')
        assert not writes
        dialog.get_by_role('button',name='取消',exact=True).click()
        expect(dialog).not_to_be_visible();expect(cell).to_have_text('未分部门');assert not writes
        cell.click();expect(dialog).to_be_visible()
        dialog.get_by_role('combobox').first.click();page.get_by_role('option',name='项目部',exact=True).click()
        dialog.get_by_role('combobox').first.press('Escape')
        dialog.get_by_role('button',name='确认',exact=True).click()
        expect(dialog).not_to_be_visible();expect(cell).to_have_text('项目部')
        cell.get_by_text('项目部',exact=True).click();expect(dialog).to_be_visible()
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        assert len(writes)==1 and writes[0]['department_ids']==['project']
        assert not errors,errors
        print(json.dumps({'passed':True,'real_users_cell_click':True,'cancel_writes':0,'confirmed_writes':len(writes),'page_errors':errors}))
        context.close();browser.close()


if __name__=='__main__':run()
