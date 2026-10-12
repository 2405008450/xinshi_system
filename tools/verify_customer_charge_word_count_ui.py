"""使用模拟接口验收收费数量快捷填报；不会连接业务数据库。"""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
METRICS = [
    ("words", "字数"),
    ("characters_no_spaces", "字符数（不计空格）"),
    ("cjk_chars_korean_words", "中文字符和朝鲜语单词"),
    ("foreign_words", "外文字数"),
    ("documents", "份数"),
    ("pages", "页数"),
]
PROJECT_ID = "00000000-0000-4000-8000-000000000001"
SUBORDER_ID = "00000000-0000-4000-8000-000000000002"


def empty_matrix():
    return {key: {metric: None for metric, _ in METRICS}
            for key in ["company", "customer", "translator_estimate"]}


def charges():
    items = [dict(item_name=label, pricing_mode="metric", metric_type=key,
                  unit_size=1000 if key not in ["pages", "documents"] else 1,
                  unit_price_excl_tax=100, unit_price_incl_tax=110,
                  total_excl_tax=100 if key == "words" else None,
                  total_incl_tax=110 if key == "words" else None,
                  currency="CNY") for key, label in METRICS]
    items.extend([
        dict(item_name="手动总价", pricing_mode="metric", metric_type="words", unit_size=1000,
             unit_price_excl_tax=100, unit_price_incl_tax=110, total_excl_tax=777,
             total_incl_tax=888, currency="CNY"),
        dict(item_name="固定收费", pricing_mode="fixed", metric_type=None,
             total_excl_tax=123, total_incl_tax=135, currency="CNY"),
    ])
    return items


def run():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    assert ROOT == Path(r"E:\xinshi_system")
    assert socket.gethostname().upper() == "PC"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    state = {"fail_get": False, "fail_patch": False, "many_translators": False}
    matrices = {key: empty_matrix() for key in [PROJECT_ID, SUBORDER_ID]}
    for matrix in matrices.values():
        matrix["customer"].update(words=1000, pages=0)
    unexpected_writes, writes, errors, checks = [], [], [], []
    project = dict(id=PROJECT_ID, order_no="TP-QA-001", source_file_name="快捷填报验收.docx",
                   project_status="confirmed", client_short_name="验收客户", assigned_translators=[],
                   customer_charge_items=charges(), sub_order_count=1)
    suborder = dict(id=SUBORDER_ID, parent_project_id=PROJECT_ID, sub_order_no="TP-QA-001-01",
                    sub_project_name="子订单验收.docx", status="confirmed", assigned_translators=[],
                    customer_charge_items=charges())

    def api(route):
        path = urlparse(route.request.url).path
        method = route.request.method
        if path.startswith("/api/word-count-matrices/"):
            entity_id = path.rsplit("/", 1)[-1]
            if method == "GET" and state["fail_get"]:
                route.fulfill(status=500, json={"detail": "模拟加载失败"})
                return
            if method == "PATCH":
                if state["fail_patch"]:
                    route.fulfill(status=500, json={"detail": "模拟保存失败"})
                    return
                payload = route.request.post_data_json
                writes.append({"path": path, "changes": payload["changes"]})
                for cell in payload["changes"]:
                    assert cell["scope"] == "entity"
                    matrices[entity_id][cell["dimension"]][cell["metric_type"]] = cell["value"]
            translators = [dict(arrangement_id=f"qa-{index}", translator_name=f"验收译员{index}",
                                planned={}, actual={}) for index in range(10)] if state["many_translators"] else []
            route.fulfill(status=200, json={**matrices[entity_id], "translators": translators})
            return
        if method != "GET":
            unexpected_writes.append(path)
            route.abort()
            return
        current_suborder = {**suborder, "word_count_matrix": matrices[SUBORDER_ID]}
        current_project = {**project, "word_count_matrix": matrices[PROJECT_ID], "sub_orders": [current_suborder]}
        if path == "/api/auth/session":
            result = dict(user_id=PROJECT_ID, username="qa", roles=["admin"], permissions=[])
        elif path == "/api/projects/translation/page":
            result = dict(items=[current_project], total=1)
        elif path == f"/api/projects/translation/{PROJECT_ID}":
            result = current_project
        elif path == f"/api/sub-orders/project/{PROJECT_ID}":
            result = [current_suborder]
        elif path.endswith("/next-order-no"):
            result = {"orderNo": "TP-QA-002"}
        elif path.endswith("/project-editor-options"):
            result = dict(project_managers=[], role_candidates={})
        elif path.endswith("/unread-count"):
            result = {"count": 0}
        else:
            result = []
        route.fulfill(status=200, json=result)

    process = subprocess.Popen(
        ["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1",
         "--port", str(port), "--strictPort"], cwd=ROOT / "frontend",
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        from urllib.request import urlopen
        for _ in range(50):
            try:
                urlopen(base, timeout=1).close()
                break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError("隔离预览启动失败")
                time.sleep(0.1)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="msedge")
            context = browser.new_context(viewport={"width": 1234, "height": 884})
            context.route("**/api/**", api)
            context.add_init_script("localStorage.setItem('token', 'isolated-charge-qa')")
            page = context.new_page()
            page.set_default_timeout(10000)
            page.on("pageerror", lambda error: errors.append(str(error)))

            def popup():
                return page.locator(".word-count-matrix-popper:visible:not(.el-fade-in-linear-leave-active)")

            def rows(dialog):
                return dialog.locator(".charge-editor .el-table__body-wrapper tbody tr")

            def open_quantity(dialog, index, label):
                try:
                    rows(dialog).nth(index).get_by_role("button", name=f"填报客户{label}", exact=True).click()
                except Exception:
                    page.screenshot(path=str(ROOT / "artifacts/charge-word-count-failure.png"))
                    print(dialog.inner_text(), flush=True)
                    raise
                box = popup()
                expect(box).to_be_visible()
                field = box.get_by_role("spinbutton", name=f"客户字数-{label}", exact=True)
                expect(field).to_be_focused()
                expect(box.locator(".is-word-count-target")).to_have_count(1)
                return box, field

            def save(box, local=False):
                box.get_by_role("button", name="应用到新建表单" if local else "保存", exact=True).click()
                expect(box).not_to_be_visible()

            page.goto(base + f"/translation-details?projectId={PROJECT_ID}&openEditor=1")
            dialog = page.locator(".project-editor-dialog")
            expect(dialog).to_be_visible()
            remarks = dialog.locator('[data-field-key="remarks"] textarea')
            remarks.fill("外层未保存的备注")
            expect(rows(dialog).nth(0).get_by_role("button", name="填报客户字数", exact=True)).to_have_text("1,000")
            expect(rows(dialog).nth(1).locator(".charge-editor__quantity")).to_have_text("填报")
            expect(rows(dialog).nth(5).locator(".charge-editor__quantity")).to_have_text("0")
            expect(rows(dialog).nth(7).locator("td").nth(4)).to_have_text("-")
            expect(rows(dialog).nth(7).locator("td").nth(4).get_by_role("button")).to_have_count(0)

            for index, (key, label) in enumerate(METRICS):
                box, field = open_quantity(dialog, index, label)
                field.fill(str(2000 if index == 0 else index + 2))
                save(box)
                assert matrices[PROJECT_ID]["customer"][key] == (2000 if index == 0 else index + 2)
                expect(remarks).to_have_value("外层未保存的备注")
            expect(rows(dialog).nth(0).locator("td").nth(8).get_by_role("spinbutton")).to_have_value("200.00")
            expect(rows(dialog).nth(0).locator("td").nth(9).get_by_role("spinbutton")).to_have_value("220.00")
            expect(rows(dialog).nth(6).get_by_role("button", name="填报客户字数", exact=True)).to_have_text("2,000")
            expect(rows(dialog).nth(6).locator("td").nth(8).get_by_role("spinbutton")).to_have_value("777.00")
            expect(rows(dialog).nth(6).locator("td").nth(9).get_by_role("spinbutton")).to_have_value("888.00")
            checks.append("六种口径聚焦、未填写、零值、固定收费、金额联动、手动总价与外层草稿保护")

            dialog.get_by_role("button", name="展开字数统计", exact=True).click()
            expect(popup().get_by_role("spinbutton", name="客户字数-字数", exact=True)).to_have_value("2000")
            popup().get_by_role("button", name="取消", exact=True).click()
            box, field = open_quantity(dialog, 0, "字数")
            field.fill("9999")
            box.get_by_role("button", name="取消", exact=True).click()
            expect(rows(dialog).nth(0).get_by_role("button", name="填报客户字数", exact=True)).to_have_text("2,000")
            assert matrices[PROJECT_ID]["customer"]["words"] == 2000
            state["fail_get"] = True
            rows(dialog).nth(0).get_by_role("button", name="填报客户字数", exact=True).click()
            expect(page.get_by_text("模拟加载失败", exact=True)).to_be_visible()
            expect(popup()).to_have_count(0)
            state["fail_get"] = False
            box, field = open_quantity(dialog, 0, "字数")
            state["fail_patch"] = True
            field.fill("3000")
            box.get_by_role("button", name="保存", exact=True).click()
            expect(page.get_by_text("模拟保存失败", exact=True)).to_be_visible()
            expect(field).to_have_value("3000")
            assert matrices[PROJECT_ID]["customer"]["words"] == 2000
            state["fail_patch"] = False
            save(box)
            checks.append("原入口同步、取消不应用、加载失败、保存失败保留输入及重试")

            # 小屏幕横向定位仅滚动小窗；外层表单和固定操作栏保持位置。
            page.set_viewport_size({"width": 600, "height": 760})
            state["many_translators"] = True
            box, field = open_quantity(dialog, 5, "页数")
            bounds = box.bounding_box()
            assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 600
            body = box.locator(".word-count-matrix__body")
            assert body.evaluate("el => el.scrollLeft > 0")
            assert body.evaluate("el => el.scrollHeight > el.clientHeight")
            assert field.evaluate("el => { const a = el.getBoundingClientRect(); const b = el.closest('.word-count-matrix__body').getBoundingClientRect(); return a.left >= b.left && a.right <= b.right }")
            expect(box.get_by_role("button", name="保存", exact=True)).to_be_in_viewport()
            expect(dialog.locator(".el-dialog__footer").get_by_role("button", name="保存", exact=True)).to_be_in_viewport()
            body.evaluate("el => { el.scrollTop = el.scrollHeight }")
            expect(box.get_by_role("button", name="保存", exact=True)).to_be_in_viewport()
            page.screenshot(path=str(ROOT / "artifacts/charge-word-count-small.png"))
            box.get_by_role("button", name="取消", exact=True).click()
            state["many_translators"] = False
            page.set_viewport_size({"width": 1234, "height": 884})
            checks.append("小屏浮层宽度、目标横向定位、多译员内部滚动与固定操作栏")

            # 项目新增态：应用仅更新草稿，不产生字数 PATCH。
            page.goto(base + "/translation-details")
            page.get_by_role("button", name="新增项目", exact=True).click()
            expect(dialog).to_be_visible()
            dialog.get_by_role("button", name="新增收费项", exact=True).click()
            before = len(writes)
            box, field = open_quantity(dialog, 0, "字数")
            field.fill("4321")
            save(box, local=True)
            assert len(writes) == before
            expect(rows(dialog).nth(0).get_by_role("button", name="填报客户字数", exact=True)).to_have_text("4,321")
            dialog.get_by_role("button", name="展开字数统计", exact=True).click()
            expect(popup().get_by_role("spinbutton", name="客户字数-字数", exact=True)).to_have_value("4321")
            popup().get_by_role("button", name="取消", exact=True).click()
            checks.append("新增项目仅应用草稿，两个入口共享数据")

            # 项目弹窗内新增、编辑子订单，验证嵌套弹窗及实体类型。
            page.goto(base + f"/translation-details?projectId={PROJECT_ID}&openEditor=1")
            page.get_by_role("button", name="放弃草稿", exact=True).click()
            dialog.get_by_role("tab", name="子订单", exact=True).click()
            dialog.get_by_role("button", name="编辑", exact=True).click()
            subdialog = page.locator(".suborder-editor-dialog:visible")
            expect(subdialog).to_be_visible()
            subdialog.get_by_role("tab", name="分配与预估", exact=True).click()
            box, field = open_quantity(subdialog, 0, "字数")
            field.fill("6000")
            save(box)
            assert writes[-1]["path"] == f"/api/word-count-matrices/suborder/{SUBORDER_ID}"
            assert matrices[PROJECT_ID]["customer"]["words"] == 3000
            expect(subdialog).to_be_visible()
            subdialog.get_by_role("button", name="取消", exact=True).click()
            expect(subdialog).not_to_be_visible()
            dialog.get_by_role("button", name="新增子订单", exact=True).click()
            expect(subdialog).to_be_visible()
            subdialog.get_by_role("tab", name="分配与预估", exact=True).click()
            subdialog.get_by_role("button", name="新增收费项", exact=True).click()
            before = len(writes)
            box, field = open_quantity(subdialog, 0, "字数")
            field.fill("0")
            save(box, local=True)
            assert len(writes) == before
            expect(rows(subdialog).nth(0).get_by_role("button", name="填报客户字数", exact=True)).to_have_text("0")
            checks.append("内嵌子订单新增与编辑、母子订单隔离、嵌套浮层可操作")

            # 独立子订单页面接入相同快捷入口。
            page.goto(base + f"/translation-sub-orders/{PROJECT_ID}")
            page.get_by_role("button", name="编辑", exact=True).click()
            expect(subdialog).to_be_visible()
            box, field = open_quantity(subdialog, 0, "字数")
            field.fill("7000")
            save(box)
            expect(rows(subdialog).nth(0).get_by_role("button", name="填报客户字数", exact=True)).to_have_text("7,000")
            subdialog.get_by_role("button", name="取消", exact=True).click()
            expect(subdialog).not_to_be_visible()
            page.get_by_role("button", name="新增子订单", exact=True).click()
            expect(subdialog).to_be_visible()
            subdialog.get_by_role("button", name="新增收费项", exact=True).click()
            before = len(writes)
            box, field = open_quantity(subdialog, 0, "字数")
            field.fill("8000")
            save(box, local=True)
            assert len(writes) == before
            expect(rows(subdialog).nth(0).get_by_role("button", name="填报客户字数", exact=True)).to_have_text("8,000")
            checks.append("独立子订单新增与编辑")
            browser.close()
        assert not unexpected_writes, unexpected_writes
        assert not errors, errors
        result = dict(passed=len(checks), checks=checks, mocked_patches=len(writes), business_requests=0)
        (ROOT / "artifacts/charge-word-count-ui.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    run()
