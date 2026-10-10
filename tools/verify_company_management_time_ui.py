"""用隔离接口验证公司管理页面的 UTC+8 时间展示，不连接业务数据库。"""
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:12428"


def run():
    assert socket.gethostname().upper() == "PC"
    assert ROOT == Path(r"E:\xinshi_system")
    user_id, section_id = str(uuid4()), str(uuid4())
    row = dict(
        id=section_id, section_key="company_rules", title="公司制度",
        display_title="公司制度", parent_id=None, sort_order=1, has_content=True,
        is_active=True, children=[], updated_by_name="Jimmy", updated_at=None,
        content_json={"type": "doc", "content": [{"type": "paragraph"}]},
    )
    errors = []

    def api(route):
        path = urlparse(route.request.url).path
        if path == "/api/auth/session":
            result = dict(id=user_id, username="qa", full_name="验收人员", roles=["qa"], permissions=[])
        elif path == "/api/company-management/tree":
            result = [row]
        elif path == f"/api/company-management/sections/{section_id}":
            result = row
        elif path.endswith("/unread-count"):
            result = {"count": 0}
        else:
            result = []
        # 验收期间禁止任何写请求。
        assert route.request.method == "GET", route.request.url
        route.fulfill(status=200, json=result)

    process = subprocess.Popen(
        ["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1",
         "--port", "12428", "--strictPort"], cwd=ROOT / "frontend",
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    checks = []
    try:
        for _ in range(50):
            try:
                urlopen(BASE, timeout=1).close()
                break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError("隔离预览启动失败")
                time.sleep(0.1)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="msedge")
            for browser_zone in ["UTC", "America/Los_Angeles", "Asia/Shanghai"]:
                context = browser.new_context(timezone_id=browser_zone)
                context.route("**/api/**", api)
                context.add_init_script("localStorage.setItem('token', 'isolated-time-qa')")
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                for value, expected in [
                    ("2026-10-09T09:18:43Z", "2026/10/09 17:18:43"),
                    ("2026-10-09T17:18:43+08:00", "2026/10/09 17:18:43"),
                    ("2026-10-09T17:18:43.787825", "2026/10/09 17:18:43"),
                    ("2026-10-09T16:00:00Z", "2026/10/10 00:00:00"),
                ]:
                    row["updated_at"] = value
                    page.goto(BASE + "/company-management")
                    expect(page.locator(".notice-content__meta")).to_have_text(
                        f"最近由 Jimmy 编辑于 {expected}"
                    )
                    checks.append(dict(browser_zone=browser_zone, input=value, display=expected))
                context.close()
            browser.close()
        assert not errors, errors
        print(json.dumps({"passed": len(checks), "checks": checks}, ensure_ascii=False))
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    run()
