"""真实页面接隔离 FastAPI/数据库；浏览器 API 桥接 TestClient，不启动业务后端。"""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare():
    import main  # noqa: F401，注册类型，不运行业务 startup。
    from database import engine
    from models import AppUser, Role, UserRole, RolePermission
    from resource_models import ResourcePerson, ResourceLanguageSkill
    from interpretation_models import InterpretationLanguage, InterpretationLanguageAlias
    from talent_overview_models import TalentOverviewSnapshot
    assert engine.url.host == "127.0.0.1" and engine.url.username == "wecom_test"
    tables = {model.__table__ for model in [AppUser, Role, UserRole, RolePermission, ResourcePerson,
                                           ResourceLanguageSkill, InterpretationLanguage, InterpretationLanguageAlias,
                                           TalentOverviewSnapshot]}
    pending = list(tables)
    while pending:
        table = pending.pop()
        for fk in table.foreign_keys:
            if fk.column.table not in tables:
                tables.add(fk.column.table)
                pending.append(fk.column.table)
    AppUser.metadata.create_all(engine, tables=list(tables))
    sql = (ROOT / "data/migrations/20261008_talent_overview_wecom.sql").read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)
        connection.exec_driver_sql(sql)
    print("隔离表和可重复迁移准备完成")


def run_ui():
    import main  # noqa: F401
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient
    from database import SessionLocal
    from models import AppUser, Role, UserRole, RolePermission
    from routers import talents, talent_overview_wecom, auth
    from concurrency import StaleUpdateError
    with SessionLocal() as db:
        admin = AppUser(id=uuid4(), username="wecom_ui_admin", full_name="企微验收员", password_hash="unused", is_active=True)
        viewer = AppUser(id=uuid4(), username="wecom_ui_viewer", full_name="只读验收员", password_hash="unused", is_active=True)
        other = AppUser(id=uuid4(), username="wecom_ui_other", full_name="另一位验收员", password_hash="unused", is_active=True)
        role = Role(id=uuid4(), role_name="admin")
        viewer_role = Role(id=uuid4(), role_name="企微只读验收")
        db.add_all([admin, viewer, other, role, viewer_role]); db.flush()
        db.add_all([UserRole(user_id=admin.id, role_id=role.id), UserRole(user_id=other.id, role_id=role.id), UserRole(user_id=viewer.id, role_id=viewer_role.id), RolePermission(role_id=viewer_role.id, permission_code='talents:read')]); db.commit()
        admin_id, viewer_id, other_id = admin.id, viewer.id, other.id
    app = FastAPI()
    app.include_router(talent_overview_wecom.router)
    app.include_router(talents.router)
    app.include_router(auth.router)

    def current_user(request: Request):
        with SessionLocal() as db:
            return db.get(AppUser, {'viewer': viewer_id, 'other': other_id}.get(request.headers.get("x-qa-user"), admin_id))
    app.dependency_overrides[auth.get_current_user] = current_user

    @app.exception_handler(StaleUpdateError)
    async def stale(_request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    client = TestClient(app)
    assert client.post("/talents/overview/languages/overview-001/groups", headers={"X-QA-User": "viewer"}, json={"name": "越权群", "is_built": False}).status_code == 403
    assert client.get("/talents/overview", headers={"X-QA-User": "viewer"}).status_code == 200
    created = client.post("/talents/overview/languages/overview-001/groups", json={"name": "英语验收一群", "is_built": True, "plan": "群运营计划", "remarks": "第一行\n第二行"})
    assert created.status_code == 201, created.text
    group = created.json()
    registered = client.post(f"/talents/overview/groups/{group['id']}/counts", json={"expected_revision": group["revision"], "statistics_date": "2026-10-08", "people_count": 120})
    assert registered.status_code == 201
    assert client.post(f"/talents/overview/groups/{group['id']}/counts", json={"expected_revision": 1, "statistics_date": "2026-10-08", "people_count": 999}).status_code == 409
    assert client.post(f"/talents/overview/groups/{group['id']}/counts", json={"expected_revision": 2, "statistics_date": "2026-10-08", "people_count": -1}).status_code == 422
    log = (ROOT / "wecom-vite.log").open("wb")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
    proc = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port", str(port), "--strictPort"], cwd=ROOT / "frontend", stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
                            env={**os.environ, "VITE_API_PROXY_TARGET": "http://127.0.0.1:9"})
    try:
        for _ in range(100):
            try:
                urlopen(f"http://127.0.0.1:{port}/", timeout=1); break
            except Exception:
                time.sleep(0.2)
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True, args=["--no-proxy-server"])
            admin_context = browser.new_context(viewport={"width": 1500, "height": 960})
            page = admin_context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            console_errors = []
            page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
            request_errors = []
            page.on('requestfailed', lambda request: request_errors.append((request.url, request.failure)))
            failures = []
            def bridge(route, qa_user=''):
                request = route.request
                path = urlsplit(request.url).path.removeprefix("/api")
                query = urlsplit(request.url).query
                # 未识别的外围接口也交给隔离应用，绝不转发到业务服务。
                if not (path.startswith('/talents') or path == '/auth/session'):
                    route.fulfill(status=200, body=json.dumps({'count': 0} if 'count' in path else []), content_type='application/json')
                    return
                response = client.request(request.method, path + ("?" + query if query else ""), content=request.post_data, headers={"Content-Type": "application/json", 'X-QA-User': qa_user})
                if response.status_code >= 500:
                    failures.append((path, response.status_code))
                route.fulfill(status=response.status_code, body=response.content, content_type="application/json")
            page.route("**/api/**", lambda route: bridge(route))
            page.add_init_script("localStorage.setItem('token','isolated-qa'); localStorage.setItem('user_roles','[\"admin\"]'); localStorage.setItem('user_permissions','[\"*\"]'); localStorage.setItem('user_id', '" + str(admin_id) + "');")
            page.goto(f"http://127.0.0.1:{port}/resource-management/talent-overview")
            page.wait_for_timeout(2500)
            page.screenshot(path=str(ROOT / "wecom-initial.png"))
            print("页面地址：", page.url, "页面错误：", errors, "控制台：", console_errors[:10], "请求错误：", request_errors[:10], flush=True)
            expect(page.get_by_text("人才总库自动统计：", exact=True)).to_be_visible(timeout=30000)
            expect(page.get_by_role("button", name="字段设置", exact=True)).to_be_visible()
            # 通过共享列筛选只显示英语行，避免与英语母语者混淆。
            page.get_by_role("button", name="语种/方言筛选", exact=True).click()
            filter_panel = page.locator(".column-header-filter-popover:visible")
            filter_panel.get_by_placeholder("搜索语种/方言").fill("英语")
            filter_panel.locator("label.el-checkbox").filter(has_text="英语").first.click()
            filter_panel.get_by_role("button", name="确定", exact=True).click()
            main_row = page.locator(".overview-table > .el-table__inner-wrapper > .el-table__body-wrapper tbody tr").first
            main_row.get_by_role("button", name="管理群", exact=True).click()
            panel = page.locator(".wecom-groups:visible").first
            expect(panel.get_by_text("英语验收一群", exact=True)).to_be_visible(timeout=20000)
            panel.get_by_role("button", name="新增企微群", exact=True).click()
            dialog = page.locator(".overview-wecom-editor:visible")
            dialog.get_by_role("button", name="保存", exact=True).click()
            expect(dialog.locator(".el-form-item.is-error input").first).to_be_focused()
            dialog.locator(".el-form-item").filter(has_text="群名").locator("input").fill("英语验收二群")
            dialog.locator(".el-form-item").filter(has_text="计划").locator("textarea").fill("拓展计划\n第二行")
            dialog.locator(".el-form-item").filter(has_text="备注").locator("textarea").fill("验收备注")
            # 拖动、边界、固定底栏、小屏、字段搜索。
            before = dialog.bounding_box()
            header = dialog.locator(".el-dialog__header")
            box = header.bounding_box()
            page.mouse.move(box["x"] + 15, box["y"] + box["height"] / 2)
            page.mouse.down(); page.mouse.move(box["x"] + 80, box["y"] + 70, steps=8); page.mouse.up()
            after = dialog.bounding_box()
            assert abs(after["x"] - before["x"]) > 10 or abs(after["y"] - before["y"]) > 10
            moved_header = header.bounding_box()
            page.mouse.move(moved_header['x'] + 15, moved_header['y'] + moved_header['height'] / 2)
            page.mouse.down(); page.mouse.move(-500, -500, steps=10); page.mouse.up()
            boundary = dialog.bounding_box()
            assert boundary['x'] >= -1 and boundary['y'] >= -1
            assert boundary['x'] + boundary['width'] <= 1501 and boundary['y'] + boundary['height'] <= 961
            page.screenshot(path=str(ROOT / "wecom-editor.png"))
            dialog.get_by_role("button", name="保存", exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(panel.get_by_text("英语验收二群", exact=True)).to_be_visible()
            first_group = panel.locator(".wecom-groups-table tbody tr").filter(has_text="英语验收一群").first
            first_group.get_by_role("button", name="登记人数", exact=True).click()
            dialog.locator('.el-form-item').filter(has_text='统计日期').locator('input').fill('2026-10-08')
            dialog.locator('.el-form-item').filter(has_text='统计日期').locator('input').press('Tab')
            dialog.locator(".el-form-item").filter(has_text="人数").locator("input").fill("125")
            dialog.get_by_role("button", name="保存", exact=True).click()
            expect(first_group).to_contain_text("125")
            first_group.get_by_role("button", name="查看详情", exact=True).click()
            popover = page.locator(".overview-management-popover:visible")
            expect(popover).to_contain_text("企微验收员")
            expect(popover).to_contain_text("当前人数")
            popover.locator(".counts-history-table tbody tr").first.get_by_role("button", name="作废", exact=True).click()
            dialog.locator("textarea").fill("验收纠错")
            dialog.get_by_role("button", name="确认作废", exact=True).click()
            expect(first_group).to_contain_text("120")
            panel.get_by_role("button", name="编辑语种计划/备注", exact=True).click()
            dialog.locator("textarea").first.fill("语种总体计划")
            dialog.get_by_role("button", name="保存", exact=True).click()
            expect(panel.locator(".language-memo")).to_contain_text("语种总体计划")
            first_group.get_by_role("button", name="归档", exact=True).click()
            page.locator(".el-message-box:visible").get_by_role("button", name="确定", exact=True).click()
            expect(first_group).to_have_count(0)
            panel.locator('label.el-checkbox').filter(has_text='显示归档群').click()
            restored = panel.locator(".wecom-groups-table tbody tr").filter(has_text="英语验收一群").first
            restored.get_by_role("button", name="恢复", exact=True).click()
            page.locator(".el-message-box:visible").get_by_role("button", name="确定", exact=True).click()
            expect(restored.get_by_role("button", name="登记人数", exact=True)).to_be_enabled()
            # 编辑态检查资料、并发冲突保留草稿以及显式重新加载。
            restored.get_by_role('button', name='编辑', exact=True).click()
            expect(dialog.locator('.el-form-item').filter(has_text='群名').locator('input')).to_have_value('英语验收一群')
            expect(dialog.locator('.el-form-item').filter(has_text='备注').locator('textarea')).to_have_value('第一行\n第二行')
            draft_plan = dialog.locator('.el-form-item').filter(has_text='计划').locator('textarea')
            draft_plan.fill('保留的冲突草稿')
            latest = client.get(f"/talents/overview/groups/{group['id']}").json()
            assert client.put(f"/talents/overview/groups/{group['id']}", json={
                'expected_revision': latest['revision'], 'name': latest['name'], 'is_built': True,
                'built_date': None, 'plan': '其他人已保存的计划', 'remarks': latest['remarks'],
            }).status_code == 200
            dialog.get_by_role('button', name='保存', exact=True).click()
            expect(dialog.get_by_text('资料已被其他人修改，当前草稿已保留。请复制需要保留的内容，再重新加载核对。')).to_be_visible()
            expect(draft_plan).to_have_value('保留的冲突草稿')
            dialog.get_by_role('button', name='重新加载（替换草稿）').click()
            page.locator('.el-message-box:visible').get_by_role('button', name='放弃修改').click()
            expect(draft_plan).to_have_value('其他人已保存的计划')
            dialog.get_by_role('button', name='取消', exact=True).click()
            # 用真实长备注验证详情小窗内部滚动和左侧定位。
            latest = client.get(f"/talents/overview/groups/{group['id']}").json()
            assert client.put(f"/talents/overview/groups/{group['id']}", json={
                'expected_revision': latest['revision'], 'name': latest['name'],
                'is_built': latest['is_built'], 'built_date': latest['built_date'],
                'plan': latest['plan'], 'remarks': '\n'.join(f'第 {i} 行详情滚动验收备注' for i in range(40)),
            }).status_code == 200
            detail_button = restored.get_by_role('button', name='查看详情', exact=True)
            detail_button.click()
            expect(popover).to_contain_text('第 39 行详情滚动验收备注')
            detail_body = popover.locator('.detail-body')
            assert detail_body.evaluate('el => el.scrollHeight > el.clientHeight && el.clientHeight <= 560')
            assert popover.bounding_box()['x'] < detail_button.bounding_box()['x']
            detail_body.evaluate('el => { el.scrollTop = el.scrollHeight }')
            assert detail_body.evaluate('el => el.scrollTop') > 0
            popover.get_by_role('tab', name='操作历史', exact=True).click()
            expect(popover).to_contain_text('修改群资料')
            page.screenshot(path=str(ROOT / 'wecom-details.png'))
            page.get_by_text('人才概览', exact=True).first.click()
            # 首次打开、拖动后关闭再打开，位置应复位。
            panel.get_by_role('button', name='新增企微群', exact=True).click()
            page.wait_for_timeout(350)
            reopened = dialog.bounding_box()
            assert abs(reopened['x'] - before['x']) < 2 and abs(reopened['y'] - before['y']) < 2, {'initial': before, 'reopened': reopened}
            dialog.get_by_role('button', name='取消', exact=True).click()
            page.screenshot(path=str(ROOT / "wecom-overview-desktop.png"))
            page.set_viewport_size({"width": 760, "height": 720})
            panel.get_by_role("button", name="新增企微群", exact=True).click()
            body = dialog.locator(".el-dialog__body")
            body.evaluate("el => { el.scrollTop = el.scrollHeight }")
            footer = dialog.locator(".el-dialog__footer").bounding_box()
            assert footer["y"] + footer["height"] <= 720
            search = dialog.get_by_placeholder("搜索字段，如计划、人数")
            search.fill("群名")
            page.locator(".project-field-search-popper:visible li").first.click()
            expect(dialog.locator(".el-form-item").filter(has_text="群名").locator("input")).to_be_focused()
            page.screenshot(path=str(ROOT / "wecom-overview-small.png"))
            dialog.get_by_role("button", name="取消", exact=True).click()
            # 字段全取消保留结构列；恢复默认、刷新持久化、用户隔离。
            page.set_viewport_size({'width': 1500, 'height': 960})
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings = page.locator('.table-column-settings-popover:visible')
            checked = settings.locator('label.el-checkbox.is-checked')
            while checked.count():
                previous_count = checked.count()
                checked.first.click()
                expect(checked).to_have_count(previous_count - 1)
            page.get_by_text('人才概览', exact=True).first.click()
            main_header = page.locator('.overview-table > .el-table__inner-wrapper > .el-table__header-wrapper')
            expect(main_header.get_by_text('语种/方言', exact=True)).to_have_count(0)
            expect(main_header.get_by_text('详情', exact=True)).to_be_visible()
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings.get_by_role('button', name='恢复默认', exact=True).click()
            settings.locator('label.el-checkbox').filter(has_text='HR1（紫霞）').click()
            page.get_by_text('人才概览', exact=True).first.click()
            page.reload()
            expect(main_header.get_by_text('HR1（紫霞）', exact=True)).to_be_visible()
            # 相同浏览器存储内切换另一位用户，只给该页面的接口选取另一身份。
            other_page = page.context.new_page()
            other_page.route('**/api/**', lambda route: bridge(route, 'other'))
            other_page.goto(f'http://127.0.0.1:{port}/resource-management/talent-overview')
            expect(other_page.get_by_role('button', name='字段设置', exact=True)).to_be_visible()
            expect(other_page.locator('.overview-table > .el-table__inner-wrapper > .el-table__header-wrapper').get_by_text('HR1（紫霞）', exact=True)).to_have_count(0)
            other_page.close()
            # 只读用户进入真实页面可以看群，无法新增、编辑或登记。
            viewer_context = browser.new_context(viewport={'width': 1500, 'height': 960})
            viewer_context.add_init_script("localStorage.setItem('token','isolated-viewer');")
            viewer_page = viewer_context.new_page()
            viewer_page.route('**/api/**', lambda route: bridge(route, 'viewer'))
            viewer_page.goto(f'http://127.0.0.1:{port}/resource-management/talent-overview')
            expect(viewer_page.get_by_role('button', name='字段设置', exact=True)).to_be_visible()
            expect(viewer_page.get_by_role('button', name='编辑', exact=True)).to_have_count(0)
            viewer_page.get_by_role('button', name='管理群', exact=True).first.click()
            expect(viewer_page.locator('.wecom-groups:visible').first.get_by_text('英语验收一群', exact=True)).to_be_visible()
            expect(viewer_page.get_by_role('button', name='新增企微群', exact=True)).to_have_count(0)
            viewer_context.close()
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings.get_by_role('button', name='恢复默认', exact=True).click()
            page.get_by_text('人才概览', exact=True).first.click()
            assert not errors, errors
            assert not failures, failures
            browser.close()
            (ROOT / "wecom-ui-results.json").write_text(json.dumps({"passed": True, "page_errors": errors, "api_failures": failures}, ensure_ascii=False, indent=2), encoding="utf-8")
            print("企微大群真实接口/页面验收通过")
    finally:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        log.close()


if __name__ == "__main__":
    assert socket.gethostname().upper() == "PC" and "xinshi_validation" in str(ROOT)
    assert "wecom_test@127.0.0.1:" in os.environ.get("DATABASE_URL", "")
    parser = argparse.ArgumentParser(); parser.add_argument("--prepare", action="store_true")
    if parser.parse_args().prepare:
        prepare()
    else:
        run_ui()
