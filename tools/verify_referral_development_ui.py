"""隔离 PostgreSQL + 真实推荐接口 + 构建页面验收，不启动常驻后端。"""
import base64
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
            context.grant_permissions(['clipboard-read', 'clipboard-write'])
            context.route('**/api/**', api)
            context.add_init_script("localStorage.setItem('token','isolated-referral-qa');localStorage.setItem('user_roles','[\"staff\"]');localStorage.setItem('user_permissions','[\"talents:read\",\"talents:write\"]')")
            context.add_init_script("""window.__referralUrls = new Set();
                const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
                URL.createObjectURL = value => { const url = create(value); window.__referralUrls.add(url); return url };
                URL.revokeObjectURL = url => { window.__referralUrls.delete(url); revoke(url) };""")
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
            page.screenshot(path=str(out / 'empty-form.png'), full_page=True, animations='disabled')
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
            encoded = base64.b64encode(buffer.getvalue()).decode('ascii')

            def paste_image(target, text=''):
                page.evaluate("""async ({encoded, text}) => {
                    const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
                    const contents = {'image/png': new Blob([bytes], {type:'image/png'})};
                    if (text) contents['text/plain'] = new Blob([text], {type:'text/plain'});
                    await navigator.clipboard.write([new ClipboardItem(contents)]);
                }""", dict(encoded=encoded, text=text))
                target.focus(); page.keyboard.press('Control+V')

            def drop_image(target, name):
                target.evaluate("""(el, {encoded, name}) => {
                    const data = new DataTransfer();
                    data.items.add(new File([Uint8Array.from(atob(encoded), c => c.charCodeAt(0))], name, {type:'image/png'}));
                    el.dispatchEvent(new DragEvent('dragenter', {bubbles:true, cancelable:true, dataTransfer:data}));
                    el.dispatchEvent(new DragEvent('drop', {bubbles:true, cancelable:true, dataTransfer:data}));
                }""", dict(encoded=encoded, name=name))

            def assert_released(url):
                page.wait_for_function('(url) => !window.__referralUrls.has(url)', arg=url)

            for label, name in [('拉人凭证','pull'), ('发圈凭证','moments'), ('发群凭证','groups'), ('微信收款码','qr')]:
                cell = item(label).locator('.referral-evidence-cell')
                cell.locator('.referral-evidence-hint').click(); expect(cell).to_be_focused()
                paste_image(cell)
                expect(cell.locator('.referral-evidence-draft')).to_have_count(1)
                preview = cell.locator('.referral-evidence-draft .el-image img').get_attribute('src')
                cell.locator('.referral-evidence-draft .el-image').click()
                expect(page.locator('.el-image-viewer__wrapper')).to_be_visible()
                page.locator('.el-image-viewer__close').click()
                cell.get_by_role('button', name='移除', exact=True).click()
                expect(cell.locator('.referral-evidence-draft')).to_have_count(0); assert_released(preview)
                if name != 'qr':
                    description = item(dict(pull='拉人说明', moments='发圈说明', groups='发群说明')[name]).locator('textarea')
                    description.focus(); page.keyboard.press('Tab'); expect(cell).to_be_focused()
                    description.fill('')
                    paste_image(description, '中文混合说明-' + name)
                    expect(description).to_have_value('中文混合说明-' + name)
                    expect(cell.locator('.referral-evidence-draft')).to_have_count(1)
                    cell.get_by_role('button', name='移除', exact=True).click()
                upload = dict(name=name + '.png', mimeType='image/png', buffer=buffer.getvalue())
                cell.locator('input[type=file]').set_input_files(upload)
                expect(cell.locator('.referral-evidence-draft')).to_have_count(1)
                selected_url = cell.locator('.referral-evidence-draft .el-image img').get_attribute('src')
                if name != 'qr':
                    cell.get_by_role('button', name='移除', exact=True).click()
                drop_image(cell, name + '-拖入.png')
                expect(cell.locator('.referral-evidence-draft')).to_have_count(1)
                assert_released(selected_url)
                if name == 'pull':
                    cell.locator('input[type=file]').set_input_files({**upload, 'name': '第二张.png'})
                    expect(cell.locator('.referral-evidence-draft')).to_have_count(2)
                if name == 'qr':
                    old_url = cell.locator('.referral-evidence-draft .el-image img').get_attribute('src')
                    paste_image(cell)
                    expect(cell.locator('.referral-evidence-draft')).to_have_count(1); assert_released(old_url)
            # 普通文本字段继续保留原生粘贴，不误分配图片类别。
            page.evaluate("navigator.clipboard.writeText('qa_new_wechat')")
            item('推荐人微信').locator('input').fill('')
            item('推荐人微信').locator('input').focus(); page.keyboard.press('Control+V')
            expect(item('推荐人微信').locator('input')).to_have_value('qa_new_wechat')
            expect(dialog.locator('.referral-evidence-draft')).to_have_count(5)
            page.screenshot(path=str(out / 'new-form.png'), full_page=True)
            footer.get_by_role('button', name='保存', exact=True).click()
            expect(dialog.get_by_text('验收模拟：此图片上传失败，请重试', exact=False)).to_be_visible(timeout=30000)
            expect(dialog.get_by_role('button', name='保存并重试图片')).to_be_visible()
            expect(dialog.locator('.referral-evidence-draft')).to_have_count(1)
            expect(dialog.locator('.referral-evidence-draft')).to_contain_text('上传失败')
            expect(dialog.locator('.referral-images .referral-image-card')).to_have_count(4)
            assert len([r for r in state['requests'] if r[0] == 'POST' and r[1] == '/referral-development/records']) == 1
            dialog.get_by_role('button', name='保存并重试图片').click()
            expect(dialog).to_have_count(0, timeout=30000)
            uploads = [r for r in state['requests'] if r[0] == 'POST' and r[1].endswith('/images')]
            assert len(uploads) == 6, uploads
            keyword = page.get_by_placeholder('推荐人姓名、微信')
            keyword.fill('qa_new_wechat'); expect(page.locator('.el-table__body tr')).to_have_count(1)
            expect(page.locator('.el-table__body')).to_contain_text('6.25')
            row = page.locator('.el-table__body tr')
            row.get_by_role('button', name='登记付款').click()
            expect(dialog.get_by_role('button', name='保存并继续新增')).to_have_count(0)
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
            expect(dialog.get_by_role('button', name='保存并继续新增')).to_have_count(0)
            expect(dialog.locator('.referral-images .referral-image-card')).to_have_count(5)
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
            # 连续新增遇到部分上传失败时停留在原记录，成功后才重置人员和凭证。
            page.get_by_role('button', name='新增', exact=True).click()
            item('推广日期').locator('input').fill('2026-09-18'); item('推广日期').locator('input').press('Tab')
            item('推荐人姓名').locator('input').fill('推广验收-连续一')
            item('推荐人微信').locator('input').fill('qa_continue_1')
            item('金额（元）').locator('input').fill('8.00')
            paste_image(item('拉人凭证').locator('.referral-evidence-cell'))
            paste_image(item('发群说明').locator('textarea'), '连续登记说明')
            state['fail_upload'] = True
            before_uploads = len([r for r in state['requests'] if r[0] == 'POST' and r[1].endswith('/images')])
            footer.get_by_role('button', name='保存并继续新增').click()
            expect(dialog.locator('.referral-evidence-draft')).to_have_count(1)
            expect(dialog.get_by_text('验收模拟：此图片上传失败，请重试', exact=False)).to_be_visible(timeout=30000)
            expect(item('推荐人姓名').locator('input')).to_have_value('推广验收-连续一')
            expect(footer).to_contain_text('全部成功后继续新增')
            failed_url = dialog.locator('.referral-evidence-draft .el-image img').get_attribute('src')
            page.screenshot(path=str(out / 'continue-upload-failure.png'), full_page=True)
            footer.get_by_role('button', name='保存并重试图片').click()
            expect(item('推荐人姓名').locator('input')).to_have_value('', timeout=30000)
            expect(item('推荐人姓名').locator('input')).to_be_focused()
            expect(item('推广日期').locator('input')).to_have_value('2026-09-18')
            for label in ['推荐人微信', '金额（元）']:
                expect(item(label).locator('input')).to_have_value('')
            for label in ['拉人说明', '发圈说明', '发群说明', '备注']:
                expect(item(label).locator('textarea')).to_have_value('')
            expect(dialog.locator('.referral-evidence-draft')).to_have_count(0)
            expect(dialog.locator('.referral-image-card')).to_have_count(0); assert_released(failed_url)
            after_uploads = len([r for r in state['requests'] if r[0] == 'POST' and r[1].endswith('/images')])
            assert after_uploads - before_uploads == 3
            first = client.get('/referral-development/records', params={'keyword': 'qa_continue_1'}).json()['items'][0]
            first_detail = client.get('/referral-development/records/' + first['id']).json()
            assert sorted(i['category'] for i in first_detail['images']) == ['groups', 'pull']
            item('推荐人姓名').locator('input').fill('推广验收-连续二')
            item('推荐人微信').locator('input').fill('qa_continue_2')
            item('金额（元）').locator('input').fill('3.00')
            paste_image(item('拉人凭证').locator('.referral-evidence-cell'))
            paste_image(item('微信收款码').locator('.referral-evidence-cell'))
            footer.get_by_role('button', name='保存', exact=True).click(); expect(dialog).to_have_count(0)
            second = client.get('/referral-development/records', params={'keyword': 'qa_continue_2'}).json()['items'][0]
            assert first['id'] != second['id'] and second['work_date'] == '2026-09-18'
            second_detail = client.get('/referral-development/records/' + second['id']).json()
            assert sorted(i['category'] for i in second_detail['images']) == ['pull', 'qr']
            # 版本冲突时禁止凭证变更，重新加载后保留待上传图片；编辑仍可替换收款码。
            keyword.fill('qa_continue_2'); expect(page.locator('.el-table__body tr')).to_have_count(1)
            page.locator('.el-table__body tr').get_by_role('button', name='编辑', exact=True).click()
            expect(dialog.locator('.referral-image-card')).to_have_count(2)
            drop_image(item('发群凭证').locator('.referral-evidence-cell'), '冲突保留.png')
            retained_url = dialog.locator('.referral-evidence-draft .el-image img').get_attribute('src')
            external = {k: second_detail[k] for k in ['id', 'revision', 'work_date', 'full_name', 'wechat', 'amount', 'pull_description', 'moments_description', 'groups_description', 'remarks']}
            external['remarks'] = '其他窗口更正'
            assert client.post('/referral-development/records', json=external).status_code == 200
            footer.get_by_role('button', name='保存', exact=True).click()
            expect(dialog.get_by_role('button', name='重新加载')).to_be_visible()
            expect(item('发群凭证').locator('input[type=file]')).to_be_disabled()
            expect(item('发群凭证').locator('.referral-evidence-cell')).to_have_attribute('tabindex', '-1')
            drop_image(item('发群凭证').locator('.referral-evidence-cell'), '禁止加入.png')
            expect(dialog.locator('.referral-evidence-draft')).to_have_count(1)
            dialog.get_by_role('button', name='重新加载').click()
            expect(item('备注').locator('textarea')).to_have_value('其他窗口更正')
            expect(item('发群凭证').locator('input[type=file]')).to_be_enabled()
            assert dialog.locator('.referral-evidence-draft .el-image img').get_attribute('src') == retained_url
            paste_image(item('微信收款码').locator('.referral-evidence-cell'))
            expect(dialog.get_by_text('新收款码保存成功后替换旧码')).to_be_visible()
            old_qr = next(i['id'] for i in second_detail['images'] if i['category'] == 'qr')
            item('拉人凭证').get_by_role('button', name='删除图片').click()
            page.locator('.el-message-box:visible').get_by_role('button', name='确定', exact=True).click()
            expect(item('拉人凭证').locator('.referral-image-card')).to_have_count(0)
            expect(dialog.locator('.referral-evidence-draft')).to_have_count(2)
            footer.get_by_role('button', name='保存', exact=True).click(); expect(dialog).to_have_count(0)
            final_second = client.get('/referral-development/records/' + second['id']).json()
            assert sorted(i['category'] for i in final_second['images']) == ['groups', 'qr']
            assert next(i['id'] for i in final_second['images'] if i['category'] == 'qr') != old_qr
            for record_id in [first['id'], second['id']]:
                latest = client.get('/referral-development/records/' + record_id).json()
                assert client.delete('/referral-development/records/' + record_id, params={'revision': latest['revision']}).status_code == 200
            keyword.fill(''); expect(page.locator('.el-table__body tr')).to_have_count(20)
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
            expect(dialog.locator('.referral-entry-heading')).not_to_be_visible()
            paste_image(item('发圈凭证').locator('.referral-evidence-cell'))
            expect(item('发圈凭证').locator('.referral-evidence-draft')).to_have_count(1)
            small_url = item('发圈凭证').locator('.referral-evidence-draft .el-image img').get_attribute('src')
            body.evaluate('(el) => { el.scrollTop = el.scrollHeight / 2 }'); expect(footer).to_be_visible()
            body.evaluate('(el) => { el.scrollTop = el.scrollHeight }'); expect(footer).to_be_visible()
            assert dialog.evaluate('(el) => el.scrollWidth <= el.clientWidth')
            page.screenshot(path=str(out / 'small-form.png'), full_page=True, animations='disabled')
            dialog.get_by_role('button', name='取消', exact=True).click(); expect(dialog).to_have_count(0); assert_released(small_url)
            page.get_by_role('button', name='新增', exact=True).click()
            expect(dialog.locator('.referral-evidence-draft')).to_have_count(0)
            dialog.get_by_role('button', name='取消', exact=True).click()
            assert not state['errors'], state['errors']
            browser.close()
        (out / 'summary.json').write_text(json.dumps(dict(result='passed', console_errors=state['errors'], request_count=len(state['requests']),
            scenarios=['新增校验与字段定位','四类凭证原生Ctrl+V、拖入和文件选择','图文混合粘贴保留说明','待上传缩略图及大图预览','收款码替换及预览资源释放',
                       '分类多图及部分上传重试','连续新增保留日期且不串人员或图片','冲突禁止变更及重新加载保留待上传图片','已保存图片即时删除',
                       '付款登记与撤销','已支付金额更正','详情左侧弹出及滚动','图片原图预览',
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
