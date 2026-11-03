"""通过本机构建产物和隔离 API 验证价格表单，绝不写入业务数据库。"""
from pathlib import Path
from urllib.parse import urlparse
import functools
import http.server
import json
import re
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from resource_schemas import ResourcePersonCreate,ResourcePersonUpdate
from playwright.sync_api import sync_playwright,expect

OUT=ROOT/'.tmp'/'talent-price-ui';OUT.mkdir(parents=True,exist_ok=True)
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if not Path(self.translate_path(self.path)).is_file() and not Path(self.path).suffix:self.path='/index.html'
        super().do_GET()

server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT/'frontend'/'dist')))
threading.Thread(target=server.serve_forever,daemon=True).start()
records={};writes=[];errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    ctx=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
    ctx.add_init_script("localStorage.setItem('token','price-ui-test-only')")
    def api(route):
        request=route.request;path=urlparse(request.url).path.removeprefix('/api').rstrip('/');result=[]
        if path=='/auth/session':result={'user_id':'price-ui-test','username':'UI测试','roles':['admin'],'permissions':['*']}
        elif path.startswith('/projects/languages'):result=[]
        elif path=='/talents/page':result={'items':list(records.values()),'total':len(records)}
        elif path=='/talents' and request.method=='POST':
            data=request.post_data_json;ResourcePersonCreate.model_validate(data);writes.append(data)
            identifier='00000000-0000-0000-0000-000000000002'
            result={**data,'id':identifier,'resource_code':'PRICE-UI-TEST','attachments':[]};records[identifier]=result
        elif path.endswith('/projects') or path.endswith('/attachments'):result=[]
        elif path.startswith('/talents/'):
            identifier=path.split('/')[2]
            if request.method=='PUT':
                data=request.post_data_json;ResourcePersonUpdate.model_validate(data);records[identifier].update(data);writes.append(data)
            result=records.get(identifier,[])
        route.fulfill(status=200,content_type='application/json',body=json.dumps(result,ensure_ascii=False))
    ctx.route('**/api/**',api)
    page=ctx.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
    def field(container,label):
        return container.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=re.compile('^'+re.escape(label)+'$')))
    def select(container,label,value):
        field(container,label).locator('.el-select').click()
        page.get_by_role('option',name=value,exact=True).click()
    try:
        page.goto(f'http://127.0.0.1:{server.server_port}/resource-management/talents')
        page.get_by_role('button',name='新增人才',exact=True).click()
        dialog=page.locator('.talent-editor-dialog:visible')
        initial=dialog.bounding_box()
        dialog.locator('.el-tab-pane:visible').get_by_role('button',name='全部展开',exact=True).first.click()
        field(dialog,'中文姓名').locator('input').fill('价格扩展隔离验收')
        field(dialog,'专业能力').locator('label.el-checkbox').filter(has_text='笔译').click()
        dialog.get_by_role('button',name='添加价格',exact=True).click()
        quote=dialog.locator('.settlement-price-row').first
        expect(field(quote,'货币').locator('.el-select')).to_contain_text('待确认')
        select(quote,'报价方式','区间价')
        field(quote,'金额下限').get_by_role('spinbutton').fill('21')
        field(quote,'金额上限').get_by_role('spinbutton').fill('20')
        select(quote,'服务细分','LQA');select(quote,'计价单位','小时')
        field(quote,'适用语言方向').locator('input').fill('EN-AR')
        field(quote,'原始报价').locator('textarea').fill('21-30$\nLQA，币种待核')
        for label,value in [('来源文件','共培.xlsx'),('来源工作表','共培总表'),('来源列','每小时')]:field(quote,label).locator('input').fill(value)
        field(quote,'来源行号').get_by_role('spinbutton').fill('521')
        dialog.get_by_role('button',name='保存',exact=True).click()
        expect(field(quote,'金额上限').locator('.el-form-item__error')).to_be_visible()
        expect(field(quote,'金额上限').get_by_role('spinbutton')).to_be_focused()
        assert not writes
        field(quote,'金额上限').get_by_role('spinbutton').fill('30')
        dialog.get_by_role('button',name='添加价格',exact=True).click()
        confirmed=dialog.locator('.settlement-price-row').nth(1)
        select(confirmed,'确认状态','已确认');select(confirmed,'价格类型','笔译');select(confirmed,'服务细分','校对')
        field(confirmed,'金额').get_by_role('spinbutton').fill('0.025')
        select(confirmed,'计价单位','词');select(confirmed,'货币','USD 美元')
        dialog.locator('.el-dialog__body').evaluate('(e)=>e.scrollTop=e.scrollHeight')
        footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=1005
        page.screenshot(path=str(OUT/'新增价格.png'))
        dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible()
        assert len(writes)==1
        q=writes[0]['settlement']['prices'][0]
        assert q['currency'] is None and q['amount']==21 and q['amount_max']==30 and q['source_row']==521
        assert writes[0]['settlement']['prices'][1]['unit']=='per_word'
        page.get_by_role('button',name='编辑',exact=True).first.click();dialog=page.locator('.talent-editor-dialog:visible')
        # 字段搜索必须能展开所在分区并定位动态重复行。
        search=dialog.locator('.dialog-field-search-header__search input');search.fill('原始报')
        page.locator('.project-field-search-popper:visible').get_by_text('原始报价',exact=True).first.click()
        quote=dialog.locator('.settlement-price-row').first
        expect(field(quote,'原始报价').locator('textarea')).to_have_value('21-30$\nLQA，币种待核')
        confirmed=dialog.locator('.settlement-price-row').nth(1)
        select(confirmed,'报价方式','区间价')
        field(confirmed,'金额上限').get_by_role('spinbutton').fill('0.05')
        page.set_viewport_size({'width':390,'height':844})
        dialog.locator('.el-dialog__body').evaluate('(e)=>e.scrollTop=e.scrollHeight')
        bounds=dialog.bounding_box();assert bounds['width']<=359 and bounds['x']>=0
        footer=dialog.locator('.el-dialog__footer').bounding_box();assert footer['y']+footer['height']<=849
        page.screenshot(path=str(OUT/'编辑价格_小屏.png'))
        dialog.get_by_role('button',name='保存',exact=True).click();expect(dialog).not_to_be_visible()
        assert writes[-1]['settlement']['prices'][0]['raw_text']==q['raw_text']
        assert writes[-1]['settlement']['prices'][0]['currency'] is None
        assert writes[-1]['settlement']['prices'][1]['amount_max']==0.05
        page.set_viewport_size({'width':1440,'height':1000})
        page.get_by_role('button',name='PRICE-UI-TEST',exact=True).first.click()
        detail_dialog=page.locator('.talent-detail-dialog:visible')
        detail_dialog.get_by_role('button',name='全部展开',exact=True).first.click()
        detail=detail_dialog.locator('.talent-settlement-detail')
        expect(detail).to_be_visible();expect(detail).to_contain_text('0.025 ～ 0.05');expect(detail).to_contain_text('待确认')
        expect(detail).to_contain_text('共培.xlsx');expect(detail).to_contain_text('LQA')
        detail.scroll_into_view_if_needed()
        page.screenshot(path=str(OUT/'价格详情.png'))
        assert not errors,errors
        print(json.dumps({'created_and_edited':True,'api_payloads_validated':len(writes),'range_error_focused':True,'unknown_currency_preserved':True,'dynamic_field_search':True,'small_viewport':True,'fixed_footer':True,'details_verified':True,'page_errors':errors,'business_database_written':False},ensure_ascii=False))
    finally:
        browser.close();server.shutdown();server.server_close()
