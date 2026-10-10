"""本机浏览器核重验收；所有 API 均为合成数据，禁止写入实际人才库。"""
import json
from pathlib import Path
import socket
import subprocess
import time
from urllib.parse import unquote, urlparse, parse_qs
from urllib.request import urlopen
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:12459"


def run():
    if socket.gethostname().upper() != "PC" or ROOT != Path(r"E:\xinshi_system"):
        raise SystemExit("仅允许在 PC 本机隔离验收")
    output = ROOT / ".tmp/talent-review-ui"
    output.mkdir(parents=True, exist_ok=True)
    a, b, user_id = [str(uuid4()) for _ in range(3)]
    members = [dict(id=identifier, resource_code=f"QA{i:03}", full_name="王测试", gender="男" if i == 1 else "女",
                    primary_email="synthetic@example.org", status="standby", created_at="2026-10-09T20:00:00+08:00",
                    updated_at="2026-10-09T20:00:00+08:00", name_duplicate=True, capability_types=[],
                    project_situation=dict(total=i)) for i, identifier in enumerate([a, b], 1)]
    fields = [dict(key="gender", label="性别", state="conflict", values=["男", "女"]),
              dict(key="residence_address", label="现居地", state="complement", values=[None, "北京"]),
              dict(key="primary_email", label="邮箱", state="same", values=["synthetic@example.org"] * 2)]
    group = dict(key="王测试", name="王测试", count=2, status="pending", summary="存在联系方式匹配，需结合身份核对")
    requests, commits, errors, deferred = [], [], [], []
    restricted, readiness, error_next = [False], [True], [False]
    operation = dict(id=str(uuid4()), action="merge", name_key="王测试", person_ids=[a, b], target_id=a,
                     actor_name="验收人员", created_at="2026-10-09T20:00:00+08:00", undone_at=None)
    history = []

    def api(route):
        req = route.request
        path = unquote(urlparse(req.url).path).removeprefix("/api")
        query = parse_qs(urlparse(req.url).query)
        requests.append((req.method, path, query))
        result = {}
        if path == "/auth/session":
            result = dict(user_id=user_id, username="qa", full_name="验收人员", roles=["普通用户"] if restricted[0] else ["admin"], permissions=["talents:read"])
        elif path == "/talents/page":
            result = dict(items=members, total=2)
        elif path in {f"/talents/{a}", f"/talents/{b}"}:
            result = dict(next(member for member in members if path.endswith(member["id"])), contact_restricted=False,
                          archived_into_id=b if path.endswith(a) else None, archived_at="2026-10-09T20:00:00+08:00" if path.endswith(a) else None)
        elif path == "/project-languages/":
            result = []
        elif path == "/talents/duplicate-review/groups":
            if error_next[0]:
                error_next[0] = False
                route.fulfill(status=500, json={"detail": "合成加载失败"})
                return
            if query.get("keyword") == ["慢查询"]:
                deferred.append(route)
                return
            result = dict(items=[group], total=1, counts=dict(pending=1, different=0, deferred=0), ready=readiness[0])
        elif path.startswith("/talents/duplicate-review/groups/"):
            result = dict(key="王测试", members=members, fields=fields if not restricted[0] else fields[:2], pairs=[dict(person_ids=[a, b], contact_matches=[] if restricted[0] else ["email"], identity_conflicts=["性别不同"], complement_count=1, decision=None)], recommended_target_id=b, ready=readiness[0], can_commit=not restricted[0] and readiness[0])
        elif path == "/talents/duplicate-review/preview":
            payload = req.post_data_json
            chosen = payload.get("decisions", {}).get("gender")
            conflicts = [dict(key="gender", label="性别", options=[dict(person_id=a, value="男"), dict(person_id=b, value="女")])] if payload["action"] == "merge" and not chosen else []
            result = dict(preview_token="a" * 64, action=payload["action"], archive_ids=[a] if payload.get("target_id") == b else [b] if payload.get("target_id") else [], conflicts=conflicts,
                          fields=[dict(key="gender", label="性别", value="男" if chosen else "女", options=[dict(person_id=a, value="男"), dict(person_id=b, value="女")])], omitted_fields=[], history_policy="原业务关联保留；来源附件只读。")
        elif path == "/talents/duplicate-review/commit":
            commits.append(req.post_data_json)
            history.append(operation)
            result = operation
        elif path == "/talents/duplicate-review/history":
            result = dict(items=history, total=len(history))
        elif path.endswith("/undo"):
            operation["undone_at"] = "2026-10-09T20:01:00+08:00"
            result = operation
        elif path.endswith("/unread-count"):
            result = dict(count=0)
        route.fulfill(status=200, json=result)

    log = (output / "preview.log").open("w", encoding="utf-8")
    process = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port", "12459", "--strictPort"], cwd=ROOT / "frontend", stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(60):
            try:
                urlopen(BASE, timeout=1).close()
                break
            except Exception:
                time.sleep(.2)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel="msedge")
            context = browser.new_context(viewport=dict(width=1440, height=900), timezone_id="America/Los_Angeles")
            context.route("**/api/**", api)
            context.add_init_script("localStorage.setItem('token','isolated-qa');localStorage.setItem('user_roles','[\"admin\"]')")
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/resource-management/talents")
            expect(page.get_by_role("button", name="同名核重", exact=True)).to_be_visible()
            page.locator(".duplicate-review-link").first.click()
            expect(page.get_by_role("heading", name="王测试 · 2 条档案")).to_be_visible()
            expect(page.locator(".comparison-matrix")).to_contain_text("现居地")
            expect(page.locator(".comparison-matrix")).not_to_contain_text("synthetic@example.org")
            page.locator(".comparison-controls .el-switch").click()
            expect(page.locator(".comparison-matrix")).to_contain_text("synthetic@example.org")
            page.get_by_role("button", name="合并资料", exact=True).click()
            dialog = page.locator(".review-action-dialog").filter(has=page.locator(".action-body"))
            expect(dialog.locator(".conflict-item")).to_have_count(1)
            page.wait_for_timeout(350)
            expect(dialog.get_by_role("button", name="确认合并资料")).to_be_disabled()
            initial = dialog.bounding_box()
            header = dialog.locator(".el-dialog__header").bounding_box()
            handle_x, handle_y = header["x"] + 15, header["y"] + header["height"] - 3
            page.mouse.move(handle_x, handle_y)
            page.mouse.down(); page.mouse.move(handle_x + 85, handle_y + 65, steps=8); page.mouse.up()
            moved = dialog.bounding_box()
            assert moved["x"] > initial["x"] + 30 and moved["y"] > initial["y"] + 30, (initial, moved)
            dragged_header = dialog.locator(".el-dialog__header").bounding_box()
            page.mouse.move(dragged_header["x"] + 15, dragged_header["y"] + dragged_header["height"] - 3); page.mouse.down(); page.mouse.move(2000, 1800, steps=10); page.mouse.up()
            bounded = dialog.bounding_box()
            assert bounded["x"] >= -1 and bounded["y"] >= -1 and bounded["x"] + bounded["width"] <= 1441 and bounded["y"] + bounded["height"] <= 901
            dialog.locator(".el-dialog__headerbtn").click()
            page.get_by_role("button", name="合并资料", exact=True).click()
            expect(dialog).to_be_visible()
            page.wait_for_timeout(350)
            reset_position = dialog.bounding_box()
            assert abs(reset_position["x"] - initial["x"]) < 2 and abs(reset_position["y"] - initial["y"]) < 2
            dialog.locator(".conflict-item .el-radio").first.click()
            dialog.get_by_role("button", name="更新预览", exact=True).click()
            expect(dialog.locator(".conflict-item")).to_have_count(0)
            dialog.locator(".el-checkbox").filter(has_text="已核对身份、最终资料及归档对象").click()
            dialog.get_by_role("button", name="确认合并资料", exact=True).click()
            expect(dialog).not_to_be_visible()
            assert len(commits) == 1 and commits[0]["decisions"]["gender"]["person_id"] == a and commits[0]["target_id"] == b
            page.get_by_role("button", name="处理历史", exact=True).click()
            history_dialog = page.locator(".review-action-dialog").filter(has_text="同名核重处理历史")
            expect(history_dialog).to_contain_text("2026")
            expect(history_dialog).to_contain_text("20:00")
            history_dialog.get_by_role("button", name="档案 1 详情", exact=True).click()
            original_detail = page.locator('.el-popover[aria-hidden="false"]').filter(has_text="人才核重档案详情")
            expect(original_detail).to_contain_text("synthetic@example.org")
            expect(original_detail).to_contain_text("已归档")
            history_dialog.get_by_role("button", name="档案 1 详情", exact=True).click()
            history_dialog.get_by_role("button", name="撤销处理").click()
            page.locator(".el-message-box").get_by_role("button", name="确定", exact=True).click()
            expect(history_dialog).to_contain_text("已撤销")
            history_dialog.get_by_role("button", name="关闭", exact=True).click()
            page.set_viewport_size(dict(width=700, height=700))
            expect(page.locator(".group-pane")).to_be_visible()
            page.get_by_role("button", name="合并资料", exact=True).click()
            expect(dialog).to_be_visible()
            dialog.locator(".el-dialog__body").evaluate("element => { element.scrollTop = element.scrollHeight }")
            footer = dialog.locator(".el-dialog__footer").bounding_box()
            assert footer["y"] >= 0 and footer["y"] + footer["height"] <= 700
            box = dialog.bounding_box()
            assert box["width"] <= 668.5 and box["x"] >= 0
            page.wait_for_timeout(350)  # 截图等待 Dialog 入场动画完成。
            page.screenshot(path=str(output / "small-screen.png"))
            dialog.get_by_role("button", name="取消", exact=True).click()
            page.set_viewport_size(dict(width=1440, height=900))
            keyword = page.get_by_placeholder("搜索姓名或人才编号")
            baseline = len([request for request in requests if request[1] == "/talents/duplicate-review/groups"])
            keyword.fill("王"); keyword.fill("王测"); keyword.fill("王测试")
            page.wait_for_timeout(180)
            assert len([request for request in requests if request[1] == "/talents/duplicate-review/groups"]) == baseline
            page.wait_for_timeout(400)
            assert len([request for request in requests if request[1] == "/talents/duplicate-review/groups"]) == baseline + 1
            keyword.fill("慢查询"); page.wait_for_timeout(550)
            keyword.fill(""); expect(page.locator(".group-item")).to_be_visible()
            for route in deferred:
                try:
                    route.fulfill(status=200, json=dict(items=[], total=0, counts={}, ready=True))
                except Exception:
                    pass
            page.wait_for_timeout(200)
            expect(page.locator(".group-item")).to_be_visible()
            error_next[0] = True
            page.get_by_role("button", name="查询", exact=True).click()
            expect(page.locator(".load-error")).to_contain_text("合成加载失败")
            page.get_by_role("button", name="重新加载", exact=True).click()
            expect(page.locator(".load-error")).not_to_be_visible()
            page.screenshot(path=str(output / "workbench.png"))
            readiness[0] = False
            page.reload()
            expect(page.get_by_text("数据库尚未启用核重结构", exact=False)).to_be_visible()
            expect(page.get_by_role("button", name="合并资料", exact=True)).to_have_count(0)
            readiness[0], restricted[0] = True, True
            page.reload()
            expect(page.get_by_text("当前账号仅可查看脱敏比对", exact=False)).to_be_visible()
            expect(page.get_by_role("button", name="合并资料", exact=True)).to_have_count(0)
            page.get_by_role("button", name="处理历史", exact=True).click()
            expect(history_dialog.get_by_role("button", name="档案 1 详情", exact=True)).to_have_count(0)
            expect(history_dialog.get_by_role("button", name="撤销处理", exact=True)).to_have_count(0)
            assert not errors, errors
            browser.close()
        print(json.dumps({"ok": True, "checks": ["列表入口与同名标签", "差异矩阵与互补", "字段冲突及最终预览", "合并提交与幂等键", "处理历史与撤销", "归档详情小窗", "跨时区展示", "拖动与视口边界", "关闭与复位", "小屏固定底栏", "400ms防抖", "清空及旧响应保护", "加载失败重试", "迁移前只读", "普通用户只读"], "screenshots": str(output)}, ensure_ascii=False))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


if __name__ == "__main__":
    run()
