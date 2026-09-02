"""七个业务列表的表头筛选与紧凑高级筛选只读验收。

环境变量：BASE_URL、LOGIN_USERNAME、LOGIN_PASSWORD；脚本只执行查询，不提交、编辑或删除业务数据。
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


MODULES = [
    ("笔译项目管理", "/translation-details", "母/子订单号、项目名称、客户名称或客户单号", 9),
    ("口译项目管理", "/interpretation-details", "订单号、项目名称、客户名称或客户单号", 9),
    ("标注项目管理", "/annotation-details", "订单号、项目名称、客户名称或客户单号", 12),
    ("招聘项目管理", "/recruitment-details", "订单号、项目名称、客户名称或客户单号", 11),
    ("人才资源库", "/resource-management/talents", "姓名、编号、电话或邮箱", 10),
    ("客户信息", "/clients", "支持客户全称、简称及子客户名称模糊搜索", 10),
    ("资源需求管理", "/resource-requests", "搜索请求编号、项目、客户或需求详情", 8),
]
NO_MATCH = "GRAY-LIST-SEARCH-NO-MATCH-260830"


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


def wait_list_idle(page: Page) -> None:
    page.wait_for_timeout(650)
    loading = page.locator(".el-table .el-loading-mask:visible")
    if loading.count():
        loading.wait_for(state="hidden", timeout=15000)


def row_count(page: Page) -> int:
    return page.locator(".el-table__body-wrapper tbody tr").count()


def first_searchable_text(page: Page) -> str:
    first_row = page.locator(".el-table__body-wrapper tbody tr").first
    buttons = first_row.locator("button.el-button")
    for index in range(buttons.count()):
        value = buttons.nth(index).inner_text().strip()
        if value and value not in {"编辑", "查看详情", "发起需求"}:
            return value
    text = re.sub(r"\s+", " ", first_row.inner_text()).strip()
    for token in text.split(" "):
        if len(token) >= 2 and token not in {"编辑", "查看详情", "发起需求"}:
            return token
    raise AssertionError("首行没有可用于关键词搜索的业务文本")


def open_advanced(page: Page):
    button = page.get_by_role("button", name=re.compile(r"^高级筛选"))
    assert button.count() == 1, "高级筛选入口应唯一"
    button.click()
    popover = page.locator(".common-advanced-filter-popover:visible")
    popover.wait_for(state="visible", timeout=5000)
    return button, popover


def check_advanced_filter(page: Page, module_name: str) -> None:
    button, popover = open_advanced(page)
    table_top_before = page.locator(".el-table").first.bounding_box()["y"]
    box = popover.bounding_box()
    assert box and box["x"] >= -1 and box["x"] + box["width"] <= page.viewport_size["width"] + 1, f"{module_name} 高级筛选横向溢出"

    selects = popover.locator(".el-select")
    if selects.count():
        selects.first.click()
        option = page.locator(".el-select-dropdown:visible .el-select-dropdown__item:not(.is-disabled)").first
        option.wait_for(state="visible", timeout=5000)
        option.click()
        wait_list_idle(page)
        assert re.search(r"高级筛选.*1", button.inner_text()), f"{module_name} 高级条件计数未更新"

        button.click()
        button, popover = open_advanced(page)
        popover.get_by_role("button", name="清空高级条件", exact=True).click()
        wait_list_idle(page)
        assert "1" not in button.inner_text(), f"{module_name} 清空高级条件后计数未归零"
    else:
        text_input = popover.locator("input").first
        text_input.fill(NO_MATCH)
        wait_list_idle(page)
        assert re.search(r"高级筛选.*1", button.inner_text()), f"{module_name} 文本高级条件计数未更新"
        button.click()
        button, popover = open_advanced(page)
        popover.get_by_role("button", name="清空高级条件", exact=True).click()
        wait_list_idle(page)

    table_top_after = page.locator(".el-table").first.bounding_box()["y"]
    assert abs(table_top_before - table_top_after) < 2, f"{module_name} 打开高级筛选改变了主表位置"


def check_module(page: Page, base_url: str, module_name: str, route: str, placeholder: str, expected_header_filters: int) -> None:
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{base_url}{route}")
    keyword = page.get_by_placeholder(placeholder, exact=True)
    keyword.wait_for(state="visible", timeout=15000)
    wait_list_idle(page)
    baseline = row_count(page)
    assert baseline > 0, f"{module_name} 没有可用于只读搜索验收的记录"
    triggers = page.locator(".el-table__header-wrapper .column-header-filter__trigger")
    assert triggers.count() == expected_header_filters, f"{module_name} 默认列表头筛选按钮数量不正确：{triggers.count()}"
    target = first_searchable_text(page)

    # 400ms 自动查询及无匹配结果。
    keyword.fill(NO_MATCH)
    wait_list_idle(page)
    assert row_count(page) == 0, f"{module_name} 自动查询未得到空结果"

    # 清空后立即恢复，不依赖回车或查询按钮。
    keyword.press("Control+A")
    keyword.press("Backspace")
    wait_list_idle(page)
    assert row_count(page) == baseline, f"{module_name} 清空关键词未立即恢复列表"

    # 回车查询。
    keyword.fill(target)
    keyword.press("Enter")
    wait_list_idle(page)
    assert row_count(page) > 0, f"{module_name} 回车查询没有结果"

    # 查询按钮。
    query_button = page.get_by_role("button", name="查询", exact=True)
    assert query_button.count() == 1
    query_button.click()
    wait_list_idle(page)
    assert row_count(page) > 0, f"{module_name} 查询按钮没有结果"

    # 快速连续输入，最终结果必须属于最后一次查询。
    keyword.fill(target)
    page.wait_for_timeout(80)
    keyword.fill(NO_MATCH)
    wait_list_idle(page)
    assert row_count(page) == 0, f"{module_name} 旧响应覆盖了最后一次查询"
    keyword.fill("")
    wait_list_idle(page)

    check_advanced_filter(page, module_name)

    # 小屏只检查公共浮层边界与内部滚动容器。
    page.set_viewport_size({"width": 390, "height": 844})
    _, popover = open_advanced(page)
    box = popover.bounding_box()
    assert box and box["x"] >= -1 and box["x"] + box["width"] <= 391, f"{module_name} 小屏高级筛选横向溢出"
    body = popover.locator(".advanced-filter-body")
    assert body.count() == 1
    assert body.evaluate("node => getComputedStyle(node).overflowY") == "auto"
    grid = popover.locator(".compact-filter-grid")
    assert grid.count() == 1
    assert len(grid.evaluate("node => getComputedStyle(node).gridTemplateColumns.split(' ')")) == 1, f"{module_name} 390px 下未切换单列"
    popover.get_by_role("button", name="关闭", exact=True).click()
    print(f"[✓] {module_name}：关键词自动/回车/按钮/清空、旧响应保护和高级筛选通过")


def main() -> int:
    base_url = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
    auth = login(base_url, required("LOGIN_USERNAME"), required("LOGIN_PASSWORD"))
    output_dir = Path("test-results/common-list-search")
    output_dir.mkdir(parents=True, exist_ok=True)

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
        for module_name, route, placeholder, expected_header_filters in MODULES:
            check_module(page, base_url, module_name, route, placeholder, expected_header_filters)
            page.screenshot(path=str(output_dir / f"{route.strip('/').replace('/', '-')}.png"), full_page=True)
        browser.close()
    print(f"七个业务列表筛选验收通过，截图目录：{output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
