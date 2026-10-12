"""用真实构建和专用隔离实例验证分类菜单与聊天，不连接业务服务。"""
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv('ISSUE_UI_BASE', '')
OUTPUT = ROOT / '.tmp/chat-topics-qa'
TOPIC = '00000000-0000-0000-0000-000000001015'


def run():
    if os.getenv('RESOURCE_ISSUES_QA') != '1' or os.getenv('CHAT_TOPICS_UI') != '1' or urlparse(BASE).hostname != 'localhost' or urlparse(BASE).port in (None, 3000, 8000):
        raise SystemExit('仅允许专用本机隔离服务')
    errors, results, requests = [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        context = browser.new_context(viewport={'width':1440, 'height':900}, timezone_id='America/Los_Angeles')
        context.add_init_script("localStorage.setItem('token','isolated-issue-collector');localStorage.setItem('user_roles','[]')")
        page = context.new_page(); page.set_default_timeout(15000)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: requests.append((r.method, r.url)))
        def api(method, path, data=None, actor='collector'):
            response = context.request.fetch(BASE + '/api' + path, method=method, data=data, headers={'Authorization':f'Bearer isolated-issue-{actor}'})
            assert response.ok, response.text()
            return response.json()
        def choose(control, label):
            control.click()
            combo = control.get_by_role('combobox')
            menu = combo.get_attribute('aria-controls')
            page.locator(f'#{menu}').get_by_role('option', name=label, exact=True).click()
        def footer_and_drag(dialog):
            page.wait_for_timeout(400)
            body = dialog.locator('.el-dialog__body')
            for position in (0, 300, 100000):
                body.evaluate('(el, value) => el.scrollTop=value', position)
                box = dialog.locator('.el-dialog__footer').bounding_box()
                assert box and box['y'] >= 0 and box['y'] + box['height'] <= page.viewport_size['height'] + 1
            body.evaluate('el=>el.scrollTop=0')
            header = dialog.locator('.el-dialog__header'); box = header.bounding_box()
            content = dialog.locator('.el-dialog')
            original = content.bounding_box()
            page.mouse.move(box['x']+50, box['y']+15); page.mouse.down(); page.mouse.move(box['x']+105, box['y']+45, steps=8); page.mouse.up()
            changed = content.bounding_box(); assert abs(changed['x']-original['x']) > 20 or abs(changed['y']-original['y']) > 15
            box = header.bounding_box(); page.mouse.move(box['x']+50, box['y']+15); page.mouse.down(); page.mouse.move(5000,5000,steps=12); page.mouse.up()
            changed = content.bounding_box(); assert changed['x'] >= -1 and changed['y'] >= -1 and changed['x']+changed['width'] <= page.viewport_size['width']+1 and changed['y']+changed['height'] <= page.viewport_size['height']+1
        try:
            page.goto(BASE + '/resource-management/resource-development?section=issues')
            expect(page.get_by_role('button',name='新增开拓事项',exact=True)).to_be_visible()
            page.get_by_role('button',name='新增开拓事项',exact=True).click()
            dialog=page.get_by_role('dialog',name='新增开拓事项',exact=True)
            dialog.locator('textarea').first.fill('浏览器验收手工新增高校安排')
            choose(dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text='讨论主题')).locator('.el-select'), '资源开拓讨论 / 高校渠道')
            footer_and_drag(dialog)
            dialog.get_by_role('button',name='保存',exact=True).click()
            expect(dialog).not_to_be_visible()
            row=page.locator('.issue-panel .el-table__row').filter(has_text='浏览器验收手工新增高校安排')
            expect(row).to_be_visible(); expect(row).to_contain_text('高校渠道')
            row.get_by_role('button',name='编辑',exact=True).click()
            dialog=page.get_by_role('dialog',name='编辑开拓问题',exact=True)
            expect(dialog.locator('textarea').first).to_have_value('浏览器验收手工新增高校安排')
            footer_and_drag(dialog)
            dialog.get_by_role('button',name='取消',exact=True).click()
            results.append('手工新增、主题落库、编辑态、拖动边界与固定底栏')

            page.get_by_role('button',name='聊天大屏',exact=True).click()
            workspace=page.locator('.chat-workspace__frame')
            expect(workspace).to_be_visible()
            expect(workspace.locator('.chat-topic-root').first.get_by_role('button').first).to_have_text('资源开拓讨论')
            workspace.locator('.chat-workspace__session').filter(has_text='开拓来源标注项目').click()
            composer=page.locator('.project-chat-window:visible .group-composer')
            expect(composer).to_be_visible()
            choose(composer.locator('.chat-send-topic'), '资源开拓讨论 / 平台讨论')
            workspace.get_by_role('button',name='高校渠道',exact=True).click()
            search=page.get_by_role('dialog',name='资源开拓讨论 / 高校渠道 · 消息检索',exact=True)
            expect(search.locator('.chat-topic-results article')).to_have_count(30)
            search.get_by_role('button',name='加载更多',exact=True).click()
            expect(search.locator('.chat-topic-results article')).to_have_count(52)
            choose(search.locator('.el-select'), '全部可访问会话')
            expect(search.locator('.chat-topic-search-hint')).to_contain_text('共 68 条消息')
            search.get_by_placeholder('搜索主题下的消息内容').fill('高校历史消息00')
            expect(search.locator('.chat-topic-results article')).to_have_count(1)
            search.get_by_placeholder('搜索主题下的消息内容').fill('')
            expect(search.locator('.chat-topic-results article')).to_have_count(30)
            search.get_by_role('button',name='关闭',exact=True).click()
            expect(composer.locator('.chat-send-topic')).to_contain_text('平台讨论')
            results.append('模块排序、历史分页、跨会话检索、防抖清空与发送主题独立')

            composer.get_by_placeholder('输入消息，@ 提及用户').fill('浏览器验收发送前平台主题')
            composer.get_by_role('button',name='发送',exact=True).click()
            article=page.locator('.project-chat-window:visible .group-message').filter(has_text='浏览器验收发送前平台主题')
            expect(article).to_be_visible(); expect(article).to_contain_text('平台讨论')
            expect(composer.locator('.chat-send-topic')).not_to_contain_text('平台讨论')
            article.get_by_role('button',name='分类',exact=True).click()
            popover=page.locator('.chat-topic-popover:visible').filter(has=page.get_by_role('button',name='保存',exact=True))
            choose(popover.locator('.el-select'), '资源开拓讨论 / 高校渠道')
            popover.get_by_role('button',name='保存',exact=True).click()
            expect(article).to_contain_text('高校渠道')
            article.get_by_role('button',name='收录到开拓问题',exact=True).click()
            page.get_by_role('menuitem',name='想法类',exact=True).click()
            issue=page.get_by_role('dialog',name='收录到开拓问题',exact=True)
            expect(issue).to_contain_text('高校渠道'); issue.get_by_role('button',name='保存',exact=True).click()
            results.append('标注发送主题、成功清空、发送后改标、四类收录')

            workspace.get_by_role('button',name='管理主题菜单',exact=True).click()
            manager=page.get_by_role('dialog',name='讨论主题管理',exact=True)
            manager.get_by_label('菜单名称',exact=True).fill('浏览器验收主题')
            manager.get_by_role('button',name='保存菜单',exact=True).click()
            expect(manager.get_by_role('button',name='浏览器验收主题',exact=True)).to_be_visible()
            footer_and_drag(manager)
            manager.get_by_role('button',name='关闭',exact=True).click()
            expect(workspace.get_by_role('button',name='浏览器验收主题',exact=True)).to_be_visible()
            results.append('团队菜单新增与即时共享、管理弹窗')

            workspace.locator('.chat-workspace__session').filter(has=page.locator('.chat-workspace__session-title strong',has_text='验收提出人')).click()
            composer=page.locator('.project-chat-window:visible .group-composer')
            choose(composer.locator('.chat-send-topic'),'资源开拓讨论 / 高校渠道')
            composer.get_by_placeholder('输入消息',exact=True).fill('浏览器验收私聊高校主题')
            composer.get_by_role('button',name='发送',exact=True).click()
            expect(page.locator('.project-chat-window:visible .group-message').filter(has_text='浏览器验收私聊高校主题')).to_contain_text('高校渠道')
            workspace.locator('.chat-workspace__session').filter(has_text='开拓来源笔译项目').click()
            translation=page.locator('.project-chat-window:visible .project-chat-panel')
            expect(translation).to_be_visible()
            choose(translation.locator('.chat-topic-compose>.el-select'),'资源开拓讨论 / 高校渠道')
            translation.locator('.tiptap').fill('浏览器验收笔译高校主题')
            translation.get_by_role('button',name='发送',exact=True).click()
            expect(translation.locator('.chat-conversation-item').filter(has_text='浏览器验收笔译高校主题')).to_contain_text('高校渠道')
            results.append('单聊及笔译聊天复用分类组件与发送主题')

            workspace.get_by_role('button',name='最小化沟通',exact=True).click()
            page.goto(BASE+'/annotation-details')
            page.get_by_role('button',name='聊天大屏',exact=True).click()
            expect(page.locator('.chat-workspace__sessions .chat-topic-root').first.get_by_role('button').first).to_have_text('标注项目')
            page.set_viewport_size({'width':390,'height':844})
            page.wait_for_timeout(500)
            page.get_by_role('button',name='会话列表',exact=True).click()
            page.locator('.chat-workspace__session').filter(has_text='开拓来源标注项目').click()
            composer=page.locator('.project-chat-window:visible .group-composer')
            expect(composer).to_be_visible()
            composer.get_by_role('button',name='讨论主题 ▾',exact=True).click()
            page.locator('.chat-topic-popover:visible .chat-topic-menu').get_by_role('button',name='高校渠道',exact=True).click()
            search=page.get_by_role('dialog',name='资源开拓讨论 / 高校渠道 · 消息检索',exact=True)
            expect(search).to_be_visible()
            box=search.locator('.el-dialog').bounding_box()
            assert box['x'] >= 0 and box['x'] + box['width'] <= 390
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
            page.screenshot(path=str(OUTPUT/'chat-topics-mobile.png'), full_page=True)
            search.get_by_role('button',name='关闭',exact=True).click()
            page.get_by_role('button',name='最小化沟通',exact=True).click()
            page.goto(BASE+'/resource-management/resource-development?section=issues')
            page.get_by_role('button',name='新增开拓事项',exact=True).click()
            dialog=page.get_by_role('dialog',name='新增开拓事项',exact=True)
            expect(dialog).to_be_visible()
            dialog.get_by_role('button',name='保存',exact=True).click()
            expect(dialog.get_by_text('请填写内容',exact=True)).to_be_visible()
            assert page.evaluate("document.activeElement.tagName === 'TEXTAREA'")
            dialog.locator('textarea').first.fill('小屏未保存草稿')
            choose(dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text='类别')).locator('.el-select'),'执行类')
            for position in (0,100000):
                dialog.locator('.el-dialog__body').evaluate('(el,value)=>el.scrollTop=value',position)
                box=dialog.locator('.el-dialog__footer').bounding_box()
                assert box and box['y']>=0 and box['y']+box['height']<=844
            page.screenshot(path=str(OUTPUT/'chat-topics-mobile-form.png'),full_page=True)
            dialog.get_by_role('button',name='取消',exact=True).click()
            page.get_by_role('button',name='放弃修改',exact=True).click()
            expect(dialog).not_to_be_visible()
            results.append('标注入口优先、小窗主题浮层、小屏检索/表单/固定底栏与校验定位')
            assert not errors, errors
            assert not [url for _,url in requests if urlparse(url).port in (3000,8000)], '浏览器误连日常服务'
            (OUTPUT/'chat-topics-ui-result.json').write_text(json.dumps({'passed':results,'page_errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'passed':results,'page_errors':errors},ensure_ascii=False))
        except Exception:
            page.screenshot(path=str(OUTPUT/'chat-topics-failure.png'),full_page=True)
            (OUTPUT/'chat-topics-failure.html').write_text(page.content(),encoding='utf-8')
            raise
        finally:
            browser.close()


if __name__=='__main__': run()
