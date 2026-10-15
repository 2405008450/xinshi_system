"""真实静态构建、真实须知 API 与隔离项目样例的浏览器验收。"""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


def run():
    base = os.getenv('NOTICE_UI_BASE', '')
    if os.getenv('PROJECT_NOTICES_QA') != '1' or urlparse(base).hostname != 'localhost' or urlparse(base).port in {None, 3000, 8000}:
        raise SystemExit('仅允许专用本机隔离服务')
    output = Path(os.environ['NOTICE_UI_OUTPUT'])
    results, errors = [], []
    modules = {'translation': '笔译', 'interpretation': '口译', 'recruitment': '招聘'}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        context = browser.new_context(viewport={'width': 1440, 'height': 900}, timezone_id='America/Los_Angeles')
        context.add_init_script("localStorage.setItem('token','isolated-notice-admin');localStorage.setItem('user_roles','[]')")
        page = context.new_page()
        page.set_default_timeout(12000)
        page.on('pageerror', lambda error: errors.append(str(error)))
        def api(module, method, path, data=None):
            response = context.request.fetch(base + '/api/project-notices/' + module + path, method=method, data=data,
                headers={'Authorization': 'Bearer isolated-notice-admin'})
            assert response.ok, response.text()
            return response.json() if response.status != 204 else None
        for module, label in modules.items():
            path = '/' + module + '-details'
            page.goto(base + path)
            expect(page.get_by_role('tab', name=label + '项目管理', exact=True)).to_have_attribute('aria-selected', 'true')
            keyword = page.locator('.project-list-keyword-filter input').first
            expect(keyword).to_be_visible()
            keyword.fill('保留筛选')
            keyword.press('Enter')
            pagination = page.locator('.el-pagination').first
            pagination.get_by_text('2', exact=True).click()
            expect(pagination.locator('.el-pager .is-active')).to_have_text('2')
            page.get_by_role('tab', name=label + '须知', exact=True).click()
            doc = page.locator('.document-sections-page')
            expect(doc).to_contain_text(label + '须知暂无栏目')
            page.get_by_role('tab', name=label + '项目管理', exact=True).click()
            expect(keyword).to_have_value('保留筛选')
            expect(pagination.locator('.el-pager .is-active')).to_have_text('2')
            page.get_by_role('tab', name=label + '须知', exact=True).click()
            doc.get_by_role('button', name='栏目管理', exact=True).click()
            manager = page.get_by_role('dialog', name=label + '须知栏目管理', exact=True)
            expect(manager).to_be_visible()
            manager.get_by_role('button', name='新增一级栏目', exact=True).click()
            create = page.get_by_role('dialog', name='新增一级栏目', exact=True)
            create.get_by_role('textbox', name='栏目名称').fill(label + '业务规范')
            create.get_by_role('button', name='确定', exact=True).click()
            expect(create).not_to_be_visible()
            manager.get_by_role('button', name='关闭', exact=True).click()
            doc.get_by_role('button', name=re.compile(label + '业务规范')).click()
            expect(doc.locator('.notice-content__heading h3')).to_have_text(label + '业务规范')
            sid = api(module, 'GET', '/tree')[0]['id']
            expect(page).to_have_url(re.compile('noticeSectionId=' + sid))
            doc.get_by_role('button', name='编辑内容', exact=True).click()
            editor = page.get_by_role('dialog', name='编辑' + label + '须知 · ' + label + '业务规范', exact=True)
            expect(editor).to_be_visible()
            composer = editor.locator('[contenteditable=true]')
            composer.fill(label + '验收正文：报价与交付注意事项')
            # 页签导航触发公共未保存提醒，取消后仍停留编辑页面。
            page.evaluate("document.querySelector('.project-workspace #tab-projects').click()")
            discard = page.get_by_role('dialog', name='放弃修改', exact=True)
            expect(discard).to_be_visible()
            discard.get_by_role('button', name='继续编辑', exact=True).click()
            expect(discard).not_to_be_visible()
            expect(editor).to_be_visible()
            expect(page.get_by_role('tab', name=label + '须知', exact=True)).to_have_attribute('aria-selected', 'true')
            # 标题栏拖动、视口约束、固定 footer 与位置复位。
            window = editor.locator('.el-dialog')
            initial = window.bounding_box()
            header = editor.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x'] + 50, header['y'] + 20)
            page.mouse.down()
            page.mouse.move(header['x'] + 130, header['y'] + 70, steps=8)
            page.mouse.up()
            moved = window.bounding_box()
            assert abs(moved['x'] - initial['x']) > 20
            page.mouse.move(moved['x'] + 50, moved['y'] + 20)
            page.mouse.down()
            page.mouse.move(-1000, -1000, steps=8)
            page.mouse.up()
            bounded = window.bounding_box()
            assert bounded['x'] >= -1 and bounded['y'] >= -1
            composer.fill('\n'.join([label + '验收正文：报价与交付注意事项'] * 60))
            body = editor.locator('.el-dialog__body')
            body.evaluate('(element) => { element.scrollTop = element.scrollHeight }')
            expect(editor.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
            editor.get_by_role('button', name='保存', exact=True).click()
            expect(editor).not_to_be_visible()
            expect(doc.locator('.notice-content__document')).to_contain_text(label + '验收正文')
            doc.get_by_role('button', name='编辑内容', exact=True).click()
            expect(editor).to_be_visible()
            page.wait_for_timeout(350)
            reopened = window.bounding_box()
            assert abs(reopened['x'] - initial['x']) < 2 and abs(reopened['y'] - initial['y']) < 2
            editor.locator('.el-dialog__headerbtn').click()
            expect(editor).not_to_be_visible()
            panel = doc.locator('.document-section-attachments')
            panel.locator('input[type=file]').set_input_files({'name': label + '说明.txt', 'mimeType': 'text/plain', 'buffer': (label + '附件内容').encode()})
            expect(panel.locator('h4')).to_contain_text('(1/50)')
            with page.expect_download() as event:
                panel.get_by_role('button', name='下载', exact=True).click()
            assert event.value.suggested_filename == label + '说明.txt'
            assert Path(event.value.path()).read_bytes() == (label + '附件内容').encode()
            page.screenshot(path=str(output / (module + '-notices.png')), full_page=True)
            # 保存的时刻与页面在美国时区下的香港展示一致。
            saved = api(module, 'GET', '/sections/' + sid)
            time_text = page.evaluate("v => new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(v))", saved['updated_at'])
            expect(doc.locator('.notice-content__meta')).to_contain_text(time_text)
            child = api(module, 'POST', '/sections', {'title': label + '二级流程', 'parent_id': sid, 'has_content': True})
            doc.get_by_role('button', name='刷新', exact=True).click()
            doc.get_by_role('button', name=re.compile(label + '二级流程')).click()
            expect(page).to_have_url(re.compile('noticeSectionId=' + child['id']))
            page.go_back()
            expect(page).to_have_url(re.compile('noticeSectionId=' + sid))
            page.go_forward()
            expect(page).to_have_url(re.compile('noticeSectionId=' + child['id']))
            page.reload()
            expect(doc.locator('.notice-breadcrumb')).to_contain_text(label + '二级流程')
            search = doc.get_by_placeholder('搜索栏目名称或内容')
            search.fill(label + '验收正文')
            expect(doc.locator('.notice-search-results')).to_contain_text('共找到 1 个栏目')
            doc.get_by_role('button', name='查看栏目', exact=True).click()
            expect(doc.locator('.notice-content__heading h3')).to_have_text(label + '业务规范')
            # 小屏编辑器只滚动内容，操作栏保持可见。
            page.set_viewport_size({'width': 390, 'height': 760})
            doc.get_by_role('button', name='编辑内容', exact=True).click()
            expect(editor.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
            body.evaluate('(element) => { element.scrollTop = element.scrollHeight }')
            expect(editor.get_by_role('button', name='取消', exact=True)).to_be_in_viewport()
            box = window.bounding_box()
            assert box['width'] <= 359 and box['y'] + box['height'] <= 761
            editor.locator('.el-dialog__headerbtn').click()
            page.set_viewport_size({'width': 1440, 'height': 900})
            results.append(label + '：空白初始化、栏目新增、编辑/未保存保护、附件、搜索、历史导航、列表状态、弹窗拖动及小屏')
            # 长内容验收后缩短正文，留下便于核对入口和布局的截图。
            version = api(module, 'GET', '/sections/' + sid)['updated_at']
            api(module, 'PUT', '/sections/' + sid + '/content', {
                'expected_updated_at': version,
                'content_json': {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': label + '验收正文：报价与交付注意事项'}]}]}
            })
            page.reload()
            expect(doc.locator('.notice-content__document')).to_contain_text(label + '验收正文')
            page.locator('.workspace-navigation').scroll_into_view_if_needed()
            page.screenshot(path=str(output / (module + '-notices.png')), full_page=True)
            # 原项目新增、定位和编辑入口继续由原组件处理；这里只打开，不保存业务记录。
            page.goto(base + path)
            add_label = '新增项目' if module == 'translation' else '新增' + label + '项目'
            page.get_by_role('button', name=add_label, exact=True).click()
            editor_class = {'translation': '.project-editor-dialog', 'interpretation': '.interpretation-editor-dialog', 'recruitment': '.recruitment-editor'}[module]
            project_editor = page.locator(editor_class + ':visible')
            expect(project_editor).to_be_visible()
            expect(project_editor.get_by_role('button', name='取消', exact=True)).to_be_in_viewport()
            project_editor.locator('.el-dialog__headerbtn').click()
            expect(project_editor).not_to_be_visible()
            project_id = '40000000-0000-0000-0000-000000000001'
            page.goto(base + path + '?projectId=' + project_id + '&openEditor=1')
            expect(project_editor).to_be_visible()
            expect(project_editor).to_contain_text('编辑')
            expect(page).not_to_have_url(re.compile('openEditor=1'))
            project_editor.locator('.el-dialog__headerbtn').click()
            results.append(label + '：原项目新增弹窗、项目定位和编辑入口')
        # 直接链接不能借用其他业务的栏目 ID。
        foreign = api('translation', 'GET', '/tree')[0]['id']
        page.goto(base + '/recruitment-details?section=notices&noticeSectionId=' + foreign)
        expect(page).not_to_have_url(re.compile('noticeSectionId='))
        expect(page.locator('.document-sections-page')).not_to_contain_text('笔译业务规范')
        reader = browser.new_context(viewport={'width': 1440, 'height': 900})
        reader.add_init_script("localStorage.setItem('token','isolated-notice-reader');localStorage.setItem('user_roles','[]')")
        read_page = reader.new_page()
        for module, label in modules.items():
            sid = api(module, 'GET', '/tree')[0]['id']
            read_page.goto(base + '/' + module + '-details?section=notices&noticeSectionId=' + sid)
            read_doc = read_page.locator('.document-sections-page')
            expect(read_doc.locator('.notice-content__document')).to_contain_text(label + '验收正文')
            expect(read_doc.get_by_role('button', name='编辑内容', exact=True)).to_have_count(0)
            expect(read_doc.get_by_role('button', name='栏目管理', exact=True)).to_have_count(0)
            expect(read_doc.get_by_role('button', name='上传附件', exact=True)).to_have_count(0)
            expect(read_doc.get_by_role('button', name='下载', exact=True)).to_be_visible()
        results.append('跨板块 ID 隔离及三个板块只读权限')
        assert not errors, errors
        reader.close()
        context.close()
        browser.close()
    (output / 'project-notices-results.json').write_text(json.dumps({'checks': results, 'page_errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False), flush=True)
    # 在同一隔离服务回归原标注须知，确保公共组件增强兼容。
    from verify_annotation_notices_ui import run as verify_annotation
    verify_annotation()


if __name__ == '__main__':
    run()
