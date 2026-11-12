"""挂载实际字数矩阵组件，隔离所有 API，不写业务数据库。"""
import json,re,tempfile
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue',timeout=30).read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
html="""<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive} from VUE;import Matrix from '/src/components/common/WordCountMatrixPopover.vue';
const s=window.testState=reactive({matrix:{company:{words:200},customer:{words:120}}});createApp({render:()=>h(Matrix,{local:true,modelValue:s.matrix,'onUpdate:modelValue':v=>s.matrix=v})}).mount('#app');</script>""".replace('from VUE','from '+json.dumps(vue))
requests=[]
def api(route):
    path=urlparse(route.request.url).path;requests.append((path,route.request.method))
    if path=='/api/document-word-count/discover':data={'files':[{'relative_path':'样本.docx','size':100}]}
    elif path in ['/api/document-word-count/upload','/api/document-word-count/paths']:data={'job_id':'test-job'}
    elif path=='/api/document-word-count/jobs/test-job':data={'status':'completed','completed':1,'total':1,'counted_files':1,'failed_files':0,'words':8,'characters_no_spaces':20,'files':[{'name':'样本.docx','words':8,'status':'counted'}]}
    elif path=='/api/editor-drafts':data={'payload':None,'revision':0}
    else:data=[]
    route.fulfill(content_type='application/json',body=json.dumps(data,ensure_ascii=False))
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge');context=browser.new_context(viewport={'width':1500,'height':1000})
    context.add_init_script("localStorage.setItem('user_id','word-count-qa');localStorage.setItem('token','qa')")
    context.route(re.compile(r'^http://localhost:3000/api/'),api)
    context.route(BASE+'/document-count-test',lambda route:route.fulfill(content_type='text/html',body=html))
    page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE+'/document-count-test');page.get_by_role('button',name='字数统计',exact=True).click()
    page.get_by_text('选择文件／UNC 共享路径自动统计',exact=True).click()
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'sample.txt';path.write_text('sample',encoding='utf-8')
        page.get_by_label('选择待统计文件').set_input_files(str(path))
        page.get_by_role('button',name='开始统计',exact=True).click()
        expect(page.get_by_text('成功 1 份',exact=False)).to_be_visible()
        page.get_by_role('button',name='回填统计结果',exact=True).click()
        expect(page.get_by_role('spinbutton',name='预统计-字数',exact=True)).to_have_value('8')
    page.get_by_text('UNC 共享路径',exact=True).click()
    page.get_by_role('textbox',name='统计共享路径').fill(r'\\Win-server\共享目录')
    page.get_by_role('button',name='读取文件列表',exact=True).click()
    page.locator('.document-counter .el-table__body .el-checkbox').first.click()
    page.get_by_role('button',name='开始统计',exact=True).click()
    expect(page.get_by_text('成功 1 份',exact=False)).to_be_visible()
    page.locator('.counter-apply .el-select').first.click()
    page.get_by_role('option',name='我司统计',exact=True).click()
    page.get_by_role('button',name='回填统计结果',exact=True).click()
    page.get_by_role('button',name='确认替换统计',exact=True).click()
    expect(page.get_by_role('spinbutton',name='我司统计-字数',exact=True)).to_have_value('8')
    output=Path('artifacts/document-word-count');output.mkdir(exist_ok=True,parents=True)
    page.screenshot(path=str(output/'ui.png'),full_page=True)
    page.get_by_role('button',name='保存',exact=True).click()
    assert page.evaluate('window.testState.matrix.preliminary.words')==8
    assert page.evaluate('window.testState.matrix.company.words')==8
    assert page.evaluate('window.testState.matrix.customer.words')==120
    assert not errors,errors
    assert all(method!='PATCH' for _,method in requests)
    output=Path('artifacts/document-word-count');output.mkdir(exist_ok=True,parents=True)
    (output/'ui.json').write_text(json.dumps({'passed':True,'requests':requests,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
print('PASS: upload, UNC selection, progress, preliminary fill and matrix save; business API mocked')
