"""窗口未保存提示：四类项目草稿、逐项定位、部分保存和失败保护；全部业务API拦截。"""
import json
from pathlib import Path
import re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

BASE='http://localhost:3000'
FIXTURE=Path(__file__).resolve().parents[1]/'frontend/tmp/verify-window-unsaved.vue'
SOURCE='''<template>
<DraggableFormDialog v-model="visible" :title="kind+'项目'+(creating?'新增':'编辑')" width="760px" top="5vh" :close-on-click-modal="false">
  <AppForm ref="formRef" :model="form" label-position="top">
    <el-tabs v-model="tab"><el-tab-pane label="基础信息" name="basic"><el-form-item label="项目名称" prop="name"><el-input v-model="form.name" aria-label="项目名称" /></el-form-item></el-tab-pane>
    <el-tab-pane label="补充信息" name="extra"><el-form-item label="项目说明" prop="notes"><el-input v-model="form.notes" aria-label="项目说明" /></el-form-item><el-collapse v-model="expanded"><el-collapse-item title="更多信息" name="details"><el-form-item label="补充备注" prop="extra"><el-input v-model="form.extra" aria-label="补充备注" /></el-form-item></el-collapse-item></el-collapse></el-tab-pane></el-tabs>
  </AppForm>
  <template #footer><el-button @click="secondary=true">子窗口</el-button><el-button @click="visible=false">关闭</el-button><el-button @click="partial">仅保存名称</el-button><el-button @click="save">保存全部</el-button></template>
</DraggableFormDialog>
<DraggableFormDialog v-model="secondary" title="独立子窗口"><AppForm :model="child"><el-form-item label="子窗口内容" prop="note"><el-input v-model="child.note" aria-label="子窗口内容" /></el-form-item></AppForm></DraggableFormDialog>
<button @click="open(kind,creating)">重新打开</button><output>{{error}}</output>
</template>
<script setup>
import {reactive,ref,nextTick,onMounted} from 'vue'
import AppForm from '@/components/common/AppForm.vue'
import DraggableFormDialog from '@/components/common/DraggableFormDialog.vue'
import {useFormDraft} from '@/composables/useFormDraft'
import api from '@/api'
const visible=ref(false),creating=ref(false),kind=ref('translation'),tab=ref('basic'),expanded=ref([]),secondary=ref(false),error=ref(''),formRef=ref()
const defaults=()=>({id:'translation',name:'已保存名称',notes:'已保存说明',extra:'已保存备注'})
const form=reactive(defaults()),child=reactive({id:'child',note:''})
const {beginDraft,pauseDraft,clearDraft,startFreshDraft}=useFormDraft({namespace:'window-unsaved-test',form,createDefault:defaults,formRef})
async function open(type,isNew=false){pauseDraft();kind.value=type;creating.value=isNew;Object.assign(form,defaults(),{id:isNew?'':type});tab.value='basic';expanded.value=[];visible.value=true;await nextTick();await beginDraft(isNew?'create':'edit:'+type)}
async function partial(){try{await api.patch('/projects/'+kind.value+'/'+form.id,{name:form.name})}catch{error.value='保存失败'}}
async function save(){try{await api.put('/projects/'+kind.value+'/'+(form.id||'new'),{...form});clearDraft();startFreshDraft('edit:'+(form.id||'new'));error.value='保存成功'+kind.value}catch{error.value='保存失败'}}
window.fixture={open,form,child,visible,secondary,tab,expanded}
onMounted(()=>open('translation'))
</script>'''


def run():
    FIXTURE.parent.mkdir(exist_ok=True)
    FIXTURE.write_text(SOURCE,encoding='utf-8')
    try:
        compiled=urlopen(BASE+'/src/main.js').read().decode()
        vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
        html='''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp} from VUE;import Fixture from '/tmp/verify-window-unsaved.vue';createApp(Fixture).mount('#app')</script>'''.replace('VUE',json.dumps(vue))
        errors=[];fail=False;held=[];hold=False
        def api(route):
            nonlocal fail,hold
            path=route.request.url.split('/api')[-1].split('?')[0]
            data={}
            if path.startswith('/projects/'):
                if fail:return route.fulfill(status=500,content_type='application/json',body='{"detail":"隔离测试保存失败"}')
                if hold:held.append(route);return
                data=route.request.post_data_json
            elif path=='/editor-drafts':data={'payload':None,'revision':0}
            elif path=='/editor-drafts/batch':data=[{**row,'revision':1} for row in route.request.post_data_json['drafts']]
            route.fulfill(content_type='application/json',body=json.dumps(data))
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            context=browser.new_context(viewport={'width':1400,'height':900},service_workers='block')
            context.add_init_script("localStorage.setItem('user_id','window-unsaved-test')")
            context.route(re.compile(r'^http://localhost:3000/api/'),api)
            context.route(BASE+'/window-unsaved-test',lambda r:r.fulfill(content_type='text/html',body=html))
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/window-unsaved-test')
            dialog=page.locator('.el-dialog:visible').first
            indicator=dialog.locator('.window-unsaved-indicator')
            expect(dialog.get_by_label('项目名称')).to_be_visible();expect(indicator).to_have_count(0)
            for kind in ['translation','interpretation','annotation','recruitment']:
                page.evaluate('(kind)=>window.fixture.open(kind)',kind)
                dialog.get_by_label('项目名称').fill(kind+'新名称')
                expect(indicator).to_contain_text('部分未保存')
                page.evaluate("window.fixture.form.notes='未保存说明';window.fixture.form.extra='未保存备注'")
                expect(indicator).to_contain_text('3处')
                indicator.click();expect(dialog.get_by_label('项目名称')).to_be_focused()
                indicator.click();expect(dialog.get_by_label('项目说明')).to_be_focused()
                expect(dialog.get_by_role('tab',name='补充信息')).to_have_attribute('aria-selected','true')
                indicator.click();expect(dialog.get_by_label('补充备注')).to_be_focused()
                expect(dialog.locator('.el-collapse-item')).to_have_class(re.compile('is-active'))
                dialog.get_by_role('button',name='仅保存名称',exact=True).click();expect(indicator).to_contain_text('2处')
                fail=True;dialog.get_by_role('button',name='保存全部',exact=True).click();expect(page.locator('output')).to_contain_text('保存失败');expect(indicator).to_contain_text('2处');fail=False
                dialog.get_by_role('button',name='保存全部',exact=True).click();expect(page.locator('output')).to_contain_text('保存成功'+kind);expect(indicator).to_have_count(0)
            page.evaluate("window.fixture.open('translation',true)")
            dialog.get_by_label('项目名称').fill('新增未保存内容');expect(indicator).to_contain_text('全部未保存')
            dialog.get_by_role('button',name='关闭',exact=True).click();page.get_by_role('button',name='重新打开',exact=True).click()
            expect(dialog.get_by_label('项目名称')).to_have_value('新增未保存内容');expect(indicator).to_contain_text('全部未保存')
            page.evaluate("window.fixture.open('late')")
            dialog.get_by_label('项目名称').fill('请求中的名称');hold=True
            dialog.get_by_role('button',name='仅保存名称',exact=True).click()
            page.wait_for_function('true')
            dialog.get_by_label('项目名称').fill('请求后继续输入')
            assert len(held)==1
            held.pop().fulfill(content_type='application/json',body='{"name":"请求中的名称"}');hold=False
            expect(indicator).to_contain_text('部分未保存')
            dialog.get_by_label('项目名称').fill('请求中的名称');expect(indicator).to_have_count(0)
            dialog.get_by_role('button',name='子窗口',exact=True).click()
            child=page.get_by_role('dialog',name='独立子窗口',exact=True);child.get_by_label('子窗口内容').fill('子窗口未保存')
            expect(child.locator('.window-unsaved-indicator')).to_contain_text('部分未保存');expect(indicator).to_have_count(0)
            assert not errors,errors
            browser.close()
        print('PASS: 四类项目未保存标识、逐项定位、自动展开页签折叠区、部分保存、失败及迟到响应保护、草稿恢复和嵌套窗口隔离')
    finally:
        FIXTURE.unlink(missing_ok=True)


if __name__=='__main__':run()
