"""本机编译页面交互验收，接口使用隔离模拟数据，不修改业务内容。"""
import json
import base64
import io
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect
from PIL import Image

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
        ["node", "node_modules/vite/bin/vite.js", "preview", "--outDir", "dist", "--host", "127.0.0.1", "--port", "12427", "--strictPort"],
        cwd=ROOT / "frontend", stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    rows = [
        dict(id=str(uuid4()), section_key=f"qa_{i}", title=title, display_title=title, parent_id=None,
             sort_order=i+1, has_content=i != 1, is_active=True, content_json=None,
             updated_at=None, structure_updated_at=NOW, updated_by_name=None, children=[])
        for i, title in enumerate(["公司制度", "人事行政", "财务规范", "常用模板"])
    ]
    attachments = {}
    images = {}
    image_requests = []
    pending_image_uploads = []
    hold_images = False
    fail_next_image = False
    picture = io.BytesIO()
    Image.new("RGB", (2800, 1800), "#e0f2fe").save(picture, format="PNG")
    picture_bytes = picture.getvalue()
    picture_base64 = base64.b64encode(picture_bytes).decode()
    second_picture = io.BytesIO()
    Image.new("RGB", (128, 96), "#fef3c7").save(second_picture, format="PNG")
    second_picture_base64 = base64.b64encode(second_picture.getvalue()).decode()
    failures = set()
    errors = []
    requests = []
    security_policy = re.search(r'add_header Content-Security-Policy "([^"]+)"',
        (ROOT / 'frontend/nginx.conf').read_text(encoding='utf-8')).group(1)

    def security_headers(route):
        if route.request.resource_type == 'document':
            response = route.fetch()
            route.fulfill(response=response, headers={**response.headers, 'Content-Security-Policy': security_policy})
        else:
            route.continue_()

    def api(route):
        nonlocal fail_next_image
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
        elif "/images/" in path:
            sid, aid = path.split("/sections/")[-1].split("/images/")
            image_requests.append((method, path, request.headers.get("authorization")))
            if method == "DELETE":
                images.pop(aid, None)
                route.fulfill(status=204); return
            route.fulfill(status=200, body=picture_bytes, headers={"Content-Type": "image/png"}); return
        elif path.endswith("/images"):
            image_requests.append((method, path, request.headers.get("authorization")))
            if fail_next_image:
                fail_next_image = False
                route.fulfill(status=400, json={"detail": "模拟图片上传失败"}); return
            sid = path.split("/")[-2]
            result = dict(id=str(uuid4()), section_id=sid, original_name="粘贴图片.png", file_size=len(picture_bytes), content_type="image/png", uploaded_by=UID, uploaded_by_name="验收人员", uploaded_at=NOW)
            result["src"] = f"/api/company-management/sections/{sid}/images/{result['id']}"
            images[result["id"]] = result
            if hold_images:
                pending_image_uploads.append((route, result)); return
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
            context.route('**/*', security_headers)
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
            # 截图粘贴、光标插入、上传期间锁定、撤销重做及稳定保存地址。
            def paste(target, html="", plain="", with_file=True, extra_file=False):
                target.evaluate("""(element, value) => {
                  element.focus(); const clipboard = new DataTransfer();
                  if (value.html) clipboard.setData('text/html', value.html);
                  if (value.plain) clipboard.setData('text/plain', value.plain);
                  for (const png of value.files) {
                    const bytes = Uint8Array.from(atob(png), c => c.charCodeAt(0));
                    clipboard.items.add(new File([bytes], '截图.png', {type:'image/png'}));
                  }
                  element.dispatchEvent(new ClipboardEvent('paste', {clipboardData: clipboard, bubbles:true, cancelable:true}));
                }""", {"html": html, "plain": plain, "files": ([picture_base64, second_picture_base64] if extra_file else [picture_base64]) if with_file else []})

            page.get_by_role("button", name="编辑内容", exact=True).click()
            prose = dialog.locator('.rich-editor__prose')
            prose.fill("前后")
            prose.evaluate("""element => { const node=element.querySelector('p').firstChild; const range=document.createRange(); range.setStart(node,1); range.collapse(true); const selection=window.getSelection(); selection.removeAllRanges(); selection.addRange(range); }""")
            hold_images = True
            paste(prose)
            expect(dialog.get_by_role("button", name="保存", exact=True)).to_be_disabled()
            expect(prose).to_have_attribute("contenteditable", "false")
            page.wait_for_timeout(150)
            assert len(pending_image_uploads) == 1
            held, result = pending_image_uploads.pop()
            held.fulfill(status=201, json=result)
            hold_images = False
            expect(prose.locator('img')).to_have_count(1)
            expect(prose).to_contain_text("前")
            expect(prose).to_contain_text("后")
            expect(prose).to_have_attribute("contenteditable", "true")
            dialog.get_by_role("button", name="撤销", exact=True).click()
            expect(prose.locator('img')).to_have_count(0)
            dialog.get_by_role("button", name="重做", exact=True).click()
            expect(prose.locator('img')).to_have_count(1)
            dialog.get_by_role("button", name="保存", exact=True).click()
            expect(page.locator('.notice-content__document img')).to_have_count(1)
            assert rows[0]['content_json']['content'][1]['attrs']['src'].startswith('/api/company-management/')
            assert 'blob:' not in json.dumps(rows[0]['content_json'])
            assert [n['type'] for n in rows[0]['content_json']['content']] == ['paragraph', 'image', 'paragraph']
            page.reload()
            expect(page.locator('.notice-content__document img')).to_have_count(1)
            page.get_by_role("button", name="编辑内容", exact=True).click()
            expect(prose.locator('img')).to_have_count(1)
            # 图文来源格式清除，文件与HTML双表示去重，原有图片不重复上传。
            before = len([r for r in image_requests if r[0] == 'POST'])
            prose.click()
            prose.press('Control+End')
            paste(prose, '<p><b>混合前文 https://example.com</b><img src="file:///word/image.png"><i>混合后文</i></p>')
            expect(prose.locator('img')).to_have_count(2)
            assert len([r for r in image_requests if r[0] == 'POST']) == before + 1
            expect(prose.locator('a[href="https://example.com"]')).to_have_count(1)
            assert prose.locator('strong,em').count() == 0
            dialog.get_by_role('button', name='取消', exact=True).click()
            page.get_by_role('button', name='放弃修改', exact=True).click()
            expect(dialog).not_to_be_visible()
            page.wait_for_timeout(150)
            assert len(images) == 1
            # 两个不同剪贴板文件按照HTML顺序插入，撤销后保存清理未使用草稿。
            page.get_by_role('button', name='编辑内容', exact=True).click()
            prose.press('Control+End')
            before = len(images)
            paste(prose, '<p>多图前文<img src="file:///a.png">多图中间<img src="file:///b.png">多图后文</p>', extra_file=True)
            expect(prose.locator('img')).to_have_count(3)
            assert len(images) == before + 2
            expect(prose).to_contain_text('多图中间')
            dialog.get_by_role('button', name='撤销', exact=True).click()
            expect(prose.locator('img')).to_have_count(1)
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog).not_to_be_visible()
            page.wait_for_timeout(150)
            assert len(images) == before
            # HTML和文件项数量不同也不漏图；内嵌图片与同内容文件只插入一次。
            page.get_by_role('button', name='编辑内容', exact=True).click()
            prose.press('Control+End')
            before = len(images)
            paste(prose, f'<p>双表示前文<img src="data:image/png;base64,{picture_base64}">双表示后文</p>', extra_file=True)
            expect(prose.locator('img')).to_have_count(3)
            assert len(images) == before + 2
            dialog.get_by_role('button', name='取消', exact=True).click()
            page.get_by_role('button', name='放弃修改', exact=True).click()
            expect(dialog).not_to_be_visible()
            page.wait_for_timeout(150)
            assert len(images) == before
            # 浏览器可读的网页图片重新入库，来源请求不携带站内登录凭据。
            external_requests = []
            def external_image(route):
                external_requests.append(route.request.headers)
                route.fulfill(status=200, body=picture_bytes, headers={"Content-Type": "image/png", "Access-Control-Allow-Origin": "*"})
            page.route('https://clipboard.example.test/image.png', external_image)
            page.get_by_role('button', name='编辑内容', exact=True).click()
            prose.press('Control+End')
            paste(prose, '<p>网页前文<img src="https://clipboard.example.test/image.png">网页后文</p>', with_file=False)
            expect(prose.locator('img')).to_have_count(2)
            assert external_requests and all('authorization' not in item and 'cookie' not in item for item in external_requests)
            dialog.get_by_role('button', name='取消', exact=True).click()
            page.get_by_role('button', name='放弃修改', exact=True).click()
            expect(dialog).not_to_be_visible()
            # 关闭上传中的弹窗并马上重新打开，迟到结果不能插入新编辑会话。
            page.get_by_role('button', name='编辑内容', exact=True).click()
            prose.press('Control+End')
            hold_images = True
            paste(prose)
            expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_disabled()
            page.wait_for_timeout(150)
            assert len(pending_image_uploads) == 1
            held, late_result = pending_image_uploads.pop()
            dialog.get_by_role('button', name='取消', exact=True).click()
            page.get_by_role('button', name='放弃修改', exact=True).click()
            expect(dialog).not_to_be_visible()
            hold_images = False
            try:
                held.fulfill(status=201, json=late_result)
            except Exception:
                pass  # 浏览器已取消网络请求，服务端遗留草稿由24小时策略清理。
            page.get_by_role('button', name='编辑内容', exact=True).click()
            expect(prose.locator('img')).to_have_count(1)
            expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_enabled()
            dialog.get_by_role('button', name='取消', exact=True).click()
            expect(dialog).not_to_be_visible()
            # 内嵌data图片无需文件项；纯图片内容保存后不能被当作空正文。
            page.get_by_role('button', name='编辑内容', exact=True).click()
            prose.fill('')
            paste(prose, f'<img src="data:image/png;base64,{picture_base64}">', with_file=False)
            expect(prose.locator('img')).to_have_count(1)
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(page.locator('.notice-content__document img')).to_have_count(1)
            expect(page.locator('.company-attachments tbody tr')).to_have_count(0)
            # 图片失败保留文字并恢复保存，不能插入来源地址。
            page.get_by_role('button', name='编辑内容', exact=True).click()
            fail_next_image = True
            prose.press('Control+End')
            paste(prose, '<p>失败前文<img src="file:///word/a.png">失败后文</p>')
            expect(page.get_by_text('模拟图片上传失败', exact=True)).to_be_visible()
            expect(prose).to_contain_text('失败前文')
            expect(prose).to_contain_text('失败后文')
            expect(dialog.get_by_role('button', name='保存', exact=True)).to_be_enabled()
            expect(prose.locator('img')).to_have_count(1)
            paste(prose, '<p>不可读前文<img src="file:///word/unknown.png">不可读后文</p>', with_file=False)
            expect(prose).to_contain_text('不可读后文')
            expect(prose.locator('img')).to_have_count(1)
            dialog.get_by_role('button', name='取消', exact=True).click()
            page.get_by_role('button', name='放弃修改', exact=True).click()
            assert all(token == 'Bearer isolated-qa' for _, _, token in image_requests)
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
            expect(page.locator('.notice-content__document img')).to_have_count(1)
            assert page.locator('.notice-content__document img').evaluate('el => el.getBoundingClientRect().width <= el.closest(".notice-content").getBoundingClientRect().width')
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
            readonly.route('**/*', security_headers)
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
