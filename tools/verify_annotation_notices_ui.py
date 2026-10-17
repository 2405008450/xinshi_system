"""真实构建和专用隔离接口的标注须知浏览器验收。"""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
GROUP = '20000000-0000-0000-0000-000000000001'
CHILD = '20000000-0000-0000-0000-000000000002'
OTHER = '20000000-0000-0000-0000-000000000003'


def run():
    base = os.getenv('NOTICE_UI_BASE', '')
    if os.getenv('ANNOTATION_NOTICES_QA') != '1' or urlparse(base).hostname != 'localhost' or urlparse(base).port in {None, 3000, 8000}:
        raise SystemExit('仅允许专用本机隔离服务')
    output = Path(os.environ['NOTICE_UI_OUTPUT'])
    errors, results, requests, cancelled = [], [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        context = browser.new_context(viewport={'width': 1440, 'height': 900}, timezone_id='America/Los_Angeles')
        context.add_init_script("localStorage.setItem('token','isolated-notice-admin');localStorage.setItem('user_roles','[]')")
        page = context.new_page()
        page.set_default_timeout(10000)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append((request.method, request.url)))
        page.on('requestfailed', lambda request: cancelled.append(request.url))
        def open_section(sid=None):
            page.goto(base + '/annotation-details?section=notices' + (('&noticeSectionId=' + sid) if sid else ''))
            expect(page.locator('.notice-breadcrumb')).to_be_visible()
        def api(method, path, data=None, module='annotation-notices'):
            response = context.request.fetch(base + '/api/' + module + path, method=method, data=data,
                headers={'Authorization': 'Bearer isolated-notice-admin'})
            assert response.ok, f'{response.status} {response.text()}'
            return response.json() if response.status != 204 else None
        def section():
            return page.locator('.document-sections-page')
        def attachment_panel():
            return section().locator('.document-section-attachments')
        def heading(count):
            expect(attachment_panel().locator('h4')).to_have_text(re.compile(rf'栏目附件\s*\({count}/50\)'))
        def cards():
            return section().locator('.notice-section-card')
        def open_card(name):
            cards().filter(has_text=name).locator('.notice-section-card__title').first.click()
        def breadcrumb():
            return section().locator('.notice-breadcrumb')
        open_section()
        expect(section().locator('.notice-nav')).to_have_count(0)
        expect(cards().filter(has_text='验收流程分组')).to_be_visible()
        assert 'noticeSectionId' not in page.url
        open_card('验收流程分组')
        expect(page).to_have_url(re.compile('noticeSectionId=' + GROUP))
        expect(breadcrumb()).to_contain_text('验收流程分组')
        expect(section().get_by_role('button', name='编辑内容', exact=True)).to_have_count(0)
        heading(0)
        open_card('验收二级栏目')
        expect(page).to_have_url(re.compile('noticeSectionId=' + CHILD))
        expect(breadcrumb()).to_contain_text(re.compile(r'标注须知\s*/\s*验收流程分组\s*/\s*验收二级栏目'))
        expect(section().get_by_role('button', name='编辑内容', exact=True)).to_be_visible()
        page.go_back()
        expect(page).to_have_url(re.compile('noticeSectionId=' + GROUP))
        page.go_forward()
        expect(page).to_have_url(re.compile('noticeSectionId=' + CHILD))
        page.reload()
        expect(breadcrumb()).to_contain_text('验收二级栏目')
        results.append('一级与二级导航、分组栏目、面包屑、刷新、前进后退')

        heading(0)
        attachment_panel().locator('input[type=file]').set_input_files([
            {'name': '中文说明.pdf', 'mimeType': 'application/pdf', 'buffer': b'%PDF-1.4 notice'},
            {'name': '操作清单.txt', 'mimeType': 'text/plain', 'buffer': '操作步骤'.encode()},
        ])
        heading(2)
        rows = attachment_panel().locator('.el-table__body-wrapper tr.el-table__row')
        expect(rows).to_have_count(2)
        with page.expect_download() as downloaded:
            rows.filter(has_text='中文说明.pdf').get_by_role('button', name='下载', exact=True).click()
        assert downloaded.value.suggested_filename == '中文说明.pdf'
        assert Path(downloaded.value.path()).read_bytes() == b'%PDF-1.4 notice'
        data = api('GET', f'/sections/{CHILD}/attachments')
        expected_time = page.evaluate("value => new Intl.DateTimeFormat('zh-CN', {timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(value))", data[0]['uploaded_at'])
        expect(rows.filter(has_text=data[0]['original_name'])).to_contain_text(expected_time)
        page.screenshot(path=str(output / 'notices-attachments.png'), full_page=True)
        breadcrumb().get_by_role('button', name='验收流程分组', exact=True).click()
        heading(0)
        open_card('验收二级栏目')
        heading(2)
        results.append('真实多文件上传、中文文件下载、栏目附件隔离、UTC+8展示')

        pattern = '**/api/annotation-notices/sections/' + CHILD + '/attachments'
        def fail_upload(route):
            if route.request.method == 'POST':
                route.fulfill(status=500, json={'detail': '模拟上传失败'})
            else:
                route.continue_()
        page.route(pattern, fail_upload)
        attachment_panel().locator('input[type=file]').set_input_files({'name': '重试.txt', 'mimeType': 'text/plain', 'buffer': b'retry'})
        expect(attachment_panel().get_by_role('button', name='重试', exact=True)).to_be_visible()
        page.unroute(pattern, fail_upload)
        attachment_panel().get_by_role('button', name='重试', exact=True).click()
        heading(3)
        rows.filter(has_text='重试.txt').get_by_role('button', name='删除', exact=True).click()
        page.get_by_role('button', name='删除', exact=True).filter(visible=True).last.click()
        heading(2)
        results.append('失败重试、删除确认与数量同步')

        # 暂停旧栏目的附件响应，切换后再释放，确认旧请求不会污染新栏目。
        held = []
        def hold_list(route):
            if route.request.method == 'GET':
                held.append(route)
            else:
                route.continue_()
        page.route(pattern, hold_list)
        section().get_by_role('button', name='刷新', exact=True).click()
        page.wait_for_timeout(250)
        assert held, '未捕获需要取消的附件请求'
        breadcrumb().get_by_role('button', name='标注须知', exact=True).click()
        open_card('独立栏目')
        heading(0)
        for route in held:
            try:
                route.fulfill(json=data)
            except Exception:
                pass  # 浏览器已经取消的请求可能无法再返回响应。
        page.wait_for_timeout(100)
        heading(0)
        expect(attachment_panel().get_by_text('中文说明.pdf', exact=True)).to_have_count(0)
        assert any('/sections/' + CHILD + '/attachments' in url for url in cancelled)
        page.unroute(pattern, hold_list)
        breadcrumb().get_by_role('button', name='标注须知', exact=True).click()
        open_card('验收流程分组')
        open_card('验收二级栏目')
        heading(2)
        results.append('快速切换取消旧附件请求，迟到响应不覆盖新栏目')

        search = section().get_by_placeholder('搜索栏目名称或内容')
        search.fill('二级')
        expect(section().locator('.notice-search-result')).to_have_count(1)
        search.fill('')
        expect(breadcrumb()).to_contain_text('验收二级栏目')
        breadcrumb().get_by_role('button', name='标注须知', exact=True).click()
        search.fill('二级')
        search.press('Enter')
        section().get_by_role('button', name='查看栏目', exact=True).click()
        expect(breadcrumb()).to_contain_text('验收二级栏目')
        heading(2)
        results.append('搜索防抖、回车、清空恢复浏览位置、搜索结果定位')

        # 编辑弹窗仍使用全局可拖拽组件，验证复位与固定底部。
        section().get_by_role('button', name='编辑内容', exact=True).click()
        dialog = page.get_by_role('dialog').filter(has_text='编辑标注须知')
        expect(dialog).to_be_visible()
        page.wait_for_timeout(350)
        window = dialog.locator('.el-dialog')
        box = window.bounding_box()
        header = dialog.locator('.el-dialog__header').bounding_box()
        x, y = header['x'] + 20, header['y'] + 15
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x+70, y+35, steps=8); page.mouse.up()
        moved = window.bounding_box()
        assert abs(moved['x'] - box['x']) > 30
        header = dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x']+20, header['y']+15); page.mouse.down(); page.mouse.move(5000, 5000, steps=8); page.mouse.up()
        bounded = window.bounding_box()
        assert bounded['x'] >= -1 and bounded['y'] >= -1
        assert bounded['x'] + bounded['width'] <= 1441 and bounded['y'] + bounded['height'] <= 901
        dialog.locator('.el-dialog__body').evaluate('el => el.scrollTop = el.scrollHeight')
        expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
        dialog.get_by_role('button', name='取消', exact=True).click()
        section().get_by_role('button', name='编辑内容', exact=True).click()
        expect(dialog).to_be_visible(); page.wait_for_timeout(350)
        reopened = window.bounding_box()
        assert abs(reopened['x'] - box['x']) < 2 and abs(reopened['y'] - box['y']) < 2
        dialog.locator('.el-dialog__headerbtn').click()
        expect(dialog).not_to_be_visible()
        results.append('正文弹窗拖动、视口边界、关闭按钮、重新打开复位和固定操作栏')

        section().get_by_role('button', name='编辑内容', exact=True).click()
        dialog.locator('[contenteditable=true]').fill('未保存修改')
        page.evaluate('history.back()')
        expect(page.get_by_role('button', name='继续编辑', exact=True)).to_be_visible()
        page.get_by_role('button', name='继续编辑', exact=True).click()
        expect(page).to_have_url(re.compile('noticeSectionId=' + CHILD))
        expect(dialog).to_be_visible()
        dialog.get_by_role('button', name='取消', exact=True).click()
        page.get_by_role('button', name='放弃修改', exact=True).click()
        expect(dialog).not_to_be_visible()
        results.append('正文编辑期间浏览器后退的未保存保护')

        original = api('GET', f'/sections/{GROUP}')
        api('PATCH', f'/sections/{GROUP}', {'title': '改名后的流程', 'has_content': False, 'expected_structure_updated_at': original['structure_updated_at']})
        section().get_by_role('button', name='刷新', exact=True).click()
        expect(breadcrumb()).to_contain_text('改名后的流程')
        page.set_viewport_size({'width': 390, 'height': 844})
        expect(breadcrumb()).to_be_visible()
        assert section().evaluate('el => el.getBoundingClientRect().right') <= 391
        breadcrumb().get_by_role('button', name='标注须知', exact=True).click()
        expect(cards().first).to_be_visible()
        assert section().locator('.notice-section-cards').evaluate('el => getComputedStyle(el).gridTemplateColumns.split(" ").length') == 1
        page.screenshot(path=str(output / 'notices-mobile.png'), full_page=True)
        page.set_viewport_size({'width': 1440, 'height': 900})
        open_section('deleted-or-invalid')
        expect(page).not_to_have_url(re.compile('noticeSectionId'))
        expect(cards().filter(has_text='改名后的流程')).to_be_visible()
        results.append('栏目改名、失效路径回首页、小屏单列和面包屑换行')

        reader = browser.new_context(viewport={'width': 1440, 'height': 900})
        reader.add_init_script("localStorage.setItem('token','isolated-notice-reader');localStorage.setItem('user_roles','[]')")
        read_page = reader.new_page()
        read_page.goto(base + '/annotation-details?section=notices&noticeSectionId=' + CHILD)
        read_panel = read_page.locator('.document-section-attachments')
        expect(read_panel.locator('h4')).to_contain_text('(2/50)')
        expect(read_panel.get_by_role('button', name='上传附件', exact=True)).to_have_count(0)
        expect(read_panel.get_by_role('button', name='删除', exact=True)).to_have_count(0)
        expect(read_panel.get_by_role('button', name='下载', exact=True).first).to_be_visible()
        reader.close()
        results.append('只读账号可查看下载，无上传删除入口')

        # 缺少结构的页面状态使用受控模拟503；后端缺表检查另有真实测试。
        page.route(pattern, lambda route: route.fulfill(status=503, json={'detail': '栏目附件尚未启用'}))
        open_section(CHILD)
        expect(attachment_panel().get_by_text('栏目附件尚未启用', exact=True)).to_be_visible()
        expect(attachment_panel().get_by_role('button', name='上传附件', exact=True)).to_be_disabled()
        expect(section().locator('.notice-content__document')).to_contain_text('验收正文')
        page.unroute(pattern)
        results.append('结构未启用提示，导航和正文继续可用')

        api('DELETE', f'/sections/{CHILD}')
        section().get_by_role('button', name='刷新', exact=True).click()
        expect(page).not_to_have_url(re.compile('noticeSectionId'))
        expect(cards().filter(has_text='改名后的流程')).to_be_visible()
        results.append('当前栏目软删除后刷新返回首页')

        # 公司管理与标注须知共用逐级导航，各模块独立保存栏目位置。
        def company_api(method, path, data=None):
            return api(method, path, data, module='company-management')
        company_root = '30000000-0000-0000-0000-000000000001'
        root_detail = company_api('GET', '/sections/' + company_root)
        company_api('PATCH', '/sections/' + company_root, {
            'title': root_detail['title'], 'has_content': False,
            'expected_structure_updated_at': root_detail['structure_updated_at'],
        })
        company_child = company_api('POST', '/sections', {
            'title': '公司制度细则', 'parent_id': company_root, 'has_content': True,
        })['id']
        page.goto(base + '/company-management')
        expect(section().locator('.notice-nav')).to_have_count(0)
        expect(breadcrumb()).to_contain_text('公司管理')
        open_card('公司资料验收')
        expect(page).to_have_url(re.compile('companySectionId=' + company_root))
        assert 'noticeSectionId' not in page.url and 'section=notices' not in page.url
        expect(section().get_by_role('button', name='编辑内容', exact=True)).to_have_count(0)
        heading(0)
        open_card('公司制度细则')
        expect(breadcrumb()).to_contain_text(re.compile(r'公司管理\s*/\s*公司资料验收\s*/\s*公司制度细则'))
        expect(page).to_have_url(re.compile('companySectionId=' + company_child))
        page.go_back()
        expect(page).to_have_url(re.compile('companySectionId=' + company_root))
        page.go_forward()
        expect(page).to_have_url(re.compile('companySectionId=' + company_child))
        page.reload()
        expect(breadcrumb()).to_contain_text('公司制度细则')
        heading(0)
        attachment_panel().locator('input[type=file]').set_input_files({'name': '公司回归.txt', 'mimeType': 'text/plain', 'buffer': b'company'})
        heading(1)
        breadcrumb().get_by_role('button', name='公司资料验收', exact=True).click()
        heading(0)
        open_card('公司制度细则')
        heading(1)
        results.append('公司管理两级面包屑、分组栏目、独立URL、刷新及前进后退、附件隔离')

        section().get_by_role('button', name='编辑内容', exact=True).click()
        company_dialog = page.get_by_role('dialog').filter(has_text='编辑公司管理')
        expect(company_dialog).to_be_visible()
        company_dialog.locator('[contenteditable=true]').fill('公司正文编辑验收')
        company_dialog.get_by_role('button', name='保存', exact=True).click()
        expect(company_dialog).not_to_be_visible()
        expect(section().locator('.notice-content__document')).to_contain_text('公司正文编辑验收')
        search.fill('制度细则')
        search.press('Enter')
        section().get_by_role('button', name='查看栏目', exact=True).click()
        expect(breadcrumb()).to_contain_text('公司制度细则')
        heading(1)
        results.append('公司管理正文编辑保存和搜索定位')

        page.set_viewport_size({'width': 390, 'height': 844})
        expect(breadcrumb()).to_be_visible()
        assert section().evaluate('el => el.getBoundingClientRect().right') <= 391
        breadcrumb().get_by_role('button', name='公司管理', exact=True).click()
        expect(cards().first).to_be_visible()
        assert section().locator('.notice-section-cards').evaluate('el => getComputedStyle(el).gridTemplateColumns.split(" ").length') == 1
        page.screenshot(path=str(output / 'company-breadcrumb-mobile.png'), full_page=True)
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto(base + '/company-management?companySectionId=' + company_child)
        expect(breadcrumb()).to_contain_text('公司制度细则')
        page.screenshot(path=str(output / 'company-breadcrumb.png'), full_page=True)
        company_api('DELETE', '/sections/' + company_child)
        section().get_by_role('button', name='刷新', exact=True).click()
        expect(page).not_to_have_url(re.compile('companySectionId'))
        expect(cards().filter(has_text='公司资料验收')).to_be_visible()
        results.append('公司管理小屏单列、直接打开栏目、删除后返回首页')
        browser.close()
    assert not errors, errors
    assert all(urlparse(url).port not in {3000, 8000, 15432} for method, url in requests), '禁止访问日常服务'
    report = {'results': results, 'pageErrors': errors}
    (output / 'ui-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
