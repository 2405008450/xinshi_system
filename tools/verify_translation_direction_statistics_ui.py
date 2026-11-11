"""方向子单复制与独立编辑提示：真实保存前窗口，接口全部模拟。"""
import json,re
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];BASE='http://localhost:3000'

def run(metric='words'):
    source=(ROOT/'tools/verify_pending_suborder_split_ui.py').read_text(encoding='utf8')
    state={'json':json,'re':re,'urlopen':urlopen,'BASE':BASE}
    exec(source[source.index('compiled='):source.index('with sync_playwright() as p:')],state)
    form={'orderNo':'TP-261110-023','sourceFileName':'订单测试文件.docx','projectName':'订单测试文件.docx','languagePair':'中文→英语；中文→法语','wordCountMatrix':{'company':{metric:100},'customer':{'pages':0}},'wordCountMatrixSource':'project','pendingSubOrderDetails':{}}
    form['originalStoragePath']=r'D:\原文目录'
    html,count=re.subn(r'form=reactive\(\{.*?\}\);window.testForm=form;',lambda _:'form=reactive('+json.dumps(form)+');window.testForm=form;',state['html'])
    assert count==1
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script("localStorage.setItem('user_id','direction-qa')")
        page.route(BASE+'/api/**',lambda route:route.fulfill(content_type='application/json',body='[]'))
        page.route(BASE+'/direction-copy-qa',lambda route:route.fulfill(content_type='text/html',body=html))
        page.goto(BASE+'/direction-copy-qa')
        def open_dialog():
            page.get_by_role('button',name='打开测试窗口').click()
            dialog=page.locator('.pending-suborder-manager:visible');expect(dialog).to_be_visible();return dialog
        dialog=open_dialog();rows=dialog.locator('tbody tr')
        expect(rows).to_have_count(2)
        expect(dialog.get_by_label('我司统计统计口径',exact=True)).to_have_value(metric)
        expect(dialog.get_by_label('客户统计统计口径',exact=True)).to_have_value('pages')
        for i in range(2):expect(rows.nth(i).locator('input').nth(1)).to_have_value('0')
        # 主动换口径只改变显示；聚焦与输入不会擅自切回，原统计仍保留。
        selector=dialog.get_by_label('我司统计统计口径',exact=True)
        selector.select_option('documents')
        expect(rows.nth(0).locator('input').nth(0)).to_have_value('')
        rows.nth(0).locator('input').nth(0).focus()
        expect(selector).to_have_value('documents')
        selector.select_option(metric)
        for i in range(2):expect(rows.nth(i).locator('td').nth(3)).to_have_text('同上一级订单')
        path=dialog.get_by_placeholder('自动填写“同上一级订单”，可单独修改',exact=True)
        expect(path).to_have_value('同上一级订单')
        path.fill(r'D:\子订单独立路径')
        expect(rows.nth(0).locator('td').nth(3)).to_have_text(r'D:\子订单独立路径')
        expect(rows.nth(1).locator('td').nth(3)).to_have_text('同上一级订单')
        for i in range(2):
            expect(rows.nth(i).locator('input').nth(0)).to_have_value('100')
            expect(rows.nth(i)).to_contain_text('已复制母订单统计')
            assert rows.nth(i).locator('input').nth(0).get_attribute('readonly') is None
        first=rows.nth(0).locator('input').nth(0)
        first.fill('80');expect(rows.nth(0)).to_contain_text('统计已单独修改')
        expect(rows.nth(1)).to_contain_text('已复制母订单统计')
        first.fill('100');expect(rows.nth(0)).to_contain_text('已复制母订单统计')
        first.fill('80')
        dialog.get_by_role('button',name='确认子订单资料',exact=True).click();expect(dialog).not_to_be_visible()
        assert page.evaluate(f'testForm.wordCountMatrix.company.{metric}')==100
        assert page.evaluate('testForm.wordCountMatrix.customer.pages')==0
        dialog=open_dialog();rows=dialog.locator('tbody tr')
        expect(dialog.get_by_placeholder('自动填写“同上一级订单”，可单独修改',exact=True)).to_have_value(r'D:\子订单独立路径')
        expect(rows.nth(0).locator('input').nth(0)).to_have_value('80')
        expect(rows.nth(0)).to_contain_text('统计已单独修改')
        expect(rows.nth(1).locator('input').nth(0)).to_have_value('100')
        dialog.get_by_role('button',name='返回母订单',exact=True).click();expect(dialog).not_to_be_visible()
        page.evaluate("testForm.languagePair+='；中文→日语'")
        dialog=open_dialog();rows=dialog.locator('tbody tr');expect(rows).to_have_count(3)
        expect(rows.nth(2).locator('input').nth(0)).to_have_value('100')
        expect(rows.nth(2)).to_contain_text('已复制母订单统计')
        expect(rows.nth(2).locator('td').nth(3)).to_have_text('同上一级订单')
        dialog.get_by_role('button',name='确认子订单资料',exact=True).click();expect(dialog).not_to_be_visible()
        assert page.evaluate(f'testForm.wordCountMatrix.company.{metric}')==100
        assert page.evaluate(f"Object.values(testForm.pendingSubOrderDetails).map(row=>row.wordCountMatrix.company.{metric})")==[80,100,100]
        assert page.evaluate("Object.values(testForm.pendingSubOrderDetails).map(row=>row.networkFilePath)")==[r'D:\子订单独立路径','同上一级订单','同上一级订单']
        assert not errors,errors
        browser.close()
    print('PASS: copied counts editable / live modified hint / restore hint / zero / independent values / reopen and add direction without multiplying aggregate')

if __name__=='__main__':
    run()
    run('characters_no_spaces')
