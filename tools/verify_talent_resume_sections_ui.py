"""用完整前端及拦截API验证新增、编辑、字段搜索和序列化；无业务库请求。"""
import functools,http.server,json,re,threading
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
import argparse
arguments=argparse.ArgumentParser();arguments.add_argument('--output',required=True);arguments=arguments.parse_args()
OUT=Path(arguments.output).resolve();OUT.mkdir(parents=True,exist_ok=True)
class Handler(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  if not Path(self.translate_path(self.path)).is_file() and not Path(self.path).suffix:self.path='/index.html'
  super().do_GET()
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(Path(__file__).resolve().parents[1]/'frontend'/'dist')));threading.Thread(target=server.serve_forever,daemon=True).start();port=server.server_port
records={};writes=[];errors=[]
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge',headless=True);ctx=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
 ctx.add_init_script("localStorage.setItem('token','ui-test-only')")
 def api(route):
  req=route.request;path=urlparse(req.url).path.removeprefix('/api').rstrip('/');result=[]
  if path=='/auth/session':result={'user_id':'ui-test','username':'UI测试','roles':['admin'],'permissions':['*']}
  elif path.startswith('/projects/languages'):result=[{'id':'00000000-0000-0000-0000-000000000001','code':'zh-CN','name_zh':'汉语','name_en':'Chinese','label':'汉语 / Chinese'}]
  elif path=='/talents/page':result={'items':list(records.values()),'total':len(records)}
  elif path=='/talents' and req.method=='POST':
   data=req.post_data_json;writes.append(data);ident='00000000-0000-0000-0000-000000000002';result={**data,'id':ident,'resource_code':'UI-TEST','attachments':[]};records[ident]=result
  elif path.startswith('/talents/'):
   ident=path.split('/')[2]
   if req.method=='PUT':records[ident].update(req.post_data_json);writes.append(req.post_data_json)
   result=records.get(ident,[])
  route.fulfill(status=200,content_type='application/json',body=json.dumps(result,ensure_ascii=False))
 ctx.route('**/api/**',api)
 page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
 try:
  page.goto(f'http://127.0.0.1:{port}/resource-management/talents');page.get_by_role('button',name='新增人才',exact=True).click()
  dialog=page.locator('.talent-editor-dialog:visible');initial=dialog.bounding_box()
  strip=dialog.locator('.app-window-drag-strip');handle=strip.bounding_box();page.mouse.move(handle['x']+50,handle['y']+15);page.mouse.down();page.mouse.move(handle['x']+130,handle['y']+55,steps=5);page.mouse.up();moved=dialog.bounding_box();assert abs(moved['x']-initial['x'])>30
  page.mouse.move(moved['x']+50,moved['y']+15);page.mouse.down();page.mouse.move(5000,5000,steps=5);page.mouse.up();bounded=dialog.bounding_box();assert bounded['x']>=0 and bounded['y']>=0 and bounded['x']+bounded['width']<=1441
  dialog.locator('.el-tab-pane:visible').get_by_role('button',name='全部展开',exact=True).first.click()
  def field(label):return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=re.compile('^'+re.escape(label)+'$')))
  field('中文姓名').locator('input').fill('通用规则测试')
  field('专业能力').locator('label.el-checkbox').filter(has_text='笔译').click()
  for label,text in [('自我评价','这是本人自述，不是公司评价'),('求职意向','历史期望地点'),('其他技能','Office'),('兴趣爱好','绘画'),('奖励和荣誉','奖学金')]:field(label).locator('textarea').fill(text)
  campus=dialog.locator('[data-section-key="editor-experience-campusPositions"]')
  campus.get_by_role('button',name='添加经历',exact=True).click();campus.locator('textarea').fill('学生会职务')
  education=dialog.locator('[data-section-key="editor-education-experience"]');education.get_by_role('button',name='添加经历',exact=True).click()
  field('学历').locator('.el-select').click();page.get_by_role('option',name='本科',exact=True).click()
  field('毕业年份').get_by_role('spinbutton').fill('2001');field('学校').locator('input').fill('测试学校')
  footer=dialog.locator('.el-dialog__footer');dialog.locator('.el-dialog__body').evaluate('(e)=>e.scrollTop=e.scrollHeight')
  box=footer.bounding_box();assert box['y']+box['height']<=1005
  page.screenshot(path=str(OUT/'新增人才_底部操作.png'))
  dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible()
  assert len(writes)==1,writes
  saved=writes[0];assert saved['resume_profile']['interests']=='绘画' and saved['resume_profile']['campus_positions'][0]['description']=='学生会职务'
  assert saved['education_experiences'][0]['graduation_year']==2001
  page.get_by_role('button',name='编辑',exact=True).first.click();dialog=page.locator('.talent-editor-dialog:visible');reopened=dialog.bounding_box();assert abs(reopened['x']-initial['x'])<5
  search=dialog.locator('.dialog-field-search-header__search input');search.fill('兴趣')
  option=page.locator('.project-field-search-popper:visible').get_by_text('兴趣爱好',exact=True);option.click()
  expect(field('兴趣爱好').locator('textarea')).to_be_visible();field('兴趣爱好').locator('textarea').fill('绘画、音乐')
  page.screenshot(path=str(OUT/'编辑人才_字段定位.png'))
  page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(150)
  box=dialog.bounding_box();assert box['width']<=359 and box['x']>=0
  dialog.locator('.el-dialog__body').evaluate('(e)=>e.scrollTop=e.scrollHeight');box=dialog.locator('.el-dialog__footer').bounding_box();assert box['y']+box['height']<=849
  dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible()
  assert writes[-1]['resume_profile']['interests']=='绘画、音乐'
  assert not errors,errors
  (OUT/'新增编辑UI复验.json').write_text(json.dumps({'save_requests_mocked':len(writes),'database_requests':0,'create_edit_roundtrip':True,'new_field_search':True,'education_year':True,'footer_visible':True,'mobile_dialog':True,'draggable_and_reopen_reset':True,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
  print('新增、编辑、字段搜索、毕业年与小屏底部操作验证通过；所有API已拦截')
 except:
  (OUT/'ui-failure.txt').write_text(page.url+'\n'+page.locator('body').inner_text()+'\n'+str(errors),encoding='utf-8');page.screenshot(path=str(OUT/'ui-failure.png'));raise
 finally:browser.close();server.shutdown()
