"""统计弹窗：真实组件、模拟数据，筛选/关闭/拖动/小屏验收。"""
import json,re
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse,parse_qs
from playwright.sync_api import sync_playwright,expect
BASE='http://localhost:3000';ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tools/verify_translation_submission_ui.py').read_text(encoding='utf8');setup=source[source.index('    compiled='):source.index('    with sync_playwright() as p:')]
namespace={'urlopen':urlopen,'re':re,'json':json,'BASE':BASE,'urlparse':urlparse};exec('def prepare():\n'+setup+'\n    return locals()\n',namespace);state=namespace['prepare']();requests=[]
amounts=[{'currency':'CNY','total_amount':'150.00','average_amount':'75.00','complete_order_count':2}]
period={'period_start':'2026-11-01','period_end':'2026-11-30','order_count':3,'customer_count':2,'new_customer_count':1,'old_customer_count':1,'new_customer_share':50,'old_customer_share':50,'new_order_count':1,'old_order_count':2,'new_order_share':33.33,'old_order_share':66.67,'unknown_order_count':0,'unknown_order_share':0,'amounts':amounts}
customer={'period_start':'2026-11-01','period_end':'2026-11-30','client_id':'c1','client_name':'统计测试有限公司','client_short_name':'统计测试','first_order_date':'2026-10-01','cohort':'old','order_count':2,'order_share':66.67,'amounts':amounts,'missing_amount_orders':0,'partial_amount_orders':0}
def api(route):
 if urlparse(route.request.url).path=='/api/projects/translation/statistics':
  params=parse_qs(urlparse(route.request.url).query);requests.append(params)
  result={'periods':[period],'customers':[customer],'order_count':3,'fallback_date_orders':0,'undated_orders':0,'generated_at':'2026-11-09T12:30:00+08:00'}
  route.fulfill(content_type='application/json',body=json.dumps(result));return
 state['api'](route)
state['html']=state['html'].replace('import {createApp,h} from',"import AppStyles from '/src/App.vue';import {createApp,h} from")
state['html']=state['html'].replace('<div id="app">','<link rel="stylesheet" href="/src/styles/theme.css"><div id="app">')
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1450,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"projects:read\",\"projects:write\"]')")
 page.route(re.compile(r'^http://localhost:3000/api/'),api);page.route(BASE+'/five-level-test',lambda r:r.fulfill(content_type='text/html',body=state['html']))
 page.goto(BASE+'/five-level-test');page.get_by_role('button',name='数据统计',exact=True).click();dialog=page.locator('.translation-statistics-dialog:visible');expect(dialog).to_be_visible()
 expect(dialog.locator('.statistics-overview')).to_contain_text('33.33%');assert requests[-1]['granularity']==['month'] and requests[-1]['date_basis']==['order']
 dialog.screenshot(path=str(ROOT/'frontend/public/help/translation/statistics-report.png'))
 dialog.get_by_role('tab',name='客户明细（1）',exact=True).click();expect(dialog.locator('.statistics-customers')).to_contain_text('统计测试');expect(dialog.locator('.statistics-customers')).to_contain_text('75.00')
 dialog.get_by_text('每周',exact=True).click();page.wait_for_timeout(200);assert requests[-1]['granularity']==['week']
 dialog.get_by_text('每天',exact=True).click();page.wait_for_timeout(200);assert requests[-1]['granularity']==['day']
 keyword=dialog.get_by_placeholder('客户全称、简称或编号');keyword.fill('统计 测试');page.wait_for_timeout(550);assert requests[-1]['client_keyword']==['统计 测试']
 keyword.fill('');page.wait_for_timeout(100);assert 'client_keyword' not in requests[-1] or requests[-1]['client_keyword']==['']
 dialog.get_by_role('button',name='上月',exact=True).click();page.wait_for_timeout(200);assert requests[-1]['granularity']==['month']
 dialog.get_by_role('button',name='重置',exact=True).click();page.wait_for_timeout(200);assert requests[-1]['date_basis']==['order'] and requests[-1]['tax_basis']==['excl_tax']
 before=dialog.bounding_box();header=dialog.locator('.el-dialog__header').bounding_box();page.mouse.move(header['x']+300,header['y']+20);page.mouse.down();page.mouse.move(header['x']+290,header['y']+55,steps=5);page.mouse.up();assert dialog.bounding_box()['y']>before['y']+10
 page.set_viewport_size({'width':650,'height':750});expect(dialog.locator('.el-dialog__footer')).to_be_visible();box=dialog.bounding_box();assert box['width']<=650 and box['y']>=0
 dialog.locator('.el-dialog__footer').get_by_role('button',name='关闭',exact=True).click();expect(dialog).not_to_be_visible()
 page.set_viewport_size({'width':1450,'height':1000});page.get_by_role('button',name='数据统计',exact=True).click();expect(dialog).to_be_visible();assert dialog.bounding_box()['y']<80
 assert not errors,errors;browser.close()
print('statistics entry / day-week-month / client debounce and clear / monetary data / reset / drag / close / small viewport / reopen reset PASS')
