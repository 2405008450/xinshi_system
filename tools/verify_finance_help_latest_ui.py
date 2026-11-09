"""财务帮助更新验收：章节、搜索、图片预览、固定操作栏；不访问业务接口。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode();vue=re.search(r'from [\"\']([^\"\']*/vue\.js[^\"\']*)',compiled).group(1)
html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h,ref} from VUE;import Help from '/src/components/common/FinanceWorkflowHelp.vue';const visible=ref(true);createApp({render:()=>h(Help,{modelValue:visible.value,'onUpdate:modelValue':value=>visible.value=value})}).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000});requests=[];errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
 page.route(re.compile(r'^http://localhost:3000/api/'),lambda r:(requests.append(r.request.url),r.fulfill(content_type='application/json',body='[]')))
 page.route(BASE+'/finance-help-latest',lambda r:r.fulfill(content_type='text/html',body=html));page.goto(BASE+'/finance-help-latest')
 dialog=page.locator('.finance-workflow-help:visible');expect(dialog).to_be_visible();expect(dialog).to_contain_text('2026-11-09')
 search=dialog.get_by_placeholder('搜索流程、入口或问题，例如：字数 单价');search.fill('单均 完整');expect(dialog.locator('#finance-help-business-statistics')).to_be_visible()
 dialog.get_by_role('link',name='数据统计：订单数量、新老客户与单均金额',exact=True).click();image=dialog.locator('#finance-help-business-statistics .el-image');image.scroll_into_view_if_needed();image.click();expect(page.locator('.el-image-viewer__wrapper')).to_be_visible();page.locator('.el-image-viewer__close').click()
 search.fill('自动@');expect(dialog.locator('#finance-help-project-notifications')).to_be_visible();expect(dialog).to_contain_text('通知已生成不等于接收人已阅读')
 search.fill('历史 方向');expect(dialog.locator('#finance-help-recent')).to_be_visible()
 search.fill('');expect(dialog.locator('#finance-help-quantity')).to_be_visible()
 page.set_viewport_size({'width':620,'height':780});expect(dialog.locator('.el-dialog__footer')).to_be_visible();assert dialog.bounding_box()['width']<=620
 assert not requests and not errors,(requests,errors)
 browser.close()
print('finance help: updated date / statistics and historical directions / real mention explanation / AND search / screenshot zoom / mobile footer / no business API requests PASS')
