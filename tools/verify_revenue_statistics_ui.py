"""营收统计页面交互验收：接口全部模拟，不读写业务数据库。"""
import json
import re
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from uuid import UUID

from playwright.sync_api import sync_playwright, expect

BASE = 'http://localhost:3000'


def run():
    from translation_revenue import report
    compiled = urlopen(BASE + '/src/components/common/RevenueStatisticsDialog.vue', timeout=20).read().decode()
    vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">import {createApp,ref,h} from VUE;import Revenue from '/src/components/common/RevenueStatisticsDialog.vue';createApp({setup(){const open=ref(false);return ()=>h('div',[h('button',{onClick:()=>open.value=true},'Open'),h(Revenue,{modelValue:open.value,'onUpdate:modelValue':v=>open.value=v,query:{only_mine:true},scopeLabel:'本人'})])}}).mount('#app')</script>'''.replace('from VUE', 'from ' + json.dumps(vue))
    entries = []
    for index in range(1,31):
        uid = str(UUID(int=index))
        for day, factor in [('2026-11-01',1),('2026-10-01',.5),('2025-11-01',.25)]:
            amount = Decimal(str(index*100*factor))
            entries.append({'key':uid,'client_id':uid,'client_name':f'测试客户{index:02}','client_short_name':f'客户{index:02}',
                            'day':date.fromisoformat(day),'billing_totals':{'CNY':str(amount)},'totals_excl_tax':{'CNY':str(amount)},
                            'totals_incl_tax':{'CNY':str(amount*Decimal('1.1'))}})
    queries = []
    errors = []
    def api(route):
        query = parse_qs(urlparse(route.request.url).query)
        queries.append(query)
        get = lambda key, default=None:query.get(key,[default])[0]
        integer = lambda key:int(get(key)) if get(key) else None
        decimal = lambda key:Decimal(get(key)) if get(key) else None
        data = report(entries,get('period','month'),date.fromisoformat(get('anchor')),get('currency','CNY'),
                      json.loads(get('client_basis','{}')),get('keyword',''),integer('rank_min'),integer('rank_max'),
                      decimal('amount_min'),decimal('amount_max'),get('focus_client'),int(get('skip','0')),int(get('limit','20')))
        data.update(currencies=['CNY','USD'],missing_date=0,fallback_date=0,partial_period=True,generated_at='2026-11-10T12:00:00+08:00')
        route.fulfill(content_type='application/json',body=json.dumps(data))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        context = browser.new_context(viewport={'width':1600,'height':1000})
        context.route(BASE+'/revenue-ui-test',lambda route:route.fulfill(content_type='text/html',body=html))
        context.route(re.compile('^http://localhost:3000/api/translation-revenue'),api)
        page = context.new_page()
        page.set_default_timeout(12000)
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/revenue-ui-test')
        page.get_by_role('button',name='Open',exact=True).click()
        dialog = page.locator('.revenue-statistics-dialog')
        expect(dialog).to_be_visible()
        anchor = dialog.get_by_role('combobox',name='所属日期')
        anchor.fill('2026-11-10');anchor.press('Enter')
        page.locator('.revenue-period').click()
        expect(dialog.locator('.revenue-cards')).to_contain_text('46,500.00')
        assert queries[-1]['only_mine']==['true']
        # 单个客户选择含税后，总营收与该客户同比环比、排名都采用该口径。
        dialog.locator('.el-table__body-wrapper .el-select').first.click()
        page.get_by_role('option',name='含税总价',exact=True).click()
        expect(dialog.locator('.revenue-cards')).to_contain_text('46,800.00')
        dialog.get_by_role('button',name='1–10名',exact=True).click()
        expect(dialog.locator('.revenue-ranking-toolbar')).to_contain_text('匹配 10 / 30')
        dialog.get_by_role('button',name='20–50名',exact=True).click()
        expect(dialog.locator('.revenue-ranking-toolbar')).to_contain_text('匹配 11 / 30')
        dialog.get_by_role('button',name='5000以上',exact=True).click()
        expect(dialog.locator('.revenue-ranking-toolbar')).to_contain_text('匹配 0 / 30')
        dialog.get_by_role('button',name='不限金额',exact=True).click()
        dialog.get_by_role('button',name=re.compile('高级筛选')).click()
        popover=page.locator('.common-advanced-filter-popover:visible')
        end=popover.get_by_role('spinbutton',name='结束名次')
        end.fill('25');end.press('Tab')
        expect(dialog.locator('.revenue-ranking-toolbar')).to_contain_text('匹配 6 / 30')
        popover.get_by_role('button',name='关闭',exact=True).click()
        dialog.get_by_role('button',name='不限排名',exact=True).click()
        keyword=dialog.get_by_role('textbox',name='客户全称或简称，多关键词搜索')
        keyword.fill('客户 30')
        expect(dialog.locator('.revenue-ranking-toolbar')).to_contain_text('匹配 1 / 30')
        expect(dialog.locator('.revenue-cards')).to_contain_text('46,800.00')
        dialog.get_by_role('button',name='跟踪',exact=True).click()
        expect(dialog.locator('.revenue-chart')).to_be_visible()
        assert queries[-1]['focus_client']==[str(UUID(int=30))]
        expect(dialog.locator('.el-tab-pane:visible')).to_contain_text('3,300.00')
        for label,value in [('周','week'),('季度','quarter'),('年','year'),('月','month')]:
            dialog.locator('.revenue-query .el-select').first.click()
            page.get_by_role('option',name=label,exact=True).click()
            page.wait_for_timeout(200)
            assert queries[-1]['period']==[value]
        # 窗口拖动、关闭重开复位；客户口径按当前用户保留。
        header=dialog.locator('.el-dialog__header')
        original=dialog.bounding_box()
        box=header.bounding_box()
        page.mouse.move(box['x']+box['width']*.5,box['y']+8)
        page.mouse.down();page.mouse.move(box['x']+box['width']*.5-100,box['y']+40,steps=6);page.mouse.up()
        moved=dialog.bounding_box()
        assert abs(moved['x']-original['x'])>20
        dialog.get_by_role('button',name='关闭',exact=True).click()
        page.get_by_role('button',name='Open',exact=True).click()
        expect(dialog).to_be_visible()
        assert abs(dialog.bounding_box()['x']-original['x'])<5
        assert json.loads(queries[-1]['client_basis'][0])[str(UUID(int=30))]=='incl'
        page.set_viewport_size({'width':600,'height':640})
        page.wait_for_timeout(250)
        size=dialog.bounding_box()
        assert size['width']<=568 and size['height']<=577,size
        dialog.locator('.el-dialog__body').evaluate('(node)=>node.scrollTop=node.scrollHeight')
        expect(dialog.locator('.el-dialog__footer')).to_be_in_viewport()
        assert not errors,errors
        browser.close()
    print('PASS: client-specific tax totals, rank and amount ranges, search, all periods, customer trend, drag/reset, small-screen footer')


if __name__=='__main__':
    run()
