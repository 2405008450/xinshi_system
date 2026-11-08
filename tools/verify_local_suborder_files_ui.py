"""本地文件批量建子订单；独立浏览器、模拟接口，不读写业务库。"""
import json
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import expect, sync_playwright

BASE='http://localhost:3000'

def run():
    compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode()
    vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
    html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import Batch from '/src/views/project/translation/components/SubOrderBatchCreateDialog.vue';import AppForm from '/src/components/common/AppForm.vue';
const visible=ref(false);const app=createApp({render:()=>h('div',{},[h('button',{onClick:()=>visible.value=true},'打开批量新增'),h(Batch,{modelValue:visible.value,'onUpdate:modelValue':value=>visible.value=value,project:{id:'00000000-0000-4000-8000-000000000001',projectName:'测试.pdf',networkFilePath:'existing-shared-folder'},existingNames:['已有.pdf']})])});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
    writes=[]
    def api(route):
        path=urlparse(route.request.url).path
        if path.endswith('/business-numbers/reserve'):
            data={'token':'00000000-0000-4000-8000-000000000099','number':'TP-261107-999.001'}
        elif path.endswith('/sub-orders/shared-folder/tree'):
            data={'storage_path':r'\\Test-server\Projects\客户','folder_entries':[{'relative_path':'客户','files':['网络一.docx','网络二.pdf','已有.pdf']}]}
        elif path.endswith('/sub-orders/shared-folder/inspect'):
            data={'storage_path':r'\\Test-server\Projects\客户','files':[{'name':name} for name in ['网络一.docx','网络二.pdf','已有.pdf']]}
        elif path.endswith('/sub-orders/folders/import'):
            writes.append(route.request.post_data_json);data={'created_count':2,'skipped_count':1,'created':[],'skipped':[]}
        elif path.endswith('/sub-orders/bulk'):
            writes.append(route.request.post_data_json);data={'created_count':2,'skipped_count':0,'created':[],'skipped':[]}
        elif '/business-numbers/' in path:data={'ok':True}
        else:data=[]
        route.fulfill(content_type='application/json',body=json.dumps(data))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1400,'height':1000})
        page.set_default_timeout(10000)
        page.add_init_script("localStorage.setItem('user_id','qa')")
        page.route(re.compile(r'^http://localhost:3000/api/'),api)
        page.route(BASE+'/local-suborder-test',lambda route:route.fulfill(content_type='text/html',body=html))
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/local-suborder-test');page.get_by_role('button',name='打开批量新增',exact=True).click()
        dialog=page.locator('.suborder-batch-create-dialog:visible')
        expect(dialog).to_be_visible()
        initial=dialog.bounding_box()
        header=dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+12,header['y']+5);page.mouse.down()
        page.mouse.move(header['x']+92,header['y']+45,steps=8);page.mouse.up()
        moved=dialog.bounding_box()
        assert abs(moved['x']-initial['x'])>20,(initial,moved)
        header=dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+12,header['y']+5);page.mouse.down()
        page.mouse.move(-1000,-1000,steps=8);page.mouse.up()
        bounded=dialog.bounding_box()
        assert bounded['x']>=-1 and bounded['y']>=-1,bounded
        dialog.get_by_role('button',name='关闭窗口',exact=True).click()
        expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='打开批量新增',exact=True).click()
        expect(dialog).to_be_visible()
        reset=dialog.bounding_box()
        assert abs(reset['x']-initial['x'])<2 and abs(reset['y']-initial['y'])<2,(initial,reset)
        dialog.get_by_role('tab',name='读取本地文件',exact=True).click()
        files=[{'name':name,'mimeType':'application/octet-stream','buffer':b'test'} for name in ['合同.docx','附件.pdf','已有.pdf','没有扩展名']]
        dialog.locator('input[type=file][aria-label="选择本地文件"]').set_input_files(files)
        expect(dialog).to_contain_text('已选 2 个')
        expect(dialog.get_by_role('checkbox',name='选择已有.pdf',exact=True)).to_be_disabled()
        expect(dialog.get_by_role('checkbox',name='选择没有扩展名',exact=True)).to_be_disabled()
        dialog.get_by_role('checkbox',name='选择合同.docx',exact=True).locator('xpath=ancestor::label[1]').click()
        expect(dialog.get_by_role('button',name='确认导入 1 条',exact=True)).to_be_enabled()
        dialog.get_by_role('button',name='清空选择',exact=True).click()
        expect(dialog.get_by_role('button',name='确认导入 0 条',exact=True)).to_be_disabled()
        dialog.get_by_role('button',name='全选可用文件',exact=True).click()
        dialog.get_by_role('button',name='确认导入 2 条',exact=True).click()
        expect(dialog).not_to_be_visible()
        assert len(writes)==1 and set(writes[0]['sub_project_names'])=={'合同.docx','附件.pdf'},writes
        assert 'file' not in writes[0] and not writes[0]['defaults']['network_file_path']
        page.get_by_role('button',name='打开批量新增',exact=True).click()
        dialog.get_by_role('tab',name='读取本地文件',exact=True).click()
        expect(dialog).to_contain_text('共 0 个文件')
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'本地文件夹'
            folder.mkdir()
            (folder/'第一层.docx').write_text('test',encoding='utf-8')
            (folder/'第二个.pdf').write_text('test',encoding='utf-8')
            nested=folder/'下层文件夹';nested.mkdir()
            (nested/'不读取.docx').write_text('nested',encoding='utf-8')
            dialog.locator('input[webkitdirectory]').set_input_files(str(folder))
            expect(dialog).to_contain_text('3 个文件')
            expect(dialog).to_contain_text('第一层.docx')
            expect(dialog).to_contain_text('不读取.docx')
            expect(dialog.get_by_role('button',name='按目录导入 4 单',exact=True)).to_be_disabled()
            dialog.get_by_placeholder('请粘贴所选根文件夹的完整路径，如 D:\\项目\\客户资料',exact=True).fill(str(folder))
            expect(dialog.get_by_role('button',name='按目录导入 4 单',exact=True)).to_be_enabled()
        dialog.get_by_role('tab',name='UNC共享路径',exact=True).click()
        dialog.get_by_role('checkbox',name='按文件夹层级导入（根目录作为母订单）',exact=True).locator('xpath=ancestor::label[1]').click()
        unc_input=dialog.get_by_role('tabpanel',name='UNC共享路径',exact=True).get_by_placeholder('请输入企业 UNC 共享文件夹路径',exact=True)
        unc_input.fill(r'\\Test-server\Projects\客户')
        dialog.get_by_role('button',name='读取共享文件夹',exact=True).click()
        expect(dialog).to_contain_text('已选 2 个')
        unc_input.fill(r'\\Test-server\Projects\另一目录')
        expect(dialog).to_contain_text('共 0 个文件')
        expect(dialog.get_by_role('button',name='确认导入 0 条',exact=True)).to_be_disabled()
        unc_input.fill(r'\\Test-server\Projects\客户')
        dialog.get_by_role('button',name='读取共享文件夹',exact=True).click()
        dialog.get_by_role('button',name='确认导入 2 条',exact=True).click()
        expect(dialog).not_to_be_visible()
        assert len(writes)==2 and writes[1]['source_folder_path']==r'\\Test-server\Projects\客户',writes
        assert set(writes[1]['sub_project_names'])=={'网络一.docx','网络二.pdf'}
        page.get_by_role('button',name='打开批量新增',exact=True).click()
        dialog.get_by_role('tab',name='读取本地文件',exact=True).click()
        page.evaluate("""()=>{const folder=(name,children)=>({name,kind:'directory',async *values(){yield*children}});window.showDirectoryPicker=async()=>folder('客户资料',[folder('空文件夹',[]),folder('含文件目录',[{kind:'file',name:'文档.docx'}])])}""")
        dialog.get_by_role('button',name='选择本地文件夹',exact=True).click()
        expect(dialog).to_contain_text('发现1个空文件夹')
        expect(dialog).to_contain_text('空文件夹（不生成订单）')
        dialog.get_by_placeholder('请粘贴所选根文件夹的完整路径，如 D:\\项目\\客户资料',exact=True).fill(r'D:\客户资料')
        dialog.get_by_role('button',name='按目录导入 2 单',exact=True).click()
        expect(dialog).not_to_be_visible()
        assert len(writes)==3 and writes[2]['empty_detection_complete'] is True,writes
        assert any(row['relative_path']=='客户资料/空文件夹' and row['files']==[] for row in writes[2]['entries'])
        assert not errors,errors
        browser.close()
    print('local files / preview / duplicate and extension checks / selection / submit / reopen reset / UNC preserved / path changes invalidate selection PASS')

if __name__=='__main__':run()
