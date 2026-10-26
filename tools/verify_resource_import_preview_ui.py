"""资源开拓导入预览界面验收：接口隔离，不写入业务库。"""
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:12457"


def run():
    if socket.gethostname().upper() != "PC" or ROOT != Path(r"E:\xinshi_system"):
        raise SystemExit("仅允许在本机执行")
    output = ROOT / ".tmp" / "resource-import-preview-ui"
    output.mkdir(parents=True, exist_ok=True)
    log = (output / "vite.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        ["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port", "12457", "--strictPort"],
        cwd=ROOT / "frontend", stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    user_id = str(uuid4())
    calls, errors = [], []
    workbook = Path(r"E:\Documents\william代码\管理系统资源\10.26资源开拓统筹.xlsx")

    def api(route):
        path = urlparse(route.request.url).path.removeprefix("/api")
        calls.append((route.request.method, path))
        if path == "/auth/session":
            result = {"id": user_id, "user_id": user_id, "username": "qa", "full_name": "测试人员", "roles": ["admin"], "permissions": ["talents:read", "talents:write", "resource_development:delegate"]}
        elif path == "/resource-development/options":
            result = {"options": [], "users": [], "languages": [], "user_id": user_id, "can_delegate": True, "can_write": True, "default_date": "2026-10-26"}
        elif path == "/resource-development/issues/access":
            result = {"ready": True, "can_resource": True, "can_enter": True, "can_collect": True, "can_manage": True, "user_id": user_id, "user_name": "测试人员"}
        elif path == "/resource-development/import-preview":
            assert route.request.method == "POST"
            result = {"sheet": "Sheet1", "total": 2, "summary": {"已存在": 1, "待核对": 1}, "old_not_in_file": 0,
                      "issues": {"日期无效": 1}, "note": "只读预览。",
                      "rows": [
                          {"row": 2, "decision": "已存在", "work_date": "2026-10-25", "platform": "BOSS直聘", "account": "HR6", "languages": ["粤语"], "status_cells": 1, "existing_ids": [str(uuid4())], "actions": [], "issues": [], "contact_mapping": {"phone": "", "wechat": "", "xiaohongshu": "JamieFromTheUK", "other": ""}, "values": {"日期": "20261025", "开拓人/HR": "王露", "姓名": "张三", "来源": "boss", "语种": "粤语", "后续跟进情况": ""}},
                          {"row": 3, "decision": "待核对", "work_date": "", "platform": "智联招聘", "account": "HR3", "languages": [], "status_cells": 0, "existing_ids": [], "actions": [], "issues": ["日期无效"], "contact_mapping": {"phone": "", "wechat": "", "xiaohongshu": "", "other": "未提供"}, "values": {"日期": "20261039", "开拓人/HR": "王露", "姓名": "李四", "来源": "智联", "语种": "", "后续跟进情况": ""}},
                      ]}
        elif path == "/resource-development/days":
            result = {"total": 0, "items": []}
        elif path.endswith("/unread-count"):
            result = {"count": 0}
        else:
            result = {}
        route.fulfill(status=200, json=result)

    try:
        for _ in range(50):
            try:
                urlopen(BASE, timeout=1).close()
                break
            except Exception:
                time.sleep(.2)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="msedge")
            context = browser.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Hong_Kong")
            context.route("**/api/**", api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/resource-management/resource-development?section=logs")
            page.wait_for_timeout(1000)
            page.get_by_role("button", name="导入预览").click()
            dialog = page.locator(".development-import-preview.el-dialog")
            dialog.wait_for(state="visible")
            assert dialog.is_visible()
            before = dialog.bounding_box()
            page.get_by_label("选择资源开拓统筹表").set_input_files(str(workbook))
            dialog.get_by_role("button", name="生成预览").click()
            dialog.get_by_text("有效行：2").wait_for()
            assert dialog.get_by_text("张三").is_visible()
            assert dialog.get_by_text("小红书 JamieFromTheUK").is_visible()
            dialog.locator(".development-import-controls .el-select").click()
            page.get_by_role("option", name="待核对").click()
            assert dialog.get_by_text("李四").is_visible()
            assert not dialog.get_by_text("张三").is_visible()
            page.screenshot(path=str(output / "preview.png"), full_page=True)
            header = dialog.locator(".el-dialog__header")
            box = header.bounding_box()
            page.mouse.move(box["x"] + 180, box["y"] + 20)
            page.mouse.down()
            page.mouse.move(box["x"] + 230, box["y"] + 60)
            page.mouse.up()
            moved = dialog.bounding_box()
            assert moved["x"] != before["x"] or moved["y"] != before["y"]
            assert moved["x"] >= 0 and moved["y"] >= 0
            dialog.get_by_role("button", name="关闭", exact=True).click()
            page.get_by_role("button", name="导入预览").click()
            reset = dialog.bounding_box()
            assert abs(reset["x"] - before["x"]) <= 2 and abs(reset["y"] - before["y"]) <= 2
            page.set_viewport_size({"width": 390, "height": 844})
            narrow = dialog.bounding_box()
            assert narrow["x"] >= 0 and narrow["x"] + narrow["width"] <= 390
            assert narrow["y"] >= 0 and narrow["y"] + narrow["height"] <= 844
            assert dialog.get_by_role("button", name="关闭", exact=True).is_visible()
            assert not errors, errors
            assert calls.count(("POST", "/resource-development/import-preview")) == 1
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()
    print(json.dumps({"ok": True, "preview_calls": 1, "screenshot": str(output / "preview.png")}, ensure_ascii=False))


if __name__ == "__main__":
    run()
