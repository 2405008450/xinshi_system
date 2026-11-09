"""笔译项目会话设置真实组件：接口模拟，不改真实设置。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'


def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Settings from '/src/components/chat/ChatSettings.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';const app=createApp({render:()=>h(Settings)});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
    ids=['00000000-0000-4000-8000-00000000000'+str(i) for i in range(1,5)]
    users=[{'id':identifier,'name':name} for identifier,name in zip(ids,['少妃','Thomas','孟花','李娴'])]
    data={'ready':True,'can_manage':True,'revision':0,'users':users,'audience':[{'value':'all','label':'全体'},{'value':'department:test','label':'笔译项目部'},{'value':'department:hr','label':'HR部'}],
          'settings':{'weekday_user_id':ids[0],'leave_backup_user_id':ids[1],'sunday_user_ids':ids[2:],'extra_audience':[],'participant_audience':['all']}}
    writes=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1200,'height':900})
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_permissions','[\"*\"]')")
        page.route(BASE+'/translation-settings-test',lambda route:route.fulfill(content_type='text/html',body=html))
        def api(route):
            if route.request.method=='PUT':writes.append(route.request.post_data_json)
            route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
        page.route(re.compile(r'^http://localhost:3000/api/'),api)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/translation-settings-test')
        page.get_by_role('button',name='笔译项目',exact=True).click()
        dialog=page.get_by_role('dialog',name='笔译项目 · 会话发送设置',exact=True)
        expect(dialog).to_be_visible()
        frame=dialog.locator('.el-dialog')
        expect(dialog).to_contain_text('少妃');expect(dialog).to_contain_text('Thomas')
        expect(dialog).to_contain_text('孟花');expect(dialog).to_contain_text('李娴')
        frame.locator('.el-dialog__header').hover()
        expect(frame).to_have_css('transform','none')
        initial=frame.bounding_box();header=dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+10,header['y']+header['height']-6);page.mouse.down();page.mouse.move(header['x']+25,header['y']+header['height']+29,steps=5);page.mouse.up()
        assert abs(frame.bounding_box()['y']-initial['y'])>10,(initial,frame.bounding_box(),header)
        field=dialog.locator('.el-form-item').filter(has_text='默认补充 @')
        field.locator('.el-select').click()
        options=page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
        expect(options.nth(0)).to_have_text('全体');expect(options.nth(1)).to_have_text('笔译项目部')
        options.nth(0).click();page.keyboard.press('Escape')
        dialog.get_by_role('button',name='保存设置',exact=True).click();expect(dialog).not_to_be_visible()
        assert writes and writes[0]['extra_audience']==['all'],writes
        page.get_by_role('button',name='笔译项目',exact=True).click();expect(dialog).to_be_visible()
        frame.locator('.el-dialog__header').hover()
        expect(frame).to_have_css('transform','none')
        assert abs(frame.bounding_box()['y']-initial['y'])<2,(initial,frame.bounding_box())
        dialog.get_by_role('button',name='关闭窗口',exact=True).click();expect(dialog).not_to_be_visible()
        assert not errors,errors;browser.close()
    print('chat settings entry / weekday fallback / Sunday candidates / all and translation-first audience / save / drag / close / reset PASS')


if __name__=='__main__':run()
