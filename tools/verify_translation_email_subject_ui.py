"""隔离接口验证笔译新增、编辑表单生成邮件主题时保留分钟。"""

import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def run():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    assert socket.gethostname().upper() == "PC"
    assert ROOT == Path(r"E:\xinshi_system")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    project_id = str(uuid4())
    row = dict(id=project_id, order_no="TP-261012-005", client_short_name="验收客户",
               source_file_name="验收.docx", project_status="confirmed",
               language_pair="中文（简体）→英语（美国）",
               customer_deadline_time="2026-10-12 17:30:00", assigned_translators=[], sub_orders=[])
    errors, writes, checks = [], [], []

    def api(route):
        path = urlparse(route.request.url).path
        # 所有接口均被拦截，不连接业务后端；写请求视为验收失败。
        if route.request.method != "GET":
            writes.append(path)
            route.abort()
            return
        if path == "/api/auth/session":
            result = dict(user_id=str(uuid4()), username="qa", roles=["admin"], permissions=[])
        elif path == "/api/projects/translation/page":
            result = dict(items=[row], total=1)
        elif path == f"/api/projects/translation/{project_id}":
            result = row
        elif path.endswith("/next-order-no"):
            result = {"orderNo": "TP-261012-006"}
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
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
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
            for zone in ["UTC", "America/Los_Angeles", "Asia/Hong_Kong"]:
                for mode in ["create", "edit"]:
                    context = browser.new_context(timezone_id=zone, viewport={"width": 1440, "height": 900})
                    context.route("**/api/**", api)
                    context.add_init_script("localStorage.setItem('token', 'isolated-subject-qa')")
                    page = context.new_page()
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    url = base + "/translation-details"
                    if mode == "edit":
                        url += f"?projectId={project_id}&openEditor=1"
                    page.goto(url)
                    if mode == "create":
                        page.get_by_role("button", name="新增项目", exact=True).click()
                    dialog = page.locator(".project-editor-dialog")
                    expect(dialog).to_be_visible()
                    deadline = dialog.locator('[data-field-key="customerDeadlineTime"] input')
                    if mode == "create":
                        deadline.fill("2026-10-12 17:30")
                        deadline.press("Enter")
                        deadline.press("Tab")
                    expect(deadline).to_have_value("2026-10-12 17:30")
                    subject = dialog.locator('[data-field-key="emailSubjectPreview"] textarea')
                    dialog.get_by_role("button", name="生成邮件主题", exact=True).click()
                    expect(subject).to_have_value(re.compile(".*10月12日17点30分回稿.*"))
                    checks.append(dict(zone=zone, mode=mode, subject=subject.input_value()))
                    context.close()
            browser.close()
        assert not errors, errors
        assert not writes, writes
        print(json.dumps({"passed": len(checks), "checks": checks}, ensure_ascii=False))
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    run()
