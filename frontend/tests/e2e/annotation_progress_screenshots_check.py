r"""标注进度截图回归：真实 Vue 组件，全部 API 在浏览器内拦截，不连接数据库。

先启动本机前端，再在项目根目录运行：
  .venv\Scripts\python.exe frontend/tests/e2e/annotation_progress_screenshots_check.py
"""
import asyncio
import base64
import json
import os
import re
import struct
import tempfile
import zlib
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.async_api import async_playwright, expect

ORIGIN = "http://localhost:3000"
IMAGE_IDS = [f"00000000-0000-0000-0000-{n:012d}" for n in range(1, 5)]
SIGNATURE = "a" * 64
REF = f"![截图](screenshot://{IMAGE_IDS[0]}#{SIGNATURE})"
OLD_REF = f"![截图](screenshot://{IMAGE_IDS[1]})"
MISSING_REF = f"![截图](screenshot://{IMAGE_IDS[2]})"
PROJECT = {"id": "test-project", "orderNo": "TEST-001", "projectName": "截图验收项目",
           "projectStatus": "ended", "tasks": [], "languageItems": [], "childCount": 0}
STAMP = "2026-10-16T13:40:00+08:00"
ROWS = [dict(id=f"record-{i}", entryKind="status" if i == 0 else "progress",
             fromStatus="project_in_progress" if i == 0 else "ended", toStatus="ended",
             changeNote=note, effectiveOn=STAMP, changedAt=STAMP, updatedAt=STAMP,
             changedByName="测试用户", track="project", recordType="progress",
             projectOrderNo="TEST-001", projectName="截图验收项目")
        for i, note in enumerate(["已开票：2099.8元\n" + REF + "\n" + OLD_REF,
                                  OLD_REF, "普通文字\n保留换行", "无法加载\n" + MISSING_REF])]


def png():
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", 120, 60, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + b"\x32\x78\xc8" * 120) * 60)) + chunk(b"IEND", b""))


HARNESS = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<body><div id="app"></div><script type="module">
import { createApp, h, ref, nextTick } from '/node_modules/.vite/deps/vue.js';
import ElementPlus from '/node_modules/.vite/deps/element-plus.js';
import { createRouter, createMemoryHistory } from '/node_modules/.vite/deps/vue-router.js';
import '/node_modules/element-plus/dist/index.css';
import '/src/styles/theme.css';
import '/src/styles/common.css';
import AppForm from '/src/components/common/AppForm.vue';
import DraggableFormDialog from '/src/components/common/DraggableFormDialog.vue';
localStorage.setItem('user_roles', JSON.stringify(['admin']));
localStorage.setItem('token', 'isolated-browser-test');
localStorage.setItem('user_id', 'isolated-browser-test');
const mode = new URL(location.href).searchParams.get('mode');
const paths = {
 project: '/src/views/project/AnnotationProjects.vue',
 customer: '/src/components/annotation/AnnotationCustomerProgressTimeline.vue',
 search: '/src/components/annotation/AnnotationProgressSearchDialog.vue',
 arrangement: '/src/components/annotation/AnnotationProjectArrangementDialog.vue',
 annotator: '/src/components/annotation/AnnotationAnnotatorProgress.vue',
 comparison: '/src/components/annotation/AnnotationProgressComparison.vue',
 child: '/src/components/annotation/AnnotationChildProgressNotice.vue'
};
const Component = (await import(paths[mode])).default;
const project = __PROJECT__, rows = __ROWS__;
const visible = ref(mode !== 'search'), target = ref();
const props = {
 project: { progressOnly: true, progressProjectId: project.id, embedded: true },
 customer: { rows }, search: {}, arrangement: { initialProject: project, canWrite: true },
 annotator: { projectId: project.id, active: true, editable: false }, comparison: {},
 child: { projectId: project.id, count: 4, hasChildren: true, recordKeys: rows.map(r=>r.id) }
}[mode];
const app = createApp({render:()=>h(Component, {...props, ref:target, modelValue:visible.value,
 'onUpdate:modelValue':v=>visible.value=v})});
app.use(ElementPlus).component('AppForm', AppForm).component('DraggableFormDialog', DraggableFormDialog);
const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',component:{render:()=>null}}]});
app.use(router); await router.push('/'); await router.isReady(); app.mount('#app'); await nextTick();
if(mode==='search') visible.value=true;
if(mode==='comparison') target.value.open(project);
window.reopen=()=>visible.value=true;
window.testReady=true;
</script></body></html>""".replace("__PROJECT__", json.dumps(PROJECT)).replace("__ROWS__", json.dumps(ROWS))


async def run():
    # 使用开发服务器当前的依赖版本，确保路由注入键与业务组件来自同一模块实例。
    with urlopen(f"{ORIGIN}/src/views/project/AnnotationProjects.vue") as response:
        compiled = response.read().decode()
    version = re.search(r"/vue-router\.js\?v=([\w-]+)", compiled).group(1)
    harness = re.sub(r"(/node_modules/\.vite/deps/[^']+\.js)'", rf"\1?v={version}'", HARNESS)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel=os.getenv("BROWSER_CHANNEL", "msedge"))
        context = await browser.new_context(viewport={"width": 1440, "height": 1000}, service_workers="block")
        page = await context.new_page()
        errors, unexpected, writes = [], [], []
        def report_error(error):
            errors.append(str(error))
            print(f"浏览器错误: {error}", flush=True)
        page.on("pageerror", report_error)
        page.on("requestfailed", lambda req: print(f"请求失败: {req.url} {req.failure}", flush=True))
        upload_gate = asyncio.Event()
        upload_started = asyncio.Event()
        fail_upload = False
        history = list(ROWS)

        async def api(route):
            nonlocal history
            req = route.request
            path = urlparse(req.url).path.removeprefix("/api")
            if path == "/editor-screenshots" and req.method == "POST":
                upload_started.set()
                await upload_gate.wait()
                if fail_upload:
                    await route.fulfill(status=500, json={"detail": "模拟上传失败"})
                else:
                    await route.fulfill(json={"id": IMAGE_IDS[3], "reference": f"screenshot://{IMAGE_IDS[3]}#{SIGNATURE}"})
                return
            if path.startswith("/editor-screenshots/"):
                if path.endswith(IMAGE_IDS[2]):
                    await route.fulfill(status=404, json={"detail": "截图不存在"})
                else:
                    await route.fulfill(content_type="image/png", body=png())
                return
            if path == "/project-chat/annotation/test-project/start":
                # 进度页会预加载沟通面板；此测试明确禁用聊天，不创建会话。
                await route.fulfill(status=403, json={"detail": "隔离验收不启用项目沟通"})
                return
            if req.method in ("POST", "PATCH", "PUT", "DELETE"):
                if path.endswith("/status") or path.endswith("/progress"):
                    payload = req.post_data_json
                    writes.append(payload)
                    history = [dict(ROWS[1], id="saved-record", changeNote=payload["change_note"])]
                    await route.fulfill(json=history if path.endswith("/progress") else PROJECT)
                else:
                    unexpected.append(f"{req.method} {path}")
                    await route.fulfill(status=400, json={"detail": "测试未允许的写入"})
                return
            if path.endswith("/project-arrangements/context"):
                result = {"projects": [PROJECT], "taskTypes": [], "assignees": []}
            elif path.endswith("/status-history/recent") or path.endswith("/status-history/search"):
                result = {"items": ROWS, "total": len(ROWS)}
            elif path.endswith("/status-history"):
                result = history
            elif path.endswith("/customer-progress") or path.endswith("/annotator-progress"):
                result = ROWS
            elif path.endswith("/child-progress"):
                result = {"items": ROWS, "total": len(ROWS), "recordKeys": [r["id"] for r in ROWS]}
            elif path == "/projects/annotation/test-project":
                result = PROJECT
            else:
                # 页面加载的辅助只读请求也只返回模拟内容，绝不转发至后端。
                result = []
            await route.fulfill(json=result)

        await context.route(f"{ORIGIN}/api/**", api)
        await context.route("**/__annotation_screenshot_test*", lambda route: route.fulfill(content_type="text/html", body=harness))

        async def open_mode(mode):
            await page.goto(f"{ORIGIN}/__annotation_screenshot_test?mode={mode}")
            await page.wait_for_function("window.testReady === true")

        async def check_images(root):
            await expect(root.locator(".screenshot-preview img").first).to_be_visible()
            await expect(root.get_by_text("截图已过期或不存在", exact=True).first).to_be_visible()
            assert "screenshot://" not in await root.inner_text()
            assert "![截图]" not in await root.inner_text()
            await expect(root.get_by_text("普通文字\n保留换行", exact=True).first).to_be_visible()
            await root.locator(".screenshot-preview img").first.click()
            await expect(page.locator(".el-image-viewer__wrapper")).to_be_visible()
            await page.locator(".el-image-viewer__close").click()
            await expect(page.locator(".el-image-viewer__wrapper")).to_have_count(0)

        for mode in ["project", "customer", "search", "annotator", "comparison", "child"]:
            await open_mode(mode)
            if mode == "child":
                await page.get_by_role("button", name="查看子订单进度", exact=False).click()
            root = page.locator(".customer-progress-history") if mode == "customer" else page.locator("body")
            await check_images(root)
            if mode == "project":
                await page.screenshot(path=os.path.join(tempfile.gettempdir(), "annotation-progress-screenshots.png"))
                project_dialog = page.locator(".annotation-progress-dialog")
                footer = project_dialog.locator(".el-dialog__footer")
                before = await footer.bounding_box()
                await project_dialog.locator(".el-dialog__body").evaluate("el=>el.scrollTop=el.scrollHeight")
                after = await footer.bounding_box()
                assert abs(before["y"] - after["y"]) < 2
            if mode == "search":
                await page.get_by_placeholder("检索项目进度、客户进度或状态变更说明").fill("已开票")
                await expect(page.locator("mark").first).to_have_text("已开票")
                assert (await page.locator(".progress-search-item__content").first.inner_text()).strip() == "已开票：2099.8元"
            await page.reload()
            await page.wait_for_function("window.testReady === true")
            if mode == "child":
                await page.get_by_role("button", name="查看子订单进度", exact=False).click()
            await expect(page.locator(".screenshot-preview img").first).to_be_visible()
            print(f"PASS {mode}: 显示、预览、异常图片、刷新", flush=True)

        await open_mode("arrangement")
        await page.get_by_role("button", name="查看具体进度", exact=True).click()
        await check_images(page.locator(".progress-groups"))
        await page.get_by_role("button", name="补充进度", exact=True).click()

        async def paste_image():
            await page.locator(".progress-editor textarea").evaluate("""(el, data) => {
                const bytes=Uint8Array.from(atob(data), c=>c.charCodeAt(0));
                const clipboard=new DataTransfer();
                clipboard.items.add(new File([bytes], '测试截图.png', {type:'image/png'}));
                el.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:clipboard}));
            }""", base64.b64encode(png()).decode())
            await asyncio.wait_for(upload_started.wait(), 10)

        await paste_image()
        # 同一轮事件中连续点击，验证提交锁而非仅依赖按钮的 loading 样式。
        await page.get_by_role("button", name="保存具体进度", exact=True).evaluate("el=>{el.click();el.click()}")
        await expect(page.locator(".progress-editor .el-button.is-loading")).to_have_count(1)
        assert len(writes) == 0
        upload_gate.set()
        await expect(page.locator(".progress-editor")).to_have_count(0)
        assert len(writes) == 1 and IMAGE_IDS[3] in writes[0]["change_note"]
        await expect(page.locator(".progress-items img")).to_be_visible()

        # 编辑历史记录：失败时不保存，保留文字与原截图，重试成功后正常保存。
        await page.locator(".progress-item").get_by_role("button", name="编辑", exact=True).click()
        await page.locator(".progress-editor textarea").fill("失败后保留草稿")
        upload_gate.clear(); upload_started.clear(); fail_upload = True
        await paste_image()
        await page.get_by_role("button", name="保存具体进度", exact=True).click()
        upload_gate.set()
        await expect(page.get_by_text("截图上传失败，请处理提示后重新保存。", exact=True)).to_be_visible()
        assert len(writes) == 1
        await expect(page.locator(".progress-editor textarea")).to_have_value("失败后保留草稿")
        fail_upload = False; upload_started.clear()
        await paste_image()
        await expect(page.get_by_text("模拟上传失败", exact=False)).to_have_count(0)
        await page.get_by_role("button", name="保存具体进度", exact=True).click()
        await expect(page.locator(".progress-editor")).to_have_count(0)
        assert len(writes) == 2 and "失败后保留草稿" in writes[-1]["change_note"]

        dialog = page.locator(".annotation-arrangement-dialog")
        original = await dialog.bounding_box()
        handle = await dialog.locator(".app-window-drag-strip").bounding_box()
        await page.mouse.move(handle["x"] + 15, handle["y"] + 3)
        await page.mouse.down(); await page.mouse.move(handle["x"] + 80, handle["y"] + 65, steps=8); await page.mouse.up()
        moved = await dialog.bounding_box()
        assert abs(moved["y"] - original["y"]) > 10
        handle = await dialog.locator(".app-window-drag-strip").bounding_box()
        await page.mouse.move(handle["x"] + 15, handle["y"] + 3)
        await page.mouse.down(); await page.mouse.move(-500, -500, steps=8); await page.mouse.up()
        bounded = await dialog.bounding_box()
        assert bounded["x"] >= 0 and bounded["y"] >= 0
        await dialog.get_by_role("button", name="关闭窗口", exact=True).click()
        await expect(dialog).to_be_hidden()
        await page.evaluate("window.reopen()")
        await expect(dialog).to_be_visible()
        await page.wait_for_function("y=>Math.abs(document.querySelector('.annotation-arrangement-dialog').getBoundingClientRect().y-y)<3", arg=original["y"])
        reset = await dialog.bounding_box()
        assert abs(reset["y"] - original["y"]) < 3
        await page.set_viewport_size({"width": 600, "height": 700})
        await expect(dialog).to_be_visible()
        assert (await dialog.bounding_box())["width"] <= 600
        assert not unexpected, unexpected
        assert not errors, errors
        print("PASS arrangement: 粘贴、等待上传、重复提交、失败保留、编辑重试、拖动复位、小屏", flush=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
