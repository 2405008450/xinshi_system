"""局域网三账号聊天联调；只创建 QA 前缀记录，结束时清理本次数据。"""
import json
from pathlib import Path
import socket
import sys
from uuid import uuid4
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5':
    raise SystemExit('仅允许在局域网调试机运行')
import main
import httpx
from playwright.sync_api import sync_playwright, expect
from database import SessionLocal
from models import AppUser, Role, UserRole, RolePermission, AppNotification
from annotation_models import AnnotationProject
from routers.auth import create_access_token

BASE = 'http://127.0.0.1:3000'
API = 'http://127.0.0.1:8000'
OUT = ROOT / '.tmp' / 'annotation-chat-ui'
OUT.mkdir(parents=True, exist_ok=True)


def main_test():
    marker = uuid4().hex[:10]
    db = SessionLocal()
    role = Role(role_name='qa-chat-' + marker)
    users = [AppUser(username=f'qa-chat-{marker}-{i}', full_name=f'群聊验收{i+1}', password_hash='disabled', is_active=True) for i in range(3)]
    project = AnnotationProject(order_no='QA-CHAT-' + marker, project_name='开放项目群验收-' + marker, project_types=[])
    db.add_all([role, project, *users]); db.flush()
    db.add(RolePermission(role_id=role.id, permission_code='projects:read'))
    db.add_all(UserRole(role_id=role.id, user_id=u.id) for u in users)
    db.commit()
    pid, uid, role_id = str(project.id), [u.id for u in users], role.id
    tokens = [create_access_token({'sub': u.username, 'user_id': str(u.id)}, expires_delta=timedelta(minutes=30)) for u in users]
    results, errors = {}, []

    def call(index, method, suffix, data=None):
        response = httpx.request(method, f'{API}/project-chat/annotation/{pid}/{suffix}',
            headers={'Authorization': 'Bearer ' + tokens[index]}, json=data, timeout=20, trust_env=False)
        response.raise_for_status()
        return response.json()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            contexts = [browser.new_context(viewport={'width': 1440, 'height': 950}) for _ in users]
            pages = [c.new_page() for c in contexts]
            for index, page in enumerate(pages):
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(BASE + '/login')
                info = {'token': tokens[index], 'user_id': str(users[index].id), 'user_name': users[index].username,
                        'user_full_name': users[index].full_name, 'user_roles': json.dumps([role.role_name]),
                        'user_permissions': json.dumps(['projects:read'])}
                page.evaluate('(info) => Object.entries(info).forEach(([key,value]) => localStorage.setItem(key,value))', info)
                page.goto(BASE + '/annotation-details', wait_until='networkidle')
                keyword = page.locator('input[placeholder*="订单号、项目名称"]')
                keyword.fill(project.order_no)
                keyword.press('Enter')
                row = page.locator('.el-table__row', has_text=project.order_no).first
                try:
                    row.wait_for(timeout=30000)
                except Exception:
                    page.screenshot(path=str(OUT / f'failure-{index}.png'))
                    (OUT / 'failure.txt').write_text(page.locator('body').inner_text(), encoding='utf-8')
                    raise
                row.get_by_role('button', name='更多').click()
                page.get_by_role('menuitem', name='沟通', exact=True).click()
                page.locator('.annotation-group:visible').wait_for()
                expect(page.locator('.annotation-group:visible').get_by_role('button', name='关注项目', exact=True)).to_be_visible()
            results['open_without_invitation'] = True
            pages[0].bring_to_front()
            editor = pages[0].locator('.annotation-group:visible textarea')
            editor.fill('请协助 @群聊验收')
            menu = pages[0].get_by_role('listbox', name='选择提及用户')
            expect(menu).to_be_visible()
            expect(editor).to_be_focused()
            assert menu.bounding_box()['y'] + menu.bounding_box()['height'] <= editor.bounding_box()['y'] + 10
            editor.press('ArrowDown')
            selected_name = menu.locator('[aria-selected="true"]').inner_text().split('\n')[-1]
            editor.press('Enter')
            expect(menu).not_to_be_visible()
            expect(editor).to_have_value('请协助 @' + selected_name + ' ')
            editor.press('Enter')
            expect(pages[0].locator('.group-content', has_text='请协助 @' + selected_name)).to_be_visible()
            sent = call(0, 'GET', 'timeline')['items'][-1]
            assert len(sent['mentions']) == 1
            editor.fill('定位第一行\n第二行 @不存在的候选名')
            expect(menu).to_contain_text('没有匹配的用户')
            editor.press('Enter')
            expect(editor).to_have_value('定位第一行\n第二行 @不存在的候选名')
            editor.press('Escape')
            expect(menu).not_to_be_visible()
            expect(pages[0].get_by_role('button', name='@', exact=True)).to_have_count(0)
            editor.fill('@')
            expect(menu).to_be_visible()
            menu.get_by_role('option').filter(has_text='群聊验收2').click()
            expect(editor).to_have_value('@群聊验收2 ')
            editor.fill('已删除提及')
            editor.press('Enter')
            expect(pages[0].locator('.group-content', has_text='已删除提及')).to_be_visible()
            assert not call(0, 'GET', 'timeline')['items'][-1]['mentions']
            pages[0].set_viewport_size({'width': 390, 'height': 700})
            editor.fill('@群聊')
            expect(menu).to_be_visible()
            bounds = menu.bounding_box()
            assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= 390 and bounds['y'] >= 0
            pages[0].screenshot(path=str(OUT / 'mention-mobile.png'))
            editor.press('Escape')
            pages[0].set_viewport_size({'width': 1440, 'height': 950})
            editor.fill('')
            editor.fill('@群聊')
            expect(menu).to_be_visible()
            pages[0].screenshot(path=str(OUT / 'mention-desktop.png'))
            editor.press('Escape')
            results['caret_mentions_keyboard_mouse_filter_mobile'] = True
            pages[0].get_by_role('button', name='收藏夹', exact=True).click()
            favorite = pages[0].get_by_role('button', name=f'定位项目 {project.order_no}', exact=True)
            expect(favorite).to_be_visible()
            pages[0].screenshot(path=str(OUT / 'followed-projects.png'))
            favorite.click()
            expect(pages[0]).to_have_url(__import__('re').compile('projectId=' + pid))
            pages[0].locator('.el-dialog:visible .el-dialog__headerbtn').last.click()
            pages[0].locator('.annotation-group:visible').get_by_role('button', name='取消关注', exact=True).click()
            pages[0].get_by_role('button', name='收藏夹', exact=True).click()
            expect(favorite).to_have_count(0)
            pages[0].get_by_role('button', name='收藏夹', exact=True).click()
            pages[0].locator('.annotation-group:visible').get_by_role('button', name='关注项目', exact=True).click()
            pages[0].get_by_role('button', name='收藏夹', exact=True).click()
            pages[0].get_by_role('button', name=f'沟通 {project.order_no}', exact=True).click()
            expect(pages[0].locator('.annotation-group:visible')).to_be_visible()
            results['favorites_locate_follow_unfollow_and_chat'] = True
            pages[0].locator('.annotation-group:visible textarea').fill('实时群聊验收第一条')
            pages[0].locator('.annotation-group:visible textarea').press('Enter')
            expect(pages[1].locator('.group-content', has_text='实时群聊验收第一条')).to_be_visible(timeout=10000)
            results['spectator_realtime'] = True
            pages[1].bring_to_front()
            bubble = pages[1].locator('.group-message', has_text='实时群聊验收第一条')
            bubble.hover(); bubble.get_by_role('button', name='引用', exact=True).click()
            pages[1].locator('.annotation-group:visible textarea').fill('这是引用回复')
            pages[1].locator('.annotation-group:visible textarea').press('Enter')
            expect(pages[0].locator('.group-content', has_text='这是引用回复')).to_be_visible(timeout=10000)
            results['reply'] = True
            pages[0].bring_to_front()
            first = pages[0].locator('.group-message').filter(has=pages[0].locator('.group-content', has_text='实时群聊验收第一条')).first
            first.hover(); first.get_by_role('button', name='撤回', exact=True).click()
            pages[0].get_by_role('button', name='确定', exact=True).click()
            expect(pages[1].locator('.group-recalled')).to_contain_text('撤回了一条消息', timeout=10000)
            expect(pages[1].locator('.group-reply')).to_contain_text('撤回了一条消息')
            results['recall_and_quote_redaction'] = True
            call(0, 'POST', 'invitations', {'user_ids': [str(users[2].id)]})
            pages[2].reload(wait_until='networkidle')
            pages[0].locator('.annotation-group:visible textarea').fill('邀请参与后的未读消息')
            pages[0].locator('.annotation-group:visible textarea').press('Enter')
            expect(pages[2].get_by_role('button', name='项目消息')).to_contain_text('1', timeout=20000)
            pages[2].get_by_role('button', name='项目消息').click()
            pages[2].get_by_role('button', name=f'{project.order_no} · {project.project_name}').click()
            expect(pages[2].locator('.group-content', has_text='邀请参与后的未读消息')).to_be_visible()
            results['closed_window_unread_and_open'] = True
            pages[0].bring_to_front()
            textarea = pages[0].locator('.annotation-group:visible textarea')
            textarea.fill('中文输入法组合测试')
            textarea.dispatch_event('compositionstart')
            textarea.dispatch_event('keydown', {'key': 'Enter', 'isComposing': True, 'keyCode': 229})
            expect(textarea).to_have_value('中文输入法组合测试')
            textarea.dispatch_event('compositionend')
            textarea.press('Shift+Enter')
            expect(textarea).to_have_value('中文输入法组合测试\n')
            textarea.fill('网络超时幂等重试测试')
            lost_response = {'done': False}

            def lose_first_response(route):
                if not lost_response['done']:
                    lost_response['done'] = True
                    route.fetch()
                    route.abort('failed')
                else:
                    route.continue_()

            pattern = f'**/project-chat/annotation/{pid}/messages'
            pages[0].route(pattern, lose_first_response)
            textarea.press('Enter')
            retry_button = pages[0].get_by_role('button', name='发送失败，重试')
            expect(retry_button).to_be_visible(timeout=15000)
            retry_button.click()
            expect(textarea).to_have_value('', timeout=15000)
            sent = call(0, 'GET', 'timeline?keyword=' + '网络超时幂等重试测试')
            assert len(sent['items']) == 1
            pages[0].unroute(pattern)
            results['ime_and_retry_idempotency'] = True
            contexts[1].set_offline(True)
            call(0, 'POST', f"messages/{sent['items'][0]['id']}/recall")
            call(0, 'POST', 'messages', {'content': '断线期间的新消息', 'client_message_id': str(uuid4())})
            contexts[1].set_offline(False)
            expect(pages[1].locator('.group-content', has_text='断线期间的新消息')).to_be_visible(timeout=20000)
            expect(pages[1].locator('.group-content', has_text='网络超时幂等重试测试')).to_have_count(0, timeout=20000)
            results['reconnect_restores_new_and_recalled_messages'] = True
            header = pages[0].locator('.project-chat-window__header').bounding_box()
            pages[0].mouse.move(header['x'] + 4, header['y'] + 20)
            pages[0].mouse.down(); pages[0].mouse.move(2400, -400, steps=10); pages[0].mouse.up()
            moved = pages[0].locator('.project-chat-window').bounding_box()
            assert moved['x'] >= 0 and moved['y'] >= 0 and moved['x'] + moved['width'] <= 1440
            pages[0].get_by_role('button', name='关闭项目沟通').click()
            row = pages[0].locator('.el-table__row', has_text=project.order_no).first
            row.get_by_role('button', name='更多').click()
            pages[0].get_by_role('menuitem', name='沟通', exact=True).click()
            reopened = pages[0].locator('.project-chat-window').bounding_box()
            assert reopened['y'] > moved['y']
            results['drag_bounds_close_and_reopen'] = True
            pages[0].screenshot(path=str(OUT / 'desktop.png'))
            pages[0].set_viewport_size({'width': 390, 'height': 700})
            pages[0].screenshot(path=str(OUT / 'mobile.png'))
            window = pages[0].locator('.project-chat-window').bounding_box()
            assert window['x'] >= 0 and window['x'] + window['width'] <= 391
            expect(pages[0].locator('.annotation-group:visible').get_by_role('button', name='发送', exact=True)).to_be_visible()
            results['small_screen'] = True
            results['page_errors'] = errors
            assert not errors, errors
            browser.close()
    except Exception:
        for index, page in enumerate(locals().get('pages', [])):
            try:
                page.screenshot(path=str(OUT / f'failure-{index}.png'))
            except Exception:
                pass
        raise
    finally:
        db.rollback()
        db.query(AppNotification).filter(AppNotification.recipient_user_id.in_(uid)).delete(synchronize_session=False)
        db.query(AnnotationProject).filter(AnnotationProject.id == project.id).delete(synchronize_session=False)
        db.query(UserRole).filter(UserRole.user_id.in_(uid)).delete(synchronize_session=False)
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete(synchronize_session=False)
        db.query(AppUser).filter(AppUser.id.in_(uid)).delete(synchronize_session=False)
        db.query(Role).filter(Role.id == role_id).delete(synchronize_session=False)
        db.commit(); db.close()
        (OUT / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(results, ensure_ascii=True))


if __name__ == '__main__':
    main_test()
