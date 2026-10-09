"""本机编译页面交互验收，接口使用隔离模拟数据，不修改业务内容。"""
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:12427"
NOW = "2026-10-06T10:00:00"
UID = str(uuid4())


def run():
    if socket.gethostname().upper() != "PC" or str(ROOT).lower() != r"e:\xinshi_system":
        raise SystemExit("仅允许在本机执行")
    out = ROOT / ".tmp" / "company-ui"
    out.mkdir(parents=True, exist_ok=True)
    log = (out / "preview.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        ["node", "node_modules/vite/bin/vite.js", "preview", "--outDir", "../.tmp/company-management-dist", "--host", "127.0.0.1", "--port", "12427", "--strictPort"],
        cwd=ROOT / "frontend", stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    rows = [
        dict(id=str(uuid4()), section_key=f"qa_{i}", title=title, display_title=title, parent_id=None,
             sort_order=i+1, has_content=i != 1, is_active=True, content_json=None,
             updated_at=None, structure_updated_at=NOW, updated_by_name=None, children=[])
        for i, title in enumerate(["公司制度", "人事行政", "财务规范", "常用模板"])
    ]
    attachments = {}
    failures = set()
    errors = []
    requests = []

    def api(route):
        request = route.request
        url = urlparse(request.url)
        path = url.path.removeprefix("/api")
        method = request.method
        requests.append((method, path))
        result, status = [], 200
        if path == "/auth/session":
            result = dict(id=UID, username="qa", full_name="验收人员", roles=["qa"], permissions=route.request.headers.get("x-qa-permission", "").split(",") if "x-qa-permission" in route.request.headers else [])
        elif path.endswith("/tree"):
            result = [row for row in rows if row["parent_id"] is None and row["is_active"]]
            for root in result:
                root["children"] = [r for r in rows if r["parent_id"] == root["id"] and r["is_active"]]
        elif path.endswith("/search"):
            keyword = parse_qs(url.query).get("keyword", [""])[0]
            matches = [r for r in rows if keyword in r["title"]]
            result = dict(total=len(matches), items=[dict(id=r["id"], section_key=r["section_key"], display_title=r["title"], parent_title=None, breadcrumb=r["title"], snippet="栏目名称命中", matched_title=True, matched_content=False) for r in matches])
        elif path.endswith("/sections") and method == "POST":
            payload = request.post_data_json
            result = dict(rows[0], **payload)
            result.update(id=str(uuid4()), section_key="custom_" + uuid4().hex, display_title=payload["title"], children=[])
            rows.append(result)
            status = 201
        elif "/attachments/" in path:
            aid = path.rsplit("/", 1)[-1]
            if method == "DELETE":
                for sid in attachments:
                    attachments[sid] = [a for a in attachments[sid] if a["id"] != aid]
                route.fulfill(status=204); return
            route.fulfill(status=200, body=b"test-download", headers={"Content-Type": "application/octet-stream"}); return
        elif path.endswith("/attachments"):
            sid = path.split("/")[-2]
            if method == "GET":
                result = attachments.get(sid, [])
            else:
                content = request.post_data_buffer or b""
                failed = "失败.pdf".encode() in content
                if failed and sid not in failures:
                    failures.add(sid)
                    route.fulfill(status=400, json={"detail": "模拟单个附件失败"}); return
                result = dict(id=str(uuid4()), section_id=sid, original_name="失败.pdf" if failed else "制度.pdf", file_size=100, content_type="application/pdf", uploaded_by=UID, uploaded_by_name="验收人员", uploaded_at=NOW)
                attachments.setdefault(sid, []).insert(0, result)
                status = 201
        elif "/sections/" in path:
            sid = path.split("/sections/")[-1].split("/")[0]
            row = next((r for r in rows if r["id"] == sid), None)
            if row:
                if method == "PUT" and path.endswith("/content"):
                    row.update(content_json=request.post_data_json["content_json"], updated_at=NOW, updated_by_name="验收人员")
                elif method == "PATCH":
                    row.update(request.post_data_json)
                result = row
        elif path.endswith("/unread-count"):
            result = {"count": 0}
        route.fulfill(status=status, json=result)

    try:
        for _ in range(50):
            try:
                urlopen(BASE, timeout=1).close(); break
            except Exception:
                time.sleep(.2)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="msedge")
            context = browser.new_context(viewport={"width":1440,"height":1000})
            context.route("**/api/**", api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"qa\"]')")
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/company-management")
            expect(page.get_by_role("heading", name="公司管理", exact=True)).to_be_visible()
            sidebar = page.locator('.sidebar-menu')
            sidebar.get_by_text('个人中心', exact=True).click()
            expect(page.get_by_role('heading', name='个人中心', exact=True)).to_be_visible()
            page.wait_for_timeout(350)
            sidebar.get_by_text('公司管理', exact=True).click()
            expect(page.get_by_role('heading', name='公司管理', exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="编辑内容", exact=True)).to_be_visible()
            # 编辑富文本、拖拽窗口、关闭重开复位，以及固定底部。
            page.get_by_role("button", name="编辑内容", exact=True).click()
            dialog = page.get_by_role("dialog", name="编辑公司管理 · 公司制度")
            expect(dialog).to_be_visible()
            page.wait_for_timeout(350)  # 等待 Element Plus 打开动画完成后测量实际窗口坐标。
            header = dialog.locator(".el-dialog__header")
            start = dialog.locator('.el-dialog').bounding_box()
            pos = header.bounding_box()
            page.mouse.move(pos["x"] + 40, pos["y"] + 20)
            page.mouse.down(); page.mouse.move(pos["x"] + 180, pos["y"] + 100, steps=10); page.mouse.up()
            moved = dialog.locator('.el-dialog').bounding_box()
            assert abs(moved["x"] - start["x"]) > 50
            page.mouse.move(moved["x"] + 40, moved["y"] + 20)
            page.mouse.down(); page.mouse.move(4000, 4000, steps=10); page.mouse.up()
            bounds = dialog.locator('.el-dialog').bounding_box()
            assert bounds["x"] >= -1 and bounds["y"] >= -1 and bounds["x"] + bounds["width"] <= 1441 and bounds["y"] + bounds["height"] <= 1001
            dialog.locator(".el-dialog__headerbtn").click()
            expect(dialog).not_to_be_visible()
            page.get_by_role("button", name="编辑内容", exact=True).click()
            expect(dialog).to_be_visible()
            page.wait_for_timeout(350)
            restored = dialog.locator('.el-dialog').bounding_box()
            assert abs(restored["x"] - start["x"]) < 2 and abs(restored["y"] - start["y"]) < 2, (start, restored)
            dialog.locator("[contenteditable=true]").fill("公司管理验收正文")
            dialog.get_by_role("button", name="保存", exact=True).click()
            expect(page.locator(".notice-content__document")).to_contain_text("公司管理验收正文")
            # 分组栏目仍展示独立附件区。
            page.locator(".notice-nav").get_by_role("button", name="人事行政", exact=True).click()
            expect(page.locator(".notice-content h3")).to_have_text("人事行政")
            expect(page.get_by_role("button", name="编辑内容", exact=True)).to_have_count(0)
            page.locator(".notice-nav").get_by_role("button", name="公司制度", exact=True).click()
            page.locator("input[type=file]").set_input_files([
                {"name":"制度.pdf", "mimeType":"application/pdf", "buffer":b"file-one"},
                {"name":"失败.pdf", "mimeType":"application/pdf", "buffer":b"file-two"},
            ])
            expect(page.locator(".company-attachments")).to_contain_text("模拟单个附件失败")
            expect(page.locator(".company-attachments tbody tr")).to_have_count(1)
            page.get_by_role("button", name="重试", exact=True).click()
            expect(page.locator(".company-attachments tbody tr")).to_have_count(2)
            with page.expect_download() as download_info:
                page.get_by_role("button", name="下载", exact=True).first.click()
            assert download_info.value.suggested_filename.endswith(".pdf")
            page.get_by_role("button", name="删除", exact=True).first.click()
            page.get_by_role("dialog", name="删除附件").get_by_role("button", name="删除", exact=True).click()
            expect(page.locator(".company-attachments tbody tr")).to_have_count(1)
            page.get_by_role("button", name="栏目管理", exact=True).click()
            manager = page.get_by_role("dialog", name="公司管理栏目管理")
            expect(manager).to_be_visible()
            manager.get_by_role("button", name="新增一级栏目", exact=True).click()
            create = page.get_by_role("dialog", name="新增一级栏目")
            create.get_by_placeholder("请输入栏目名称").fill("自定义制度")
            create.get_by_role("button", name="确定", exact=True).click()
            expect(create).not_to_be_visible()
            expect(manager).to_contain_text("自定义制度")
            manager.get_by_role("button", name="关闭", exact=True).click()
            expect(page.locator(".notice-nav")).to_contain_text("自定义制度")
            search = page.get_by_placeholder("搜索栏目名称或内容")
            search.fill("自定义")
            expect(page.locator(".notice-search-results")).to_contain_text("自定义制度")
            search.fill("")
            expect(page.locator(".notice-layout")).to_be_visible()
            page.screenshot(path=str(out / "company-desktop.png"), full_page=True)
            # 小屏与长正文固定底部。
            page.set_viewport_size({"width":390,"height":844})
            expect(page.locator(".notice-page__mobile-select")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.get_by_role("button", name="编辑内容", exact=True).click()
            page.wait_for_timeout(350)
            dialog.locator("[contenteditable=true]").fill("\n".join(["长文档验收内容"] * 80))
            dialog.locator(".el-dialog__body").evaluate("el => el.scrollTop = el.scrollHeight")
            expect(dialog.get_by_role("button", name="保存", exact=True)).to_be_in_viewport()
            expect(dialog.get_by_role("button", name="取消", exact=True)).to_be_in_viewport()
            page.screenshot(path=str(out / "company-mobile-dialog.png"))
            dialog.get_by_role("button", name="取消", exact=True).click()
            page.get_by_role("button", name="放弃修改", exact=True).click()
            context.close()
            # 没有公司管理授权的普通用户仍可编辑；标注须知继续按项目权限控制。
            readonly = browser.new_context(viewport={"width":1440,"height":1000}, extra_http_headers={"x-qa-permission":"projects:read"})
            readonly.route("**/api/**", api)
            readonly.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"qa\"]')")
            page = readonly.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/company-management")
            expect(page.get_by_role("heading", name="公司管理", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="栏目管理", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="上传附件", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="编辑内容", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="下载", exact=True)).to_be_visible()
            # 标注须知公共组件回归。
            page.goto(BASE + "/annotation-details?section=notices")
            expect(page.get_by_role("heading", name="标注须知", exact=True)).to_be_visible()
            expect(page.locator(".notice-nav")).to_contain_text("公司制度")
            expect(page.get_by_role("button", name="栏目管理", exact=True)).to_have_count(0)
            expect(page.get_by_role("button", name="编辑内容", exact=True)).to_have_count(0)
            assert not errors, errors
            browser.close()
        print(json.dumps({"passed":True, "requests":len(requests), "screenshots":str(out), "page_errors":errors}, ensure_ascii=False))
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()


if __name__ == "__main__":
    run()
