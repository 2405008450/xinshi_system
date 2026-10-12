"""复用隔离聊天夹具，在实际页面验收聊天布局；不访问业务数据。"""
import json
from playwright.sync_api import expect
from verify_chat_phase_one_ui import run


def verify(page, workspace, contexts, errors, requests, output, me, other, annotation, translation, direct):
    output = output.parent / 'chat-layout-ui'
    output.mkdir(exist_ok=True)
    if page.locator('.el-notification__closeBtn:visible').count():
        page.locator('.el-notification__closeBtn:visible').first.click()
    # 与用户真实项目名称一样，覆盖全角括号开头的标题。
    page.evaluate("localStorage.setItem('xinshi.chatPane.' + localStorage.getItem('user_id'), 'messages')")
    workspace.locator('.chat-workspace__session', has_text='阶段一标注').click()
    chat = page.locator('.project-chat-window:visible .annotation-group')
    expect(chat.locator('.group-content').first).to_be_visible()
    expect(workspace.locator('.group-participants')).to_be_visible()
    expect(chat.locator('.group-toolbar')).to_have_count(0)
    expect(chat.locator('.group-date-divider')).to_have_count(1)
    expect(chat.locator('.group-message-avatar')).to_have_count(1)
    expect(chat.locator('.group-message--grouped')).to_have_count(29)
    expect(chat.locator('.group-compose-tools .chat-topic-navigation')).to_have_count(0)
    chat.locator('textarea').focus()
    page.wait_for_timeout(250)
    assert chat.locator('.group-composer').evaluate("""el => { const probe = document.createElement('span'); probe.style.color = 'var(--el-color-primary)'; el.append(probe); const color = getComputedStyle(probe).color; probe.remove(); return getComputedStyle(el).borderTopColor === color }""")
    handle = chat.get_by_role('button', name='调整输入区高度', exact=True)
    box = handle.bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + 4)
    page.mouse.down()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] - 40, steps=6)
    page.mouse.up()
    assert float(page.evaluate("localStorage.getItem('xinshi.chatComposerHeight.' + localStorage.getItem('user_id'))")) > 80
    # 文件拖放进入已有上传队列，夹具返回失败也必须可以移除和重试。
    chat.evaluate("""el => {
      const transfer = new DataTransfer(); transfer.items.add(new File(['isolated'], '布局验收.txt', {type:'text/plain'}));
      el.dispatchEvent(new DragEvent('dragenter', {bubbles:true,dataTransfer:transfer}));
    }""")
    expect(chat.locator('.chat-file-drop')).to_be_visible()
    chat.evaluate("""el => {
      const transfer = new DataTransfer(); transfer.items.add(new File(['isolated'], '布局验收.txt', {type:'text/plain'}));
      el.dispatchEvent(new DragEvent('drop', {bubbles:true,dataTransfer:transfer}));
    }""")
    expect(chat.locator('.group-file-queue')).to_contain_text('布局验收.txt')
    chat.get_by_role('button', name='移除', exact=True).click()
    expect(chat.locator('.chat-file-drop')).to_have_count(0)
    workspace.get_by_role('button', name='项目详情', exact=True).click()
    expect(page.locator('.chat-project-popover:visible')).to_contain_text('AN-QA-001')
    workspace.locator('.chat-workspace__brand').click()
    expect(page.locator('.chat-project-popover:visible')).to_have_count(0)
    page.screenshot(path=str(output / 'fullscreen.png'))

    def bounds():
        assert workspace.locator('.chat-workspace__header').evaluate('el => el.scrollWidth <= el.clientWidth + 1')
        assert chat.locator('.group-composer').evaluate('el => el.getBoundingClientRect().bottom <= innerHeight')
        assert chat.locator('.group-timeline').evaluate("el => getComputedStyle(el).overflowY === 'auto' && el.clientHeight > 100")
        rect = page.locator('.project-chat-window:visible').bounding_box()
        if workspace.locator('.chat-workspace__rail').count():
            side = workspace.locator('.chat-workspace__sessions').bounding_box()
            assert abs(rect['x'] - side['x'] - side['width']) <= 2

    bounds()
    for mode, label in [('medium', '中窗'), ('large', '大窗')]:
        workspace.get_by_role('button', name='窗口状态').click()
        page.locator('.chat-window-state-menu:visible').get_by_role('button', name=label, exact=True).click()
        expect(workspace.locator('.chat-workspace__pane-tabs')).to_be_visible()
        expect(workspace.locator('.chat-workspace__rail')).to_have_count(0)
        bounds()
        # 标题拖动、视口约束以及按钮操作。
        header = workspace.locator('.chat-workspace__header').bounding_box()
        page.mouse.move(header['x'] + header['width'] * .35, header['y'] + 45)
        page.mouse.down(); page.mouse.move(-100, -100, steps=8); page.mouse.up()
        assert workspace.bounding_box()['x'] >= 0 and workspace.bounding_box()['y'] >= 0
        page.screenshot(path=str(output / f'{mode}.png'))

    workspace.get_by_role('button', name='通讯录', exact=True).click()
    expect(workspace.locator('.chat-contact').first).to_be_visible()
    expect(workspace.locator('.chat-contacts__group').last).to_contain_text('未分配部门')
    search = workspace.locator('.direct-user-search input')
    before = sum(path == '/chat/users' for _, path in requests)
    search.fill('译员'); page.wait_for_timeout(200)
    assert sum(path == '/chat/users' for _, path in requests) == before
    expect(workspace.locator('.chat-contact', has_text='译员丁').first).to_be_visible()
    search.fill(''); expect(workspace.locator('.chat-contact', has_text='验收乙').first).to_be_visible()
    first = workspace.locator('.chat-contact').first
    first.focus(); page.keyboard.press('ArrowDown')
    assert not first.evaluate('el => el === document.activeElement')
    workspace.locator('.chat-contact', has_text='验收乙').first.click()
    expect(workspace.locator('.chat-workspace__session.is-active')).to_contain_text('验收乙')
    direct_chat = page.locator('.project-chat-window:visible .annotation-group')
    expect(workspace.locator('.group-participants:visible')).to_have_count(0)
    direct_chat.locator('textarea').fill('布局验收消息')
    direct_chat.get_by_role('button', name='发送', exact=True).click()
    expect(direct_chat.locator('.group-message--own .group-content')).to_contain_text('布局验收消息')
    expect(direct_chat.locator('.group-message--own .group-message-meta strong')).to_have_count(0)
    page.screenshot(path=str(output / 'contacts-direct.png'))
    workspace.get_by_role('button', name='主题', exact=True).click()
    expect(workspace.locator('.chat-workspace__topic-panel')).to_be_visible()
    workspace.get_by_role('button', name='消息', exact=True).click()
    workspace.locator('.chat-workspace__session', has_text='阶段一标注').click()
    page.set_viewport_size(dict(width=390, height=740))
    expect(workspace.get_by_role('button', name='会话列表', exact=True)).to_be_visible()
    expect(workspace.locator('.chat-workspace--narrow')).to_be_visible()
    expect(workspace.locator('.chat-workspace__heading .el-tag')).to_have_count(0)
    bounds()
    page.screenshot(path=str(output / 'narrow.png'))
    workspace.get_by_role('button', name='会话列表', exact=True).click()
    workspace.get_by_role('button', name='通讯录', exact=True).click()
    expect(workspace.locator('.direct-user-list')).to_be_visible()
    page.screenshot(path=str(output / 'narrow-contacts.png'))
    page.set_viewport_size(dict(width=1440, height=900))
    page.reload(); page.get_by_role('button', name='聊天大屏', exact=True).click()
    expect(workspace.locator('.chat-contacts')).to_be_visible()
    assert page.evaluate("localStorage.getItem('xinshi.chatPane.' + localStorage.getItem('user_id'))") == 'contacts'
    workspace.get_by_role('button', name='消息', exact=True).click()
    workspace.locator('.chat-workspace__session', has_text='阶段一笔译').click()
    expect(page.locator('.project-chat-window:visible .chat-toolbar')).to_have_count(0)
    expect(page.locator('.project-chat-window:visible .chat-bubble mark')).to_have_text('@验收甲')
    page.screenshot(path=str(output / 'translation.png'))
    # 同样布局在咨询页面工作。
    page.goto('http://localhost:3000/consultations')
    page.get_by_role('button', name='聊天大屏', exact=True).click()
    expect(workspace).to_be_visible()
    page.screenshot(path=str(output / 'consultations.png'))
    assert not errors, errors
    report = dict(checks=['四种尺寸边界与内部滚动', '单行头部与参与人浮层', '连续消息分组与日期分隔', '私聊隐藏本人姓名和参与人', '通讯录分组、防抖、清空、键盘和私聊', '面板持久化', '主题独立面板', '输入卡片聚焦与高度保存', '文件拖放队列', '标题拖动与视口约束', '项目详情浮层', '咨询和核重页面'], errors=errors)
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    run(verify_layout=verify)
