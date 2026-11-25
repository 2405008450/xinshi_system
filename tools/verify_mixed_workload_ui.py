"""多种工作量同时填写：真实表单、小窗、子订单表格；不访问业务库。"""
import json,re
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
base='http://127.0.0.1:3000'
compiled=urlopen(base+'/src/views/project/ProjectWorkspace.vue',timeout=10).read().decode()
vue=re.search(r'from ["\x27]([^"\x27]*/vue\.js[^"\x27]*)',compiled).group(1)
html=f'''<meta charset="utf-8"><div id="app"></div><script type="module">
import {{createApp,h,ref,reactive}} from {json.dumps(vue)};
import Form from '/src/components/common/WordCountMatrixForm.vue';
import Popover from '/src/components/common/WordCountMatrixPopover.vue';
import Grid from '/src/views/project/translation/components/SubOrderStatisticsGrid.vue';
const matrix=ref({{company:{{words:100,documents:2,pages:3,minutes:90}}}});
const rows=reactive([{{id:'child',subOrderNo:'TP-261124-001.001',subProjectName:'样例.pdf',wordCountMatrix:{{company:{{words:100,documents:2,pages:3,minutes:90}}}}}}]);
window.state={{matrix,rows}};
createApp({{render:()=>h('main',[
h(Form,{{modelValue:matrix.value,'onUpdate:modelValue':v=>matrix.value=v}}),
h(Popover,{{local:true,modelValue:matrix.value,'onUpdate:modelValue':v=>matrix.value=v}}),
h(Grid,{{local:true,editable:true,rows}})
])}}).mount('#app');
</script>'''
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge')
 page=browser.new_page(viewport={'width':1450,'height':1100})
 page.set_default_timeout(7000);errors=[];requests=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.route(base+'/api/**',lambda r:(requests.append(r.request.url),r.fulfill(json={})))
 page.route(base+'/mixed-workload-check',lambda r:r.fulfill(content_type='text/html',body=html))
 page.goto(base+'/mixed-workload-check')
 form=page.locator('.word-count-inline')
 for label,value in [('我司统计 字数','120'),('我司统计 份数','4'),('我司统计 页数','8'),('我司统计 分钟','60')]:
  cell=form.locator('input[aria-label="'+label+'"]')
  expect(cell).to_be_enabled();cell.fill(value);cell.press('Tab')
 for key,value in [('words',120),('documents',4),('pages',8),('minutes',60)]:
  assert page.evaluate('(key)=>state.matrix.value.company[key]',key)==value
 expect(form.locator('input[aria-label="我司统计 小时"]')).to_be_disabled()
 page.get_by_role('button',name='工作量统计',exact=True).click()
 popup=page.locator('.word-count-matrix:visible')
 expect(popup).to_be_visible()
 for label,value in [('我司统计-字数','130'),('我司统计-份数','5'),('我司统计-页数','9')]:
  cell=popup.locator('input[aria-label="'+label+'"]')
  expect(cell).to_be_enabled();cell.fill(value);cell.press('Tab')
 popup.get_by_role('combobox',name='我司统计-时长单位').select_option('hours')
 expect(popup.locator('input[aria-label="我司统计-时长"]')).to_have_value(re.compile(r'^1(?:\.0+)?$'))
 popup.get_by_role('button',name='保存',exact=True).click()
 expect(popup).not_to_be_visible()
 assert page.evaluate('state.matrix.value.company.words')==130
 assert page.evaluate('state.matrix.value.company.documents')==5
 assert page.evaluate('state.matrix.value.company.pages')==9
 assert page.evaluate('state.matrix.value.company.hours')==1
 grid=page.locator('.suborder-statistics-grid')
 control=grid.get_by_role('combobox',name='我司统计统计口径')
 for metric,value in [('documents','6'),('pages','10'),('words','150')]:
  control.select_option(metric)
  field=grid.locator('input[data-row="0"][data-col="0"]')
  expect(field).to_be_enabled();field.fill(value)
 grid.get_by_role('button',name=re.compile('暂存工作量')).click()
 assert page.evaluate('state.rows[0].wordCountMatrix.company.words')==150
 assert page.evaluate('state.rows[0].wordCountMatrix.company.documents')==6
 assert page.evaluate('state.rows[0].wordCountMatrix.company.pages')==10
 assert page.evaluate('state.rows[0].wordCountMatrix.company.minutes')==90
 assert not errors,errors
 assert not requests,requests
 browser.close()
print('PASS form/popover/grid mixed quantities and save, duration unit switch, no business requests')
