"""真实统计表实时逐级累计，输入/清空/粘贴/口径切换；业务接口全部模拟。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000'
compiled=urlopen(BASE+'/src/views/project/ProjectWorkspace.vue',timeout=30).read().decode();vue=re.search(r'from [\"\']([^\"\']*/vue\.js[^\"\']*)',compiled).group(1)
html='''<meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,reactive} from VUE;import Grid from '/src/views/project/translation/components/SubOrderStatisticsGrid.vue';
const base='TP-261109-999';const rows=reactive([
{id:'parent',subOrderNo:base+'.001',subProjectName:'一级目录',wordCountMatrix:{company:{words:9999}}},
{id:'file-a',subOrderNo:base+'.001.001',subProjectName:'a.pdf',wordCountMatrix:{company:{words:10}}},
{id:'nested',subOrderNo:base+'.001.002',subProjectName:'二级目录',wordCountMatrix:{company:{words:9999}}},
{id:'file-b',subOrderNo:base+'.001.002.001',subProjectName:'b.pdf',wordCountMatrix:{company:{words:20}}},
{id:'file-c',subOrderNo:base+'.001.002.002',subProjectName:'c.pdf',wordCountMatrix:{company:{words:30}}},
{id:'outside',subOrderNo:base+'.002',subProjectName:'独立.pdf',wordCountMatrix:{company:{words:500}}}]);
window.sourceRows=rows;window.originalRows=JSON.stringify(rows);createApp({render:()=>h(Grid,{rows,editable:true,local:location.search==='?local=1'})}).mount('#app');</script>'''.replace('from VUE','from '+json.dumps(vue))
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1550,'height':950});requests=[];errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 def api(route):
  requests.append((route.request.url,route.request.post_data_json));route.fulfill(content_type='application/json',body='{}')
 page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(re.compile(r'^http://localhost:3000/live-statistics-test'),lambda r:r.fulfill(content_type='text/html',body=html))
 for local in (False,True):
  requests.clear();page.goto(BASE+'/live-statistics-test'+('?local=1' if local else ''))
  cell=lambda row,col:page.locator(f'input[data-row="{row}"][data-col="{col}"]')
  expect(cell(0,0)).to_have_value('60');expect(cell(2,0)).to_have_value('50');expect(cell(0,0)).to_have_attribute('readonly','')
  cell(1,0).fill('89');expect(cell(0,0)).to_have_value('139');expect(cell(2,0)).to_have_value('50')
  cell(3,0).fill('100');expect(cell(2,0)).to_have_value('130');expect(cell(0,0)).to_have_value('219')
  cell(1,1).fill('70');cell(3,1).fill('80');expect(cell(0,1)).to_have_value('150');expect(cell(2,1)).to_have_value('80')
  cell(4,0).fill('');expect(cell(2,0)).to_have_value('100');expect(cell(0,0)).to_have_value('189')
  cell(3,0).fill('0');expect(cell(2,0)).to_have_value('0');expect(cell(0,0)).to_have_value('89')
  cell(3,0).evaluate("el=>{const clipboardData=new DataTransfer();clipboardData.setData('text/plain','5\\t6\\t7\\t8\\n10\\t20\\t30\\t40');el.dispatchEvent(new ClipboardEvent('paste',{clipboardData,bubbles:true,cancelable:true}))}")
  expect(cell(2,0)).to_have_value('15');expect(cell(2,1)).to_have_value('26');expect(cell(2,2)).to_have_value('37');expect(cell(2,3)).to_have_value('48')
  page.get_by_role('combobox',name='我司统计统计口径',exact=True).select_option('characters_no_spaces');cell(1,0).fill('200');expect(cell(0,0)).to_have_value('200')
  page.get_by_role('combobox',name='我司统计统计口径',exact=True).select_option('words');expect(cell(0,0)).to_have_value('15');expect(cell(5,0)).to_have_value('500')
  assert not requests,requests
  assert page.evaluate('JSON.stringify(sourceRows)===originalRows')
  page.get_by_role('button',name=re.compile('暂存统计' if local else '保存统计')).click();page.wait_for_timeout(500)
  if local:assert not requests
  else:
   assert len(requests)==3,requests
   assert all('/parent' not in url and '/nested' not in url for url,_ in requests)
 assert not errors,errors
 browser.close()
print('local and saved grids: live four-dimension multi-level totals; no double counting; blank/zero/paste/unit changes; no writes before Save; leaf-only persistence PASS')
