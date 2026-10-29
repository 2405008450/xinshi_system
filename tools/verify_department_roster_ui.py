"""部门名册嵌套弹窗的多选、搜索、保存及权限验收；所有接口隔离。"""
import json
import re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    data={'ready':True,'canManage':True,'membershipReady':True,'aliases':{},'items':[{'id':'project','name':'项目部','revision':1,'userCount':1}],
          'people':[{'id':'existing','name':'原有人员','username':'existing','active':True,'primaryDepartment':'项目部','departments':[{'id':'project','name':'项目部','position':'项目助理'}]},
                    {'id':'added1','name':'测试甲','username':'added1','active':True,'primaryDepartment':'HR部','departments':[{'id':'hr','name':'HR部','position':''}]},
                    {'id':'added2','name':'测试乙','username':'added2','active':True,'primaryDepartment':'排版','departments':[{'id':'layout','name':'排版','position':''}]},
                    {'id':'inactive','name':'停用人员','username':'inactive','active':False,'primaryDepartment':'HR部','departments':[]}]}
    data['items'].extend([{'id':'hr','name':'HR部','revision':1,'userCount':1},{'id':'layout','name':'排版','revision':1,'userCount':1}])
    writes=[];person_writes=[];errors=[]
    html=f'''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
    import {{createApp,h,ref}} from {json.dumps(vue)};
    import Dialog from '/src/components/common/DraggableFormDialog.vue';
    import Roster from '/src/components/common/DepartmentRoster.vue';
    import PersonDialog from '/src/components/common/UserDepartmentDialog.vue';
    import AppForm from '/src/components/common/AppForm.vue';
    const app=createApp({{setup(){{const visible=ref(true),personVisible=ref(false);return()=>h('div',[h(Dialog,{{modelValue:visible.value,'onUpdate:modelValue':v=>visible.value=v,title:'项目部',width:'min(1000px, calc(100vw - 32px))'}},{{default:()=>[h(Roster,{{departmentName:'项目部'}}),h('button',{{onClick:()=>personVisible.value=true}},'调整测试甲的所属部门')]}}),h(PersonDialog,{{modelValue:personVisible.value,'onUpdate:modelValue':v=>personVisible.value=v,user:{{id:'added1',username:'added1',full_name:'测试甲'}}}})])}}}});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.mount('#app');</script>'''
    def api(route):
        path=urlparse(route.request.url).path
        if path=='/api/departments/organization':result=data
        elif path=='/api/departments/people/added1/memberships' and route.request.method=='PUT':
            body=route.request.post_data_json;person_writes.append(body)
            person=next(p for p in data['people'] if p['id']=='added1')
            person['departments']=[{'id':d['id'],'name':d['name'],'position':''} for d in data['items'] if d['id'] in body['department_ids']]
            person['primaryDepartment']=next((d['name'] for d in data['items'] if d['id']==body['primary_department_id']),None)
            result=data
        elif path=='/api/departments/project/members' and route.request.method=='PUT':
            body=route.request.post_data_json;writes.append(body)
            for person in data['people']:
                entry=next((row for row in body['members'] if row['user_id']==person['id']),None)
                person['departments']=[d for d in person['departments'] if d['id']!='project']
                if entry:person['departments'].append({'id':'project','name':'项目部','position':entry['position']})
            data['items'][0]['revision']+=1;data['items'][0]['userCount']=len(body['members']);result=data
        else:result=[]
        route.fulfill(content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':900},service_workers='block')
        context.route(re.compile(r'^http://localhost:3000/api/'),api)
        context.route(BASE+'/roster-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/roster-test')
        page.get_by_role('button',name='添加人员',exact=True).click()
        editor=page.locator('.department-roster-editor.el-dialog')
        expect(editor).to_be_visible()
        picker=page.get_by_role('combobox',name='从全公司选择添加人员',exact=True)
        picker.click()
        page.get_by_role('option',name=re.compile('测试甲')).click()
        page.get_by_role('option',name=re.compile('测试乙')).click()
        picker.press('Escape')
        page.get_by_role('button',name='添加并保存',exact=True).click()
        expect(editor).not_to_be_visible()
        assert len(writes)==1 and {row['user_id'] for row in writes[0]['members']}=={'existing','added1','added2'}
        expect(page.get_by_role('row').filter(has_text='测试甲')).to_be_visible()
        expect(page.get_by_role('row').filter(has_text='测试乙')).to_be_visible()
        page.get_by_role('button',name='调整测试甲的所属部门',exact=True).click()
        person_dialog=page.locator('.user-department-dialog.el-dialog')
        expect(person_dialog).to_be_visible()
        page.wait_for_function("!document.querySelector('[class*=fade-enter-active]')")
        initial=person_dialog.bounding_box()
        header=person_dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+200,header['y']+header['height']-10)
        page.mouse.down();page.mouse.move(header['x']+240,header['y']+header['height']+30,steps=6);page.mouse.up()
        assert abs(person_dialog.bounding_box()['x']-initial['x'])>5
        person_dialog.get_by_role('combobox').first.click()
        page.get_by_role('option',name='排版',exact=True).click()
        person_dialog.get_by_role('combobox').first.press('Escape')
        assert not person_writes
        person_dialog.get_by_role('button',name='取消',exact=True).click()
        assert not person_writes
        page.get_by_role('button',name='调整测试甲的所属部门',exact=True).click()
        expect(person_dialog).to_be_visible()
        page.wait_for_function("!document.querySelector('[class*=fade-enter-active]')")
        assert abs(person_dialog.bounding_box()['x']-initial['x'])<5
        person_dialog.get_by_role('combobox').first.click()
        page.get_by_role('option',name='排版',exact=True).click()
        person_dialog.get_by_role('combobox').first.press('Escape')
        person_dialog.get_by_role('button',name='确认',exact=True).click()
        expect(person_dialog).not_to_be_visible()
        assert len(person_writes)==1 and set(person_writes[0]['department_ids'])=={'hr','project','layout'}
        assert not errors,errors
        print(json.dumps({'passed':True,'saved_members':len(writes[0]['members']),'person_department_saves':len(person_writes),'page_errors':errors}))
        context.close();browser.close()


if __name__=='__main__':run()
