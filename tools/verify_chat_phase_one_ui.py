"""在实际页面验收聊天；全部 HTTP API 和 WebSocket 均由合成夹具拦截。"""
import json
import re
import socket
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://localhost:3000'


def run(legacy=False, verify_layout=None):
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('仅允许在 PC 本机验收')
    output = ROOT / ('.tmp/chat-legacy-mention-ui' if legacy else '.tmp/chat-phase-one-ui')
    output.mkdir(parents=True, exist_ok=True)
    me, other, annotation, translation, direct, translator, unassigned, badge_direct, badge_message = [str(uuid4()) for _ in range(9)]
    names = {me: '验收甲', other: '验收乙'}
    messages = {annotation: [], translation: [], direct: []}
    reads, prefs, sockets, requests, errors = {}, {}, [], [], []
    opened = [False]
    notification_read = [False]
    serial = [0]

    def message(scope, sender, content, mentioned=False):
        serial[0] += 1
        row = dict(id=str(uuid4()), project_id=scope, sender_user_id=sender, sender_name=names[sender],
            content=content, message_type='user', sequence_no=serial[0], created_at='2026-10-10T09:18:43Z',
            mentions=[dict(mentioned_user_id=me, mentioned_user_name=names[me])] if mentioned else [],
            attachments=[], acknowledgements=[], acknowledgement_count=0, is_acknowledged=False, is_favorited=False,
            recalled_at=None, can_recall=sender == me, metadata={})
        messages[scope].append(row)
        return row
    mention = message(annotation, other, '@验收甲 第一条待确认的标注消息', True)
    for i in range(45): message(annotation, other, f'标注历史消息 {i + 1}')
    translation_mention = message(translation, other, '@验收甲 笔译检查', True)

    def notify(scope, kind):
        payload = json.dumps(dict(type='direct_chat_changed' if scope == direct else 'annotation_chat_changed', projectId=scope, kind=kind), ensure_ascii=False)
        for ws in sockets:
            try: ws.send(payload)
            except Exception: pass

    def session_rows(user):
        result = []
        for scope, kind, title, subtitle in [(annotation, 'annotation', '阶段一标注', 'AN-QA-001'), (translation, 'translation', '阶段一笔译', 'TP-QA-001'), (direct, 'direct', names[other if user == me else me], '内部私聊')]:
            if legacy and kind != 'annotation': continue
            if scope == direct and not opened[0]: continue
            visible = [m for m in messages[scope] if not m['recalled_at'] and m['sender_user_id'] != user and m['sequence_no'] > reads.get((user, scope), 0)]
            mentions = [m['id'] for m in visible if any(u['mentioned_user_id'] == user for u in m['mentions'])]
            last = messages[scope][-1] if messages[scope] else None
            result.append(dict(key=f'{kind}:{scope}', kind=kind, project_id=scope, title=title, subtitle=subtitle,
                unread=len(visible), mention_unread=len(mentions), mention_message_ids=mentions,
                pinned=prefs.get((user, scope), {}).get('pinned', False), starred=prefs.get((user, scope), {}).get('starred', False),
                is_creator=scope == annotation, last_message=dict(id=last['id'], preview=last['recall_label'] if last['recalled_at'] else last['content'], sender_name=last['sender_name'], created_at=last['created_at'], mentions_me=not last['recalled_at'] and any(u['mentioned_user_id'] == user for u in last['mentions'])) if last else None))
        if not legacy:
            result.append(dict(key=f'direct:{badge_direct}', kind='direct', project_id=badge_direct, title='译员丁', subtitle='内部私聊',
                unread=2, mention_unread=0, mention_message_ids=[], pinned=False, starred=False, is_creator=False,
                last_message=dict(id=badge_message, preview='未读角标', sender_name='译员丁', created_at='2026-10-10T09:00:00Z', mentions_me=False)))
        return result

    def mention_rows(user, keyword=''):
        result = []
        for session in session_rows(user):
            scope = session['project_id']
            for row in messages.get(scope, []):
                if row['recalled_at'] or not any(m['mentioned_user_id'] == user for m in row['mentions']):
                    continue
                if keyword and keyword not in ' '.join((session['title'], session['subtitle'], row['sender_name'], row['content'])):
                    continue
                result.append(dict(message_id=row['id'], sequence_no=row['sequence_no'], key=session['key'],
                    project_id=scope, project_type=session['kind'], title=session['title'], subtitle=session['subtitle'],
                    sender_name=row['sender_name'], preview=row['content'] or '[附件]', created_at=row['created_at'],
                    unread=row['sequence_no'] > reads.get((user, scope), 0)))
        return sorted(result, key=lambda row: row['sequence_no'], reverse=True)

    def pane_button(target, label):
        rail = target.locator(f'.chat-workspace__rail button[aria-label="{label}"]')
        if rail.count() and rail.is_visible():
            return rail
        return target.locator('.chat-workspace__pane-tabs button', has_text=label)

    def handle(route, user):
        req = route.request
        if not urlparse(req.url).path.startswith('/api/'):
            route.continue_()
            return
        path = urlparse(req.url).path.removeprefix('/api').rstrip('/')
        query = parse_qs(urlparse(req.url).query)
        requests.append((req.method, path))
        result, status = {}, 200
        if path == '/auth/session': result = dict(user_id=user, username='qa', full_name=names[user], roles=['admin'], permissions=['*'])
        elif path == '/chat/sessions':
            items = session_rows(user)
            result = dict(items=items, total=sum(s['unread'] for s in items), mention_total=sum(s['mention_unread'] for s in items),
                mention_history_total=len(mention_rows(user)), phase_one_enabled=not legacy)
        elif path == '/chat/mentions':
            rows = mention_rows(user, (query.get('keyword') or [''])[0]); total = len(rows)
            if query.get('before'): rows = [row for row in rows if row['sequence_no'] < int(query['before'][0])]
            limit = int((query.get('limit') or ['50'])[0]); more = len(rows) > limit; rows = rows[:limit]
            result = dict(items=rows, total=total, has_more=more, next_before=rows[-1]['sequence_no'] if more else None)
        elif path == '/chat/users':
            scope = (query.get('scope') or ['search'])[0]
            text = (query.get('keyword') or [''])[0].strip()
            peer = other if user == me else me
            rows = [dict(row) for row in (
                dict(id=me, name=names[me], username='qa-jia', department='项目部'),
                dict(id=other, name=names[other], username='internal-qa', department='项目部'),
                dict(id=translator, name='译员丁', username='translator-ding', department='译员部', conversation_id=badge_direct),
                dict(id=unassigned, name='未分配丙', username='unassigned-bing', department=None),
            ) if row['id'] != user]
            if opened[0]:
                for row in rows:
                    if row['id'] == peer: row['conversation_id'] = direct
            if text:
                rows = [row for row in rows if text in row['name'] or text in row['username'] or text in (row['department'] or '')]
            recent = [dict(user_id=translator, conversation_id=badge_direct, last_message_at='2026-10-10T09:00:00+08:00')]
            if opened[0]: recent.insert(0, dict(user_id=peer, conversation_id=direct, last_message_at='2026-10-10T10:00:00+08:00'))
            result = dict(recent=recent) if scope == 'recent' else dict(items=rows, recent=recent, self=dict(id=user, name=names.get(user, '我'), username='qa', department='项目部'))
        elif path == '/chat/direct/conversations': opened[0] = True; result = dict(id=direct, title=names[other if user == me else me], subtitle='内部私聊')
        elif path.startswith('/chat/sessions/'):
            scope = path.split('/')[4]; data = req.post_data_json
            prefs.setdefault((user, scope), {}).update({k: v for k, v in data.items() if k in ('pinned', 'starred')})
            if data.get('mark_read'): reads[(user, scope)] = serial[0]
            if data.get('read_message_id'): reads[(user, scope)] = next(m['sequence_no'] for m in messages[scope] if m['id'] == data['read_message_id'])
        elif path == f'/chat/mentions/{mention["id"]}/target': result = dict(message_id=mention['id'])
        elif path.startswith('/chat/direct/') or path.startswith('/project-chat/annotation/'):
            scope = direct if path.startswith('/chat/direct/') else annotation
            suffix = path.split(scope + '/')[-1]
            if suffix == 'group': result = dict(members=[dict(id=u, name=n) for u, n in names.items()], eligible_users=[] if scope == direct else [dict(id=u, name=n) for u,n in names.items()], following=True, last_read_sequence=reads.get((user, scope), 0))
            elif suffix == 'timeline':
                rows = messages[scope]
                if query.get('around'):
                    anchor = next(m for m in rows if m['id'] == query['around'][0])
                    rows = [m for m in rows if abs(m['sequence_no'] - anchor['sequence_no']) < 20]
                elif query.get('after'): rows = [m for m in rows if m['sequence_no'] > int(query['after'][0])]
                elif query.get('before'): rows = [m for m in rows if m['sequence_no'] < int(query['before'][0])][-30:]
                else: rows = rows[-30:]
                result = dict(items=rows, has_more=False)
            elif suffix == 'refresh': result = dict(items=[m for m in messages[scope] if m['id'] in req.post_data_json['message_ids']])
            elif suffix == 'messages': result = message(scope, user, req.post_data_json['content']); result['client_message_id'] = req.post_data_json['client_message_id']; notify(scope, 'message')
            elif suffix == 'read':
                target = next(m for m in messages[scope] if m['id'] == req.post_data_json['message_id'])
                reads[(user, scope)] = max(reads.get((user, scope), 0), target['sequence_no']); notify(scope, 'state')
                result = dict(last_read_sequence=reads[(user, scope)])
            elif suffix.endswith('/recall'):
                target = next(m for m in messages[scope] if m['id'] == suffix.split('/')[1]); target.update(recalled_at='2026-10-10T18:00:00+08:00', recall_label='验收甲撤回了一条消息', content=''); result = target; notify(scope, 'recall')
            elif suffix == 'history': result = dict(items=[], counts=dict(all=0,image=0,link=0,file=0), next_cursor=None)
        elif path == f'/project-chat/{translation}/messages': result = dict(items=messages[translation][::-1], total=len(messages[translation]), enabled=True, can_manage=False)
        elif path == f'/projects/annotation/{annotation}': result = dict(id=annotation, project_name='阶段一标注', order_no='AN-QA-001', project_status='in_progress', project_types=[], remarks='合成项目', created_at='2026-10-10T09:18:43Z')
        elif path.startswith(f'/projects/annotation/{annotation}/'): result = []
        elif path == f'/projects/translation/{translation}': result = dict(id=translation, project_name='阶段一笔译', order_no='TP-QA-001', project_status='in_progress', created_at='2026-10-10T09:18:43Z')
        elif path == '/annotation-ops/custom-fields': result = []
        elif path.startswith('/notifications'):
            if path.endswith('/read') or path.endswith('/read-all'): notification_read[0] = True
            elif path.endswith('unread-count'): result = dict(count=int(user == me and not notification_read[0]))
            elif user == me and not notification_read[0]: result = [dict(id=mention['id'], notification_type='annotation_project_chat_mention', title='@验收甲提醒', content='点击定位第一条消息', is_read=False, related_project_type='annotation', related_entity_id=annotation, created_at='2026-10-10T09:18:43Z')]
            else: result = []
        elif path == '/talents/duplicate-review/groups': result = dict(items=[],total=0, counts=dict(pending=0, confirmed_same=0,confirmed_different=0,deferred=0))
        elif path == '/users': result = [dict(id=u, username='qa', full_name=n, is_active=True) for u,n in names.items()]
        route.fulfill(status=status, json=result)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        contexts = []
        for user in (me, other):
            context = browser.new_context(viewport=dict(width=1440,height=900), timezone_id='America/Los_Angeles')
            def handler(actor):
                def api(route): handle(route, actor)
                return api
            context.route('**/api/**', handler(user))
            context.route_web_socket('**/api/notifications/ws**', lambda ws: sockets.append(ws))
            context.add_init_script(f"localStorage.setItem('token','isolated-qa');localStorage.setItem('user_id','{user}');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"*\"]')")
            contexts.append(context)
        page = contexts[0].new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/resource-management/talent-duplicate-review?return=/resource-management/talents')
        page.wait_for_timeout(1500)
        page.screenshot(path=str(output / 'initial.png'), full_page=True)
        print(json.dumps(dict(url=page.url, errors=errors, requests=requests[-15:]), ensure_ascii=False), flush=True)
        page.locator('button[aria-label="会话"], button[aria-label="聊天大屏"]').first.click()
        workspace = page.locator('.chat-workspace-shell:visible')
        expect(workspace).to_be_visible()
        if verify_layout:
            verify_layout(page, workspace, contexts, errors, requests, output, me, other, annotation, translation, direct)
            browser.close()
            return
        expect(workspace.locator('.chat-workspace__session')).to_have_count(1 if legacy else 3)
        if not legacy:
            messages_tab = workspace.locator('.chat-workspace__rail button[aria-label="消息"]')
            expect(messages_tab).to_have_attribute('aria-pressed', 'true')
            expect(messages_tab.locator('.chat-mention-label')).to_have_text('@')
            expect(messages_tab.locator('.el-badge__content')).to_be_visible()
            expect(workspace.get_by_role('button', name='发起私聊', exact=True)).to_have_count(0)
        row = workspace.locator('.chat-workspace__session', has_text='阶段一标注')
        expect(row.locator('.chat-session-preview')).to_contain_text('[有人@我]')
        expect(row.locator('.chat-session-preview')).not_to_contain_text('暂无消息')
        page.locator('.mention-notification').click()
        expect(page.locator('.project-chat-window:visible').locator(f'[data-message-id="{mention["id"]}"]')).to_be_visible()
        assert ('GET', f'/chat/mentions/{mention["id"]}/target') in requests
        workspace.locator('.chat-workspace__session', has_text='阶段一标注').click()
        chat = page.locator('.project-chat-window:visible .annotation-group')
        expect(chat.get_by_role('button', name='1 条消息@了你')).to_be_visible()
        chat.get_by_role('button', name='1 条消息@了你').click()
        expect(chat.locator('.group-message--mentioned mark')).to_have_text('@验收甲')
        expect(chat.locator(f'[data-message-id="{mention["id"]}"]')).to_be_visible()
        expect(chat.get_by_role('button', name='1 条消息@了你')).to_have_count(0)
        # 已打开会话仍保留新提及提醒，点击定位后仅清除未读状态。
        latest_mention = message(annotation, other, '@验收甲 新到达的列表提及', True)
        notify(annotation, 'message')
        expect(row.locator('.chat-session-preview')).to_contain_text('[有人@我]')
        expect(row.locator('.chat-session-preview')).to_contain_text('新到达的列表提及')
        chat.get_by_role('button', name='1 条消息@了你').click()
        expect(row.locator('.chat-session-preview .chat-mention-label')).to_have_count(0)
        expect(row.locator('.chat-mention-preview')).to_have_text('[@我]')
        expect(row.locator('.el-badge__content:visible')).to_have_count(0)
        # 等待定位滚动完成后留存截图，避免截到滚动和角标消退动画的中间态。
        page.wait_for_timeout(500)
        page.screenshot(path=str(output / 'mention-read.png'), full_page=True)
        latest_mention.update(recalled_at='2026-10-10T18:00:00+08:00', recall_label='验收乙撤回了一条消息', content='')
        notify(annotation, 'recall')
        expect(row.locator('.chat-session-preview')).to_contain_text('验收乙撤回了一条消息')
        expect(row.locator('.chat-mention-preview')).to_have_count(0)
        if legacy:
            assert not errors, errors
            report = dict(checks=['旧结构真实预览', '列表未读@提示', '已打开群新提及保留提醒', '阅读后清除未读并保留末条@标记', '撤回同步清除标记'], requests=len(requests), errors=errors)
            (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False))
            browser.close()
            return
        workspace.get_by_role('button', name='项目详情', exact=True).click()
        expect(page.locator('.chat-project-popover:visible')).to_contain_text('AN-QA-001')
        page.locator('.chat-workspace__brand').click()
        workspace.get_by_role('button', name='项目资料', exact=True).click()
        materials = page.get_by_role('tooltip', name='项目资料', exact=True)
        expect(materials).to_contain_text('项目资料')
        assert materials.evaluate('(el)=>Number(getComputedStyle(el).zIndex)') >= 100000
        page.locator('.chat-workspace__brand').click()
        row = workspace.locator('.chat-workspace__session', has_text='阶段一标注')
        row.hover()
        row.hover()
        row.get_by_role('button', name='会话操作').click()
        page.locator('.chat-session-popover:visible').get_by_role('button', name='置顶', exact=True).click()
        expect(row.locator('[title="已置顶"]')).to_be_visible()
        page.locator('.chat-workspace__brand').click()
        pane_button(workspace, '通讯录').click()
        expect(workspace.locator('.chat-contacts__me')).to_contain_text('我')
        expect(workspace.locator('.chat-contacts__group').last).to_contain_text('未分配部门')
        workspace.locator('.chat-contact', has_text='验收乙').first.click()
        expect(pane_button(workspace, '消息')).to_have_attribute('aria-pressed', 'true')
        expect(workspace.locator('.chat-workspace__session.is-active')).to_contain_text('验收乙')
        expect(workspace.locator('.chat-workspace__session')).to_have_count(4)
        expect(workspace.get_by_role('button', name='项目详情', exact=True)).to_have_count(0)
        chat = page.locator('.project-chat-window:visible .annotation-group')
        chat.locator('textarea').fill('私聊验收消息')
        chat.get_by_role('button', name='发送', exact=True).click()
        expect(chat.locator('.group-content')).to_have_text('私聊验收消息')
        page2 = contexts[1].new_page()
        page2.on('pageerror', lambda error: errors.append(str(error)))
        page2.goto(BASE + '/resource-management/talent-duplicate-review?return=/resource-management/talents')
        page2.get_by_role('button', name='聊天大屏', exact=True).click()
        # Headless 中两个独立上下文不会可靠地产生系统焦点切换，显式模拟失焦事件。
        page.evaluate("Object.defineProperty(document,'hasFocus',{configurable:true,value:()=>false});window.dispatchEvent(new Event('blur'))")
        expect(page).to_have_title(re.compile(r'^\[有人@我\]'))
        page2.locator('.chat-workspace__session').filter(has=page2.locator('.chat-workspace__session-title strong', has_text='验收甲')).click()
        chat2 = page2.locator('.project-chat-window:visible .annotation-group')
        expect(chat2.locator('.group-content')).to_have_text('私聊验收消息')
        chat2.locator('textarea').fill('实时回复')
        chat2.get_by_role('button', name='发送', exact=True).click()
        expect(chat.locator('.group-content')).to_contain_text(['私聊验收消息', '实时回复'])
        page.bring_to_front()
        page.evaluate("Object.defineProperty(document,'hasFocus',{configurable:true,value:()=>true});window.dispatchEvent(new Event('focus'))")
        expect(page).not_to_have_title(re.compile(r'^\[有人@我\]'))
        chat.locator('.group-message--own .group-content', has_text='私聊验收消息').click(button='right')
        page.get_by_role('menuitem', name='撤回', exact=True).click()
        page.locator('.el-message-box:visible').get_by_role('button', name='确定', exact=True).click()
        expect(chat2.locator('.group-recalled')).to_be_visible()
        expect(page.locator('.el-message-box:visible')).to_have_count(0)
        page.screenshot(path=str(output / 'direct.png'), full_page=True)
        workspace.locator('.chat-workspace__session', has_text='阶段一笔译').click()
        expect(workspace.get_by_role('button', name='项目详情', exact=True)).to_be_visible()
        expect(workspace.get_by_role('button', name='项目资料', exact=True)).to_have_count(0)
        workspace.get_by_role('button', name='项目详情', exact=True).click()
        expect(page.get_by_role('tooltip', name='笔译项目详情', exact=True)).to_contain_text('TP-QA-001')
        page.locator('.chat-workspace__brand').click()
        expect(page.locator('.project-chat-window:visible .chat-bubble mark')).to_have_text('@验收甲')
        page.screenshot(path=str(output / 'workspace.png'), full_page=True)
        page.set_viewport_size(dict(width=390,height=740))
        page.screenshot(path=str(output / 'mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.set_viewport_size(dict(width=1440,height=900))
        direct_row = workspace.locator('.chat-workspace__session').filter(has=page.locator('.chat-workspace__session-title strong', has_text='验收乙'))
        direct_row.hover()
        direct_row.get_by_role('button', name='会话操作').click()
        page.locator('.chat-session-popover:visible').get_by_role('button', name='特别关注', exact=True).click()
        page.locator('.chat-workspace__brand').click()
        groups = [('all','消息'),('pinned','置顶'),('unread','未读'),('mention','@我'),('direct','单聊'),('starred','特别关注'),('project','项目群'),('annotation','标注项目群'),('translation','笔译项目群'),('creator','我创建的')]
        def matches(row, key):
            if key == 'all': return True
            if key == 'creator': return row['is_creator']
            if key == 'project': return row['kind'] != 'direct'
            if key in ('direct','annotation','translation'): return row['kind'] == key
            return bool(row[key])
        for key, label in groups:
            count = len(mention_rows(me)) if key == 'mention' else sum(matches(row,key) for row in session_rows(me))
            workspace.locator('.chat-workspace__filter').click()
            page.locator('.chat-session-popover:visible').get_by_role('button', name=f'{label} ({count})', exact=True).click()
            expect(workspace.locator('.chat-mention-inbox__message' if key == 'mention' else '.chat-workspace__session')).to_have_count(count)
            page.locator('.chat-workspace__brand').click()
        # 分组选择跨刷新保存；另一账号仍保持独立的消息分组。
        page.reload()
        page.locator('button[aria-label="会话"], button[aria-label="聊天大屏"]').first.click()
        expect(workspace.locator('.chat-workspace__filter')).to_contain_text('我创建的')
        expect(workspace.locator('.chat-workspace__session')).to_have_count(1)
        expect(page2.locator('.chat-workspace__filter')).to_contain_text('消息')
        workspace.locator('.chat-workspace__filter').click()
        page.locator('.chat-session-popover:visible').get_by_role('button', name=f'消息 ({sum(matches(row, "all") for row in session_rows(me))})', exact=True).click()
        page.locator('.chat-workspace__brand').click()
        workspace.locator('.chat-workspace__search input').fill('实时回复')
        expect(workspace.locator('.chat-workspace__session')).to_have_count(1)
        workspace.locator('.chat-workspace__search input').fill('')
        expect(workspace.locator('.chat-workspace__session')).to_have_count(4)
        pane_button(workspace, '通讯录').click()
        expect(workspace.locator('.chat-contacts__group-title', has_text='项目部')).to_contain_text('项目部 · 1')
        expect(workspace.locator('.chat-contacts__group-title', has_text='译员部')).to_contain_text('译员部 · 1')
        expect(workspace.locator('.chat-contacts__group').last).to_contain_text('未分配部门 · 1')
        badge = workspace.locator('.chat-contact', has_text='译员丁').first
        badge.hover()
        expect(badge.locator('.chat-contact__send')).to_be_visible()
        expect(badge.locator('.chat-contact__unread')).to_have_text('2')
        translator_title = workspace.locator('.chat-contacts__group-title', has_text='译员部 · 1')
        translator_group = translator_title.locator('xpath=ancestor::section[1]')
        translator_title.click()
        expect(translator_group.locator('.chat-contact')).to_have_count(0)
        def user_calls():
            return [item for item in requests if item[1] == '/chat/users']
        before = len(user_calls())
        workspace.locator('.chat-contacts__search input').fill('译员')
        page.wait_for_timeout(200)
        assert len(user_calls()) == before, user_calls()
        page.wait_for_timeout(400)
        assert len(user_calls()) == before + 1, user_calls()
        expect(translator_group.locator('.chat-contact', has_text='译员丁')).to_be_visible()
        expect(workspace.locator('.chat-contacts__group-title', has_text='项目部')).to_have_count(0)
        before = len(user_calls())
        workspace.locator('.chat-contacts__search input').fill('')
        expect(workspace.locator('.chat-contacts__group-title', has_text='未分配部门')).to_be_visible()
        page.wait_for_timeout(120)
        assert len(user_calls()) == before, user_calls()
        first_contact = workspace.locator('.chat-contact').first
        first_contact.focus()
        first_text = first_contact.inner_text()
        page.keyboard.press('ArrowDown')
        assert page.evaluate('document.activeElement.innerText') != first_text
        page.keyboard.press('ArrowUp')
        workspace.locator('.chat-contact', has_text='验收乙').first.click()
        expect(pane_button(workspace, '消息')).to_have_attribute('aria-pressed', 'true')
        expect(workspace.locator('.chat-workspace__session.is-active')).to_contain_text('验收乙')
        expect(workspace.locator('.chat-workspace__session')).to_have_count(4)
        assert len([item for item in requests if item == ('POST', '/chat/direct/conversations')]) >= 2

        def assert_header(target):
            header = target.locator('.chat-workspace__header')
            expect(header).to_be_visible()
            assert header.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1')
            tabs = target.locator('.chat-workspace__pane-tabs')
            if tabs.count():
                tops = tabs.locator('button').evaluate_all('els => els.map(el => Math.round(el.getBoundingClientRect().top))')
                assert len(tops) == 3 and len(set(tops)) == 1

        def assert_contacts_scroll(target):
            listing = target.locator('.chat-contacts__list')
            expect(listing).to_be_visible()
            assert listing.evaluate('(el) => ["auto", "scroll"].includes(getComputedStyle(el).overflowY)')
            assert target.locator('.chat-workspace__sessions').evaluate('''(el) => {
              const shell = el.closest('.chat-workspace-shell')
              const side = el.getBoundingClientRect(), frame = shell.getBoundingClientRect()
              return getComputedStyle(el).overflowY === 'hidden' && side.bottom <= frame.bottom + 1 && side.right <= frame.right + 1
            }''')

        pane_button(workspace, '通讯录').click()
        assert_header(workspace)
        assert_contacts_scroll(workspace)
        workspace.locator('.chat-workspace__brand').screenshot(path=str(output / 'contacts-fullscreen-header.png'))
        page.screenshot(path=str(output / 'contacts-fullscreen.png'))
        workspace.get_by_role('button', name='窗口状态').click()
        page.locator('.chat-window-state-menu:visible').get_by_role('button', name='中窗', exact=True).click()
        assert_header(workspace)
        assert_contacts_scroll(workspace)
        page.screenshot(path=str(output / 'contacts-medium.png'))
        workspace.get_by_role('button', name='窗口状态').click()
        page.locator('.chat-window-state-menu:visible').get_by_role('button', name='大窗', exact=True).click()
        assert_header(workspace)
        assert_contacts_scroll(workspace)
        page.screenshot(path=str(output / 'contacts-large.png'))
        pane_button(workspace, '消息').click()
        assert_header(workspace)
        page.set_viewport_size(dict(width=390, height=740))
        page.wait_for_timeout(300)
        workspace.get_by_role('button', name='会话列表', exact=True).click()
        expect(workspace.locator('.chat-workspace__sessions')).to_be_visible()
        assert_header(workspace)
        pane_button(workspace, '通讯录').click()
        assert_contacts_scroll(workspace)
        page.screenshot(path=str(output / 'contacts-narrow.png'))
        page.set_viewport_size(dict(width=1440, height=900))
        workspace.get_by_role('button', name='窗口状态').click()
        page.locator('.chat-window-state-menu:visible').get_by_role('button', name='全屏聊天').click()
        pane_button(workspace, '通讯录').click()
        page.reload()
        page.locator('button[aria-label="会话"], button[aria-label="聊天大屏"]').first.click()
        expect(pane_button(workspace, '通讯录')).to_have_attribute('aria-pressed', 'true')
        assert page.evaluate("localStorage.getItem('xinshi.chatPane.' + localStorage.getItem('user_id'))") == 'contacts'
        assert page2.evaluate("localStorage.getItem('xinshi.chatPane.' + localStorage.getItem('user_id'))") in (None, 'messages')
        expect(pane_button(page2.locator('.chat-workspace-shell:visible'), '消息')).to_have_attribute('aria-pressed', 'true')
        assert not errors, errors
        browser.close()
    report = dict(checks=['实际核重页面打开大屏', '消息页签未读与@标记', '通知点击精确定位', '列表预览与未读@提示', '已打开群新提及保留提醒', '阅读及撤回同步标记', '失焦标签页@提示', '未读提及定位与高亮', '项目详情和资料浮层', '通讯录打开私聊并回到消息', '双账号实时收发', '撤回实时更新', '置顶与特别关注', '十个分组计数筛选', '刷新保存与用户隔离', '搜索预览防抖与清空', '通讯录分组搜索角标与键盘', '四种尺寸头部与内部滚动', '页签按用户持久化', '笔译入口与正文提及高亮', '小屏无横向溢出'], requests=len(requests), errors=errors)
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--legacy', action='store_true', help='验收未迁移结构下的列表提及提醒')
    run(legacy=parser.parse_args().legacy)
