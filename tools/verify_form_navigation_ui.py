"""公共表单导航组件浏览器回归；只在本机隔离源码目录运行。"""
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1] / 'frontend'
(root / 'qa-navigation.html').write_text('<div id="app"></div><script type="module" src="/qa-navigation.js"></script>', encoding='utf-8')
(root / 'qa-navigation.js').write_text("import {createApp} from 'vue'; import ElementPlus from 'element-plus'; import 'element-plus/dist/index.css'; import Page from './qa-navigation.vue'; createApp(Page).use(ElementPlus).mount('#app');", encoding='utf-8')
(root / 'qa-navigation.vue').write_text('''<script setup>
import {ref,reactive,nextTick} from 'vue'
import AppForm from './src/components/common/AppForm.vue'
import DraggableFormDialog from './src/components/common/DraggableFormDialog.vue'
const visible=ref(true),formRef=ref(),tab=ref('base'),expanded=ref([])
const form=reactive({items:[{unitPrice:1},{unitPrice:null}]})
async function reset(){formRef.value.clearValidate();tab.value='base';expanded.value=[];await nextTick()}
async function server(){await reset();await formRef.value.applyServerErrors({rawDetail:{message:'第2行单价有误',fieldErrors:[{path:['items',1,'unit_price'],message:'请修改第2行单价'}]}})}
async function unknown(){await reset();await formRef.value.applyServerErrors({detail:'服务暂时异常，请稍后重试'})}
</script>
<template><DraggableFormDialog v-model="visible" title="公共表单回归" class="qa-form-dialog" top="5vh" width="min(760px,calc(100vw - 32px))">
<AppForm ref="formRef" :model="form" label-width="100px">
<el-tabs v-model="tab"><el-tab-pane label="基本" name="base">基本信息</el-tab-pane>
<el-tab-pane label="明细" name="details"><el-collapse v-model="expanded"><el-collapse-item title="价格明细" name="prices">
<div style="height:650px">长内容</div>
<el-form-item v-for="(row,index) in form.items" :key="index" :label="`第${index+1}行单价`" :prop="['items',String(index),'unitPrice']" :rules="[{required:true,type:'number',message:'请填写单价'}]"><el-input-number v-model="row.unitPrice" /></el-form-item>
</el-collapse-item></el-collapse></el-tab-pane></el-tabs></AppForm>
<template #footer><el-button @click="formRef.validate().catch(()=>false)">校验</el-button><el-button @click="server">接口错误</el-button><el-button @click="unknown">未知错误</el-button></template>
</DraggableFormDialog></template>
<style>.qa-form-dialog{display:flex;flex-direction:column;max-height:90vh;overflow:hidden}.qa-form-dialog .el-dialog__header,.qa-form-dialog .el-dialog__footer{flex-shrink:0}.qa-form-dialog .el-dialog__body{flex:1;min-height:0;overflow-y:auto}</style>''', encoding='utf-8')
log = (root / 'qa-navigation.log').open('wb')
proc = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '12221', '--strictPort'],
                        cwd=root, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
try:
    for _ in range(40):
        try:
            urlopen('http://127.0.0.1:12221/qa-navigation.html', timeout=1)
            break
        except OSError:
            time.sleep(1)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 540, 'height': 720})
        page.goto('http://127.0.0.1:12221/qa-navigation.html')
        dialog = page.locator('.qa-form-dialog')
        dialog.wait_for()
        before = dialog.bounding_box()
        for button in ['校验', '接口错误']:
            dialog.get_by_role('button', name=button, exact=True).click()
            page.wait_for_timeout(800)
            assert page.get_by_role('tab', name='明细', exact=True).get_attribute('aria-selected') == 'true'
            assert 'is-active' in dialog.locator('.el-collapse-item').get_attribute('class')
            errors = dialog.locator('.el-form-item.is-error')
            assert errors.count() == 1
            assert '第2行单价' in errors.inner_text()
            assert errors.locator('input').evaluate('(el)=>el===document.activeElement')
            footer = dialog.locator('.el-dialog__footer').bounding_box()
            assert footer['y'] + footer['height'] <= 720
            assert abs(dialog.bounding_box()['y'] - before['y']) < 2
        dialog.get_by_role('button', name='未知错误', exact=True).click()
        page.wait_for_timeout(300)
        assert page.get_by_role('tab', name='基本', exact=True).get_attribute('aria-selected') == 'true'
        assert dialog.locator('.el-form-item.is-error').count() == 0
        assert dialog.locator('.app-form-server-error').is_visible()
        page.screenshot(path=str(root.parent / 'form-regression-results/form-navigation-small.png'))
        browser.close()
        print('NAVIGATION PASS: hidden tab/collapse/indexed row/focus/fixed footer/unknown error')
finally:
    subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
    log.close()
