"""通用本机草稿与真实性能验证；业务请求全部拦截，不连接业务数据库。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/components/common/AppForm.vue').read().decode()
vue=re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)',compiled).group(1)
center=urlopen(BASE+'/src/components/common/AutoDraftCenter.vue').read().decode()
drafts=re.search(r'from ["\']([^"\']*autoDrafts\.js[^"\']*)',center).group(1)
html='''<!doctype html><meta charset="utf-8"><title>草稿验证</title><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive,ref} from VUE;
import AppForm from '/src/components/common/AppForm.vue';import Input from '/src/components/common/ScreenshotInput.vue';import Center from '/src/components/common/AutoDraftCenter.vue';
import {installAutoDrafts,autoDraftState,refreshAutoDrafts,restoreAutoDraft} from '/src/utils/autoDrafts.js';import {createAutoDraftStore} from '/src/utils/autoDraftStore.js';import api from '/src/api/index.js';
localStorage.setItem('user_id','isolated-auto-draft-user');window.__draftState=autoDraftState;window.__refresh=refreshAutoDrafts;window.__restore=restoreAutoDraft;window.__makeStore=createAutoDraftStore;
const app=createApp({setup(){const first=reactive({id:'record-a',name:'',password:'do-not-persist'}),second=reactive({id:'record-b',name:''}),standalone=ref(''),hidden=ref(false);return()=>h('div',[h(Center,{showEntry:false}),h(AppForm,{model:first},()=>[h(Input,{modelValue:first.name,'onUpdate:modelValue':v=>first.name=v,'aria-label':'表单姓名'}),h('button',{type:'button',onClick:()=>api.post('/auto-draft-test-save',first)},'保存')]),h('div',{class:'el-dialog',style:{display:hidden.value?'none':'block'}},[h(AppForm,{model:second},()=>h(Input,{modelValue:second.name,'onUpdate:modelValue':v=>second.name=v,'aria-label':'其他记录'})),h('button',{type:'button',onClick:()=>{second.name='';hidden.value=true}},'取消编辑B')]),h(Input,{type:'textarea',modelValue:standalone.value,'onUpdate:modelValue':v=>standalone.value=v,'aria-label':'独立编辑框'}),h('input',{'aria-label':'原生编辑框'}),h('input',{type:'password','aria-label':'密码'})])}});
installAutoDrafts(app);app.mount('#app');</script>'''.replace('VUE',json.dumps(vue)).replace("'/src/utils/autoDrafts.js'",json.dumps(drafts))
with sync_playwright() as pw:
 browser=pw.chromium.launch(channel='msedge',headless=True)
 context=browser.new_context();context.route(BASE+'/auto-draft-ui-check',lambda route:route.fulfill(content_type='text/html',body=html))
 calls=[];errors=[]
 def api(route):calls.append(route.request.method);route.fulfill(content_type='application/json',body='{"ok":true}')
 context.route(re.compile(r'^http://localhost:3000/api/'),api)
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/auto-draft-ui-check')
 page.get_by_role('textbox',name='表单姓名',exact=True).fill('未提交姓名')
 page.get_by_role('textbox',name='独立编辑框',exact=True).fill('未提交长文本')
 page.get_by_role('textbox',name='原生编辑框',exact=True).fill('原生输入草稿')
 page.get_by_label('密码',exact=True).fill('do-not-store-password')
 page.wait_for_function('window.__draftState.records.length>=3')
 assert not calls,calls
 raw=page.evaluate("localStorage.getItem('xinshi.autoDraft.v1:isolated-auto-draft-user')")
 assert 'do-not-persist' not in raw and 'do-not-store-password' not in raw
 records=json.loads(raw);assert len(records)==3,records
 assert next(row for row in records.values() if row['record']=='record-a')['data']['name']=='未提交姓名'
 assert not any(row['record']=='record-b' for row in records.values())
 page.reload();expect(page.get_by_role('textbox',name='表单姓名',exact=True)).to_have_value('')
 expect(page.get_by_role('button',name='草稿',exact=True)).to_have_count(0)
 page.get_by_role('textbox',name='表单姓名',exact=True).click()
 expect(page.get_by_role('dialog')).to_be_visible()
 page.get_by_role('button',name='恢复',exact=True).click()
 record=page.evaluate("window.__draftState.records.find(row=>row.record==='record-a').id")
 expect(page.get_by_role('dialog')).not_to_be_visible()
 expect(page.get_by_role('textbox',name='表单姓名',exact=True)).to_have_value('未提交姓名')
 expect(page.get_by_role('textbox',name='其他记录',exact=True)).to_have_value('')
 page.get_by_role('button',name='保存',exact=True).click();page.wait_for_function("!window.__draftState.records.some(row=>row.record==='record-a')")
 assert calls==['POST'],calls
 page.get_by_role('textbox',name='其他记录',exact=True).fill('关闭前尚未保存')
 page.get_by_role('button',name='取消编辑B',exact=True).click()
 assert page.evaluate("window.__draftState.records.find(row=>row.record==='record-b')?.data.name")=='关闭前尚未保存'
 page.wait_for_timeout(500)
 assert page.evaluate("JSON.parse(localStorage.getItem('xinshi.autoDraft.v1:isolated-auto-draft-user'))[window.__draftState.records.find(row=>row.record==='record-b').id].data.name")=='关闭前尚未保存'
 page.evaluate("localStorage.setItem('user_id','other-user');window.__refresh()")
 assert page.evaluate('window.__draftState.records.length')==0
 performance=page.evaluate('''()=>{const store=window.__makeStore({storage:localStorage,owner:'benchmark'}),data=Object.fromEntries(Array.from({length:500},(_,i)=>['field'+i,'草稿文本'.repeat(15)])),times=[];for(let i=0;i<40;i++){data.field0='编辑'+i;const start=performance.now();store.save({id:'large-form',data});times.push(performance.now()-start)}localStorage.removeItem('xinshi.autoDraft.v1:benchmark');times.sort((a,b)=>a-b);return {fields:500,characters:JSON.stringify(data).length,median_ms:times[20],p95_ms:times[38],max_ms:times[39]}}''')
 assert not errors,errors
 print(json.dumps({'drafts_without_business_submit':True,'native_and_vue_inputs':True,'refresh_restore':True,'close_before_debounce_keeps_draft':True,'record_and_user_isolation':True,'submitted_draft_cleared':True,'passwords_excluded':True,'performance':performance,'page_errors':errors}))
 browser.close()
