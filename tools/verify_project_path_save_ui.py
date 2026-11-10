"""项目路径组：新增后重新挂载、慢加载、加载失败、缺少原文路径；接口模拟。"""
import json,re,time
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref,reactive,nextTick} from VUE;import Files from '/src/views/project/translation/components/ProjectFilesTab.vue';import AppForm from '/src/components/common/AppForm.vue';
const mode=new URLSearchParams(location.search).get('mode'),id=ref(''),files=ref(),result=ref(''),source=ref(mode==='missing'?'':'D:\\\\原文目录'),draft=ref({storage_path:source.value,dispatch_path:'D:\\\\派稿目录',file_format:'DOCX'});
async function save(){const snapshot=files.value.getPathGroupSnapshot();id.value='new-project';await nextTick();try{await files.value.savePathGroup({projectId:id.value,orderNo:'TP-261110-999',snapshot,silent:true});result.value='保存成功'}catch(error){result.value=error.message}}
const app=createApp({render:()=>h('div',[h('button',{onClick:save},'模拟新增项目后保存路径'),h('p',{id:'result'},result.value),h(Files,{key:id.value||'draft',ref:files,projectId:id.value,allowDraft:true,active:true,sourcePath:source.value,'onUpdate:sourcePath':v=>source.value=v,draft:draft.value,'onUpdate:draft':v=>draft.value=v})])});app.component('AppForm',AppForm);app.mount('#app');
</script>'''.replace('from VUE','from '+json.dumps(vue))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge')
        for mode in ('slow','load-fail','missing'):
            page=browser.new_page(viewport={'width':1400,'height':1000});errors=[];writes=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_permissions','[\"*\"]')")
            def api(route):
                path=urlparse(route.request.url).path
                if '/project-files/project/' in path:
                    time.sleep(.3)
                    if mode=='load-fail':route.fulfill(status=503,content_type='application/json',body=json.dumps({'detail':'模拟加载失败'}));return
                    data=[]
                elif path.rstrip('/')=='/api/project-files' and route.request.method=='POST':
                    body=route.request.post_data_json;writes.append(body);data={**body,'id':'saved-file'}
                else:data=[]
                route.fulfill(content_type='application/json',body=json.dumps(data))
            page.route(BASE+'/api/**',api)
            page.route(BASE+'/path-save-qa*',lambda route:route.fulfill(content_type='text/html',body=html))
            page.goto(BASE+'/path-save-qa?mode='+mode)
            page.get_by_role('button',name='模拟新增项目后保存路径',exact=True).click()
            if mode=='slow':
                expect(page.locator('#result')).to_have_text('保存成功')
                assert len(writes)==1 and writes[0]['storage_path']==r'D:\原文目录' and writes[0]['dispatch_path']==r'D:\派稿目录' and writes[0]['file_format']=='DOCX',writes
            elif mode=='load-fail':
                expect(page.locator('#result')).to_have_text('项目文件加载失败，请在“项目文件”中重新加载后保存')
                assert not writes
            else:
                expect(page.locator('#result')).to_have_text('请在“项目文件”中填写原文路径')
                assert not writes
            assert not errors,errors
            page.close()
        browser.close()
    print('PASS: slow path load awaited / all entered paths preserved across new-project remount / load failure distinct / missing source path distinct')
if __name__=='__main__':run()
