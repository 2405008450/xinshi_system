"""本机资源开拓交互验收；真实页面配合隔离接口，不修改业务数据。"""
import copy
import json
import re
import socket
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:12428'


def run():
    if socket.gethostname().upper() != 'PC' or str(ROOT).lower() != r'e:\xinshi_system':
        raise SystemExit('仅允许在本机执行')
    out = ROOT / '.tmp' / 'resource-optimization-ui'
    out.mkdir(parents=True, exist_ok=True)
    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--outDir', '../.tmp/resource-optimization-dist', '--host', '127.0.0.1', '--port', '12428', '--strictPort'], cwd=ROOT / 'frontend', stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    uid, owner, rid, platform, language, account, person = [str(uuid4()) for _ in range(7)]
    today = date.today().isoformat()
    latest = (date.today() - timedelta(days=30)).isoformat()
    row = dict(id=rid, revision=1, full_name='验收人才', owner_id=owner, owner_name='原开拓人', platform_id=platform, platform_name='测试平台', account_id=account, account_name='HR1', work_date=latest, language_ids=[language], language_names='测试语种', phone='', wechat='', follow_up='', remarks='', actions=[], capabilities=[], person_id=person, resource_code='QA-001', progress={}, can_edit=True, can_delete=True, add_friend_follow_up='')
    requests, saves, errors = [], [], []
    friend = dict(revision=0, rows=[], audit=[], updated_at=None)

    def api(route):
        req = route.request
        path = urlparse(req.url).path.removeprefix('/api')
        query = parse_qs(urlparse(req.url).query)
        requests.append((req.method, path, query))
        result = []
        if path == '/auth/session':
            result = dict(id=uid, username='qa', full_name='实际操作人', roles=['admin'], permissions=['talents:read', 'talents:write', 'resource_development:delegate'])
        elif path == '/resource-development/options':
            result = dict(options=[dict(id=platform, kind='platform', category='national', name='测试平台'), dict(id=account, kind='account', name='HR1')], users=[dict(id=uid,name='实际操作人'),dict(id=owner,name='原开拓人')], languages=[dict(id=language,label='测试语种',language_type='language')], user_id=uid, is_admin=True, can_delegate=True, can_write=True, default_date=today)
        elif path == '/resource-development/friend-daily/options':
            result = dict(accounts=[dict(key='w',label='HR1',channel='wechat'),dict(key='e',label='HR1企微',channel='enterprise')],languages=[dict(id=language,label='测试语种',language_type='language',overview_key='test')],overview_rows=[dict(key='test',label='测试语种')],can_write=True)
        elif path.startswith('/resource-development/friend-daily/'):
            if req.method == 'PUT':
                payload = req.post_data_json
                saves.append(('friend',payload))
                friend.update(rows=payload['rows'],revision=friend['revision']+1)
            result = friend
        elif path == '/resource-development/days':
            matches = query.get('start', [''])[0] <= latest <= query.get('end', ['9999-12-31'])[0]
            result = dict(total=1 if matches else 0,items=[dict(date=latest,count=1,people=[dict(owner_id=owner,owner_name='原开拓人',duration_minutes=0,count=1)])] if matches else [])
        elif path == '/resource-development/records':
            if req.method == 'POST':
                payload = req.post_data_json
                saves.append(('record',copy.deepcopy(payload)))
                row.update(payload,revision=row['revision']+1)
                result = row
            else:
                result = dict(total=1,items=[row])
        elif path.startswith('/resource-development/records/'):
            result = row
        elif path == '/resource-development/duplicates':
            result = dict(items=[])
        elif path == '/resource-development/record-duplicates':
            result = dict(total=0, items=[])
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        route.fulfill(status=200,json=result)

    def choose(page, dialog, text):
        dialog.locator('.el-form-item').filter(has=page.locator('label',has_text='加微跟进')).first.locator('.el-select').click()
        page.get_by_role('option',name=text,exact=True).click()

    try:
        for _ in range(50):
            try:
                urlopen(BASE,timeout=1).close()
                break
            except Exception:
                time.sleep(.2)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True,channel='msedge')
            context = browser.new_context(viewport=dict(width=1440,height=900),timezone_id='Asia/Hong_Kong')
            context.route('**/api/**',api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page()
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(BASE+'/resource-management/resource-development')
            expect(page.get_by_role('heading',name='资源开拓',exact=True)).to_be_visible()
            expect(page.get_by_role('button',name='填写加微跟进')).to_be_visible()
            first = next(q for _,p,q in requests if p.endswith('/days'))
            assert 'start' not in first and 'end' not in first
            initial_records = next(q for _,p,q in requests if p.endswith('/records'))
            assert initial_records['start'] == initial_records['end'] == [latest]
            assert initial_records['limit'] == ['10']
            date_editor = page.locator('.development-filters .el-date-editor')
            date_inputs = date_editor.locator('input')
            expect(date_inputs.nth(0)).to_have_value('')
            expect(date_inputs.nth(1)).to_have_value('')
            page.screenshot(path=str(out/'default-history.png'),full_page=True)
            date_inputs.nth(0).fill(today)
            date_inputs.nth(1).fill(today)
            date_inputs.nth(1).press('Enter')
            page.get_by_role('heading',name='资源开拓',exact=True).click()
            expect(page.get_by_text('所选日期暂无开拓记录，可调整或清空日期查询历史数据',exact=True)).to_be_visible()
            date_editor.hover()
            date_editor.locator('.el-range__close-icon').click()
            expect(page.get_by_role('button',name='填写加微跟进')).to_be_visible()
            assert 'start' not in next(q for _,p,q in reversed(requests) if p.endswith('/days'))
            date_inputs.nth(0).fill(today)
            date_inputs.nth(1).fill(today)
            date_inputs.nth(1).press('Enter')
            page.get_by_role('button',name='重置',exact=True).click()
            expect(page.get_by_role('button',name='填写加微跟进')).to_be_visible()
            expect(date_inputs.nth(0)).to_have_value('')
            assert 'start' not in next(q for _,p,q in reversed(requests) if p.endswith('/days'))
            titles = [t.strip() for t in page.locator('.el-table__header th').all_text_contents()]
            assert titles.index('加微跟进') == titles.index('企微')+1
            search = page.get_by_placeholder('姓名、招呼编号、联系方式、语种/方言')
            before = len([r for r in requests if r[1].endswith('/days')])
            search.fill('测试语种'); page.wait_for_timeout(200)
            assert len([r for r in requests if r[1].endswith('/days')]) == before
            page.wait_for_timeout(500)
            assert next(q for _,p,q in reversed(requests) if p.endswith('/records'))['keyword'] == ['测试语种']
            search.fill(''); page.wait_for_timeout(200)
            assert 'keyword' not in next(q for _,p,q in reversed(requests) if p.endswith('/days'))
            page.get_by_role('button',name='填写加微跟进').click()
            dialog = page.locator('.development-dialog')
            expect(dialog).to_be_visible()
            choose(page,dialog,'已添加微信和企微')
            expect(dialog.get_by_text('进入人才总库',exact=True)).to_have_count(0)
            for field in dialog.locator('.el-form-item').filter(has=page.locator('label',has_text='操作人员')).all():
                expect(field).to_contain_text('实际操作人')
            page.wait_for_timeout(350)
            start = dialog.bounding_box()
            header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x']+35,header['y']+15)
            page.mouse.down(); page.mouse.move(header['x']+130,header['y']+70,steps=8); page.mouse.up()
            moved = dialog.bounding_box()
            assert abs(moved['x']-start['x']) > 40
            page.mouse.move(moved['x']+35,moved['y']+15)
            page.mouse.down(); page.mouse.move(3000,3000,steps=8); page.mouse.up()
            bounds = dialog.bounding_box()
            assert bounds['x'] >= -1 and bounds['y'] >= -1
            assert bounds['x']+bounds['width'] <= 1441 and bounds['y']+bounds['height'] <= 901
            dialog.locator('.el-dialog__headerbtn').click()
            expect(dialog).not_to_be_visible()
            page.get_by_role('button',name='填写加微跟进').click()
            expect(dialog).to_be_visible(); page.wait_for_timeout(350)
            restored = dialog.bounding_box()
            assert abs(start['x']-restored['x'])<2 and abs(start['y']-restored['y'])<2
            choose(page,dialog,'已添加微信和企微')
            dialog.get_by_role('button',name='保存',exact=True).click()
            expect(dialog).not_to_be_visible()
            payload = next(x for kind,x in reversed(saves) if kind=='record')
            assert 'friend_choice' not in payload
            assert [a['channel'] for a in payload['actions']] == ['wechat','enterprise']
            assert all(a['operator_id']==uid and a['action_date']==today and a['status']=='已添加' for a in payload['actions'])
            expected_statuses = ['未处理', '搜不到', '一次请求', '一次请求未通过', '二次请求', '二次请求未通过', '三次请求', '三次请求未通过', '已添加', '（对方）已删']
            # 分别从微信、企微列打开快捷跟进，验证实际下拉、默认值及保存请求。
            for index, channel in enumerate(['wechat', 'enterprise']):
                for status in expected_statuses[2:]:
                    if status == '已添加':
                        continue
                    page.locator('.el-table__body-wrapper button.development-progress').nth(index).click()
                    current = dialog.locator('.development-action:visible').last
                    select = current.locator('.el-form-item').filter(has=page.locator('label', has_text='跟进状态')).locator('.el-select')
                    expect(select).to_contain_text('已添加')
                    select.click()
                    options = page.get_by_role('option').filter(visible=True)
                    expect(options).to_have_text(expected_statuses)
                    page.get_by_role('option', name=status, exact=True).click()
                    expect(dialog.get_by_text('进入人才总库', exact=True)).to_have_count(0)
                    dialog.get_by_role('button', name='保存', exact=True).click()
                    expect(dialog).not_to_be_visible()
                    latest_payload = next(x for kind, x in reversed(saves) if kind == 'record')
                    assert latest_payload['actions'][-1]['channel'] == channel
                    assert latest_payload['actions'][-1]['status'] == status
            page.get_by_role('button', name=re.compile('^高级筛选')).click()
            advanced = page.locator('.development-advanced:visible')
            advanced.locator('.el-select').last.click()
            expect(page.get_by_role('option').filter(visible=True)).to_have_text(expected_statuses)
            page.get_by_role('option', name='（对方）已删', exact=True).click()
            page.wait_for_timeout(350)
            for suffix in ['/days', '/records']:
                assert next(q for _, p, q in reversed(requests) if p.endswith(suffix))['state'] == ['（对方）已删']
            page.get_by_role('button', name='重置', exact=True).click()
            expect(page.locator('.el-loading-mask:visible')).to_have_count(0)
            # 表头多选必须使用同一组新状态，确认后才发出查询。
            page.get_by_role('button', name='微信筛选', exact=True).click()
            funnel = page.locator('.column-header-filter-popover:visible')
            expect(funnel.locator('.el-checkbox__label')).to_have_text(expected_statuses)
            funnel.get_by_text('一次请求未通过', exact=True).click()
            funnel.get_by_text('（对方）已删', exact=True).click()
            funnel.get_by_role('button', name='确定', exact=True).click()
            page.wait_for_timeout(350)
            for suffix in ['/days', '/records']:
                filters = json.loads(next(q for _, p, q in reversed(requests) if p.endswith(suffix))['column_filters'][0])
                assert filters['wechat_status'] == ['一次请求未通过', '（对方）已删']
            page.get_by_role('button', name='清空列筛选', exact=True).click()
            page.get_by_role('button',name='新增统计',exact=True).click()
            daily = page.locator('.friend-daily-dialog')
            expect(daily).to_contain_text('每日新增微信/企微好友统计')
            assert requests[-1][1] == '/resource-development/friend-daily/'+latest
            daily.locator('.friend-language-col .el-select').click()
            page.get_by_role('option',name='未知',exact=True).click()
            expect(daily.get_by_text('概览对应语种',exact=True)).to_have_count(0)
            daily.locator('input[data-grid-account="w"]').fill('3')
            daily.get_by_role('button',name='保存',exact=True).click()
            expect(daily).not_to_be_visible()
            payload = next(x for kind,x in reversed(saves) if kind=='friend')
            assert payload['rows'][0]['language_value']=='__unknown__' and payload['rows'][0]['count']==3
            for button,title in [('新增','新增资源开拓'),('编辑','编辑资源开拓')]:
                page.get_by_role('button',name=button,exact=True).click()
                expect(dialog).to_contain_text(title)
                if button == '新增':
                    dialog.get_by_role('button', name='新增一次跟进', exact=True).click()
                    current = dialog.locator('.development-action:visible').last
                    expect(current.locator('.el-form-item').filter(has=page.locator('label', has_text='跟进状态'))).to_contain_text('一次请求')
                for pos in [0,400,100000]:
                    dialog.locator('.el-dialog__body').evaluate('(el,pos)=>el.scrollTop=pos',pos)
                    expect(dialog.get_by_role('button',name='保存',exact=True)).to_be_visible()
                    expect(dialog.get_by_role('button',name='取消',exact=True)).to_be_visible()
                assert dialog.evaluate("el=>getComputedStyle(el).overflow==='hidden'")
                dialog.get_by_role('button',name='取消',exact=True).click()
            page.set_viewport_size(dict(width=600,height=760))
            page.get_by_role('button',name='填写加微跟进').click()
            expect(dialog).to_be_visible()
            page.wait_for_timeout(450)  # 等待弹窗动画结束后检查小屏实际布局。
            box=dialog.bounding_box()
            assert box['width']<=568 and box['y']+box['height']<=761
            page.screenshot(path=str(out/'small-screen.png'),full_page=True)
            dialog.get_by_role('button',name='取消',exact=True).click()
            assert not errors, errors
            browser.close()
        print(json.dumps(dict(ok=True,checks=['默认历史记录与每页10条','日期筛选、清空与重置','列顺序','防抖与清空','双渠道添加','实际操作人','未知统计','拖动与边界','关闭与复位','新增编辑固定底部','小屏窗口','微信企微全部新状态及保存','请求未通过和已删不显示入库表单','新增一次请求与快捷已添加默认值','高级筛选与表头多选新状态']),ensure_ascii=False))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


if __name__ == '__main__':
    run()
