"""真实构建+专用隔离实例：行内主题管理及双账号团队会话分类验收。"""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import expect, sync_playwright
from verify_chat_topics_ui import run as verify_existing_topics

BASE = os.getenv('ISSUE_UI_BASE', '')
OUTPUT = Path(os.environ.get('ISSUE_UI_OUTPUT', '.tmp/chat-session-categories-qa'))


def run():
    if os.getenv('RESOURCE_ISSUES_QA') != '1' or os.getenv('CHAT_TOPICS_UI') != '1' or urlparse(BASE).hostname != 'localhost' or urlparse(BASE).port in (None, 3000, 8000):
        raise SystemExit('仅允许专用本机隔离服务')
    verify_existing_topics()
    results, errors, requests = [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        def login(actor):
            context = browser.new_context(viewport={'width': 1280, 'height': 900}, timezone_id='America/Los_Angeles')
            context.add_init_script(f"localStorage.setItem('token','isolated-issue-{actor}');localStorage.setItem('user_roles','[]')")
            page = context.new_page()
            page.set_default_timeout(12000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append(request.url))
            page.goto(BASE + '/resource-management/resource-development?section=issues')
            page.get_by_role('button', name='聊天大屏', exact=True).click()
            return context, page
        def pane(page, label):
            page.locator('.chat-workspace__rail:visible, .chat-workspace__pane-tabs:visible').get_by_role('button', name=label, exact=True).click()
        def groups(page):
            page.locator('.chat-workspace__filter').click()
            return page.locator('.chat-session-popover:visible').filter(has=page.locator('.chat-category-menu'))
        def api(context, method, path, body=None, actor='collector'):
            return context.request.fetch(BASE + '/api/chat/' + path, method=method, data=body, headers={'Authorization': f'Bearer isolated-issue-{actor}'})
        def drag(dialog, page):
            page.wait_for_timeout(350)
            content = dialog.locator('.el-dialog')
            original = content.bounding_box()
            header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x'] + 35, header['y'] + 15); page.mouse.down()
            page.mouse.move(header['x'] + 110, header['y'] + 45, steps=8); page.mouse.up()
            moved = content.bounding_box()
            assert abs(moved['x'] - original['x']) > 20
            header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x'] + 35, header['y'] + 15); page.mouse.down(); page.mouse.move(5000, 5000, steps=10); page.mouse.up()
            moved = content.bounding_box()
            assert moved['x'] >= -1 and moved['y'] >= -1 and moved['x'] + moved['width'] <= page.viewport_size['width'] + 1 and moved['y'] + moved['height'] <= page.viewport_size['height'] + 1
            return original
        try:
            context, page = login('collector')
            pane(page, '主题')
            page.get_by_role('button', name='管理主题菜单', exact=True).click()
            dialog = page.get_by_role('dialog', name='讨论主题管理', exact=True)
            expect(dialog.get_by_role('button', name='标注项目', exact=True)).to_be_disabled()
            dialog.get_by_role('button', name='新增一级菜单', exact=True).click()
            name = dialog.get_by_role('textbox', name='主题名称', exact=True)
            expect(name).to_be_focused()
            name.press('Escape')
            expect(name).to_have_count(0)
            dialog.get_by_role('button', name='新增一级菜单', exact=True).click()
            name.press('Enter')
            expect(dialog.get_by_text('请填写名称', exact=True)).to_be_visible()
            name.fill('字' * 81); name.press('Enter')
            expect(dialog.get_by_text('名称不能超过80个字符', exact=True)).to_be_visible()
            name.fill('资源开拓讨论'); name.press('Enter')
            expect(dialog.get_by_text('同一层级已有同名讨论主题', exact=True)).to_be_visible()
            name.fill('行内主题验收')
            name.dispatch_event('compositionstart')
            name.press('Enter')
            expect(name).to_be_visible()
            name.dispatch_event('compositionend')
            def fail_topic(route):
                if route.request.method == 'POST': route.fulfill(status=503, json={'detail': '验收模拟保存失败'})
                else: route.continue_()
            page.route('**/api/chat/topics', fail_topic)
            name.press('Enter')
            expect(dialog.locator('.chat-inline-name-editor .el-form-item__error')).to_be_visible()
            expect(name).to_have_value('行内主题验收')
            page.unroute('**/api/chat/topics', fail_topic)
            expect(name).to_be_enabled()
            expect(name).to_be_focused()
            name.press('Enter')
            expect(dialog.get_by_role('button', name='行内主题验收', exact=True)).to_be_visible()
            root = dialog.locator('.topic-manager-root').filter(has=page.get_by_role('button', name='行内主题验收', exact=True))
            root.get_by_role('button', name='新增二级', exact=True).click()
            name.fill('行内子主题'); name.press('Tab')
            expect(dialog.get_by_role('button', name='行内子主题', exact=True)).to_be_visible()
            dialog.get_by_role('button', name='行内子主题', exact=True).click()
            name.fill('行内子主题改名'); name.press('Enter')
            expect(dialog.get_by_role('button', name='行内子主题改名', exact=True)).to_be_visible()
            dialog.get_by_role('button', name='行内子主题改名设置', exact=True).click()
            settings = page.get_by_role('dialog', name='行内子主题改名设置', exact=True)
            initial = drag(settings, page)
            settings.locator('.el-dialog__headerbtn').click()
            expect(settings).not_to_be_visible()
            expect(dialog).to_be_visible()
            dialog.get_by_role('button', name='行内子主题改名设置', exact=True).click()
            page.wait_for_timeout(350)
            assert abs(settings.locator('.el-dialog').bounding_box()['x'] - initial['x']) < 2
            settings.locator('textarea').fill('独立设置说明')
            settings.get_by_role('button', name='保存设置', exact=True).click()
            expect(settings).not_to_be_visible()
            dialog.get_by_role('button', name='行内子主题改名', exact=True).click()
            name.fill('行内子主题保留说明'); name.press('Enter')
            expect(dialog.get_by_role('button', name='行内子主题保留说明', exact=True)).to_be_visible()
            data = api(context, 'GET', 'topics').json()
            assert next(row for row in data['items'] if row['name'] == '行内子主题保留说明')['description'] == '独立设置说明'
            page.screenshot(path=str(OUTPUT / 'inline-topic-manager.png'), full_page=True)
            dialog.get_by_role('button', name='关闭', exact=True).click()
            results.append('主题新增/二级定位/自动聚焦/改名/失焦保存/Esc/校验/中文输入/失败草稿/嵌套拖动复位及设置保留')

            pane(page, '消息')
            menu = groups(page)
            menu.get_by_role('button', name='新增分类', exact=True).click()
            field = menu.get_by_role('textbox', name='分类名称', exact=True)
            expect(field).to_be_focused()
            field.fill('团队验收一'); field.press('Enter')
            expect(menu.get_by_role('button', name='团队验收一 (0)', exact=True)).to_be_visible()
            menu.get_by_role('button', name='新增分类', exact=True).click()
            field.fill('团队验收二'); field.press('Enter')
            expect(menu.get_by_role('button', name='团队验收二 (0)', exact=True)).to_be_visible()
            menu.get_by_role('button', name='重命名团队验收一', exact=True).click()
            field.fill('团队验收一改名'); field.press('Enter')
            expect(menu.get_by_role('button', name='团队验收一改名 (0)', exact=True)).to_be_visible()
            menu.get_by_role('button', name=re.compile(r'^消息 \(\d+\)$')).click()
            session = page.locator('.chat-workspace__session').filter(has_text='开拓来源标注项目')
            session.hover(); session.get_by_role('button', name='会话操作', exact=True).click()
            page.get_by_role('button', name='设置分类', exact=True).click()
            assignment = page.get_by_role('dialog', name='设置会话分类', exact=True)
            assignment_initial = drag(assignment, page)
            assignment.locator('.el-checkbox').filter(has_text='团队验收一改名').click()
            assignment.locator('.el-checkbox').filter(has_text='团队验收二').click()
            assignment.get_by_role('button', name='取消', exact=True).click()
            session.hover(); session.get_by_role('button', name='会话操作', exact=True).click()
            page.get_by_role('button', name='设置分类', exact=True).click()
            page.wait_for_timeout(350)
            assert abs(assignment.locator('.el-dialog').bounding_box()['x'] - assignment_initial['x']) < 2
            expect(assignment.get_by_role('checkbox', name='团队验收一改名', exact=True)).not_to_be_checked()
            assignment.locator('.el-checkbox').filter(has_text='团队验收一改名').click()
            assignment.locator('.el-checkbox').filter(has_text='团队验收二').click()
            def fail_assignment(route):
                if route.request.method == 'PUT' and route.request.url.endswith('/' + partial_target): route.fulfill(status=503, json={'detail': '验收模拟归类失败'})
                else: route.continue_()
            partial_target = next(row['id'] for row in api(context, 'GET', 'session-categories').json()['items'] if row['name'] == '团队验收二')
            page.route('**/api/chat/sessions/*/*/categories/*', fail_assignment)
            assignment.get_by_role('button', name='确定', exact=True).click()
            expect(assignment.locator('.el-alert')).to_contain_text('团队验收二')
            expect(assignment.get_by_role('checkbox', name='团队验收二', exact=True)).to_be_checked()
            page.unroute('**/api/chat/sessions/*/*/categories/*', fail_assignment)
            assignment.get_by_role('button', name='确定', exact=True).click()
            expect(assignment).not_to_be_visible()
            menu = groups(page)
            expect(menu.get_by_role('button', name='团队验收一改名 (1)', exact=True)).to_be_visible()
            menu.get_by_role('button', name='团队验收一改名 (1)', exact=True).click()
            expect(page.locator('.chat-workspace__session')).to_have_count(1)
            page.reload(); page.get_by_role('button', name='聊天大屏', exact=True).click()
            expect(page.locator('.chat-workspace__filter')).to_contain_text('团队验收一改名')
            expect(page.locator('.chat-workspace__session')).to_have_count(1)
            results.append('团队分类原位新增改名、多选归类、取消不提交、部分失败重试、弹窗拖动复位、统计/列表一致、刷新保留')

            second_context, second_page = login('proposer')
            second_menu = groups(second_page)
            expect(second_menu.get_by_role('button', name='新增分类', exact=True)).to_have_count(0)
            second_sessions = api(second_context, 'GET', 'sessions', actor='proposer').json()['items']
            first_category = next(row for row in api(context, 'GET', 'session-categories').json()['items'] if row['name'] == '团队验收一改名')
            second_count = sum(first_category['id'] in row['category_ids'] for row in second_sessions)
            expect(second_menu.get_by_role('button', name=f'团队验收一改名 ({second_count})', exact=True)).to_be_visible()
            first_sessions = api(context, 'GET', 'sessions').json()['items']
            target = next(row for row in first_sessions if row['kind'] == 'translation')
            category = next(row for row in api(context, 'GET', 'session-categories').json()['items'] if row['name'] == '团队验收二')
            assert api(context, 'PUT', f"sessions/translation/{target['project_id']}/categories/{category['id']}", actor='proposer').ok
            second_page.reload(); second_page.get_by_role('button', name='聊天大屏', exact=True).click()
            second_menu = groups(second_page)
            expect(second_menu.get_by_role('button', name=f'团队验收二 ({second_count + 1})', exact=True)).to_be_visible()
            page.wait_for_timeout(16000)  # 隔离实例未启用通知WS，验收既有轮询兜底。
            menu = groups(page)
            expect(menu.get_by_role('button', name='团队验收二 (2)', exact=True)).to_be_visible()
            menu.get_by_role('button', name='停用团队验收一改名', exact=True).click()
            expect(page.locator('.chat-workspace__filter')).to_contain_text('消息')
            results.append('双账号共享目录和归属、普通用户归类权限、目录范围不扩张、轮询同步、停用回退')

            page.set_viewport_size({'width': 390, 'height': 844})
            page.get_by_role('button', name='会话列表', exact=True).click()
            menu = groups(page)
            box = menu.bounding_box()
            assert box['x'] >= 0 and box['x'] + box['width'] <= 390
            menu.get_by_role('button', name='新增分类', exact=True).click()
            field = menu.get_by_role('textbox', name='分类名称', exact=True)
            expect(field).to_be_focused()
            field.fill('小屏分类草稿')
            page.wait_for_timeout(350)
            page.screenshot(path=str(OUTPUT / 'inline-session-category-mobile.png'), full_page=True)
            field.press('Escape')
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
            results.append('小屏分类面板、原位输入、取消及视口边界')
            assert not errors, errors
            assert not [url for url in requests if urlparse(url).port in (3000, 8000)]
            (OUTPUT / 'session-categories-ui-result.json').write_text(json.dumps({'passed': results, 'page_errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'passed': results, 'page_errors': errors}, ensure_ascii=False))
        except Exception:
            if 'page' in locals():
                page.screenshot(path=str(OUTPUT / 'session-categories-failure.png'), full_page=True)
                (OUTPUT / 'session-categories-failure.html').write_text(page.content(), encoding='utf-8')
            raise
        finally:
            browser.close()


if __name__ == '__main__':
    run()
