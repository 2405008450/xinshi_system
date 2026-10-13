"""团队资源真实前后端浏览器验收，仅连接专用隔离服务。"""
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("TEAM_UI_BASE", "")
OUTPUT = ROOT / ".tmp/resource-teams-qa"


def run():
    if os.getenv("TEAM_RESOURCE_QA") != "1" or urlparse(BASE).hostname != "localhost" or urlparse(BASE).port in {None, 3000, 8000}:
        raise SystemExit("仅允许连接本机专用团队隔离服务")
    errors, results, requests = [], [], []
    fields = ["short_name", "full_name", "team_type", "introduction", "resource_types", "other_resource_description", "resource_situation", "remarks", "contacts", "contact_user_id", "contact_date", "follow_up_user_id", "revision"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel="msedge")

        def new_context(token="isolated-team-editor", timezone="Asia/Hong_Kong", width=1440, height=900):
            context = browser.new_context(viewport={"width": width, "height": height}, timezone_id=timezone)
            context.add_init_script(f"if (!localStorage.getItem('token')) {{ localStorage.setItem('token', {json.dumps(token)}); }} localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page()
            page.set_default_timeout(10000)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append((request.method, request.url)))
            page.goto(BASE + "/resource-management/teams")
            expect(page.get_by_role("heading", name="团队资源", exact=True)).to_be_visible()
            expect(page.locator(".el-loading-mask:visible")).to_have_count(0)
            return context, page

        context, page = new_context()
        headers = {"Authorization": "Bearer isolated-team-editor"}

        def api(method, path, data=None):
            response = context.request.fetch(BASE + "/api" + path, method=method, data=data, headers=headers)
            assert response.ok, f"{method} {path}: {response.status} {response.text()}"
            return response.json() if response.status != 204 else None

        def list_rows(keyword):
            return api("GET", "/teams?keyword=" + keyword)["items"]

        def update(row, **changes):
            return api("PUT", "/teams/" + row["id"], {**{k: row[k] for k in fields}, **changes, "allow_duplicate": True})

        def form_item(dialog, label):
            return dialog.locator(".el-form-item").filter(has=page.locator(".el-form-item__label", has_text=label)).first

        def select(dialog, label, option):
            control = form_item(dialog, label).locator(".el-select")
            control.click()
            menu_id = control.get_by_role("combobox").get_attribute("aria-controls")
            page.locator(f"#{menu_id}").get_by_role("option", name=option, exact=True).click()
            page.keyboard.press("Escape")

        def dialog():
            return page.locator(".team-form-dialog:visible").first

        def footer_check(target):
            body = target.locator(".el-dialog__body")
            for value in [0, 300, 100000]:
                body.evaluate("(el, value) => el.scrollTop = value", value)
                footer = target.locator(".el-dialog__footer").bounding_box()
                assert footer["y"] >= 0 and footer["y"] + footer["height"] <= page.viewport_size["height"] + 1

        def confirm_delete(multiple):
            page.mouse.move(300, 130)
            page.get_by_role("button", name="删除所选", exact=False).click()
            box = page.locator(".el-message-box:visible")
            if multiple: box.locator("input").fill("删除")
            box.get_by_role("button", name="确定删除", exact=True).click()

        expect(page.locator(".el-table__body tr")).to_have_count(20)
        expect(page.locator(".resource-nav__secondary button")).to_have_count(5)
        assert page.locator(".resource-nav__secondary button").last.inner_text() == "团队资源"
        page.screenshot(path=str(OUTPUT / "team-list.png"), full_page=True)
        search = page.get_by_placeholder("团队简称或全称")
        count = lambda: len([r for r in requests if r[0] == "GET" and "/api/teams?" in r[1]])
        before = count(); search.fill("验收公司全称01"); page.wait_for_timeout(150); assert count() == before
        expect(page.locator(".el-table__body tr")).to_have_count(1)
        search.fill(""); expect(page.locator(".el-table__body tr")).to_have_count(20)
        results.append("导航、默认分页、全称搜索、400ms防抖及清空查询")

        held = []
        def hold_old_query(route):
            if parse_qs(urlparse(route.request.url).query).get("keyword") == ["验收团队0"]:
                held.append((route, route.fetch()))
            else:
                route.continue_()
        page.route("**/api/teams?**", hold_old_query)
        search.fill("验收团队0"); page.wait_for_timeout(600)
        assert held, "旧请求必须先发出再验证新请求"
        search.fill("验收团队01"); expect(page.locator(".el-table__body tr")).to_have_count(1)
        held[0][0].fulfill(response=held[0][1])
        page.wait_for_timeout(100)
        expect(page.locator(".el-table__body tr")).to_have_count(1)
        expect(page.locator(".el-table__body tr").first).to_contain_text("验收团队01")
        page.unroute("**/api/teams?**", hold_old_query)
        search.fill(""); expect(page.locator(".el-table__body tr")).to_have_count(20)
        results.append("延迟旧响应不能覆盖新查询")

        height = page.locator(".el-table").bounding_box()["height"]
        page.get_by_role("button", name="高级筛选", exact=True).click()
        popover = page.locator(".team-advanced:visible")
        popover.locator(".el-select").first.click(); page.get_by_role("option", name="验收对接人", exact=True).click()
        expect(page.get_by_role("button", name="高级筛选（1）")).to_be_visible()
        popover.get_by_role("button", name="关闭", exact=True).click()
        assert abs(page.locator(".el-table").bounding_box()["height"] - height) < 2
        page.get_by_role("button", name="重置", exact=True).click()
        results.append("高级筛选计数、关闭保留、重置及表格高度")

        page.get_by_role("button", name="新增团队", exact=True).click()
        target = dialog(); expect(target).to_be_visible(); footer_check(target)
        target.get_by_role("button", name="保存", exact=True).click()
        expect(form_item(target, "团队简称")).to_have_class(re.compile("is-error"))
        expect(form_item(target, "团队简称").locator("input")).to_be_focused()
        form_item(target, "团队简称").locator("input").fill("新增验收团队")
        form_item(target, "团队全称").locator("input").fill("新增验收公司")
        select(target, "团队类型", "小团队")
        select(target, "资源类型", "其他")
        target.get_by_role("button", name="保存", exact=True).click()
        expect(form_item(target, "其他资源说明").locator("input")).to_be_focused()
        form_item(target, "其他资源说明").locator("input").fill("多语种采集")
        target.get_by_role('button', name='编辑团队对接人', exact=True).click()
        contacts_dialog = page.locator('.team-contacts-dialog:visible')
        expect(contacts_dialog.locator('.team-contact-section')).to_have_count(1)
        contacts_dialog.get_by_role('button', name=re.compile('增加对接人')).click()
        contacts_dialog.get_by_role('button', name=re.compile('增加对接人')).click()
        expect(contacts_dialog.locator('.team-contact-section')).to_have_count(3)
        expect(contacts_dialog.get_by_role('button', name=re.compile('增加对接人'))).to_be_disabled()
        for index, section in enumerate(contacts_dialog.locator('.team-contact-section').all()):
            section.locator('textarea').fill(f'private-contact-{index + 1}\n微信：测试账号')
        contacts_dialog.get_by_role('button', name='确定', exact=True).click()
        expect(contacts_dialog.locator('.team-contact-section').first.locator('input').first).to_be_focused()
        for index, section in enumerate(contacts_dialog.locator('.team-contact-section').all()):
            section.locator('input').nth(0).fill(f'联系人{index + 1}')
            section.locator('input').nth(1).fill(f'昵称{index + 1}')
        page.get_by_placeholder('搜索字段，如昵称').fill('昵称')
        page.locator('.el-autocomplete-suggestion:visible li').filter(has_text='对接人3').first.click()
        expect(contacts_dialog.locator('.team-contact-section').nth(2).locator('.el-form-item').nth(1)).to_have_class(re.compile('is-dialog-field-search-highlight'))
        footer_check(contacts_dialog)
        page.set_viewport_size({'width':390,'height':700}); footer_check(contacts_dialog)
        bounds = contacts_dialog.bounding_box(); assert bounds['width'] <= 358 and bounds['y'] + bounds['height'] <= 701
        page.screenshot(path=str(OUTPUT / 'team-contacts-mobile.png'))
        page.set_viewport_size({'width':1440,'height':900}); page.wait_for_timeout(300)
        original = contacts_dialog.bounding_box(); handle = contacts_dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(handle['x'] + 6, handle['y'] + 6); page.mouse.down(); page.mouse.move(handle['x'] + 66, handle['y'] + 26, steps=10); page.mouse.up()
        assert abs(contacts_dialog.bounding_box()['x'] - original['x']) > 30
        handle = contacts_dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(handle['x'] + 6, handle['y'] + 6); page.mouse.down(); page.mouse.move(3000,3000,steps=10); page.mouse.up()
        bounds = contacts_dialog.bounding_box(); assert bounds['x'] >= -1 and bounds['y'] >= -1 and bounds['x'] + bounds['width'] <= 1441 and bounds['y'] + bounds['height'] <= 901
        contacts_dialog.get_by_role('button', name='确定', exact=True).click()
        expect(contacts_dialog).not_to_be_visible(); expect(target).to_be_visible()
        assert list_rows('新增验收团队') == [], '联系人子弹窗不得单独写库'
        results.append('联系人默认一位、上限三位、姓名昵称校验、重复字段搜索、嵌套拖拽边界、小屏固定底部及草稿回填')
        target.get_by_role("button", name="编辑简介", exact=True).click()
        nested = page.locator(".team-form-dialog").filter(has=page.locator(".el-dialog__title", has_text="编辑简介"))
        nested.locator("textarea").fill("团队简介第一行\n团队简介第二行")
        footer_check(nested)
        nested.get_by_role("button", name="确定", exact=True).click()
        assert list_rows("新增验收团队") == [], "子弹窗确定不得单独写数据库"
        target.get_by_role("button", name="编辑资源情况", exact=True).click()
        nested = page.locator(".team-form-dialog").filter(has=page.locator(".el-dialog__title", has_text="编辑资源情况"))
        nested.locator("textarea").fill("仅草稿，不回填")
        nested.get_by_role("button", name="取消", exact=True).click()
        page.locator(".el-message-box:visible").get_by_role("button", name="确定", exact=True).click()
        expect(nested).not_to_be_visible()
        select(target, "信实对接人", "验收对接人"); select(target, "信实跟进人", "验收对接人")
        page.set_viewport_size({"width": 390, "height": 700}); footer_check(target)
        bounds = target.bounding_box(); assert bounds["width"] <= 358 and bounds["y"] + bounds["height"] <= 701
        page.screenshot(path=str(OUTPUT / "team-form-mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 900})
        target.get_by_role("button", name="保存", exact=True).click()
        expect(target).not_to_be_visible()
        row = list_rows("新增验收团队")[0]
        assert row["introduction"] == "团队简介第一行\n团队简介第二行" and row["resource_situation"] == ""
        assert row["contact_user_id"] == row["follow_up_user_id"]
        assert len(row['contacts']) == 3 and row['contacts'][2]['nickname'] == '昵称3'
        results.append("新增校验定位、其他条件必填、文本草稿、嵌套取消、小屏固定底部与同人对接跟进")

        search.fill("新增验收团队"); expect(page.locator(".el-table__body tr")).to_have_count(1)
        page.get_by_role('button', name='联系人1 等3人', exact=True).click()
        contact_popover = page.locator('.team-contacts-popover:visible')
        expect(contact_popover.locator('.el-descriptions')).to_have_count(3)
        expect(contact_popover).to_contain_text('private-contact-1')
        assert contact_popover.get_attribute('data-popper-placement').startswith('left')
        page.screenshot(path=str(OUTPUT / 'team-contacts-details.png'))
        page.get_by_role('heading', name='团队资源', exact=True).click()
        page.get_by_role("button", name="查看详情", exact=True).click()
        details = page.locator(".team-details:not(.team-contacts-popover):visible")
        expect(details.get_by_text("团队简介第一行\n团队简介第二行", exact=True)).to_be_visible()
        assert "el-popper" in details.get_attribute("class") and details.get_attribute("data-popper-placement").startswith("left")
        page.keyboard.press("Escape"); page.get_by_role("heading", name="团队资源", exact=True).click()
        page.get_by_role("button", name="编辑", exact=True).click(); target = dialog(); expect(target).to_be_visible(); footer_check(target)
        expect(form_item(target, "团队全称").locator("input")).to_have_value("新增验收公司")
        target.get_by_role('button', name='编辑团队对接人', exact=True).click()
        contacts_dialog = page.locator('.team-contacts-dialog:visible'); page.wait_for_timeout(300)
        expect(contacts_dialog.locator('.team-contact-section').first.locator('input').first).to_have_value('联系人1')
        assert abs(contacts_dialog.bounding_box()['x'] - original['x']) < 2
        contacts_dialog.locator('.team-contact-section').nth(2).locator('input').nth(1).fill('丢弃昵称')
        contacts_dialog.locator('.el-dialog__headerbtn').click()
        page.locator('.el-message-box:visible').get_by_role('button', name='确定', exact=True).click()
        target.get_by_role('button', name='编辑团队对接人', exact=True).click()
        contacts_dialog = page.locator('.team-contacts-dialog:visible')
        expect(contacts_dialog.locator('.team-contact-section').nth(2).locator('input').nth(1)).to_have_value('昵称3')
        contacts_dialog.get_by_role('button', name='移除对接人3', exact=True).click()
        contacts_dialog.get_by_role('button', name='确定', exact=True).click()
        page.get_by_placeholder("搜索字段，如资源情况").fill("情况")
        suggestion = page.locator(".el-autocomplete-suggestion:visible li").filter(has_text="资源情况").first
        expect(suggestion).to_be_visible(); suggestion.click()
        expect(form_item(target, "资源情况")).to_have_class(re.compile("is-dialog-field-search-highlight"))
        form_item(target, "备注").locator("textarea").fill("本地草稿保留")
        latest = update(row, remarks="另一位用户已修改")
        target.get_by_role("button", name="保存", exact=True).click()
        expect(target.get_by_role("button", name="重新读取最新内容")).to_be_visible()
        expect(form_item(target, "备注").locator("textarea")).to_have_value("本地草稿保留")
        target.get_by_role("button", name="重新读取最新内容").click()
        expect(form_item(target, "备注").locator("textarea")).to_have_value("另一位用户已修改")
        target.get_by_role("button", name="恢复保留的草稿").click()
        expect(form_item(target, "备注").locator("textarea")).to_have_value("本地草稿保留")
        target.get_by_role("button", name="保存", exact=True).click(); expect(target).not_to_be_visible()
        assert list_rows("新增验收团队")[0]["revision"] == latest["revision"] + 1
        page.get_by_role("button", name="查看详情", exact=True).click()
        expect(page.locator(".team-details:not(.team-contacts-popover):visible").get_by_text("本地草稿保留", exact=True)).to_be_visible()
        expect(page.locator('.team-details:not(.team-contacts-popover):visible .team-contact-details section')).to_have_count(2)
        page.get_by_role("heading", name="团队资源", exact=True).click()
        results.append("详情按需加载、左弹出、编辑回显、字段搜索、真实版本冲突、恢复草稿及详情缓存刷新")

        restricted_context, restricted_page = new_context('isolated-team-other')
        restricted_page.get_by_placeholder('团队简称或全称').fill('新增验收团队')
        expect(restricted_page.locator('.el-table__body tr')).to_have_count(1)
        restricted_page.get_by_role('button', name='联系人1 等2人', exact=True).click()
        expect(restricted_page.locator('.team-contacts-popover:visible')).to_contain_text('******')
        assert 'private-contact' not in restricted_page.locator('.team-contacts-popover:visible').inner_text()
        restricted_page.get_by_role('heading', name='团队资源', exact=True).click()
        restricted_page.get_by_role('button', name='编辑', exact=True).click()
        restricted_main = restricted_page.locator('.team-form-dialog:visible').first
        restricted_main.get_by_role('button', name='编辑团队对接人', exact=True).click()
        restricted_contacts = restricted_page.locator('.team-contacts-dialog:visible')
        expect(restricted_contacts.locator('textarea')).to_have_count(0)
        expect(restricted_contacts.get_by_role('button', name='移除对接人2', exact=True)).to_be_disabled()
        restricted_contacts.locator('.team-contact-section').first.locator('input').nth(1).fill('普通用户改昵称')
        restricted_contacts.get_by_role('button', name='确定', exact=True).click()
        restricted_main.get_by_role('button', name='保存', exact=True).click(); expect(restricted_main).not_to_be_visible()
        updated_contacts = list_rows('新增验收团队')[0]['contacts']
        assert updated_contacts[0]['nickname'] == '普通用户改昵称' and updated_contacts[0]['contact_info'].startswith('private-contact-1')
        restricted_context.close()
        results.append('联系人查看小窗、编辑回显、取消丢弃、移除、重开复位、缓存清理及受限用户姓名编辑保护联系方式')

        page.get_by_role('button', name='上传/查看（0）', exact=True).click()
        attachment_dialog = page.locator('.team-attachments-dialog:visible')
        expect(attachment_dialog.get_by_text('暂无附件', exact=True)).to_be_visible()
        files = [{'name': '团队简介.pdf', 'mimeType': 'application/pdf', 'buffer': b'%PDF-1.4\nisolated-team-document'},
                 {'name': '服务清单.txt', 'mimeType': 'text/plain', 'buffer': '中文资料附件验收'.encode('utf-8')}]
        attachment_dialog.locator('input[type=file]').set_input_files(files)
        expect(attachment_dialog.locator('.el-table__body tr')).to_have_count(2)
        with page.expect_download() as downloaded:
            attachment_dialog.locator('.el-table__body tr').filter(has_text='团队简介.pdf').get_by_role('button', name='下载', exact=True).click()
        download = downloaded.value
        assert download.suggested_filename == '团队简介.pdf'
        download.save_as(str(OUTPUT / 'team-document-download.pdf'))
        assert (OUTPUT / 'team-document-download.pdf').read_bytes() == files[0]['buffer']
        fail_once = [True]
        def attachment_failure(route):
            if route.request.method == 'POST' and fail_once[0]:
                fail_once[0] = False
                route.fulfill(status=503, content_type='application/json', body='{"detail":"模拟上传失败"}')
            else: route.continue_()
        page.route('**/api/teams/*/attachments', attachment_failure)
        attachment_dialog.locator('input[type=file]').set_input_files({'name': '重试资料.txt', 'mimeType': 'text/plain', 'buffer': b'retry-file'})
        expect(attachment_dialog.get_by_role('button', name='重试', exact=True)).to_be_visible()
        attachment_dialog.get_by_role('button', name='关闭', exact=True).click()
        warning = page.locator('.el-message-box:visible')
        expect(warning).to_contain_text('未成功上传')
        warning.get_by_role('button', name='取消', exact=True).click()
        attachment_dialog.get_by_role('button', name='重试', exact=True).click()
        expect(attachment_dialog.locator('.el-table__body tr')).to_have_count(3)
        page.unroute('**/api/teams/*/attachments', attachment_failure)
        footer_check(attachment_dialog)
        page.screenshot(path=str(OUTPUT / 'team-attachments.png'))
        page.set_viewport_size({'width':390,'height':700}); footer_check(attachment_dialog)
        bounds = attachment_dialog.bounding_box(); assert bounds['width'] <= 358 and bounds['y'] + bounds['height'] <= 701
        page.screenshot(path=str(OUTPUT / 'team-attachments-mobile.png'))
        page.set_viewport_size({'width':1440,'height':900}); page.wait_for_timeout(300)
        attachment_original = attachment_dialog.bounding_box(); handle = attachment_dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(handle['x']+6,handle['y']+6); page.mouse.down(); page.mouse.move(handle['x']+106,handle['y']+46,steps=10); page.mouse.up()
        assert abs(attachment_dialog.bounding_box()['x'] - attachment_original['x']) > 30
        handle = attachment_dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(handle['x']+6,handle['y']+6); page.mouse.down(); page.mouse.move(3000,3000,steps=10); page.mouse.up()
        bounds = attachment_dialog.bounding_box(); assert bounds['x'] >= -1 and bounds['y'] >= -1 and bounds['x']+bounds['width'] <=1441 and bounds['y']+bounds['height'] <=901
        attachment_dialog.locator('.el-dialog__headerbtn').click(); expect(attachment_dialog).not_to_be_visible()
        expect(page.get_by_role('button', name='上传/查看（3）', exact=True)).to_be_visible()
        page.get_by_role('button', name='上传/查看（3）', exact=True).click(); expect(attachment_dialog).to_be_visible(); page.wait_for_timeout(300)
        assert abs(attachment_dialog.bounding_box()['x'] - attachment_original['x']) < 2
        attachment_dialog.locator('.el-table__body tr').filter(has_text='服务清单.txt').get_by_role('button',name='删除',exact=True).click()
        page.locator('.el-message-box:visible').get_by_role('button',name='删除',exact=True).click()
        expect(attachment_dialog.locator('.el-table__body tr')).to_have_count(2)
        attachment_dialog.get_by_role('button',name='关闭',exact=True).click(); expect(attachment_dialog).not_to_be_visible()
        expect(page.get_by_role('button',name='上传/查看（2）',exact=True)).to_be_visible()
        page.get_by_role('button',name='编辑',exact=True).click(); target=dialog()
        target.get_by_role('button',name='管理资料附件',exact=True).click(); expect(attachment_dialog).to_be_visible()
        expect(attachment_dialog.locator('.el-table__body tr')).to_have_count(2)
        attachment_dialog.get_by_role('button',name='关闭',exact=True).click(); expect(attachment_dialog).not_to_be_visible(); expect(target).to_be_visible()
        target.get_by_role('button',name='取消',exact=True).click(); expect(target).not_to_be_visible()
        file_reader_context, file_reader = new_context('isolated-team-reader')
        file_reader.get_by_placeholder('团队简称或全称').fill('新增验收团队'); expect(file_reader.locator('.el-table__body tr')).to_have_count(1)
        file_reader.get_by_role('button',name='查看附件（2）',exact=True).click()
        reader_files = file_reader.locator('.team-attachments-dialog:visible')
        expect(reader_files.locator('.el-table__body tr')).to_have_count(2)
        expect(reader_files.get_by_role('button',name='上传附件',exact=True)).to_have_count(0)
        expect(reader_files.get_by_role('button',name='删除',exact=True)).to_have_count(0)
        expect(reader_files.get_by_role('button',name='下载',exact=True)).to_have_count(2)
        file_reader_context.close()
        results.append('公共附件组件、中文多文件上传、下载内容校验、失败重试、未上传关闭保护、计数刷新、编辑嵌套入口、拖拽复位、小屏固定底部和只读权限')

        # 空白新增表单便于验证拖动后关闭及再次打开的位置。
        page.get_by_role("button", name="新增团队", exact=True).click(); target = dialog(); page.wait_for_timeout(300)
        original = target.bounding_box(); handle = target.locator(".el-dialog__header").bounding_box()
        page.mouse.move(handle["x"] + 6, handle["y"] + 6); page.mouse.down(); page.mouse.move(handle["x"] + 106, handle["y"] + 46, steps=10); page.mouse.up()
        assert abs(target.bounding_box()["x"] - original["x"]) > 30
        handle = target.locator(".el-dialog__header").bounding_box()
        page.mouse.move(handle["x"] + 6, handle["y"] + 6); page.mouse.down(); page.mouse.move(3000, 3000, steps=10); page.mouse.up()
        moved = target.bounding_box(); assert moved["x"] >= -1 and moved["y"] >= -1 and moved["x"] + moved["width"] <= 1441 and moved["y"] + moved["height"] <= 901
        target.locator(".el-dialog__headerbtn").click(); expect(target).not_to_be_visible()
        page.get_by_role("button", name="新增团队", exact=True).click(); target = dialog(); page.wait_for_timeout(300)
        restored = target.bounding_box(); assert abs(restored["x"] - original["x"]) < 2 and abs(restored["y"] - original["y"]) < 2
        form_item(target, "团队简称").locator("input").fill("新增验收团队")
        select(target, "团队类型", "中小型企业"); select(target, "资源类型", "笔译")
        target.get_by_role("button", name="保存", exact=True).click()
        duplicate = page.locator(".el-message-box:visible")
        expect(duplicate.get_by_text(re.compile("发现同名团队"))).to_be_visible()
        duplicate.get_by_role("button", name="仍然保存", exact=True).click(); expect(target).not_to_be_visible()
        assert len(list_rows("新增验收团队")) == 2
        results.append("拖拽边界、关闭按钮、重开复位及重名确认后独立保存")

        page.get_by_role("button", name="新增团队", exact=True).click(); target = dialog()
        form_item(target, "团队简称").locator("input").fill("未保存草稿")
        target.get_by_role("button", name="取消", exact=True).click()
        page.locator(".el-message-box:visible").get_by_role("button", name="取消", exact=True).click()
        expect(form_item(target, "团队简称").locator("input")).to_have_value("未保存草稿")
        target.locator(".el-dialog__headerbtn").click()
        page.locator(".el-message-box:visible").get_by_role("button", name="确定", exact=True).click()
        expect(target).not_to_be_visible(); assert not list_rows("未保存草稿")
        results.append("主表单放弃确认及取消确认时保留草稿")

        page.get_by_role("button", name="字段设置", exact=True).click()
        columns = page.locator(".table-column-settings-popover:visible")
        expect(columns).to_be_visible()
        expect(columns.locator(".el-checkbox.is-checked")).to_have_count(9)
        while columns.locator(".el-checkbox.is-checked").count():
            columns.locator(".el-checkbox.is-checked").first.click()
        expect(page.locator(".el-table__header th")).to_have_count(3)
        page.get_by_role("heading", name="团队资源", exact=True).click(); page.reload()
        expect(page.locator(".el-table__header th")).to_have_count(3)
        page.evaluate("localStorage.setItem('token', 'isolated-team-other')"); page.reload()
        expect(page.locator(".el-table__header th")).to_have_count(12)
        page.evaluate("localStorage.setItem('token', 'isolated-team-editor')"); page.reload()
        expect(page.locator(".el-table__header th")).to_have_count(3)
        other_context, other_page = new_context("isolated-team-other", "America/Los_Angeles")
        expect(other_page.locator(".el-table__header th")).to_have_count(12)
        other_context.close()
        page.get_by_role("button", name="字段设置", exact=True).click()
        page.locator(".table-column-settings-popover:visible").get_by_role("button", name="恢复默认", exact=True).click()
        expect(page.locator(".el-table__header th")).to_have_count(12)
        page.get_by_role("heading", name="团队资源", exact=True).click()
        results.append("全部取消、刷新保留、用户隔离及恢复默认")

        created = [api("POST", "/teams", {"short_name": name, "team_type": "small_team", "resource_types": ["annotation"]}) for name in ["批删团队甲", "批删团队乙"]]
        search = page.get_by_placeholder("团队简称或全称"); search.fill("批删团队"); expect(page.locator(".el-table__body tr")).to_have_count(2)
        page.get_by_role("button", name="删除管理", exact=True).click()
        expect(page.get_by_role("button", name="新增团队", exact=True)).not_to_be_visible()
        expect(page.get_by_role("button", name="编辑", exact=True)).to_have_count(0)
        page.locator(".el-table__header .el-checkbox").click()
        update(created[0], remarks="制造真实删除版本冲突")
        confirm_delete(True)
        expect(page.locator(".el-table__body tr")).to_have_count(1)
        expect(page.get_by_text("已选 1 条", exact=True)).to_be_visible()
        expect(page.get_by_text(re.compile("团队已被其他人修改")).first).to_be_visible()
        page.locator(".el-notification:visible .el-notification__closeBtn").click()
        page.mouse.move(300, 130)
        expect(page.locator(".el-notification:visible")).to_have_count(0)
        page.get_by_role("heading", name="团队资源", exact=True).click()
        confirm_delete(False)
        expect(page.get_by_role("button", name="删除管理", exact=True)).to_be_visible()
        assert not list_rows("批删团队")
        results.append("删除模式入口、强确认、真实部分失败、保留失败选择及单条删除")

        search.fill("验收公司全称"); expect(page.locator(".el-table__body tr")).to_have_count(20)
        page.locator(".el-pagination .btn-next").click(); expect(page.locator(".el-table__body tr")).to_have_count(4)
        page.get_by_role("button", name="删除管理", exact=True).click()
        page.locator(".el-table__header .el-checkbox").click(); confirm_delete(True)
        expect(page.locator(".el-table__body tr")).to_have_count(20)
        expect(page.locator(".el-pager .is-active")).to_have_text("1")
        page.get_by_role("button", name="删除管理", exact=True).click()
        page.locator(".el-table__body .el-checkbox").first.click()
        page.locator(".el-pagination .el-select").click(); page.get_by_role("option", name="10条/页", exact=True).click()
        expect(page.get_by_role("button", name="删除管理", exact=True)).to_be_visible()
        results.append("末页删除回退与切换分页退出删除模式")

        reader_context, reader_page = new_context("isolated-team-reader", "UTC")
        expect(reader_page.get_by_role("button", name="新增团队", exact=True)).to_have_count(0)
        expect(reader_page.get_by_role("button", name="删除管理", exact=True)).to_have_count(0)
        expect(reader_page.get_by_role("button", name="编辑", exact=True)).to_have_count(0)
        reader_page.get_by_placeholder("团队简称或全称").fill("验收公司全称")
        expect(reader_page.locator(".el-table__body tr")).to_have_count(20)
        expect(reader_page.locator(".el-table__body tr").first).to_contain_text("验收公司全称")
        reader_page.get_by_role("button", name="查看详情", exact=True).first.click()
        expect(reader_page.locator(".team-details:not(.team-contacts-popover):visible .el-descriptions")).to_be_visible()
        details = reader_page.locator(".team-details:not(.team-contacts-popover) .business-detail-popover__content:visible")
        assert details.evaluate("el => el.scrollHeight > el.clientHeight")
        reader_page.screenshot(path=str(OUTPUT / "team-details.png"), full_page=True)
        reader_context.close(); context.close(); browser.close()
        results.append("只读账号及详情内容独立滚动")
    assert not errors, errors
    (OUTPUT / "browser-report.json").write_text(json.dumps({"passed": results, "page_errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("浏览器真实前后端验收通过：" + "；".join(results))


if __name__ == "__main__":
    run()
