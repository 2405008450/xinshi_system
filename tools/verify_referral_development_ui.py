"""隔离 PostgreSQL + 真实推荐接口 + 构建页面验收，不启动常驻后端。"""
import json
from datetime import date
from io import BytesIO
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system\.tmp\referral-verification-workspace':
        raise SystemExit('仅允许在本机隔离工作区运行')
    from database import engine, SessionLocal
    from models import AppUser
    from referral_development_models import ReferralRecord
    from referral_development_service import now
    from routers.referral_development import router
    from routers.auth import get_current_user
    assert engine.url.host == '127.0.0.1' and engine.url.username == 'referral_test'
    # 注册全套 ORM 关联；只导入应用，不运行启动事件或常驻服务。
    import main  # noqa: F401
    uid, other = uuid4(), uuid4()
    with SessionLocal() as db:
        db.add_all([AppUser(id=uid, username='referral_ui_' + uuid4().hex, full_name='推荐验收员工', password_hash='not-a-login', is_active=True),
                    AppUser(id=other, username='referral_ui_' + uuid4().hex, full_name='其他验收员工', password_hash='not-a-login', is_active=True)])
        for index in range(22):
            db.add(ReferralRecord(id=uuid4(), work_date=date(2026, 8, 26), full_name=f'推广验收-{index:02d}', wechat=f'qa_wechat_{index}',
                                  pull_description='拉人情况', moments_description='', groups_description='', remarks='验收备注',
                                  amount='3.00', payment_status='unpaid', created_by=uid, updated_by=uid,
                                  created_at=now(), updated_at=now(), revision=1))
        db.commit()
        users = {u.id: u for u in db.query(AppUser).filter(AppUser.id.in_([uid, other]))}
        for u in users.values():
            db.expunge(u)
    state = dict(mode='owner', fail_upload=True, fail_delete=None, lists=[], requests=[], errors=[])
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: users[uid if state['mode'] == 'owner' else other]
    out = ROOT / '.tmp/referral-verification/ui'
    out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/referral-dist', '--host', '127.0.0.1', '--port', str(port), '--strictPort'],
                               cwd=ROOT / 'frontend', stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(80):
            try:
                urlopen(base, timeout=1).close(); break
            except Exception:
                time.sleep(.2)
        permissions = lambda *args: ['talents:read', *(['talents:write'] if state['mode'] == 'owner' else [])]
        with patch('routers.auth.get_user_permission_codes', side_effect=permissions), \
             patch('referral_development_service.can_delegate', return_value=False), \
             patch('referral_development_service.is_admin', return_value=False), \
             patch('routers.referral_development.can_delegate', return_value=False), \
             patch('routers.referral_development.is_admin', return_value=False), \
             patch('referral_development_service.can_write', side_effect=lambda *args: state['mode'] == 'owner'), \
             patch('routers.referral_development.can_write', side_effect=lambda *args: state['mode'] == 'owner'), TestClient(app) as client, sync_playwright() as pw:
            def api(route):
                req = route.request; parsed = urlparse(req.url); path = parsed.path.removeprefix('/api')
                state['requests'].append((req.method, path, parsed.query))
                if path == '/auth/session':
                    current = uid if state['mode'] == 'owner' else other
                    route.fulfill(json=dict(user_id=str(current), username='qa', full_name=users[current].full_name, roles=['staff'], permissions=permissions())); return
                if not path.startswith('/referral-development'):
                    route.fulfill(json=dict(count=0, items=[])); return
                if req.method == 'POST' and path.endswith('/images') and state['fail_upload'] and b'groups' in (req.post_data_buffer or b''):
                    state['fail_upload'] = False; route.fulfill(status=422, json={'detail': '验收模拟：此图片上传失败，请重试'}); return
                if req.method == 'DELETE' and path.endswith(str(state['fail_delete'])):
                    state['fail_delete'] = None; route.fulfill(status=409, json={'detail': '验收模拟：记录已被修改'}); return
                headers = {'Content-Type': req.headers.get('content-type', 'application/json')}
                response = client.request(req.method, path + ('?' + parsed.query if parsed.query else ''), content=req.post_data_buffer, headers=headers)
                if path == '/referral-development/records' and req.method == 'GET' and response.status_code == 200:
                    state['lists'].append(response.json())
                route.fulfill(status=response.status_code, body=response.content, content_type=response.headers.get('content-type', 'application/json'))

            browser = pw.chromium.launch(headless=True, channel='msedge')
            context = browser.new_context(viewport=dict(width=1440, height=900), timezone_id='America/New_York')
            context.route('**/api/**', api)
            context.add_init_script("localStorage.setItem('token','isolated-referral-qa');localStorage.setItem('user_roles','[\"staff\"]');localStorage.setItem('user_permissions','[\"talents:read\",\"talents:write\"]')")
            page = context.new_page(); page.on('pageerror', lambda error: state['errors'].append(str(error)))
            page.goto(base + '/resource-management/referral-development')
            expect(page.get_by_role('heading', name='推荐拓展')).to_be_visible()
            expect(page.locator('.el-table__body tr')).to_have_count(20)
            expect(page.locator('.el-table__header th')).to_have_count(10)
            page.get_by_role('button', name='新增', exact=True).click()
            dialog = page.locator('.referral-editor:visible')
            expect(dialog).to_be_visible()
            # 等待 Element Plus 入场动画结束，再比较实际位置。
            page.wait_for_timeout(350)
            initial = dialog.bounding_box()
            footer = dialog.locator('.el-dialog__footer')
            expect(footer.get_by_role('button', name='保存', exact=True)).to_be_visible()
            footer.get_by_role('button', name='保存', exact=True).click()
            expect(dialog.get_by_text('请填写推荐人姓名', exact=True)).to_be_visible()
            def item(label):
                return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=label))
            expect(item('推荐人姓名').locator('input')).to_be_focused()
            item('推荐人姓名').locator('input').fill('推广验收-新记录')
            item('推荐人微信').locator('input').fill('qa_new_wechat')
            item('金额（元）').locator('input').fill('6.25')
            body = dialog.locator('.el-dialog__body')
            body.evaluate('(el) => { el.scrollTop = el.scrollHeight }')
            expect(footer).to_be_visible()
            assert footer.bounding_box()['y'] + footer.bounding_box()['height'] <= 901
            dialog.locator('.dialog-field-search-header input').fill('发群说明')
            page.locator('.project-field-search-popper:visible').get_by_text('发群说明', exact=True).click()
            expect(item('发群说明').locator('textarea')).to_be_focused()
            item('发群说明').locator('textarea').fill('微信群推广')
            expect(footer).to_be_visible()
            buffer = BytesIO(); Image.new('RGB', (40, 40), 'white').save(buffer, 'PNG')
            for label, name in [('拉人凭证','pull'), ('发圈凭证','moments'), ('发群凭证','groups'), ('微信收款码','qr')]:
                upload = dict(name=name + '.png', mimeType='image/png', buffer=buffer.getvalue())
                item(label).locator('input[type=file]').set_input_files([upload, {**upload, 'name': '第二张.png'}] if name == 'pull' else upload)
            page.screenshot(path=str(out / 'new-form.png'), full_page=True)
            footer.get_by_role('button', name='保存', exact=True).click()
            expect(dialog.get_by_text('验收模拟：此图片上传失败，请重试', exact=False)).to_be_visible(timeout=30000)
            expect(dialog.get_by_role('button', name='保存并重试图片')).to_be_visible()
            assert len([r for r in state['requests'] if r[0] == 'POST' and r[1] == '/referral-development/records']) == 1
            dialog.get_by_role('button', name='保存并重试图片').click()
            expect(dialog).to_have_count(0, timeout=30000)
            keyword = page.get_by_placeholder('推荐人姓名、微信')
            keyword.fill('qa_new_wechat'); expect(page.locator('.el-table__body tr')).to_have_count(1)
            expect(page.locator('.el-table__body')).to_contain_text('6.25')
            row = page.locator('.el-table__body tr')
            row.get_by_role('button', name='登记付款').click()
            expect(dialog).to_contain_text('付款登记／更正')
            expect(item('付款日期').locator('input')).not_to_have_value('')
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog).to_have_count(0)
            expect(row).to_contain_text('已支付')
            row.get_by_role('button', name='查看详情').click()
            popover = page.locator('.referral-detail-popover:visible')
            expect(popover).to_contain_text('付款登记／更正')
            expect(popover.locator('.el-image')).to_have_count(5)
            assert popover.get_attribute('data-popper-placement').startswith('left')
            expect(popover.locator('.referral-detail-content')).to_be_visible()
            assert popover.locator('.referral-detail-content').evaluate('(el) => el.scrollHeight > el.clientHeight')
            popover.locator('.el-image').first.click()
            expect(page.locator('.el-image-viewer__wrapper')).to_be_visible()
            page.locator('.el-image-viewer__close').click()
            page.screenshot(path=str(out / 'detail.png'), full_page=True)
            page.mouse.click(220, 70)
            row.get_by_role('button', name='编辑', exact=True).click()
            item('金额（元）').locator('input').fill('8.00')
            dialog.get_by_role('button', name='保存', exact=True).click(); expect(dialog).to_have_count(0)
            expect(row).to_contain_text('8.00'); expect(row).to_contain_text('已支付')
            row.get_by_role('button', name='更正付款').click()
            item('付款状态').locator('.el-select').click()
            page.locator('.el-select-dropdown:visible').get_by_text('未支付', exact=True).click()
            expect(item('付款日期')).to_have_count(0)
            dialog.get_by_role('button', name='保存', exact=True).click(); expect(dialog).to_have_count(0)
            expect(row).to_contain_text('未支付')
            row.get_by_role('button', name='编辑', exact=True).click()
            box = dialog.bounding_box(); header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x'] + 15, header['y'] + 10); page.mouse.down(); page.mouse.move(header['x'] + 90, header['y'] + 40, steps=8); page.mouse.up()
            moved = dialog.bounding_box(); assert abs(moved['x'] - box['x']) > 10
            header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x'] + 15, header['y'] + 10); page.mouse.down(); page.mouse.move(2400, 1700, steps=10); page.mouse.up()
            bounded = dialog.bounding_box(); assert bounded['x'] >= -1 and bounded['y'] >= -1 and bounded['x'] + bounded['width'] <= 1441 and bounded['y'] + bounded['height'] <= 901
            dialog.locator('.el-dialog__headerbtn').click(); expect(dialog).to_have_count(0)
            row.get_by_role('button', name='编辑', exact=True).click()
            page.wait_for_timeout(350)
            reset = dialog.bounding_box(); assert abs(reset['x'] - initial['x']) < 3 and abs(reset['y'] - initial['y']) < 3, {'initial': initial, 'reset': reset}
            dialog.get_by_role('button', name='取消', exact=True).click(); expect(dialog).to_have_count(0)
            keyword.fill(''); expect(page.locator('.el-table__body tr')).to_have_count(20)
            height = page.locator('.el-table').bounding_box()['height']
            page.get_by_role('button', name='高级筛选', exact=True).click()
            advanced = page.locator('.referral-advanced:visible')
            advanced.locator('.el-select').first.click(); page.locator('.el-select-dropdown:visible').get_by_text('其他验收员工', exact=True).click()
            expect(page.get_by_role('button', name='高级筛选（1）')).to_be_visible()
            advanced.get_by_role('button', name='清空高级条件').click(); expect(page.locator('.el-table__body tr')).to_have_count(20)
            advanced.get_by_role('button', name='关闭', exact=True).click()
            assert abs(page.locator('.el-table').bounding_box()['height'] - height) < 3
            page.get_by_role('button', name='字段设置', exact=True).click()
            columns = page.locator('.referral-column-options')
            for checkbox in columns.locator('.el-checkbox').all():
                if checkbox.locator('input').is_checked(): checkbox.click()
            expect(page.locator('.el-table__header th')).to_have_count(3)
            page.mouse.click(220, 70)
            page.reload(); expect(page.locator('.el-table__header th')).to_have_count(3)
            page.get_by_role('button', name='字段设置', exact=True).click(); page.locator('.el-popover:visible').get_by_role('button', name='恢复默认').click()
            expect(page.locator('.el-table__header th')).to_have_count(10)
            page.mouse.click(220, 70)
            page.locator('.el-pagination .btn-next').click(); expect(page.locator('.el-table__body tr')).to_have_count(3)
            state['fail_delete'] = state['lists'][-1]['items'][0]['id']
            page.get_by_role('button', name='删除管理', exact=True).click()
            expect(page.get_by_role('button', name='新增', exact=True)).to_have_count(0)
            expect(page.locator('.el-table__body').get_by_role('button', name='编辑', exact=True)).to_have_count(0)
            page.locator('.el-table__header .el-checkbox').click()
            page.get_by_role('button', name='删除所选（3）').click()
            confirmation = page.locator('.el-message-box:visible'); confirmation.locator('input').fill('删除'); confirmation.get_by_role('button', name='确定删除').click()
            expect(page.get_by_text('已选 1 条', exact=True)).to_be_visible(timeout=30000)
            expect(page.locator('.el-table__body tr')).to_have_count(1)
            page.get_by_role('button', name='删除所选（1）').click(); page.locator('.el-message-box:visible').get_by_role('button', name='确定删除').click()
            expect(page.locator('.el-table__body tr')).to_have_count(20)
            expect(page.locator('.el-pagination .number.is-active')).to_have_text('1')
            page.screenshot(path=str(out / 'list.png'), full_page=True)
            page.get_by_role('button', name='字段设置', exact=True).click()
            page.locator('.referral-column-options .el-checkbox').filter(has_text='推广日期').click()
            expect(page.locator('.el-table__header th')).to_have_count(9)
            page.mouse.click(220, 70)
            state['mode'] = 'readonly'; page.reload()
            expect(page.get_by_role('heading', name='推荐拓展')).to_be_visible()
            expect(page.get_by_role('button', name='新增', exact=True)).to_have_count(0)
            expect(page.locator('.el-table__header th')).to_have_count(10)
            expect(page.locator('.el-table__body')).to_contain_text('只读')
            page.locator('.el-table__body tr').first.get_by_role('button', name='查看详情').click()
            expect(page.locator('.referral-detail-popover:visible')).to_contain_text('微信及凭证仅向本人')
            page.mouse.click(220, 70)
            page.set_viewport_size(dict(width=600, height=800))
            page.get_by_role('button', name='高级筛选', exact=True).click()
            advanced = page.locator('.referral-advanced:visible'); expect(advanced).to_be_visible()
            rect = advanced.bounding_box(); assert rect['x'] >= -1 and rect['x'] + rect['width'] <= 601
            advanced.get_by_role('button', name='关闭', exact=True).click()
            state['mode'] = 'owner'; page.reload()
            expect(page.locator('.el-table__header th')).to_have_count(9)
            page.get_by_role('button', name='新增', exact=True).click()
            expect(dialog).to_be_visible(); rect = dialog.bounding_box(); assert rect['width'] <= 569
            expect(footer.get_by_role('button', name='保存', exact=True)).to_be_visible()
            dialog.get_by_role('button', name='取消', exact=True).click()
            assert not state['errors'], state['errors']
            browser.close()
        (out / 'summary.json').write_text(json.dumps(dict(result='passed', console_errors=state['errors'], request_count=len(state['requests']),
            scenarios=['新增校验与字段定位','分类多图及部分上传重试','付款登记与撤销','已支付金额更正','详情左侧弹出及滚动','图片原图预览',
                       '弹窗拖拽边界及复位','固定底部操作栏','高级条件计数及清空','全部取消列及持久化','用户配置隔离',
                       '批量删除部分失败及末页回退','只读权限','小屏弹窗和筛选']), ensure_ascii=False, indent=2), encoding='utf-8')
        print('推荐拓展真实接口及页面验收通过；浏览器运行错误0')
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


if __name__ == '__main__':
    run()
