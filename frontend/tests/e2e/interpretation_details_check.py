"""口译项目详情页只读交互验收。

环境变量：BASE_URL、LOGIN_USERNAME、LOGIN_PASSWORD；脚本不会提交或删除业务数据。
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"缺少环境变量 {name}")
    return value


def login(base_url: str, username: str, password: str) -> dict:
    request = urllib.request.Request(
        f"{base_url}/api/auth/login/json",
        data=json.dumps({"username": username, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    base_url = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
    auth = login(base_url, required("LOGIN_USERNAME"), required("LOGIN_PASSWORD"))
    output = Path("test-results/interpretation-details.png")
    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel=os.environ.get("BROWSER_CHANNEL", "msedge"))
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{base_url}/login")
        page.evaluate(
            """(auth) => {
              localStorage.setItem('token', auth.access_token);
              localStorage.setItem('user_id', auth.user_id || '');
              localStorage.setItem('user_name', auth.username || '');
              localStorage.setItem('user_roles', JSON.stringify(auth.roles || []));
              localStorage.setItem('user_permissions', JSON.stringify(auth.permissions || []));
            }""",
            auth,
        )
        page.goto(f"{base_url}/interpretation-details")
        page.wait_for_selector(".interpretation-table", timeout=15000)

        headers = page.locator(".interpretation-table .el-table__header th").all_inner_texts()
        assert "客户编号" not in headers, "客户编号不应默认显示"
        assert "译员编号" not in headers, "译员编号不应默认显示"
        assert "子客户/联系人" not in headers, "子客户/联系人不应默认显示"
        assert "客户单号/项目标识" not in headers, "客户单号/项目标识不应默认显示"
        assert headers.index("序号") < headers.index("订单号"), "序号应位于订单号之前"

        if page.get_by_role("button", name="新增口译项目", exact=True).count():
            page.get_by_role("button", name="新增口译项目", exact=True).click()
            dialog = page.locator(".interpretation-editor-dialog")
            dialog.wait_for(state="visible")
            assert dialog.get_by_text("译员人数", exact=True).count()
            assert dialog.get_by_text("译员性别", exact=True).count()
            assert dialog.get_by_text("口译水平", exact=True).count()
            assert dialog.get_by_text("特殊要求", exact=True).count()
            assert dialog.get_by_text("形象与着装要求", exact=True).count()
            footer = dialog.locator(".el-dialog__footer")
            before = footer.bounding_box()
            dialog.locator(".el-dialog__body").evaluate("node => { node.scrollTop = node.scrollHeight }")
            after = footer.bounding_box()
            assert before and after and abs(before["y"] - after["y"]) < 2, "滚动时底部操作栏发生位移"
            dialog.get_by_role("button", name="取消", exact=True).click()

        first_order = page.locator(".interpretation-table .el-table__body .order-cell .el-button").first
        if first_order.count():
            first_order.click()
            popover = page.locator(".interpretation-detail-popover")
            popover.wait_for(state="visible")
            assert popover.get_by_text("客户对译员评价", exact=True).count()
            assert popover.get_by_text("邮件主题预览", exact=True).count()

        page.screenshot(path=str(output), full_page=True)
        browser.close()
    print(f"口译详情页验收通过，截图：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
