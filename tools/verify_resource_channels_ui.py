"""本机渠道页面实际交互验收，接口隔离，不修改业务数据。"""
import copy
import json
from pathlib import Path
import socket
import subprocess
import time
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:12458"


def run():
    if socket.gethostname().upper() != "PC" or str(ROOT).lower() != r"e:\xinshi_system":
        raise SystemExit("仅允许在本机执行")
    out = ROOT / ".tmp" / "resource-channels-ui"
    out.mkdir(parents=True, exist_ok=True)
    uid, other, stopped = [str(uuid4()) for _ in range(3)]
    people = [dict(id=uid, name="实际操作人", is_active=True), dict(id=other, name="其他人员", is_active=True), dict(id=stopped, name="历史人员", is_active=False)]
    channels = [dict(id=str(uuid4()), kind="platform", name=f"验收平台{i:02d}", category="national" if i % 2 == 0 else "local",
                     purpose="招聘用途", description="平台说明\n" * 180, revision=1, code=f"QA{i}", maintainers=[people[0]], users=[people[1]],
                     created_at=None, updated_at="2026-10-08T14:30:00", created_by_name=None, updated_by_name="实际操作人") for i in range(24)]
    channels[0]["maintainers"].append(people[2])
    requests, saves, errors = [], [], []
    state = dict(write=True, user_id=uid, conflict=False)

    def api(route):
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path.removeprefix("/api")
        query = parse_qs(parsed.query)
        requests.append((request.method, path, query))
        result = []
        if path == "/auth/session":
            result = dict(user_id=state["user_id"], username="qa", full_name="实际操作人", roles=["admin"], permissions=["talents:read"] + (["talents:write"] if state["write"] else []))
        elif path == "/resource-development/options":
            result = dict(options=channels, users=people[:2], languages=[], user_id=state["user_id"], can_write=state["write"], can_delegate=True, default_date="2026-10-08")
        elif path == "/resource-development/channels/people":
            result = people
        elif path == "/resource-development/channels":
            if request.method == "POST":
                payload = request.post_data_json; saves.append((path, copy.deepcopy(payload)))
                row = dict(id=str(uuid4()), kind="platform", code="NEW", revision=1, created_at="2026-10-08T14:00:00", created_by_name="实际操作人", updated_at=None, updated_by_name=None)
                row.update({k: v for k, v in payload.items() if k not in {"revision", "maintainer_ids", "user_ids"}})
                row.update(maintainers=[p for p in people if p["id"] in payload["maintainer_ids"]], users=[p for p in people if p["id"] in payload["user_ids"]])
                channels.insert(0, row); result = row
            else:
                keyword = query.get("keyword", [""])[0]
                matches = [row for row in channels if keyword in row["name"] or keyword in row["purpose"]]
                if query.get("category"): matches = [row for row in matches if row["category"] == query["category"][0]]
                for key, field in [("maintainer_ids", "maintainers"), ("user_ids", "users")]:
                    if query.get(key): matches = [row for row in matches if any(p["id"] in query[key] for p in row[field])]
                skip, limit = int(query.get("skip", [0])[0]), int(query.get("limit", [20])[0])
                result = dict(items=matches[skip:skip + limit], total=len(matches))
        elif path.startswith("/resource-development/channels/"):
            row = next(row for row in channels if row["id"] == path.split("/")[3])
            if request.method == "PUT":
                payload = request.post_data_json; saves.append((path, copy.deepcopy(payload)))
                if state["conflict"]:
                    state["conflict"] = False; row["revision"] += 1
                    route.fulfill(status=409, json=dict(detail="记录已被修改，请重新打开后再保存")); return
                assert payload["revision"] == row["revision"]
                row.update({k: v for k, v in payload.items() if k not in {"revision", "maintainer_ids", "user_ids"}})
                row["revision"] += 1
                if "maintainer_ids" in payload:
                    row.update(maintainers=[p for p in people if p["id"] in payload["maintainer_ids"]], users=[p for p in people if p["id"] in payload["user_ids"]])
            result = row
        elif path == "/resource-development/days": result = dict(items=[], total=0)
        elif path.endswith("/unread-count"): result = dict(count=0)
        route.fulfill(status=200, json=result)

    def form_item(dialog, label):
        return dialog.locator(".el-form-item").filter(has=dialog.page.locator("label", has_text=label)).first

    def assert_footer(page, dialog):
        body = dialog.locator(".el-dialog__body")
        for position in [0, 300, 100000]:
            body.evaluate("(el, value) => el.scrollTop = value", position)
            footer = dialog.locator(".el-dialog__footer").bounding_box()
            assert footer["y"] >= 0 and footer["y"] + footer["height"] <= page.viewport_size["height"] + 1

    def drag_and_reset(page, dialog, reopen):
        page.wait_for_timeout(300)
        original = dialog.bounding_box(); header = dialog.locator(".el-dialog__header").bounding_box()
        page.mouse.move(header["x"] + 6, header["y"] + 6)
        page.mouse.down(); page.mouse.move(header["x"] + 100, header["y"] + 45, steps=10); page.mouse.up()
        moved = dialog.bounding_box(); assert abs(moved["x"] - original["x"]) > 30
        header = dialog.locator(".el-dialog__header").bounding_box()
        page.mouse.move(header["x"] + 6, header["y"] + 6)
        page.mouse.down(); page.mouse.move(3000, 3000, steps=10); page.mouse.up()
        bounds = dialog.bounding_box()
        assert bounds["x"] >= -1 and bounds["y"] >= -1
        assert bounds["x"] + bounds["width"] <= page.viewport_size["width"] + 1
        assert bounds["y"] + bounds["height"] <= page.viewport_size["height"] + 1
        dialog.locator(".el-dialog__headerbtn").click(); expect(dialog).not_to_be_visible()
        reopen(); expect(dialog).to_be_visible(); page.wait_for_timeout(300)
        restored = dialog.bounding_box()
        assert abs(restored["x"] - original["x"]) < 2 and abs(restored["y"] - original["y"]) < 2

    log = (out / "preview.log").open("w", encoding="utf-8")
    process = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--outDir", "../.tmp/resource-channels-dist", "--host", "127.0.0.1", "--port", "12458", "--strictPort"],
                               cwd=ROOT / "frontend", stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(50):
            try: urlopen(BASE, timeout=1).close(); break
            except Exception: time.sleep(.2)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel="msedge")
            context = browser.new_context(viewport=dict(width=1440, height=900), timezone_id="Asia/Hong_Kong")
            context.route("**/api/**", api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page(); page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/resource-management/resource-channels")
            expect(page.get_by_role("heading", name="渠道管理", exact=True)).to_be_visible()
            expect(page.locator(".el-table__body tr")).to_have_count(20)
            expect(page.locator(".el-loading-mask:visible")).to_have_count(0)
            page.screenshot(path=str(out / "channel-list.png"), full_page=True)
            search = page.get_by_placeholder("渠道／平台名称、平台用途")
            count = lambda: len([r for r in requests if r[1] == "/resource-development/channels"])
            before = count(); search.fill("验收平台01"); page.wait_for_timeout(150); assert count() == before
            expect(page.locator(".el-table__body tr")).to_have_count(1)
            search.fill(""); expect(page.locator(".el-table__body tr")).to_have_count(20)
            table_height = page.locator(".el-table").bounding_box()["height"]
            page.get_by_role("button", name="高级筛选", exact=True).click()
            popover = page.locator(".channel-advanced:visible")
            popover.locator(".el-select").nth(0).click()
            page.get_by_role("option", name="实际操作人", exact=True).click()
            page.get_by_role("option", name="其他人员", exact=True).click()
            page.keyboard.press("Escape")
            expect(page.get_by_role("button", name="高级筛选（1）")).to_be_visible()
            assert abs(page.locator(".el-table").bounding_box()["height"] - table_height) < 2
            assert next(q for _, p, q in reversed(requests) if p == "/resource-development/channels")["maintainer_ids"] == [uid, other]
            popover.get_by_role("button", name="关闭", exact=True).click()
            expect(page.get_by_role("button", name="高级筛选（1）")).to_be_visible()
            page.get_by_role("button", name="重置", exact=True).click()
            expect(page.get_by_role("button", name="高级筛选", exact=True)).to_be_visible()
            page.get_by_role("button", name="查看详情", exact=True).first.click()
            details = page.locator(".channel-details:visible")
            expect(details.locator(".el-descriptions")).to_be_visible()
            assert details.locator(".channel-details-body").evaluate("el=>el.scrollHeight>el.clientHeight")
            assert details.bounding_box()["x"] < page.get_by_role("button", name="查看详情", exact=True).first.bounding_box()["x"]
            page.get_by_role("heading", name="渠道管理", exact=True).click()
            page.get_by_role("button", name="字段设置", exact=True).click()
            columns = page.locator(".el-popper:visible").filter(has=page.locator(".channel-column-options"))
            expect(columns.locator(".el-checkbox")).to_have_count(10)
            for label in ["渠道／平台名称", "平台性质", "平台用途", "维护人", "使用人"]:
                checkbox = columns.locator(".el-checkbox").filter(has_text=label)
                expect(checkbox.locator("input")).to_be_checked()
                checkbox.click()
                expect(checkbox.locator("input")).not_to_be_checked()
            expect(page.locator(".el-table__header th")).to_have_count(4)
            columns.get_by_role("button", name="恢复默认", exact=True).click()
            columns.locator(".el-checkbox").filter(has_text="平台用途").click()
            page.reload(); expect(page.get_by_role("heading", name="渠道管理", exact=True)).to_be_visible()
            expect(page.locator(".el-table__header").get_by_text("平台用途", exact=True)).to_have_count(0)
            state["user_id"] = other; page.reload()
            expect(page.locator(".el-table__header").get_by_text("平台用途", exact=True)).to_be_visible()
            state["user_id"] = uid; page.reload()
            page.get_by_role("button", name="新增渠道", exact=True).click()
            editor = page.locator(".channel-dialog:visible")
            editor.get_by_role("button", name="保存", exact=True).click()
            expect(form_item(editor, "渠道／平台名称").locator("input")).to_be_focused()
            form_item(editor, "渠道／平台名称").locator("input").fill("新渠道验收")
            form_item(editor, "平台性质").locator(".el-select").click()
            page.get_by_role("option", name="国外平台", exact=True).click()
            form_item(editor, "维护人").locator(".el-select").click()
            expect(page.get_by_role("option", name="历史人员（已停用）", exact=True)).to_have_count(0)
            page.get_by_role("option", name="实际操作人", exact=True).click()
            page.get_by_role("option", name="其他人员", exact=True).click(); page.keyboard.press("Escape")
            form_item(editor, "平台用途").locator("textarea").fill("寻访与招聘")
            form_item(editor, "平台情况说明").locator("textarea").fill("新增渠道说明")
            assert_footer(page, editor)
            editor.get_by_role("button", name="保存", exact=True).click(); expect(editor).not_to_be_visible()
            assert saves[-1][1]["maintainer_ids"] == [uid, other]
            page.get_by_role("button", name="编辑", exact=True).first.click(); expect(editor).to_be_visible()
            expect(form_item(editor, "渠道／平台名称").locator("input")).to_have_value("新渠道验收")
            assert_footer(page, editor)
            field_search = editor.get_by_placeholder("搜索字段，如维护人")
            field_search.fill("用途")
            page.locator(".project-field-search-popper:visible").get_by_text("平台用途", exact=True).click()
            expect(form_item(editor, "平台用途").locator("textarea")).to_be_focused()
            page.screenshot(path=str(out / "channel-editor.png"))
            drag_and_reset(page, editor, lambda: page.get_by_role("button", name="编辑", exact=True).first.click())
            form_item(editor, "平台用途").locator("textarea").fill("保留的渠道草稿")
            state["conflict"] = True; editor.get_by_role("button", name="保存", exact=True).click()
            expect(editor.get_by_text("渠道已被修改，草稿已保留。请重新读取最新内容后再保存。")).to_be_visible()
            expect(form_item(editor, "平台用途").locator("textarea")).to_have_value("保留的渠道草稿")
            editor.get_by_role("button", name="重新读取最新内容").click()
            editor.get_by_role("button", name="恢复保留的草稿").click()
            editor.get_by_role("button", name="保存", exact=True).click(); expect(editor).not_to_be_visible()
            page.get_by_role("button", name="编辑情况说明", exact=True).first.click()
            description = page.locator(".channel-dialog:visible")
            description.locator("textarea").fill("渠道共享说明")
            state["conflict"] = True; description.get_by_role("button", name="保存", exact=True).click()
            expect(description.locator("textarea")).to_have_value("渠道共享说明")
            description.get_by_role("button", name="重新读取最新内容").click()
            description.get_by_role("button", name="恢复保留的草稿").click()
            description.get_by_role("button", name="保存", exact=True).click(); expect(description).not_to_be_visible()
            assert set(saves[-1][1]) == {"description", "revision"}
            page.get_by_role("button", name="资源开拓", exact=True).click()
            page.get_by_role("button", name="平台与选项", exact=True).click()
            settings = page.locator(".development-dialog:visible")
            settings.get_by_role("button", name="新渠道验收 · 情况说明", exact=True).click()
            expect(description.locator("textarea")).to_have_value("渠道共享说明")
            drag_and_reset(page, description, lambda: settings.get_by_role("button", name="新渠道验收 · 情况说明", exact=True).click())
            description.locator("textarea").fill("开拓入口共享说明")
            description.get_by_role("button", name="保存", exact=True).click()
            settings.get_by_role("button", name="关闭", exact=True).click()
            page.get_by_role("button", name="渠道管理", exact=True).click()
            page.get_by_role("button", name="编辑情况说明", exact=True).first.click()
            expect(description.locator("textarea")).to_have_value("开拓入口共享说明")
            description.get_by_role("button", name="取消", exact=True).click()
            page.set_viewport_size(dict(width=390, height=760))
            page.get_by_role("button", name="新增渠道", exact=True).click()
            expect(editor).to_be_visible()
            page.wait_for_timeout(350)
            editor.locator(".el-dialog__body").evaluate("el => el.scrollTop = 0")
            page.screenshot(path=str(out / "channel-mobile-initial.png"))
            assert_footer(page, editor)
            assert editor.bounding_box()["width"] <= 358
            page.screenshot(path=str(out / "channel-mobile.png"))
            editor.locator(".el-dialog__headerbtn").click()
            state["write"] = False; page.reload()
            expect(page.get_by_role("button", name="新增渠道", exact=True)).to_have_count(0)
            page.get_by_role("button", name="查看情况说明", exact=True).first.click()
            expect(description.locator("textarea")).to_have_count(0)
            expect(description.get_by_role("button", name="保存", exact=True)).to_have_count(0)
            expect(description).to_contain_text("开拓入口共享说明")
            assert not errors, errors
            browser.close()
        print(json.dumps(dict(ok=True, checks=["防抖与清空", "多选筛选与固定表格高度", "详情浮窗方向和滚动", "字段配置与用户隔离", "新增编辑人员多选", "校验和字段搜索定位", "冲突草稿", "两入口共享说明", "拖拽边界和复位", "固定底部和小屏", "只读权限"]), ensure_ascii=False))
    finally:
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill()
        log.close()


if __name__ == "__main__":
    run()
