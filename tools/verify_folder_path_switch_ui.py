"""UNC 切换本地路径及待保存子单方向：真实组件、全部 API 隔离模拟。"""
import json
import os
import re
from urllib.parse import urlparse
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv('UI_BASE_URL', 'http://localhost:9011')


def run():
    compiled = urlopen(BASE+'/src/views/project/ProjectWorkspace.vue', timeout=30).read().decode()
    def dep(name):
        return json.dumps(re.search(r'from ["\']([^"\']*/'+name+r'\.js[^"\']*)', compiled).group(1))
    html = '''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import {createRouter,createWebHistory} from ROUTER;
import Projects from '/src/views/project/translation/ProjectDetails.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const projects=ref();window.form=()=>projects.value.$.setupState.form;
const app=createApp({render:()=>h(Projects,{ref:projects})});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/folder-switch-test',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE', 'from '+dep('vue')).replace('from ROUTER', 'from '+dep('vue-router'))
    inspections = []
    single_inspections = []
    writes = []
    allow_local_stats_to_finish = False
    unc_root = r'\\allowed\share\客户资料'
    unc_entries = [
        {'relative_path': '客户资料', 'files': []},
        {'relative_path': '客户资料/A', 'files': ['same.txt']},
        {'relative_path': '客户资料/B', 'files': ['same.txt']},
        {'relative_path': '客户资料/空目录', 'files': []},
    ]
    def api(route):
        path = urlparse(route.request.url).path
        if path.endswith('/document-word-count/single-path'):
            source = route.request.post_data_json['path']
            single_inspections.append(source)
            if source.endswith('multiple'):
                route.fulfill(status=400,json={'detail':'目录有多个文件或包含子文件夹时，请到「新增母子订单」选项卡处理。'})
            else:
                route.fulfill(json={'name':'shared.txt','job_id':'single-qa'})
            return
        if path.endswith('/document-word-count/jobs/single-qa'):
            route.fulfill(json={'status':'completed','files':[
                {'name':'shared.txt','status':'counted','words':4,'characters_no_spaces':12,'cjk_chars_korean_words':2},
            ]})
            return
        if path.endswith('/document-word-count/discover'):
            route.fulfill(json={'files': [{'relative_path': f'{folder}/same.txt', 'size': 12} for folder in ['A', 'B']]})
            return
        if path.endswith('/document-word-count/paths'):
            request = route.request.post_data_json
            assert request['path'] == unc_root and request['relative_paths'] == ['A/same.txt', 'B/same.txt']
            route.fulfill(json={'job_id': 'qa'})
            return
        if path.endswith('/document-word-count/upload'):
            route.fulfill(json={'job_id': 'local-qa'})
            return
        if path.endswith('/document-word-count/jobs/local-qa'):
            if not allow_local_stats_to_finish:
                route.fulfill(json={'status':'running', 'completed':0, 'files':[]})
                return
            route.fulfill(json={'status':'completed', 'files':[
                {'name':'a.pdf','file_index':0,'status':'counted','words':30,
                 'characters_no_spaces':47,'cjk_chars_korean_words':0},
            ]})
            return
        if path.endswith('/document-word-count/jobs/qa'):
            route.fulfill(json={'status':'completed', 'files':[
                {'name':'B/same.txt','status':'counted','words':17,'characters_no_spaces':27,'cjk_chars_korean_words':3},
                {'name':'A/same.txt','status':'counted','words':11,'characters_no_spaces':19,'cjk_chars_korean_words':7},
            ]})
            return
        if '/shared-folder/' in path:
            inspections.append(path)
            if 'allowed' in route.request.url:
                route.fulfill(json={'storage_path': unc_root, 'folder_entries': unc_entries})
            else:
                route.fulfill(status=400, content_type='application/json', body=json.dumps({'detail':'测试 UNC 不可达'}))
            return
        if route.request.method in ('POST','PUT','PATCH','DELETE'):
            writes.append(path)
        if '/business-numbers/reserve' in path:
            data={'token':'00000000-0000-4000-8000-000000000099','number':'TP-261110-999'}
        elif path.endswith('/editor-drafts'):
            data={'payload':None,'revision':0}
        elif path=='/api/projects/languages':
            data=[{'id':str(i),'label':label} for i,label in enumerate(['中文','英语','法语'])]
        elif path.endswith('/page'):
            data={'items':[],'total':0}
        else:
            data=[]
        route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge')
        page=browser.new_page(viewport={'width':1500,'height':1000})
        errors=[]
        page.on('pageerror',lambda err:(errors.append(str(err)),print('PAGE ERROR:',str(err),flush=True)))
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\",\"project_files:read\",\"project_files:write\"]')")
        page.route(re.compile('^'+re.escape(BASE)+r'/api/'),api)
        page.route(BASE+'/folder-switch-test',lambda route:route.fulfill(content_type='text/html',body=html))
        page.goto(BASE+'/folder-switch-test')
        page.get_by_role('button',name='新增项目',exact=True).click()
        dialog=page.locator('.project-editor-dialog:visible')
        expect(dialog).to_be_visible()
        path_input=dialog.locator('[data-field-key=originalStoragePath] input:visible')
        name_input=dialog.locator('[data-field-key=sourceFileName] input:visible')
        extract=dialog.get_by_role('button',name='提取文件名与工作量',exact=True)
        path_input.fill(r'\\allowed\share\single')
        name_input.focus()
        expect(name_input).to_have_value('')
        assert not single_inspections
        extract.click()
        expect(name_input).to_have_value('shared.txt')
        expect(dialog.locator('.single-source-counts')).to_contain_text('中朝统计 2')
        path_input.fill(r'\\allowed\share\multiple')
        extract.click()
        expect(dialog.locator('.single-source-extraction')).to_contain_text('「新增母子订单」选项卡处理')
        expect(name_input).to_have_value('shared.txt')
        path_input.fill(r'D:\本机\资料')
        extract.click()
        local_folder=dialog.get_by_role('button',name='选择本地文件夹',exact=True)
        page.evaluate("window.showDirectoryPicker=async()=>({name:'资料',kind:'directory',async *values(){yield {name:'empty',kind:'directory'}}})")
        local_folder.click()
        expect(dialog.locator('.single-source-extraction')).to_contain_text('目录有多个文件或包含子文件夹')
        page.evaluate("window.showDirectoryPicker=async()=>({name:'资料',kind:'directory',async *values(){yield {name:'a.pdf',kind:'file',getFile:async()=>new File(['hello'],'a.pdf')}}})")
        allow_local_stats_to_finish = True
        local_folder.click()
        expect(name_input).to_have_value('a.pdf')
        expect(dialog.locator('.single-source-counts')).to_contain_text('字符数（不计空格） 47')
        assert page.evaluate('form().wordCountMatrix.company.words') == 30
        allow_local_stats_to_finish = False
        dialog.get_by_role('tab',name='新增母子订单',exact=True).click()
        expect(name_input).to_have_attribute('readonly', '')
        expect(name_input).to_have_value('')
        expect(dialog.locator('[data-field-key=sourceFileName]:visible')).to_contain_text('请点击右上角的「读取路径」')
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(page.get_by_text('请先点击右上角的「读取路径」，并将读取结果应用到新增表单',exact=True)).to_be_visible()
        page.evaluate(r"Object.assign(window.form(),{originalStoragePath:'\\\\old-server\\share\\客户资料',networkFilePath:'\\\\old-server\\share\\客户资料',filePathDraft:{storage_path:'\\\\old-server\\share\\客户资料'},languagePair:'中文→英语',serviceContent:'翻译'})")
        dialog.get_by_role('button',name='读取路径',exact=True).click()
        batch=page.locator('.suborder-batch-create-dialog:visible')
        batch.get_by_role('tab',name='UNC',exact=True).click()
        expect(batch.get_by_placeholder('请输入企业 UNC 共享文件夹路径',exact=True)).to_have_value(r'\\old-server\share\客户资料')
        batch.get_by_role('button',name='读取共享文件夹',exact=True).click()
        expect(batch).to_contain_text('测试 UNC 不可达')
        batch.get_by_role('tab',name='本地',exact=True).click()
        page.evaluate("window.showDirectoryPicker=async()=>({name:'客户资料',kind:'directory',async *values(){yield {name:'a.pdf',kind:'file',getFile:async()=>new File(['hello'],'a.pdf')};yield {name:'image.png',kind:'file'}}})")
        batch.get_by_role('button',name='选择本地文件夹',exact=True).click()
        root=batch.get_by_placeholder('请粘贴所选根文件夹的完整路径，如 D:\\项目\\客户资料',exact=True)
        expect(root).to_have_value('')
        counts=batch.locator('.pending-file-counts:visible')
        expect(counts).to_contain_text('已处理 1 / 2 个文件')
        allow_local_stats_to_finish = True
        expect(counts).to_contain_text('成功 1 个，无法统计 1 个')
        local_result = counts.get_by_role('row').filter(has_text='a.pdf')
        for value in ['30', '47', '0']:
            expect(local_result.get_by_role('cell',name=value,exact=True)).to_be_visible()
        expect(counts.get_by_role('row').filter(has_text='image.png')).to_contain_text('该格式暂不支持自动统计')
        expect(batch).to_contain_text('已读取 1 个文件夹、2 个文件')
        root.fill(r'D:\本机\客户资料')
        batch.get_by_role('button',name='应用到新增表单',exact=True).click()
        expect(batch).not_to_be_visible()
        expect(name_input).to_have_value('客户资料')
        expect(name_input).to_have_attribute('readonly', '')
        assert page.evaluate("form().pendingSubOrderDetails['001'].wordCountMatrix.company") == {
            'words':30, 'characters_no_spaces':47, 'cjk_chars_korean_words':0,
        }
        for tab in ['项目文件','新增母子订单']:
            dialog.get_by_role('tab',name=tab,exact=True).click()
            page.wait_for_timeout(100)
            assert page.evaluate("[form().originalStoragePath,form().networkFilePath,form().filePathDraft.storage_path]")==[r'D:\本机\客户资料']*3
        dialog.get_by_role('button',name='打开子订单管理（填写工作量并汇总）',exact=True).click()
        child=page.locator('.pending-suborder-manager:visible')
        expect(child.get_by_role('button',name='从文件统计工作量',exact=True)).to_have_count(0)
        expect(child.get_by_role('textbox',name='TP-261110-999.001 我司统计',exact=True)).to_have_value('30')
        expect(child.get_by_role('textbox',name='TP-261110-999.002 我司统计',exact=True)).to_have_value('')
        direction=child.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text='翻译方向'))
        expect(direction).to_contain_text('中文→英语')
        direction.locator('.el-tag__close').click()
        direction.locator('input').first.fill('中文 法语')
        page.locator('.language-pair-option__label:visible').filter(has_text='中文→法语').click()
        child.locator('.pending-language-hint').click()
        expect(page.locator('.language-pair-option__label:visible')).to_have_count(0)
        child.get_by_role('button',name='返回母订单',exact=True).click()
        expect(child).not_to_be_visible()
        assert page.evaluate("form().pendingSubOrderDetails['001'].languagePair")=='中文→法语'
        dialog.get_by_role('button',name='打开子订单管理（填写工作量并汇总）',exact=True).click()
        expect(direction).to_contain_text('中文→法语')
        expect(child.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text='原文路径')).locator('input')).to_have_value(r'D:\本机\客户资料\a.pdf')
        page.set_viewport_size({'width':800,'height':700})
        expect(child.get_by_role('button',name='返回母订单',exact=True)).to_be_in_viewport()
        child.get_by_role('button',name='返回母订单',exact=True).click()
        page.set_viewport_size({'width':1500,'height':1000})
        dialog.get_by_role('button',name='读取路径',exact=True).click()
        batch.get_by_role('tab',name='UNC',exact=True).click()
        unc_input=batch.get_by_placeholder('请输入企业 UNC 共享文件夹路径',exact=True)
        unc_input.fill(f'"{unc_root}\\"')
        batch.get_by_role('button',name='读取共享文件夹',exact=True).click()
        expect(unc_input).to_have_value(unc_root)
        expect(batch).to_contain_text('发现1个空文件夹')
        expect(batch).to_contain_text('生成 4 个子订单')
        unc_input.fill(unc_root + r'\修改')
        expect(batch.get_by_role('button',name='应用到新增表单',exact=True)).to_have_count(0)
        expect(batch.get_by_role('button',name='确认导入 0 条',exact=True)).to_be_disabled()
        unc_input.fill(unc_root)
        batch.get_by_role('button',name='读取共享文件夹',exact=True).click()
        expect(counts).to_contain_text('成功 2 个，无法统计 0 个')
        for folder, values in [('A',['11','19','7']), ('B',['17','27','3'])]:
            result = counts.get_by_role('row').filter(has_text=f'{folder}/same.txt')
            for value in values:
                expect(result.get_by_role('cell',name=value,exact=True)).to_be_visible()
        batch.get_by_role('button',name='应用到新增表单',exact=True).click()
        expect(batch).not_to_be_visible()
        assert page.evaluate('form().originalStoragePath') == unc_root
        dialog.get_by_role('button',name='打开子订单管理（填写工作量并汇总）',exact=True).click()
        expect(child.get_by_role('button',name='从文件统计工作量',exact=True)).to_have_count(0)
        for suffix, value in [('001.001','11'), ('002.001','17')]:
            expect(child.get_by_role('textbox',name=f'TP-261110-999.{suffix} 我司统计',exact=True)).to_have_value(value)
        child.get_by_role('button',name='汇总至母订单并确认',exact=True).click()
        expect(child).not_to_be_visible()
        assert page.evaluate("""() => {
            const {words, characters_no_spaces, cjk_chars_korean_words} = form().wordCountMatrix.company;
            return [words, characters_no_spaces, cjk_chars_korean_words];
        }""") == [28, 46, 10]
        assert len(inspections)==3,inspections
        assert not [path for path in writes if '/business-numbers/' not in path and '/editor-drafts' not in path],writes
        assert not errors,errors
        browser.close()
    print('PASS: local and UNC folder preview, same-name file matching, per-order counts and rollup; all APIs mocked')


if __name__=='__main__':
    run()
