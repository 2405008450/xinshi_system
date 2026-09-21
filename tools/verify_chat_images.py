"""仅在局域网调试机运行：用临时项目验证图片沟通，并清理本次测试数据。"""
import base64
import json
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main  # noqa: F401，注册项目模型并读取环境配置
from database import SessionLocal
from models import AppUser, ChatProjectAttachment
from permission_service import user_has_permission
from routers.auth import create_access_token
from routers.project_chat import get_chat_upload_dir
from sqlalchemy import text
from playwright.sync_api import sync_playwright, expect

BASE = 'http://127.0.0.1:3000'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=')


def main_test():
    project_id = uuid4()
    marker = 'CHAT-IMAGE-E2E-' + uuid4().hex[:10]
    uploaded_ids = set()
    with SessionLocal() as db:
        users = db.query(AppUser).filter(AppUser.is_active.is_(True)).all()
        sender = next(user for user in users if user.username == 'admin')
        receiver = next(user for user in users if user.id != sender.id and user_has_permission(db, user.id, 'projects:read'))
        tokens = [create_access_token({'sub': user.username}, timedelta(minutes=15)) for user in (sender, receiver)]
        db.execute(text('INSERT INTO annotation_project (id, order_no, project_name, created_by) VALUES (:id, :order, :name, :owner)'),
                   {'id': project_id, 'order': marker, 'name': marker, 'owner': receiver.id})
        db.commit()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge', headless=True)
            pages = []
            errors = []
            for token in tokens:
                context = browser.new_context(viewport={'width': 1440, 'height': 1000}, permissions=['clipboard-read', 'clipboard-write'])
                context.add_init_script('localStorage.setItem("token", ' + json.dumps(token) + ')')
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                def record_upload(response):
                    if response.url.endswith('/project-chat/attachments') and response.status == 201:
                        uploaded_ids.add(response.json()['id'])
                page.on('response', record_upload)
                page.goto(BASE + '/annotation-details', wait_until='networkidle')
                page.evaluate('''async projectId => {
                    const { useProjectChatDock } = await import('/src/composables/useProjectChatDock.js')
                    useProjectChatDock().openChat({ projectId, projectType: 'annotation', title: '图片沟通联调' })
                }''', str(project_id))
                expect(page.locator('.project-chat-window textarea')).to_be_visible()
                pages.append(page)
            page, receiver_page = pages
            win = page.locator('.project-chat-window')
            textarea = win.locator('textarea')
            send = win.get_by_role('button', name='发送', exact=True)

            def paste(count=1, with_text=''):
                textarea.evaluate('''(element, args) => {
                    const data = new DataTransfer()
                    if (args.text) data.setData('text/plain', args.text)
                    const bytes = Uint8Array.from(atob(args.png), c => c.charCodeAt(0))
                    for (let i = 0; i < args.count; i++) data.items.add(new File([bytes], `截图${i}.png`, { type: 'image/png' }))
                    const event = new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true })
                    element.dispatchEvent(event)
                    if (args.text && event.defaultPrevented) throw Error('混合粘贴不应阻止原生文字插入')
                }''', {'png': base64.b64encode(PNG).decode(), 'count': count, 'text': with_text})

            # 截图粘贴先预览，不自动创建消息；纯图片发送及另一账号实时接收。
            page.bring_to_front()
            page.evaluate('''async () => {
                const canvas = document.createElement('canvas')
                canvas.width = 160; canvas.height = 100
                const ctx = canvas.getContext('2d')
                ctx.fillStyle = '#dbeafe'; ctx.fillRect(0, 0, 160, 100)
                ctx.fillStyle = '#1e40af'; ctx.fillText('Clipboard image', 20, 50)
                const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'))
                await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
            }''')
            textarea.focus()
            textarea.press('Control+V')
            expect(win.locator('.chat-images__item')).to_have_count(1)
            expect(send).to_be_enabled()
            expect(win.locator('.message-attachment')).to_have_count(0)
            with page.expect_response(lambda r: '/messages' in r.url and r.request.method == 'POST') as sent:
                textarea.press('Enter')
            assert sent.value.status == 201, sent.value.text()
            expect(win.locator('.message-attachment img')).to_have_count(1)
            expect(receiver_page.locator('.message-attachment img')).to_have_count(1, timeout=10000)
            expect(win.locator('.chat-images__item')).to_have_count(0)

            # 上传失败保留预览并禁止发送，重试可恢复。
            page.route('**/api/project-chat/attachments', lambda route: route.fulfill(status=500, json={'detail': '测试上传失败'}))
            paste()
            expect(win.get_by_text('上传失败', exact=True)).to_be_visible()
            expect(send).to_be_disabled()
            page.unroute('**/api/project-chat/attachments')
            win.get_by_role('button', name='重试').click()
            expect(send).to_be_enabled()
            win.get_by_role('button', name='移除').click()
            expect(win.locator('.chat-images__item')).to_have_count(0)

            # 图文混合、连续多图和发送失败草稿保留。
            textarea.fill('图片联调文字')
            paste(2, '混合文字')
            expect(win.locator('.chat-images__item')).to_have_count(2)
            expect(send).to_be_enabled()
            page.route('**/api/project-chat/annotation/*/messages', lambda route: route.fulfill(status=500, json={'detail': '测试发送失败'}) if route.request.method == 'POST' else route.continue_())
            send.click()
            expect(page.get_by_text('测试发送失败', exact=True)).to_be_visible()
            expect(win.locator('.chat-images__item')).to_have_count(2)
            expect(textarea).to_have_value('图片联调文字')
            page.unroute('**/api/project-chat/annotation/*/messages')
            send.click()
            expect(win.locator('.message-attachment img')).to_have_count(3)
            expect(win.locator('.chat-images__item')).to_have_count(0)

            # 本地选图入口、九张限制、删除，以及关闭后清空草稿。
            win.locator('input[type=file]').set_input_files({'name': '选择图片.png', 'mimeType': 'image/png', 'buffer': PNG})
            expect(win.locator('.chat-images__item')).to_have_count(1)
            paste(10)
            expect(win.locator('.chat-images__item')).to_have_count(9)
            expect(send).to_be_enabled()
            page.screenshot(path='.codex_chat_images_preview.png', full_page=True)
            win.get_by_role('button', name='关闭项目沟通').click()
            expect(page.locator('.chat-images__item')).to_have_count(0)

            # 刷新后从接口恢复图片，验证进度弹窗中的第二个沟通入口。
            page.goto(BASE + f'/annotation-details?projectId={project_id}&tab=chat', wait_until='networkidle')
            panel = page.locator('.el-dialog:visible .project-chat-panel')
            expect(panel.locator('.message-attachment img')).to_have_count(3)
            expect(panel.locator('button').filter(has_text='添加图片')).to_be_visible()
            panel.locator('input[type=file]').set_input_files({'name': '进度窗口图片.png', 'mimeType': 'image/png', 'buffer': PNG})
            expect(panel.locator('.chat-images__item')).to_have_count(1)
            expect(panel.get_by_role('button', name='发送消息')).to_be_enabled()
            panel.get_by_role('button', name='发送消息').click()
            expect(panel.locator('.message-attachment img')).to_have_count(4)
            assert panel.locator('.message-attachment img').first.evaluate('(img) => img.complete && img.naturalWidth > 0')
            page.screenshot(path='.codex_chat_images_history.png', full_page=True)
            assert not errors, errors
            browser.close()
            print('PASS: paste preview, pure image, realtime receiver, retry, text+images, send failure, file selection, nine-image limit, close cleanup, refresh and progress dialog')
    finally:
        with SessionLocal() as db:
            db.execute(text('DELETE FROM annotation_project WHERE id=:id AND order_no=:marker'), {'id': project_id, 'marker': marker})
            for attachment_id in uploaded_ids:
                attachment = db.get(ChatProjectAttachment, __import__('uuid').UUID(attachment_id))
                if attachment:
                    path = get_chat_upload_dir() / attachment.storage_name
                    db.delete(attachment)
                    path.unlink(missing_ok=True)
            db.commit()
        print('Temporary project, messages and recorded image uploads cleaned up.')


if __name__ == '__main__':
    main_test()
