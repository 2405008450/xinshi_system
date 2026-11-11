"""简单需求字数真实表单与历史提示；全部业务接口模拟。"""
import json,re
from urllib.request import urlopen
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000';pid='00000000-0000-4000-8000-000000000099';uid='00000000-0000-4000-8000-000000000001'
compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode();vue=re.search(r'from [\"\']([^\"\']*/vue\.js[^\"\']*)',compiled).group(1)
html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,h} from VUE;import Notes from '/src/views/project/translation/components/ProjectShortNotes.vue';import AppForm from '/src/components/common/AppForm.vue';const app=createApp({render:()=>h(Notes,{projectId:PID,projectUpdatedAt:'2026-11-09T12:00:00+08:00',canWrite:true,onSaved:data=>window.savedResult=data})});app.component('AppForm',AppForm);app.mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue)).replace('projectId:PID','projectId:'+json.dumps(pid))
items=[];writes=[]
def api(route):
 path=urlparse(route.request.url).path
 if path.endswith('/recipients'):data={'items':[{'id':uid,'name':'卢少妃'}],'default_recipient_ids':[uid]}
 elif path==f'/api/translation-simple-requirements/projects/{pid}' and route.request.method=='POST':
  body=route.request.post_data_json;writes.append(body);row={'id':'req1','project_id':pid,'actor_name':'测试人员','created_at':'2026-11-09T12:01:00+08:00',**body,'recipients':[]};items.append(row)
  data={'item':row,'project_status':'confirmed','project_updated_at':'2026-11-09T12:01:00+08:00','word_count_added':True,'word_count_matrix':{'company':{'words':120},'customer':{'words':98}},'word_count_matrix_source':'project','word_count_sub_order_count':0,'simple_requirement_word_count_matrix':body['word_count_matrix']}
 elif path==f'/api/translation-simple-requirements/projects/{pid}':data={'items':items,'total':len(items),'project_status':'confirmed','project_updated_at':'2026-11-09T12:00:00+08:00'}
 else:data={'items':[],'total':0}
 route.fulfill(content_type='application/json',body=json.dumps(data))
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1250,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script("localStorage.setItem('user_id','qa')");page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(BASE+'/simple-count-test',lambda r:r.fulfill(content_type='text/html',body=html))
 page.goto(BASE+'/simple-count-test');page.get_by_role('button',name='简单需求',exact=True).click();dialog=page.locator('.simple-requirement-dialog:visible');expect(dialog).to_be_visible()
 dialog.get_by_role('button',name='统计字数',exact=True).click();expect(dialog.locator('.word-count-inline')).to_be_visible()
 dialog.locator('.word-count-inline input[aria-label="我司统计 字数"]').fill('20');dialog.locator('.word-count-inline input[aria-label="客户统计 字数"]').fill('18')
 assert not writes
 dialog.locator('textarea').nth(0).fill('测试简单需求');dialog.locator('textarea').nth(1).fill('Simple requirement test');dialog.get_by_text('不收费',exact=True).click()
 dialog.get_by_role('button',name='保存需求',exact=True).click()
 expect(dialog.locator('.requirement-added-counts')).to_contain_text('已加入简单需求字数');assert len(writes)==1
 assert writes[0]['word_count_matrix']['company']['words']==20 and writes[0]['word_count_matrix']['customer']['words']==18
 assert page.evaluate('savedResult.word_count_matrix.company.words')==120
 expect(page.get_by_text('简单需求已保存并发送通知，已将简单需求字数加入当前订单',exact=True)).to_be_visible()
 dialog.get_by_role('button',name='关闭',exact=True).click();page.get_by_role('button',name='简单需求',exact=True).click();expect(dialog.locator('.requirement-added-counts')).to_contain_text('20')
 assert not errors,errors;browser.close()
print('simple requirement statistics button/form / no write before Save / dimension payload / cumulative result / added-count notice / history reopen PASS')
