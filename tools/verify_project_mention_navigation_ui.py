"""本机真实聊天大屏组件验收；全部业务请求隔离为浏览器测试数据。"""
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://localhost:3000/__project_mention_navigation_check'
HTML = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<link rel="stylesheet" href="/node_modules/element-plus/dist/index.css">
<style>html,body,#app{height:100%;margin:0;font-family:Arial,"Microsoft YaHei",sans-serif}</style>
<div id="app"></div><script type="module">
import { createApp, h } from '/node_modules/.vite/deps/vue.js';
import { createRouter, createMemoryHistory } from '/node_modules/.vite/deps/vue-router.js';
import ElementPlus from '/node_modules/.vite/deps/element-plus.js';
import Dock from '/src/components/chat/ProjectChatDock.vue';
import { useProjectChatDock } from '/src/composables/useProjectChatDock.js';
localStorage.clear();localStorage.setItem('user_id','mention-test');
localStorage.setItem('xinshi.chatGroup.mention-test','annotation');
window.dock=useProjectChatDock();window.dock.ensurePreferences();
Object.assign(window.dock.state,{layout:'workspace',workspaceOpened:true,workspaceMaximized:true,maximizedFrom:'workspace'});
const app=createApp({render:()=>h(Dock)});
app.use(createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]}));
app.use(ElementPlus);app.mount('#app');
</script></html>'''


def run():
    output = ROOT / 'outputs/project-mention-navigation'
    output.mkdir(parents=True, exist_ok=True)
    dependency_hash = json.loads((ROOT / 'frontend/node_modules/.vite/deps/_metadata.json').read_text(encoding='utf-8'))['browserHash']
    html = re.sub(r"(/node_modules/\.vite/deps/[^']+\.js)'", rf"\1?v={dependency_hash}'", HTML)
    projects = [dict(key=f'annotation:{i}', project_id=str(i), kind='annotation', title=f'测试项目{i}',
                     subtitle=f'AP-{i}', project_status='trial_in_progress', following=True, unread=0, mention_unread=0)
                for i in range(1, 5)]
    projects[0].update(mention_unread=1, mention_message_ids=['m55'])
    messages = [dict(message_id=f'm{i}', sequence_no=i, key='annotation:1', project_id='1', project_type='annotation',
                     title='测试项目1', sender_name='测试同事', preview=f'需要确认的提及 {i}', unread=i == 55,
                     created_at='2026-10-14T10:00:00+08:00') for i in range(1, 56)]
    messages.append(dict(messages[0], message_id='other', sequence_no=56, key='annotation:2', project_id='2', title='测试项目2'))
    requests, errors = [], []

    def api(route):
        parsed = urlparse(route.request.url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        requests.append((parsed.path, params, route.request.method))
        body = dict(items=[], total=0, ready=True, phase_one_enabled=True)
        if parsed.path == '/api/chat/sessions':
            body.update(items=projects, mention_history_total=len(messages), annotation_mention_counts=[
                dict(project_id='1', count=55), dict(project_id='2', count=1)])
        elif parsed.path == '/api/chat/mentions':
            rows = sorted([m for m in messages if not params.get('project_id') or m['project_id'] == params['project_id']],
                          key=lambda m: m['sequence_no'], reverse=True)
            total = len(rows)
            rows = [m for m in rows if not params.get('before') or m['sequence_no'] < int(params['before'])]
            limit = int(params.get('limit', 50)); more = len(rows) > limit; rows = rows[:limit]
            body = dict(items=rows, total=total, has_more=more, next_before=rows[-1]['sequence_no'] if more else None)
        elif parsed.path.endswith('/group'):
            body = dict(members=[], eligible_users=[], following=True, last_read_sequence=0)
        elif parsed.path.endswith('/timeline'):
            pid = parsed.path.split('/')[-2]
            matches = [m for m in messages if m['project_id'] == pid]
            target = params.get('around')
            rows = [m for m in matches if m['message_id'] == target] if target else matches[-1:]
            body = dict(items=[dict(id=m['message_id'], sequence_no=m['sequence_no'], sender_user_id='peer',
                                   sender_name=m['sender_name'], content=m['preview'], created_at=m['created_at'],
                                   message_type='user', attachments=[], mentions=[]) for m in rows], has_more=False)
        elif parsed.path.startswith('/api/annotation-projects/'):
            body = dict(project_name='测试项目', order_no='AP-TEST', project_status='trial_in_progress')
        route.fulfill(status=200, content_type='application/json', body=json.dumps(body, ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', args=['--disable-features=LocalNetworkAccessChecks'])
        page = browser.new_page(viewport={'width': 1239, 'height': 884})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('http://localhost:3000/api/**', api)
        page.route(URL, lambda route: route.fulfill(content_type='text/html', body=html))
        page.goto(URL)
        filters = page.locator('.chat-workspace__annotation-filters')
        expect(filters).to_be_visible(timeout=30000)
        # 普通会话列表也有入口；打开项目不查询提及、不定位历史。
        page.locator('.chat-workspace__session').filter(has_text='测试项目1').locator('strong').click()
        nav = page.get_by_role('region', name='提及消息导航').filter(visible=True)
        expect(nav).to_contain_text('@我 55 条')
        unread = page.get_by_role('button', name='1 条消息@了你', exact=True)
        expect(unread).to_be_visible()
        nav_box, unread_box = nav.bounding_box(), unread.bounding_box()
        assert unread_box['y'] >= nav_box['y'] + nav_box['height']
        expect(nav.get_by_role('button', name='更新的提及')).to_be_disabled()
        assert not any(path == '/api/chat/mentions' for path, _, _ in requests)
        assert not any(params.get('around') for _, params, _ in requests)
        nav.get_by_role('button', name='定位最新提及').click()
        expect(nav).to_contain_text('@我 1/55')
        nav.get_by_role('button', name='更早的提及').click()
        expect(nav).to_contain_text('@我 2/55')
        nav.get_by_role('button', name='更新的提及').click()
        expect(nav).to_contain_text('@我 1/55')
        filters.get_by_role('button', name='@我', exact=True).click()
        expect(page.locator('.chat-workspace__session')).to_have_count(2)
        # 预览其他项目不影响当前导航对象。
        page.get_by_role('button', name='查看 1 条历史提及', exact=True).click()
        expect(page.get_by_role('region', name='项目内提及消息').filter(visible=True).locator('.project-mention-list__item')).to_have_count(1)
        expect(nav).to_contain_text('@我 1/55')
        page.locator('.chat-workspace__heading').click()
        timeline_count = sum(path.endswith('/timeline') for path, _, _ in requests)
        page.get_by_role('button', name='查看 55 条历史提及', exact=True).click()
        popup = page.get_by_role('region', name='项目内提及消息').filter(visible=True)
        expect(popup).to_have_count(1)
        expect(popup.locator('.project-mention-list__item')).to_have_count(50)
        # 摘要打开不会打开会话或发送已读请求。
        assert sum(path.endswith('/timeline') for path, _, _ in requests) == timeline_count
        page.screenshot(path=str(output / 'summary-desktop.png'))
        popup.get_by_role('button', name=re.compile('需要确认的提及 6$')).click()
        expect(nav).to_contain_text('@我 50/55')
        expect(page.locator('[data-message-id="m6"]')).to_have_class(re.compile('group-message--highlight'))
        nav.get_by_role('button', name='更早的提及').click()
        expect(nav).to_contain_text('@我 51/55')
        expect(page.locator('[data-message-id="m5"]')).to_have_class(re.compile('group-message--highlight'))
        nav.get_by_role('button', name='更新的提及').click()
        expect(nav).to_contain_text('@我 50/55')
        nav.get_by_role('button', name='消息列表').click()
        popup = page.get_by_role('region', name='项目内提及消息').filter(visible=True)
        expect(popup).to_have_count(1)
        expect(popup.locator('.project-mention-list__item')).to_have_count(55)
        popup.get_by_role('button', name=re.compile('需要确认的提及 1$')).click()
        expect(nav.get_by_role('button', name='更早的提及')).to_be_disabled()
        expect(popup).to_have_count(0)
        page.screenshot(path=str(output / 'navigation-desktop.png'))
        # 新消息刷新保留锚点，不改变聊天原文。
        messages.append(dict(messages[0], message_id='new', sequence_no=100, preview='新增提及'))
        page.wait_for_timeout(15500)
        expect(nav).to_contain_text('@我 56/56')
        expect(page.locator('[data-message-id="m1"]')).to_be_visible()
        # 普通窗口与小屏保持导航及输入可见，浮层不超出屏幕。
        page.get_by_role('button', name='还原窗口', exact=True).click()
        expect(nav).to_be_visible()
        page.screenshot(path=str(output / 'navigation-window.png'))
        page.set_viewport_size({'width': 390, 'height': 760})
        expect(nav).to_be_visible()
        nav.get_by_role('button', name='消息列表').click()
        popup = page.get_by_role('region', name='项目内提及消息').filter(visible=True)
        expect(popup).to_have_count(1)
        expect(popup).to_be_visible()
        box = popup.bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= 390
        assert box['y'] >= 0 and box['y'] + box['height'] <= 760
        page.screenshot(path=str(output / 'summary-mobile.png'))
        popup.get_by_role('button', name=re.compile('新增提及')).click()
        expect(nav.get_by_role('button', name='更新的提及')).to_be_disabled()
        expect(popup).to_have_count(0)
        page.screenshot(path=str(output / 'navigation-mobile.png'))
        nav.get_by_role('button', name='收起提及导航').click()
        expect(nav.get_by_role('button', name='展开提及导航')).to_be_visible()
        expect(page.locator('[data-message-id="new"]')).to_be_visible()
        nav.get_by_role('button', name='展开提及导航').click()
        expect(nav).to_contain_text('@我 1/56')
        page.get_by_role('button', name='会话列表', exact=True).click()
        page.get_by_role('button', name='查看 1 条历史提及', exact=True).click()
        popup = page.get_by_role('region', name='项目内提及消息').filter(visible=True)
        expect(popup).to_have_count(1)
        expect(popup.locator('.project-mention-list__item')).to_have_count(1)
        popup.locator('.project-mention-list__item').click()
        expect(nav).to_contain_text('@我 1/1')
        expect(nav.get_by_role('button', name='更新的提及')).to_be_disabled()
        expect(nav.get_by_role('button', name='更早的提及')).to_be_disabled()
        page.get_by_role('button', name='会话列表', exact=True).click()
        page.locator('.chat-workspace__session').filter(has_text='测试项目1').locator('strong').click()
        expect(nav.get_by_role('button', name='定位最新提及')).to_be_visible()
        # 同项目切换独立小窗保留锚点。
        nav.get_by_role('button', name='定位最新提及').click()
        expect(nav).to_contain_text('@我 1/56')
        page.set_viewport_size({'width': 1239, 'height': 884})
        page.evaluate("window.dock.setLayout('float')")
        first_window = page.locator('.project-chat-window').filter(has=page.locator('.project-chat-window__title-row').filter(has_text='测试项目1'))
        nav = first_window.get_by_role('region', name='提及消息导航')
        expect(nav).to_contain_text('@我 1/56')
        nav.get_by_role('button', name='更早的提及').click()
        expect(nav).to_contain_text('@我 2/56')
        page.screenshot(path=str(output / 'navigation-float.png'))
        second_window = page.locator('.project-chat-window').filter(has=page.locator('.project-chat-window__title-row').filter(has_text='测试项目2'))
        second_nav = second_window.get_by_role('region', name='提及消息导航')
        second_nav.get_by_role('button', name='定位最新提及').click()
        expect(second_nav).to_contain_text('@我 1/1')
        expect(nav.get_by_role('button', name='定位最新提及')).to_be_visible()
        assert not errors, errors
        assert all(params.get('project_type') == 'annotation' for path, params, _ in requests if path == '/api/chat/mentions')
        browser.close()
    print('项目内提及摘要、跨页定位、锚点刷新、普通窗口与小屏验收通过')


if __name__ == '__main__':
    run()
