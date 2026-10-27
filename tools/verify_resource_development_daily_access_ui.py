"""在本机真实前端用零权限账号和隔离接口验收；所有 API 请求均拦截。"""
import copy
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://localhost:3000'


def run():
    uid, owner, rid, platform = [str(uuid4()) for _ in range(4)]
    day = '2026-10-27'
    row = dict(id=rid, revision=1, platform_id=platform, platform_name='隔离测试平台',
               owner_id=owner, owner_name='原开拓人', full_name='隔离资源', work_date=day,
               account_id=None, friend_accounts=[], language_ids=[], language_names='',
               phone='******', wechat='******', whatsapp='******', xiaohongshu='******',
               custom_accounts=[], custom_fields={}, remarks='受限内容', follow_up='受限内容',
               actions=[], follow_ups=[], capabilities=[], progress={}, person_id=None,
               can_edit=True, can_delete=False, contact_restricted=True)
    arrangement = dict(work_date=day, revision=0, remarks='', cells=[], can_manage=True)
    saves, errors = [], []

    def api(route):
        request = route.request
        path = urlparse(request.url).path.removeprefix('/api')
        result = []
        if path == '/auth/session':
            result = dict(user_id=uid, username='isolated', full_name='普通用户', roles=['普通用户'], permissions=[])
        elif path == '/resource-development/issues/access':
            result = dict(ready=True, can_enter=False, can_collect=False, can_manage=False, can_resource=False)
        elif path == '/resource-development/options':
            result = dict(options=[dict(id=platform, kind='platform', name='隔离测试平台', category='national')],
                          arrangement_platforms=[dict(id=platform, name='隔离测试平台', category='national')],
                          users=[dict(id=uid, name='普通用户'), dict(id=owner, name='原开拓人')], languages=[],
                          user_id=uid, is_admin=False, can_delegate=False, can_write=True, can_configure=False,
                          default_date=day, custom_account_fields=[])
        elif path == '/resource-development/days':
            result = dict(total=1, items=[dict(date=day, count=1, people=[dict(owner_id=owner, duration_minutes=0)])])
        elif path == '/resource-development/records':
            if request.method == 'POST':
                saves.append(copy.deepcopy(request.post_data_json))
                result = row | dict(revision=2)
            else:
                result = dict(total=1, items=[row])
        elif path == f'/resource-development/records/{rid}':
            result = row
        elif path in ('/resource-development/duplicates', '/resource-development/record-duplicates'):
            result = dict(items=[], total=0)
        elif path == '/resource-development/friend-daily/options':
            result = dict(accounts=[], languages=[], overview_rows=[], can_write=True, can_configure=False)
        elif path.startswith('/resource-development/friend-daily/'):
            result = dict(work_date=day, rows=[], revision=0, audit=[], can_write=True, can_configure=False)
        elif path == '/resource-development/work':
            result = dict(id=str(uuid4()), work_date=day, owner_id=owner, periods=[], deduction=0,
                          completed=True, explanation='受限内容', duration_minutes=0, revision=1,
                          can_edit=True, contact_restricted=True, screenshots=[])
        elif path == '/resource-development/arrangements':
            result = dict(total=1, items=[arrangement])
        elif path.startswith('/resource-development/arrangements/'):
            result = arrangement
        elif path == '/resource-development/arrangement-options':
            result = dict(targets=[], request_projects=[], projects=[])
        elif path == '/resource-development/arrangement-requests':
            result = dict(items=[], total=0)
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        route.fulfill(status=200, json=result)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel='msedge')
        context = browser.new_context(viewport=dict(width=1440, height=900), timezone_id='Asia/Hong_Kong')
        context.route(re.compile(re.escape(BASE) + r'/api/.*'), api)
        context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_permissions','[]');localStorage.setItem('user_roles','[\"普通用户\"]')")
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/resource-management/resource-development')
        expect(page.locator('.page-title')).to_have_text('资源开拓')
        expect(page.get_by_role('button', name='新增', exact=True)).to_be_visible()
        for label in ('删除管理', '导入预览', '平台与选项'):
            expect(page.get_by_role('button', name=label, exact=True)).to_have_count(0)
        expect(page.get_by_role('tab', name='需求管理')).to_have_count(0)
        expect(page.get_by_role('tab', name='开拓问题')).to_have_count(0)
        page.get_by_role('button', name='编辑', exact=True).click()
        dialog = page.locator('.el-dialog:visible').first
        expect(dialog.get_by_text('编辑资源开拓', exact=True)).to_be_visible()
        phone = dialog.locator('.el-form-item').filter(has=page.locator('label', has_text='资源手机'))
        expect(phone.locator('input')).to_be_disabled()
        expect(phone.locator('input')).to_have_value('无权查看或修改')
        expect(dialog.get_by_role('button', name='增加自定义字段')).to_have_count(0)
        name = dialog.locator('.el-form-item').filter(has=page.locator('label', has_text='资源姓名')).first.locator('input').first
        name.fill('跨人员修改')
        # 长表单只滚动 body，底部保存始终可见；拖拽后重新打开复位。
        page.wait_for_timeout(350)  # 等待 Element Plus 入场动画结束后测量坐标。
        before = dialog.bounding_box()
        header = dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 4, header['y'] + 4)
        page.mouse.down(); page.mouse.move(header['x'] + 84, header['y'] + 54, steps=8); page.mouse.up()
        moved = dialog.bounding_box()
        assert abs(moved['x'] - before['x']) > 20
        header = dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 4, header['y'] + 4)
        page.mouse.down(); page.mouse.move(-500, -500, steps=8); page.mouse.up()
        bounded = dialog.bounding_box()
        assert bounded['x'] >= -1 and bounded['y'] >= -1
        dialog.locator('.el-dialog__body').evaluate('(el) => { el.scrollTop = el.scrollHeight / 2 }')
        expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
        dialog.locator('.el-dialog__body').evaluate('(el) => { el.scrollTop = el.scrollHeight }')
        expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        assert saves and saves[0]['full_name'] == '跨人员修改'
        page.get_by_role('button', name='编辑', exact=True).click()
        expect(dialog).to_be_visible()
        page.wait_for_timeout(350)
        reset = dialog.bounding_box()
        assert abs(reset['x'] - before['x']) < 2 and abs(reset['y'] - before['y']) < 2
        dialog.get_by_role('button', name='关闭窗口', exact=True).click()
        # 新增态仍可输入联系方式、选择开拓人，配置入口继续隐藏。
        page.get_by_role('button', name='新增', exact=True).click(button='right')
        expect(dialog.get_by_text('新增资源开拓', exact=True)).to_be_visible()
        phone = dialog.locator('.el-form-item').filter(has=page.locator('label', has_text='资源手机'))
        expect(phone.locator('input')).to_be_enabled()
        dialog.get_by_role('button', name='关闭窗口', exact=True).click()
        page.get_by_role('button', name='每日工作', exact=True).click()
        work = page.locator('.el-dialog:visible').first
        expect(work.get_by_text('每日开拓工作', exact=True)).to_be_visible()
        work.get_by_role('button', name='关闭窗口', exact=True).click()
        page.get_by_role('button', name='新增统计', exact=True).click()
        stats = page.locator('.el-dialog:visible').first
        expect(stats.get_by_role('button', name='保存', exact=True)).to_be_visible()
        expect(stats.get_by_role('button', name='新增微信 / 企微账号')).to_have_count(0)
        stats.get_by_role('button', name='关闭', exact=True).click()
        page.get_by_role('tab', name='每日安排').click()
        expect(page.get_by_role('button', name='沿用最近一次安排')).to_be_visible()
        expect(page.get_by_role('button', name='增加平台', exact=True)).to_have_count(0)
        page.get_by_role('button', name='编辑当日', exact=True).click()
        editor = page.locator('.el-dialog:visible').first
        expect(editor.get_by_role('button', name='保存', exact=True)).to_be_visible()
        editor.get_by_role('button', name='关闭窗口', exact=True).click()
        page.set_viewport_size(dict(width=390, height=844))
        page.get_by_role('tab', name='开拓日志').click()
        page.get_by_role('button', name='编辑', exact=True).click()
        small = page.locator('.el-dialog:visible').first
        expect(small.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
        page.wait_for_timeout(350)
        assert small.bounding_box()['width'] <= 390 - 30, small.evaluate('(el) => ({ box: el.getBoundingClientRect().toJSON(), style: el.getAttribute("style"), viewport: innerWidth })')
        out = ROOT / '.tmp' / 'resource-development-daily-access'
        out.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out / 'ordinary-user-mobile.png'))
        small.get_by_role('button', name='关闭窗口', exact=True).click()
        assert not errors, errors
        print(json.dumps(dict(result='passed', saves=len(saves), page_errors=errors), ensure_ascii=False))
        browser.close()


if __name__ == '__main__':
    run()
