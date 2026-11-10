"""编号确认临时503恢复后正常保存并发送，全部接口模拟，无业务写入。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive,ref} from VUE;import AppForm from '/src/components/common/AppForm.vue';import api from '/src/api/index.js';
const model=reactive({id:'',orderNo:'',projectName:'必须保留的项目内容'}),form=ref(),status=ref('');async function save(){if(!await form.value.validate().catch(()=>false))return;await api.post('/projects/translation/',{order_no:model.orderNo,project_name:model.projectName});await api.post('/translation-delivery/qa-project/chat',{request_key:'qa-only'});status.value='保存并发送完成'}
createApp({render:()=>h('div',[h(AppForm,{ref:form,model,numberScope:'translation',numberField:'orderNo',numberActive:true},{default:()=>[h('input',{'aria-label':'订单号',readonly:true,value:model.orderNo}),h('input',{'aria-label':'项目内容',value:model.projectName,onInput:event=>model.projectName=event.target.value})]}),h('button',{onClick:save},'保存并发送会话'),h('p',{id:'status'},status.value)])}).mount('#app');
</script>'''.replace('from VUE','from '+json.dumps(vue))
    heartbeats=[];creates=[];chats=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page();errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script("localStorage.setItem('user_id','number-recovery-qa');localStorage.setItem('token','isolated')")
        def api(route):
            path=urlparse(route.request.url).path
            if path=='/api/business-numbers/reserve':result={'token':'qa-lease','number':'TP-261110-099'}
            elif path.endswith('/heartbeat'):
                heartbeats.append(path)
                if len(heartbeats)==1:route.fulfill(status=503,content_type='application/json',body=json.dumps({'detail':'服务繁忙，请稍后重试'}));return
                result={'ok':True}
            elif path=='/api/projects/translation/':creates.append(route.request.post_data_json);result={'id':'qa-project'}
            elif path=='/api/translation-delivery/qa-project/chat':chats.append(route.request.post_data_json);result={'chat_count':1}
            else:result={}
            route.fulfill(content_type='application/json',body=json.dumps(result))
        page.route(BASE+'/api/**',api);page.route(BASE+'/number-recovery-qa',lambda route:route.fulfill(content_type='text/html',body=html))
        page.goto(BASE+'/number-recovery-qa');number=page.get_by_role('textbox',name='订单号',exact=True)
        expect(number).to_have_value('TP-261110-099')
        page.get_by_role('button',name='保存并发送会话',exact=True).click()
        error=page.get_by_text('订单号暂时无法确认，系统正在重试，填写内容已保留，请稍后保存。',exact=True)
        expect(error).to_be_visible();assert not creates and not chats
        expect(error).not_to_be_visible(timeout=10000)
        expect(number).to_have_value('TP-261110-099');expect(page.get_by_role('textbox',name='项目内容',exact=True)).to_have_value('必须保留的项目内容')
        page.get_by_role('button',name='保存并发送会话',exact=True).click();expect(page.locator('#status')).to_have_text('保存并发送完成')
        assert len(creates)==1 and len(chats)==1
        assert creates[0]['order_no']=='TP-261110-099'
        assert not errors,errors
        browser.close()
    print('PASS: transient numbering failure blocks writes / auto recovery in seconds / contents and number retained / save and chat exactly once')
if __name__=='__main__':run()
