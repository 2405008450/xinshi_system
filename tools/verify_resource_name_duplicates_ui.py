"""本机姓名查重交互验收；接口隔离，不写入实际业务数据。"""
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:12439"


def run():
    if socket.gethostname().upper() != "PC" or not ROOT.is_relative_to(Path(r"E:\xinshi_system")):
        raise SystemExit("仅允许在本机执行")
    out = ROOT / ".tmp" / "name-duplicates-ui"
    out.mkdir(parents=True, exist_ok=True)
    requests, saves, errors, delayed = [], [], [], []
    uid, owner, platform, rid = [str(uuid4()) for _ in range(4)]
    row = dict(id=rid, revision=1, full_name="已有资源", owner_id=uid, owner_name="测试人员", platform_id=platform,
               platform_name="测试平台", work_date="2026-10-08", actions=[], language_ids=[], phone="", wechat="",
               follow_up="", remarks="", can_edit=True, can_delete=True, progress={})
    candidates = [dict(id=str(uuid4()), full_name="同名资源", greeting_no=f"QA-{i:03}", wechat=f"wechat_{i}",
                       phone=f"1380000{i:04}", owner_name="其他人员" if i % 2 else "测试人员", platform_name="历史平台",
                       work_date="2025-01-02", contact_restricted=bool(i % 2)) for i in range(21)]
    fail_next = [False]

    def api(route):
        req = route.request
        path = urlparse(req.url).path.removeprefix("/api")
        query = parse_qs(urlparse(req.url).query)
        requests.append((req.method, path, query))
        result = {}
        if path == "/auth/session":
            result = dict(user_id=uid, username="qa", full_name="测试人员", roles=["admin"], permissions=["talents:read", "talents:write"])
        elif path == "/resource-development/options":
            result = dict(options=[dict(id=platform, kind="platform", category="national", name="测试平台")], users=[dict(id=uid, name="测试人员")],
                          languages=[], user_id=uid, can_delegate=False, can_write=True, default_date="2026-10-08")
        elif path == "/resource-development/days":
            result = dict(total=1, items=[dict(date="2026-10-08", count=1, people=[])])
        elif path == "/resource-development/records":
            if req.method == "POST":
                saves.append(req.post_data_json)
                result = {**req.post_data_json, "revision": 1}
            else:
                result = dict(total=1, items=[row])
        elif path.startswith("/resource-development/records/"):
            result = row
        elif path == "/resource-development/record-duplicates":
            if query.get("full_name") == ["慢同名"]:
                delayed.append(route)
                return
            if fail_next[0]:
                fail_next[0] = False
                route.fulfill(status=500, json={"detail": "测试查询失败"})
                return
            skip = int(query.get("skip", ["0"])[0])
            name = query.get("full_name", [""])[0]
            items = candidates if name == "同名资源" else []
            result = dict(total=len(items), items=items[skip:skip + 20])
        elif path == "/resource-development/duplicates":
            result = dict(items=[])
        elif path.endswith("/unread-count"):
            result = dict(count=0)
        route.fulfill(status=200, json=result)

    log = (out / "preview.log").open("w", encoding="utf-8")
    process = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port", "12439", "--strictPort"],
                               cwd=ROOT / "frontend", stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(50):
            try:
                urlopen(BASE, timeout=1).close()
                break
            except Exception:
                time.sleep(.2)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel="msedge")
            context = browser.new_context(viewport=dict(width=1440, height=900), timezone_id="Asia/Hong_Kong")
            context.route("**/api/**", api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/resource-management/resource-development")
            page.get_by_role("button", name="新增", exact=True).click()
            dialog = page.locator(".development-dialog")
            field = dialog.locator(".el-form-item").filter(has=page.locator("label", has_text="资源姓名")).locator("input")
            count = lambda: len([r for r in requests if r[1] == "/resource-development/record-duplicates"])
            baseline = count()
            field.fill("同名资源"); page.wait_for_timeout(200)
            assert count() == baseline
            expect(dialog.get_by_text("资源开拓中存在 21 条同名记录，请人工核实")).to_be_visible()
            assert not any(p == "/resource-development/duplicates" for _, p, _ in requests)
            assert requests[-1][2].get("full_name") == ["同名资源"]
            dialog.get_by_role("button", name="查看同名记录").click()
            popover = page.locator(".record-name-duplicates-popover")
            expect(popover).to_be_visible()
            expect(popover.get_by_text("wechat_0", exact=True)).to_be_visible()
            expect(popover.get_by_text("受限", exact=True).first).to_be_visible()
            assert popover.locator(".record-name-duplicate-item").count() == 20
            assert popover.locator(".record-name-duplicates-body").evaluate("el=>el.scrollHeight>el.clientHeight")
            expect(popover.get_by_text("2025/1/2", exact=True).first).to_be_visible()
            page.wait_for_timeout(350)
            box = popover.bounding_box()
            assert box["y"] >= 0 and box["y"] + box["height"] <= 900
            page.screenshot(path=str(out / "same-name.png"), full_page=True)
            popover.locator(".btn-next").click()
            expect(popover.get_by_text("wechat_20", exact=True)).to_be_visible()
            assert next(q for _, p, q in reversed(requests) if p.endswith("/record-duplicates"))["skip"] == ["20"]
            popover.get_by_role("button", name="关闭", exact=True).click()
            field.fill(""); expect(dialog.locator(".record-name-warning")).to_have_count(0)
            before = count(); page.wait_for_timeout(500); assert count() == before
            field.fill("慢同名"); page.wait_for_timeout(500)
            assert delayed
            field.fill("没有重复")
            page.wait_for_timeout(600)
            # 旧请求即使晚到也不能显示同名提示；取消后的路由可能已关闭。
            try:
                delayed.pop().fulfill(status=200, json=dict(total=21, items=candidates[:20]))
            except Exception:
                pass
            page.wait_for_timeout(200)
            expect(dialog.locator(".record-name-warning")).to_have_count(0)
            field.fill("同名资源"); page.wait_for_timeout(120); field.fill("快速改名")
            page.wait_for_timeout(500)
            expect(dialog.locator(".record-name-warning")).to_have_count(0)
            before = count()
            field.fill("失焦检查"); field.press("Tab")
            page.wait_for_timeout(150); assert count() == before + 1
            fail_next[0] = True
            field.fill("失败资源")
            expect(dialog.get_by_text("查重失败，请重试", exact=True)).to_be_visible()
            dialog.get_by_role("button", name="重试", exact=True).click()
            expect(dialog.get_by_text("查重失败，请重试", exact=True)).to_have_count(0)
            field.fill("同名资源")
            expect(dialog.get_by_text("资源开拓中存在 21 条同名记录，请人工核实")).to_be_visible()
            page.set_viewport_size(dict(width=600, height=760))
            dialog.get_by_role("button", name="查看同名记录").click()
            expect(popover).to_be_visible(); page.wait_for_timeout(350)
            box = popover.bounding_box()
            assert box["width"] <= 568 and box["x"] >= 0 and box["x"] + box["width"] <= 600
            assert box["y"] >= 0 and box["y"] + box["height"] <= 760
            page.screenshot(path=str(out / "small-screen.png"), full_page=True)
            popover.get_by_role("button", name="关闭", exact=True).click()
            page.set_viewport_size(dict(width=1440, height=900))
            dialog.locator(".el-form-item").filter(has=page.locator("label", has_text="开拓平台")).locator(".el-select").click()
            page.get_by_role("option", name="测试平台", exact=True).click()
            dialog.get_by_role("button", name="保存并继续新增", exact=True).click()
            expect(field).to_have_value("")
            assert saves[-1]["full_name"] == "同名资源" and not saves[-1]["duplicate_note"]
            expect(dialog.locator(".record-name-warning")).to_have_count(0)
            field.fill("待关闭请求"); dialog.get_by_role("button", name="取消", exact=True).click()
            before = count(); page.wait_for_timeout(500); assert count() == before
            page.get_by_role("button", name="新增", exact=True).click()
            expect(field).to_have_value(""); expect(dialog.locator(".record-name-warning")).to_have_count(0)
            dialog.get_by_role("button", name="取消", exact=True).click()
            page.get_by_role("button", name="编辑", exact=True).click()
            before = count(); field.fill("同名资源"); field.press("Tab"); page.wait_for_timeout(500)
            assert count() == before
            assert not errors, errors
            browser.close()
        print(json.dumps({"ok": True, "checks": ["400ms防抖", "失焦立即检查", "仅开拓记录", "信息与权限提示", "分页与滚动", "清空", "失败重试", "小屏", "同名保存与连续新增", "关闭复位", "编辑不查重"]}, ensure_ascii=False))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


if __name__ == "__main__":
    run()
