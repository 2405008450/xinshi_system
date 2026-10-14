"""通过本机 Vite 加载真实聊天组件，所有业务接口使用浏览器内隔离数据。"""
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
URL = 'http://localhost:3000/__chat_status_check'
HTML = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<link rel="stylesheet" href="/node_modules/element-plus/dist/index.css">
<style>html,body,#app{height:100%;margin:0;font-family:Arial,"Microsoft YaHei",sans-serif}</style>
<div id="app"></div><script type="module">
import { createApp, h, reactive } from '/node_modules/.vite/deps/vue.js';
import { createRouter, createMemoryHistory } from '/node_modules/.vite/deps/vue-router.js';
import ElementPlus from '/node_modules/.vite/deps/element-plus.js';
import ChatWorkspace from '/src/components/chat/ChatWorkspace.vue';
localStorage.setItem('user_id','chat-status-ui');
localStorage.setItem('xinshi.chatGroup.chat-status-ui','annotation');
const statuses = ['initial_consultation','trial_preparation','trial_in_progress','project_in_progress','client_feedback','paused'];
const names = ['咨询项目','准备项目','试标项目','进行项目','反馈项目','暂停项目'];
window.fixture = reactive({ maximized:true, narrow:false, sidebarOpen:true, sessionWidth:300,
  sessions:statuses.map((status,i)=>({key:'annotation:'+i,projectId:String(i),projectType:'annotation',
    title:names[i],subtitle:'AP-'+i,projectStatus:status,mentionHistoryCount:i===2?55:i===4?1:0,unread:i===2?1:0,mentionUnread:i===2?1:0})),
  mentionHistoryTotal:58 });
window.fixture.sessions.push({key:'direct:1',projectId:'1',projectType:'direct',title:'单聊同事'});
const app=createApp({render:()=>h(ChatWorkspace,{...window.fixture,
  onLocateMention:item=>window.located=item.messageId,
  onToggleMaximize:()=>window.fixture.maximized=!window.fixture.maximized})});
app.use(createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]}));
app.use(ElementPlus);app.mount('#app');
</script></html>'''


def run():
    output = ROOT / 'outputs' / 'chat-status-filter'
    output.mkdir(parents=True, exist_ok=True)
    # 与 Vite 编译后的组件使用相同依赖 URL，避免 Vue Router 注入键出现两个实例。
    dependency_hash = json.loads((ROOT / 'frontend/node_modules/.vite/deps/_metadata.json').read_text(encoding='utf-8'))['browserHash']
    html = re.sub(r"(/node_modules/\.vite/deps/[^']+\.js)'", rf"\1?v={dependency_hash}'", HTML)
    requests = []
    messages = [dict(message_id=f'm{i}', sequence_no=i, key='annotation:2', project_id='2',
                     project_type='annotation', title='试标项目', subtitle='AP-2', sender_name='测试同事',
                     preview=f'确认试标 {i}', unread=i == 55, created_at='2026-10-13T10:00:00+08:00',
                     status='trial_in_progress') for i in range(1, 56)]
    messages.extend([dict(messages[0], message_id='feedback', sequence_no=56, title='反馈项目',
                          project_id='4', key='annotation:4', status='client_feedback', preview='反馈内容'),
                     dict(messages[0], message_id='outside', sequence_no=58, title='目录外历史项目',
                          project_id='99', key='annotation:99', status='trial_in_progress', preview='目录外提及'),
                     dict(messages[0], message_id='translation', sequence_no=57, title='笔译项目',
                          project_type='translation', status='', preview='笔译内容')])

    def api(route):
        parsed = urlparse(route.request.url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if parsed.path == '/api/chat/mentions':
            requests.append(params)
            rows = [m for m in messages if (not params.get('project_type') or m['project_type'] == params['project_type'])
                    and (not params.get('project_status') or m['status'] == params['project_status'])
                    and (not params.get('keyword') or params['keyword'] in m['preview'] or params['keyword'] in m['title'])]
            total = len(rows)
            rows = sorted((m for m in rows if not params.get('before') or m['sequence_no'] < int(params['before'])),
                          key=lambda m: m['sequence_no'], reverse=True)
            limit = int(params.get('limit', 50)); more = len(rows) > limit; rows = rows[:limit]
            body = dict(items=rows, total=total, has_more=more, next_before=rows[-1]['sequence_no'] if more else None)
        else:
            body = dict(items=[], total=0, ready=True, phase_one_enabled=True)
        route.fulfill(status=200, content_type='application/json', body=json.dumps(body, ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', args=['--disable-features=LocalNetworkAccessChecks'])
        page = browser.new_page(viewport={'width': 1233, 'height': 884})
        errors = []
        page.on('pageerror', lambda e: (errors.append(str(e)), print(str(e), flush=True)))
        page.on('console', lambda m: print(m.text, flush=True) if m.type == 'error' else None)
        page.route('http://localhost:3000/api/**', api)
        page.route(URL, lambda route: route.fulfill(status=200, content_type='text/html', body=html))
        page.goto(URL)
        filters = page.locator('.chat-workspace__annotation-filters')
        rows = page.locator('.chat-workspace__session')
        expect(filters).to_be_visible(timeout=30000)
        expect(rows).to_have_count(6)
        expect(filters.get_by_role('button', name='不限状态', exact=True)).to_contain_text('(6)')
        expect(filters.get_by_role('button', name='更多状态', exact=True)).to_contain_text('(1)')
        trial_status = filters.get_by_role('button', name='试标中', exact=True)
        expect(trial_status).to_contain_text('(1)')
        expect(trial_status).to_contain_text('@我')
        expect(trial_status).to_have_css('color', 'rgb(185, 28, 28)')
        expect(filters.get_by_role('button', name='客户反馈', exact=True)).not_to_contain_text('@我')
        for label in ['初步咨询', '试标准备', '试标中', '项目进行中', '客户反馈']:
            filters.get_by_role('button', name=label, exact=True).click()
            expect(rows).to_have_count(1)
        filters.get_by_role('button', name='试标中', exact=True).click()
        expect(rows.locator('.chat-mention-label')).to_have_text('[有人@我] ')
        assert rows.locator('strong').evaluate('(el)=>getComputedStyle(el).color') == 'rgb(185, 28, 28)'
        page.screenshot(path=str(output / 'desktop.png'))
        # 收起只隐藏状态选项，保留筛选、项目数、未读提示和会话/提及切换。
        list_height = page.locator('.chat-workspace__list').bounding_box()['height']
        filters.get_by_role('button', name='收起状态筛选', exact=True).click()
        summary = filters.get_by_role('button', name='展开状态筛选', exact=True)
        expect(summary).to_have_attribute('aria-expanded', 'false')
        expect(summary).to_contain_text('试标中 (1)')
        expect(summary).to_contain_text('@我')
        expect(page.get_by_role('group', name='标注项目状态', exact=True)).to_be_hidden()
        expect(rows).to_have_count(1)
        assert page.locator('.chat-workspace__list').bounding_box()['height'] > list_height + 40
        page.screenshot(path=str(output / 'collapsed.png'))
        filters.get_by_role('button', name='@我', exact=True).click()
        expect(rows).to_have_count(1)
        expect(rows).to_contain_text('55 条历史提及')
        expect(page.locator('.chat-workspace__result-count')).to_have_text('1 个会话')
        expect(page.locator('.chat-mention-inbox')).to_have_count(0)
        expect(summary).to_be_visible()
        summary.press('Enter')
        expect(filters.get_by_role('button', name='收起状态筛选', exact=True)).to_have_attribute('aria-expanded', 'true')
        expect(trial_status).to_contain_text('(1)')
        # 已读仅取消着色，不移除含历史提及的项目。
        page.evaluate('window.fixture.sessions[2].mentionUnread=0')
        expect(rows).to_have_count(1)
        expect(rows).not_to_have_class(re.compile('has-unread-mention'))
        search = page.get_by_placeholder('搜索名称、订单号、消息')
        search.fill('准备项目')
        expect(rows).to_have_count(0)
        search.fill('试标项目')
        expect(rows).to_have_count(1)
        search.fill('')
        filters.get_by_role('button', name='客户反馈', exact=True).click()
        expect(rows).to_have_count(1)
        expect(rows).to_contain_text('反馈项目')
        filters.get_by_role('button', name='试标准备', exact=True).click()
        expect(rows).to_have_count(0)
        assert not requests, '项目内 @我 不应请求全局消息收件箱'
        filters.get_by_role('button', name='全部会话', exact=True).click()
        filters.get_by_role('button', name='更多状态').click()
        popup = page.locator('.chat-status-popover:visible')
        expect(popup.get_by_role('button', name='暂停', exact=True)).to_contain_text('(1)')
        expect(popup.get_by_role('button', name='已结束', exact=True)).to_contain_text('(0)')
        popup.get_by_role('button', name='暂停', exact=True).click()
        expect(rows).to_contain_text('暂停项目')
        expect(popup).to_have_count(0)
        filters.get_by_role('button', name='不限状态', exact=True).click()
        expect(rows).to_have_count(6)
        page.evaluate("window.fixture.sessions[2].mentionUnread=0; window.fixture.sessions[2].projectStatus='client_feedback'")
        filters.get_by_role('button', name='试标中', exact=True).click()
        expect(rows).to_have_count(0)
        expect(trial_status).to_contain_text('(0)')
        expect(trial_status).not_to_contain_text('@我')
        filters.get_by_role('button', name='客户反馈', exact=True).click()
        expect(rows).to_have_count(2)
        expect(filters.get_by_role('button', name='客户反馈', exact=True)).to_contain_text('(2)')
        expect(page.locator('.has-unread-mention')).to_have_count(0)

        def group(label):
            page.get_by_role('button', name=re.compile('^会话分组 ')).click()
            page.locator('.chat-session-popover:visible').get_by_role('button', name=re.compile('^' + re.escape(label) + r' \(')).click()
            page.locator('.chat-workspace__stage').click(position={'x': 30, 'y': 100})

        group('单聊'); expect(rows).to_have_count(1); expect(filters).to_have_count(0)
        group('@我')
        items = page.locator('.chat-mention-inbox__message')
        expect(items).to_have_count(50)
        expect(page.locator('.chat-mention-inbox__heading')).to_contain_text('58 条')
        assert not requests[-1].get('project_status') and not requests[-1].get('project_type')
        page.get_by_role('button', name='加载更多', exact=True).click()
        expect(items).to_have_count(58)
        items.first.click()
        assert page.evaluate('window.located') == 'outside'
        search.fill('确认试标 55')
        expect(items).to_have_count(1)
        search.fill('')
        expect(items).to_have_count(50)
        group('标注项目群')
        page.evaluate('window.fixture.maximized=false')
        page.locator('#app').evaluate("el=>{el.style.width='760px';el.style.height='680px'}")
        expect(filters).to_be_visible()
        page.screenshot(path=str(output / 'window.png'))
        page.set_viewport_size({'width': 390, 'height': 700})
        page.locator('#app').evaluate("el=>{el.style.width='100%';el.style.height='100%'}")
        page.evaluate('window.fixture.narrow=true;window.fixture.sessionWidth=280')
        page.evaluate('window.fixture.sessions[5].mentionUnread=2')
        expect(filters.get_by_role('button', name='更多状态', exact=True)).to_contain_text('@我')
        filters.get_by_role('button', name='更多状态').click()
        expect(popup).to_be_visible()
        expect(popup).to_have_css('opacity', '1')
        expect(popup.get_by_role('button', name='暂停', exact=True)).to_have_css('color', 'rgb(185, 28, 28)')
        expect(popup.get_by_role('button', name='暂停', exact=True)).to_contain_text('@我')
        box = popup.bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= 390
        assert box['y'] >= 0 and box['y'] + box['height'] <= 700, box
        assert popup.locator('.chat-session-groups').evaluate('el=>el.scrollHeight>el.clientHeight')
        page.screenshot(path=str(output / 'mobile.png'))
        popup.get_by_role('button', name='已结束', exact=True).click()
        expect(rows).to_have_count(0)
        expect(filters.get_by_role('button', name='已结束', exact=True)).to_contain_text('(0)')
        filters.get_by_role('button', name='已结束', exact=True).click()
        popup.get_by_role('button', name='暂停', exact=True).click()
        expect(filters.get_by_role('button', name='暂停', exact=True)).to_contain_text('(1)')
        expect(filters.get_by_role('button', name='暂停', exact=True)).to_contain_text('@我')
        page.evaluate('window.fixture.sessions[5].mentionUnread=0')
        expect(filters.get_by_role('button', name='暂停', exact=True)).not_to_contain_text('@我')
        filters.get_by_role('button', name='暂停', exact=True).click()
        expect(popup).to_be_visible()
        # 即使更多状态小窗打开，收起也必须同时关闭它，不能留下悬空浮层。
        filters.get_by_role('button', name='收起状态筛选', exact=True).click()
        expect(popup).to_have_count(0)
        expect(filters.get_by_role('button', name='展开状态筛选', exact=True)).to_contain_text('暂停 (1)')
        page.evaluate('window.fixture.sessions[2].mentionUnread=1')
        expect(filters.get_by_role('button', name='展开状态筛选', exact=True)).to_contain_text('@我')
        expect(filters.get_by_role('button', name='展开状态筛选', exact=True)).to_have_attribute('title', re.compile('其他状态有未读 @我'))
        page.screenshot(path=str(output / 'mobile-collapsed.png'))
        # 复现用户的四个项目目录：消息再多也只能筛出原目录的子集。
        page.set_viewport_size({'width': 1233, 'height': 884})
        page.evaluate("window.fixture.narrow=false;window.fixture.maximized=true;window.fixture.sessionWidth=300;window.fixture.sessions=window.fixture.sessions.filter(s=>['annotation:0','annotation:2','annotation:4','annotation:5'].includes(s.key))")
        filters.get_by_role('button', name='展开状态筛选', exact=True).click()
        filters.get_by_role('button', name='不限状态', exact=True).click()
        filters.get_by_role('button', name='全部会话', exact=True).click()
        expect(rows).to_have_count(4)
        before_titles = set(rows.locator('.chat-workspace__session-title strong').all_text_contents())
        page.screenshot(path=str(output / 'four-projects.png'))
        filters.get_by_role('button', name='@我', exact=True).click()
        expect(rows).to_have_count(2)
        expect(page.locator('.chat-workspace__result-count')).to_have_text('2 个会话')
        after_titles = set(rows.locator('.chat-workspace__session-title strong').all_text_contents())
        assert after_titles <= before_titles and '目录外历史项目' not in after_titles
        page.screenshot(path=str(output / 'two-mentioned-projects.png'))
        page.evaluate('window.fixture.sessions.forEach(s=>s.mentionHistoryCount=0)')
        expect(rows).to_have_count(0)
        assert not errors, errors
        browser.close()
    print('通过：四个项目筛为两个项目、排除目录外历史消息、已读提及保留、状态区展开/收起、保留筛选和提及切换、键盘展开、列表空间回收、浮层关闭、项目数与未读提示、普通/最大化/小屏布局。')
    print(f'截图：{output}')


if __name__ == '__main__':
    run()
