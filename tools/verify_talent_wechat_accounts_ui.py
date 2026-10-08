"""本机真实页面账号控件验收；接口隔离，不写入业务数据。"""
import copy
import json
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:12448'


def run(out):
    uid, platform, account, person_id, record_id = [str(uuid4()) for _ in range(5)]
    errors, saves, checks = [], [], []
    talent = dict(id=person_id, full_name='账号验收人才', chinese_name='账号验收人才', resource_code='QA-ACCOUNTS',
                  status='active', capability_types=['annotation'], capabilities=[dict(capability_type='annotation', status='active')],
                  wechat_accounts=['HR1', 'HR2企微', '已删微信'], wechat_accounts_revision=5,
                  wechat_account='HR1、HR2企微、已删微信', wechat='personal_wechat',
                  other_names=[], education_experiences=[], language_skills=[], certificates=[], attachments=[])
    record = dict(id=record_id, full_name='账号验收人才', greeting_no='QA-ACCOUNTS-001', revision=2,
                  platform_id=platform, platform_name='验收平台', owner_id=uid, owner_name='验收人员',
                  account_id=account, account_name='交换旧账号', friend_accounts=['HR1', 'HR2企微'],
                  friend_accounts_text='HR1、HR2企微', work_date='2026-10-08', phone='', wechat='personal_wechat',
                  language_ids=[], language_names='', person_id=person_id, resource_code='QA-ACCOUNTS',
                  follow_up='', follow_ups=[], remarks='', historical_markers={}, actions=[], audit=[],
                  progress={'wechat': dict(status='（对方）已删', action_date='2026-10-08', operator_name='验收人员', source='talent', synchronized=True)},
                  wechat_status='（对方）已删', enterprise_status='未处理', can_edit=True, can_delete=True)

    def api(route):
        request = route.request
        path = urlparse(request.url).path.removeprefix('/api').rstrip('/')
        result = []
        if path == '/auth/session':
            result = dict(user_id=uid, username='账号验收', roles=['admin'], permissions=['*'])
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        elif path.startswith('/projects/languages'):
            result = []
        elif path == '/resource-development/options':
            result = dict(user_id=uid, can_write=True, can_delegate=True, is_admin=True, default_date='2026-10-08',
                options=[dict(id=platform, kind='platform', name='验收平台', category='national'),
                         dict(id=account, kind='account', name='交换旧账号')], users=[dict(id=uid, name='验收人员')], languages=[])
        elif path == '/resource-development/days':
            result = dict(total=1, items=[dict(date='2026-10-08', count=1, people=[dict(duration_minutes=0)])])
        elif path == '/resource-development/record-duplicates' or path == '/resource-development/duplicates':
            result = dict(total=0, items=[])
        elif path == '/resource-development/records':
            if request.method == 'GET':
                result = dict(items=[record], total=1)
            else:
                data = request.post_data_json
                saves.append(('development', copy.deepcopy(data)))
                result = {**record, **data, 'revision': record['revision'] + 1}
        elif path == '/resource-development/records/' + record_id:
            result = record
        elif path == '/talents/page':
            result = dict(items=[talent], total=1)
        elif path == '/talents/' + person_id:
            if request.method == 'PUT':
                data = request.post_data_json
                saves.append(('talent', copy.deepcopy(data)))
                talent.update(data)
                if 'wechat_accounts' in data:
                    talent['wechat_accounts_revision'] += 1
                    talent['wechat_account'] = '、'.join(talent['wechat_accounts'])
            result = talent
        elif path == '/talents' and request.method == 'POST':
            data = request.post_data_json
            saves.append(('talent-create', copy.deepcopy(data)))
            result = {**data, 'id': str(uuid4()), 'resource_code': 'QA-CREATE', 'wechat_accounts_revision': 1}
        route.fulfill(content_type='application/json', body=json.dumps(result, ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True, args=['--no-proxy-server'])
        context = browser.new_context(viewport=dict(width=1440, height=900), timezone_id='Asia/Hong_Kong')
        context.add_init_script("localStorage.setItem('token','isolated-wechat-qa')")
        context.route('**/api/**', api)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))

        def field(dialog, label):
            return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=re.compile('^' + re.escape(label) + '$')))

        def choose(dialog, label, value):
            field(dialog, label).locator('.el-select').click()
            page.get_by_role('option', name=value, exact=True).click()
            dialog.locator('.el-dialog__header').click(position=dict(x=10, y=10))

        def custom(dialog, label, value):
            choose(dialog, label, '其他（自主添加）')
            field(dialog, label).locator('input[maxlength="100"]').fill(value)
            field(dialog, label).get_by_role('button', name='添加', exact=True).click()

        def verify_dialog(dialog):
            header = dialog.locator('.el-dialog__header')
            before = dialog.bounding_box()
            header_box = header.bounding_box()
            page.mouse.move(header_box['x'] + 30, header_box['y'] + 20)
            page.mouse.down()
            page.mouse.move(header_box['x'] + 70, header_box['y'] + 55, steps=8)
            page.mouse.up()
            moved = dialog.bounding_box()
            assert abs(moved['x'] - before['x']) > 10 or abs(moved['y'] - before['y']) > 10
            page.mouse.move(header_box['x'] + 70, header_box['y'] + 55)
            page.mouse.down(); page.mouse.move(-500, -500, steps=10); page.mouse.up()
            bounds = dialog.bounding_box()
            assert bounds['x'] >= -1 and bounds['y'] >= -1
            for position in [0, 300, 10000]:
                dialog.locator('.el-dialog__body').evaluate('(el, y) => el.scrollTop = y', position)
                expect(dialog.locator('.el-dialog__footer').get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
            return before

        page.goto(BASE + '/resource-management/resource-development')
        expect(page.get_by_role('button', name='编辑', exact=True).first).to_be_visible()
        expect(page.locator('.el-table__header')).to_contain_text('交换账号')
        expect(page.locator('.el-table__header')).to_contain_text('添加微信')
        expect(page.locator('.el-table__header')).to_contain_text('加微账号')
        page.get_by_role('button', name='查看详情', exact=True).first.click()
        detail = page.locator('.development-detail:visible')
        expect(detail).to_contain_text('HR1、HR2企微')
        expect(detail).to_contain_text('联系状态同步')
        page.locator('.development-heading h2').click()
        page.get_by_role('button', name='编辑', exact=True).first.click()
        dialog = page.locator('.development-dialog:visible')
        expect(field(dialog, '交换账号').locator('.el-select')).not_to_have_class(re.compile('is-multiple'))
        expect(field(dialog, '加微账号').locator('.el-tag')).to_have_count(2)
        choose(dialog, '加微账号', 'HR3')
        custom(dialog, '加微账号', '自定义开拓账号')
        original = verify_dialog(dialog)
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        assert saves[-1][1]['friend_accounts'] == ['HR1', 'HR2企微', 'HR3', '自定义开拓账号']
        assert saves[-1][1]['account_id'] == account
        page.get_by_role('button', name='编辑', exact=True).first.click()
        expect(dialog).to_be_visible()
        page.wait_for_timeout(350)  # 等待 Element Plus 入场动画结束后比较实际位置。
        restored = dialog.bounding_box()
        assert abs(restored['x'] - original['x']) < 2 and abs(restored['y'] - original['y']) < 2, (original, restored)
        dialog.locator('.el-dialog__headerbtn').click()
        page.get_by_role('button', name='新增', exact=True).click()
        expect(field(dialog, '加微账号').locator('.el-tag')).to_have_count(0)
        choose(dialog, '加微账号', 'HR6企微')
        dialog.locator('.el-dialog__headerbtn').click()
        checks.append('资源开拓新增/编辑、多选自定义、交换账号单选、详情同步来源、拖动边界、位置复位、固定底栏')

        page.goto(BASE + '/resource-management/talents')
        page.get_by_role('button', name='编辑', exact=True).first.click()
        dialog = page.locator('.talent-editor-dialog:visible')
        expect(field(dialog, '所在微信').locator('.el-tag')).to_have_count(3)
        expect(field(dialog, '微信').locator('input')).to_have_value('personal_wechat')
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        assert 'wechat_accounts' not in saves[-1][1]  # 未修改账号不提交旧快照。
        page.get_by_role('button', name='编辑', exact=True).first.click()
        choose(dialog, '所在微信', '已删微信')  # 取消已选的删除标记。
        choose(dialog, '所在微信', '已删企微')
        custom(dialog, '所在微信', '自定义总库账号')
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        assert saves[-1][1]['wechat_accounts'] == ['HR1', 'HR2企微', '已删企微', '自定义总库账号']
        assert saves[-1][1]['wechat_accounts_revision'] == 5
        page.get_by_role('button', name='新增人才', exact=True).click()
        choose(dialog, '所在微信', 'HR4')
        choose(dialog, '所在微信', 'HR5企微')
        field(dialog, '中文姓名').locator('input').fill('新账号验收人才')
        field(dialog, '专业能力').locator('label.el-checkbox').filter(has_text='笔译').click()
        page.set_viewport_size(dict(width=600, height=760))
        bounds = dialog.bounding_box()
        assert bounds['width'] <= 568 + 1
        dialog.locator('.el-dialog__body').evaluate('(el) => el.scrollTop = 10000')
        expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
        page.screenshot(path=str(out / 'small-screen.png'))
        dialog.get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        assert saves[-1][1]['wechat_accounts'] == ['HR4', 'HR5企微']
        checks.append('人才总库新增/编辑、多选删除标记、自定义、未变更省略提交、版本号、本人微信独立、小屏固定底栏')
        assert not errors, errors
        browser.close()
    (out / 'result.json').write_text(json.dumps(dict(ok=True, checks=checks, page_errors=errors), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(ok=True, checks=checks), ensure_ascii=False))


def main():
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在本机执行')
    out = ROOT / '.tmp' / 'talent-wechat-ui'
    out.mkdir(parents=True, exist_ok=True)
    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/talent-wechat-dist',
        '--host', '127.0.0.1', '--port', '12448', '--strictPort'], cwd=ROOT / 'frontend', stdout=log,
        stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(50):
            try:
                urlopen(BASE, timeout=1).close(); break
            except Exception:
                time.sleep(.2)
        run(out)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


if __name__ == '__main__':
    main()
