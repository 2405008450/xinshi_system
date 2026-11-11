"""真实笔译编辑器：保存后清空、会话优先于刷新、失败同键重试；所有接口模拟。"""
import json,re
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
BASE='http://localhost:3000'

def run():
    source=(ROOT/'tools/verify_translation_submission_ui.py').read_text(encoding='utf8')
    prefix=source[source.index('    compiled='):source.index('    with sync_playwright() as p:')]
    scope={'urlopen':urlopen,'json':json,'re':re,'BASE':BASE,'urlparse':urlparse}
    exec('def prepare():\n'+prefix+'\n    return locals()\n',scope)
    state=scope['prepare']()
    root=state['root'];root.update(source_file_name='测试.pdf',project_name='测试.pdf',sub_orders=[],word_count_sub_order_count=0,word_count_matrix={'company':{'words':10}})
    state['rows'].clear()
    requests=[];chat_attempts=[];failure={'active':False};refresh_failure={'active':False}
    def api(route):
        path=urlparse(route.request.url).path
        requests.append((route.request.method,path))
        if path=='/api/translation-delivery/p1/chat':
            chat_attempts.append(route.request.post_data_json)
            if failure['active']:
                route.fulfill(status=503,content_type='application/json',body=json.dumps({'detail':'测试会话暂不可用'}));return
            route.fulfill(content_type='application/json',body=json.dumps({'room_id':'room-test','chat_count':1,'mail_count':0,'warnings':[]}));return
        if path=='/api/sub-orders/project/p1' and refresh_failure['active']:
            route.fulfill(status=503,content_type='application/json',body='{}');return
        if path=='/api/projects/translation/p1' and route.request.method in ('PUT','PATCH'):
            refresh_failure['active']=True
        state['api'](route)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api)
        page.route(BASE+'/five-level-test',lambda route:route.fulfill(content_type='text/html',body=state['html']))
        page.goto(BASE+'/five-level-test')
        def edit():
            refresh_failure['active']=False
            page.get_by_role('button',name='编辑',exact=True).first.click()
            dialog=page.locator('.project-editor-dialog:visible');expect(dialog).to_be_visible();return dialog
        dialog=edit()
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(dialog).not_to_be_visible(timeout=10000)
        page.get_by_role('button',name='新增项目',exact=True).click()
        dialog=page.locator('.project-editor-dialog:visible');expect(dialog).to_be_visible()
        expect(dialog.locator('[data-field-key="clientName"] input')).to_have_value('')
        expect(dialog.locator('[data-field-key="clientShortName"] input')).to_have_value('')
        # 清空不校验必填；空白状态可以保存，但不创建空订单。
        dialog.locator('[data-field-key="clientName"] input').fill('应被清除的旧客户')
        dialog.get_by_role('button',name='清空',exact=True).click()
        expect(dialog.locator('[data-field-key="clientName"] input')).to_have_value('')
        expect(dialog.locator('.el-form-item__error')).to_have_count(0)
        writes_before=len(state['project_writes']);request_start=len(requests)
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(dialog).not_to_be_visible(timeout=10000)
        assert len(state['project_writes'])==writes_before
        assert not any(method=='POST' and path=='/api/projects/translation/' for method,path in requests[request_start:])
        page.get_by_role('button',name='新增项目',exact=True).click()
        dialog=page.locator('.project-editor-dialog:visible');expect(dialog).to_be_visible()
        expect(dialog.locator('[data-field-key="clientName"] input')).to_have_value('')
        # 清空后重新录入必须按正常项目校验，不能沿用空白保存通道。
        dialog.get_by_role('button',name='清空',exact=True).click()
        dialog.locator('[data-field-key="clientName"] input').fill('新客户')
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(dialog.locator('.el-form-item__error').first).to_be_visible()
        assert len(state['project_writes'])==writes_before
        dialog.get_by_role('button',name='清空',exact=True).click()
        expect(dialog.locator('.el-form-item__error')).to_have_count(0)
        dialog.get_by_role('button',name='关闭窗口',exact=True).first.click();expect(dialog).not_to_be_visible()
        # 保存成功即使子订单刷新不可用，也必须发送会话并关闭表单。
        dialog=edit();requests.clear()
        dialog.get_by_role('button',name=re.compile(r'^保存并发送会话(?:（.*）)?$')).click()
        expect(dialog).not_to_be_visible(timeout=10000)
        assert len(chat_attempts)==1,chat_attempts
        assert ('POST','/api/translation-delivery/p1/chat') in requests,requests
        # 失败保留明确提示；重试只重发会话，复用幂等键，不重复保存项目。
        failure['active']=True
        dialog=edit()
        dialog.get_by_role('button',name=re.compile(r'^保存并发送会话(?:（.*）)?$')).click()
        retry=dialog.get_by_role('button',name='重试发送会话（无需再次保存）',exact=True)
        expect(retry).to_be_visible(timeout=10000)
        expect(dialog).to_contain_text('项目已保存，会话尚未确认发送')
        saved_count=len(state['project_writes']);failed_key=chat_attempts[-1]['request_key']
        failure['active']=False
        retry.click();expect(dialog).not_to_be_visible(timeout=10000)
        assert len(state['project_writes'])==saved_count
        assert chat_attempts[-1]['request_key']==failed_key
        assert not errors,errors
        browser.close()
    print('PASS: save closes / next create empty / refresh failure cannot block chat / visible failure / retry same key without saving')

if __name__=='__main__':run()
