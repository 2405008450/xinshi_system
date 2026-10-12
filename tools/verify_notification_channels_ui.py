"""在实际页面验证通知与聊天分流，接口及 WebSocket 全部使用隔离夹具。"""
import json
from uuid import uuid4
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import expect
from verify_chat_phase_one_ui import run


def verify(page, workspace, contexts, errors, requests, output, me, other, annotation, translation, direct):
    output = output.parent / 'notification-channels-ui'
    output.mkdir(exist_ok=True)
    page.on('pageerror', lambda error: (output / 'browser-error.txt').write_text(error.stack or str(error), encoding='utf-8'))
    console_messages = []
    page.on('console', lambda message: console_messages.append(message.text) if message.type in ('error', 'warning') else None)
    records = [
        dict(id=str(uuid4()), notification_type='workflow_handover_pending', title='待接收的工作交接', content='工作台交接内容'),
        dict(id=str(uuid4()), notification_type='project_manager_handover_pending', title='待接收的项目经理交接', content='关键业务信息'),
        dict(id=str(uuid4()), notification_type='annotation_project_chat_mention', title='群聊中有人@我', content='群聊消息', related_project_type='annotation', related_entity_id=annotation),
        dict(id=str(uuid4()), notification_type='project_chat', title='笔译群聊消息', content='只属于聊天', related_project_type='translation', related_entity_id=translation),
    ]
    for row in records:
        row.update(is_read=False, created_at='2026-10-12T18:00:00+08:00')
    operations, sockets = [], []
    def is_chat(row):
        return 'chat' in row['notification_type']
    def handle(route):
        path = urlparse(route.request.url).path.rstrip('/')
        params = parse_qs(urlparse(route.request.url).query)
        channel = params.get('channel', ['all'])[0]
        matching = [row for row in records if channel == 'all' or is_chat(row) == (channel == 'chat')]
        if path.endswith('/unread-count'):
            result = {'count': sum(not row['is_read'] for row in matching)}
        elif path.endswith('/read-all'):
            operations.append(('read-all', channel))
            result = {'updated': sum(not row['is_read'] for row in matching)}
            for row in matching: row['is_read'] = True
        elif path.endswith('/read'):
            target = next(row for row in records if row['id'] == path.split('/')[-2])
            operations.append(('read', target['notification_type'])); target['is_read'] = True; result = target
        else:
            if params.get('unread_only') == ['true']: matching = [row for row in matching if not row['is_read']]
            result = matching[:int(params.get('limit', [20])[0])]
        route.fulfill(json=result)
    contexts[0].route('**/api/notifications/**', handle)
    contexts[0].route_web_socket('**/api/notifications/ws**', lambda ws: sockets.append(ws))
    page.goto('http://localhost:3000/resource-management/referral-development')
    expect(page.locator('.mention-notification')).to_contain_text('群聊中有人@我')
    bell = page.locator('.header-right .el-badge').filter(has=page.get_by_role('button', name='业务通知', exact=True))
    expect(bell.locator('.el-badge__content')).to_have_text('2')
    # 快照总数故意混合，铃铛必须采用业务计数。
    page.wait_for_timeout(300)
    assert sockets
    sockets[-1].send(json.dumps(dict(type='snapshot', unread_count=99, business_unread_count=2)))
    expect(bell.locator('.el-badge__content')).to_have_text('2')
    page.get_by_role('button', name='业务通知', exact=True).click()
    panel = page.locator('.notification-popover:visible')
    expect(panel.locator('.notification-item')).to_have_count(2)
    expect(panel).to_contain_text('待接收的工作交接')
    expect(panel).not_to_contain_text('群聊中有人@我')
    expect(panel).not_to_contain_text('笔译群聊消息')
    expect(panel).to_have_css('opacity', '1')
    page.screenshot(path=str(output / 'business-notifications.png'))
    before_chat_unread = page.locator('.header-chat-badge .el-badge__content').inner_text()
    panel.get_by_role('button', name='全部已读', exact=True).click()
    expect(panel.get_by_role('button', name='全部已读', exact=True)).to_have_count(0)
    assert operations == [('read-all', 'business')]
    assert all(not row['is_read'] for row in records if is_chat(row))
    expect(page.locator('.header-chat-badge .el-badge__content')).to_have_text(before_chat_unread)
    expect(page.locator('.mention-notification')).to_be_visible()
    panel.locator('.notification-item', has_text='待接收的工作交接').click()
    expect(page).to_have_url('http://localhost:3000/workbench')
    expect(panel).to_have_count(0)
    assert page.locator('.project-chat-window:visible').count() == 0
    assert not errors, ('业务通知跳转后', errors)
    # 同一实时连接中，聊天事件不增业务铃铛；业务事件不弹聊天提及卡片。
    new_chat = dict(records[2], id=str(uuid4()), is_read=False, title='新的群聊提及')
    records.append(new_chat)
    sockets[-1].send(json.dumps(dict(type='notification', notification=new_chat)))
    expect(page.locator('.mention-notification', has_text='新的群聊提及')).to_be_visible()
    expect(bell.locator('.el-badge__content')).to_be_hidden()
    new_business = dict(records[0], id=str(uuid4()), is_read=False, title='新的交接待办')
    records.append(new_business)
    sockets[-1].send(json.dumps(dict(type='notification', notification=new_business)))
    expect(bell.locator('.el-badge__content')).to_have_text('1')
    expect(page.locator('.mention-notification', has_text='新的交接待办')).to_have_count(0)
    assert not errors, ('实时更新后', errors)
    page.locator('.mention-notification', has_text='群聊中有人@我').click()
    expect(page.locator('.project-chat-window:visible .annotation-group')).to_be_visible()
    assert ('read', 'annotation_project_chat_mention') in operations
    expect(bell.locator('.el-badge__content')).to_have_text('1')
    page.screenshot(path=str(output / 'chat-reminders.png'))
    assert not errors, (errors, console_messages)
    report = {'checks': ['业务列表仅包含交接', '两个入口计数独立', '快照业务计数', '业务全部已读保留聊天未读及提及卡片', '交接打开工作台', '聊天提及打开会话', '实时事件按职责分流'], 'errors': errors, 'operations': operations}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    run(verify_layout=verify)
