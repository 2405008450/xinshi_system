"""项目详情页(/translation-details)主表列宽与字段搜索验收脚本。

用你 .venv 之外的全局 Python(已装 playwright)直接运行：

    set BASE_URL=http://localhost:3000
    set LOGIN_USERNAME=admin
    set LOGIN_PASSWORD=xxxxxx
    "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" ^
        frontend/tests/e2e/translation_details_check.py

校验内容：
1. 经 /api/auth/login/json 登录，注入 localStorage，使路由守卫放行；
2. 启用主表全部列(含收缩后的进度列、优先级、服务内容等“相对固定”字段)；
3. 断言每个表头完整显示未被省略号截断(scrollWidth <= clientWidth)；
4. 打印每列实际宽度与留白占比，并对进度列断言 <140px；
5. 验证新增项目弹窗可以跨 Tab、跨折叠分组搜索定位字段；
6. 验证条件字段不会被搜索自动启用，并检查窄屏弹窗不溢出；
7. 全页截图归档到 test-results/translation-details.png。

依赖：playwright(Python)、浏览器内核(已装)。
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

from playwright.sync_api import sync_playwright

# 与 ProjectDetails.vue 中 projectDetailItems 的 key 一致，用于在 localStorage 启用全部列。
ALL_COLUMN_KEYS = [
    "id", "orderNo", "projectName", "serviceContent", "taskType", "consultationId",
    "clientId", "subClientId", "clientShortName", "clientCode", "customerOrderNo",
    "projectManagerName", "clientManager", "managerContact", "projectStatus",
    "fileTypeSecondary", "projectFileName", "projectFileTranslationDomainLevel1",
    "projectFileTypeLevel1", "projectFileFormat", "projectFileAttributeLevel1",
    "projectFileDifficulty", "projectContractType", "quotationRequired",
    "customerRequirementProfessional", "customerRequirementSpecial", "languagePair",
    "priority", "customerWordCount", "customerWordCountType", "internalWordCount",
    "internalWordCountType", "wordCount", "customerReceptionTime", "customerDeadlineTime",
    "sentToClientTime", "clientFeedback", "pmConfirmedBy", "majorProjectManagerConfirmation",
    "assignedTranslators", "translatorAssignmentTime", "expectedTranslatorStatsMethod",
    "expectedTranslatorWordCount", "translatorDeliveryProgress", "preReviewQcProgress",
    "review1Progress", "review2Progress", "postReviewQcProgress", "layoutProgress",
    "consolidationProgress", "networkFilePath", "referenceFilePathOne", "createdBy",
    "createdAt", "updatedAt",
]

PROGRESS_LABELS = ["译员交付进度", "审校前 QC", "审校 1", "审校 2", "审校后 QC", "排版进度", "整合进度"]


def login_via_api(base_url: str, username: str, password: str) -> dict:
    url = f"{base_url}/api/auth/login/json"
    data = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"登录失败 {exc.code}: {body}") from None


def check_field_search(page, can_write: bool) -> list[str]:
    """验证母项目新增弹窗的字段搜索，不提交任何业务数据。"""
    failures = []
    if not can_write:
        print("[跳过] 当前账号无 projects:write 权限，未执行字段搜索交互验收")
        return failures

    page.get_by_role("button", name="新增项目", exact=True).click()
    dialog = page.locator(".project-editor-dialog")
    dialog.wait_for(state="visible", timeout=10000)
    search_input = dialog.locator(".project-field-search input")

    def locate(query: str, option_text: str, field_key: str):
        search_input.fill(query)
        option = page.locator(".project-field-search-popper li").filter(
            has_text=option_text
        ).first
        option.wait_for(state="visible", timeout=5000)
        option.click()
        target = dialog.locator(f'[data-field-key="{field_key}"]')
        target.wait_for(state="visible", timeout=5000)
        page.wait_for_function(
            """(fieldKey) => document.querySelector(
                `.project-editor-dialog [data-field-key="${fieldKey}"]`
            )?.classList.contains('is-field-search-highlight')""",
            arg=field_key,
            timeout=5000,
        )
        return target

    network_path = locate("网络路径", "网络文件路径", "networkFilePath")
    active_tab = dialog.locator(".el-tabs__item.is-active").inner_text().strip()
    if active_tab != "分配与预估":
        failures.append(f"跨 Tab 定位失败，当前 Tab 为“{active_tab}”")
    if "is-field-search-highlight" not in (network_path.get_attribute("class") or ""):
        failures.append("网络文件路径定位后未高亮")

    dialog.get_by_role("tab", name="基础信息", exact=True).click()
    business_section = dialog.locator(".el-collapse-item").filter(
        has_text="项目商务信息"
    ).first
    if "is-active" in (business_section.get_attribute("class") or ""):
        business_section.locator(".el-collapse-item__header").click()

    special_requirement = locate(
        "特殊要求", "客户特殊要求", "customerRequirementSpecial"
    )
    if not special_requirement.is_visible():
        failures.append("折叠分组中的客户特殊要求未重新展开")
    if "is-active" not in (business_section.get_attribute("class") or ""):
        failures.append("字段定位后项目商务信息分组仍处于折叠状态")

    quotation_checkbox = dialog.locator(
        '[data-field-key="quotationRequired"] input[type="checkbox"]'
    )
    quotation_status = locate("报价状态", "报价单状态", "quotationRequired")
    if quotation_checkbox.is_checked():
        failures.append("搜索报价单状态时意外启用了报价单开关")
    if dialog.locator('[data-field-key="quotationStatus"]').count():
        failures.append("报价单开关关闭时条件字段被意外显示")
    if "is-field-search-highlight" not in (quotation_status.get_attribute("class") or ""):
        failures.append("条件字段未定位并高亮前置开关")

    page.set_viewport_size({"width": 480, "height": 800})
    page.wait_for_timeout(150)
    box = dialog.bounding_box()
    if not box or box["x"] < -1 or box["x"] + box["width"] > 481:
        failures.append("窄屏下项目编辑弹窗超出视口")
    if not search_input.is_visible():
        failures.append("窄屏下字段搜索框不可见")
    if not dialog.locator(".el-dialog__footer").is_visible():
        failures.append("窄屏下弹窗底部操作栏不可见")

    page.set_viewport_size({"width": 1600, "height": 900})
    dialog.locator(".el-dialog__headerbtn").click()
    dialog.wait_for(state="hidden", timeout=5000)

    edit_buttons = page.get_by_role("button", name="编辑", exact=True)
    edit_button_count = edit_buttons.count()
    if edit_button_count:
        edit_buttons.first.click()
        dialog.wait_for(state="visible", timeout=10000)
        if search_input.input_value():
            failures.append("从新增切换到编辑弹窗后仍残留搜索词")
        layout_progress = locate("排版进度", "排版进度", "layoutProgress")
        active_tab = dialog.locator(".el-tabs__item.is-active").inner_text().strip()
        if active_tab != "进度跟踪":
            failures.append(f"编辑弹窗进度字段定位失败，当前 Tab 为“{active_tab}”")
        if not layout_progress.is_visible():
            failures.append("编辑弹窗未显示定位后的排版进度字段")
        dialog.locator(".el-dialog__headerbtn").click()
        dialog.wait_for(state="hidden", timeout=5000)
    else:
        print("[跳过] 当前列表没有可用于验证编辑弹窗的项目")

    if failures:
        for failure in failures:
            print(f"[✗] 字段搜索：{failure}", file=sys.stderr)
    else:
        print("[✓] 字段搜索支持跨 Tab、展开分组、条件字段保护和窄屏布局")
    return failures


def main() -> int:
    base_url = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
    username = os.environ.get("LOGIN_USERNAME")
    password = os.environ.get("LOGIN_PASSWORD")
    if not username or not password:
        print("[!] 请通过环境变量设置 LOGIN_USERNAME / LOGIN_PASSWORD", file=sys.stderr)
        return 2

    auth = login_via_api(base_url, username, password)
    permissions = auth.get("permissions") or []
    if "projects:read" not in permissions and "*" not in permissions:
        print(f"[!] 该账号无 projects:read 权限，无法访问项目详情页", file=sys.stderr)
        return 3

    user_id = str(auth.get("user_id") or username)
    init_script = """
    ([{token}, {userId}, {userName}, {roles}, {permissions}, {allKeys}]) => {{
      localStorage.setItem('token', token);
      localStorage.setItem('user_id', userId);
      localStorage.setItem('user_name', userName);
      localStorage.setItem('user_full_name', userName);
      localStorage.setItem('user_roles', JSON.stringify(roles));
      localStorage.setItem('user_permissions', JSON.stringify(permissions));
      localStorage.setItem(`table-columns:translation-details-v2:${{userId}}`, JSON.stringify(allKeys));
    }}
    """.format(
        token=json.dumps(auth.get("access_token", "")),
        userId=json.dumps(user_id),
        userName=json.dumps(username),
        roles=json.dumps(auth.get("roles", [])),
        permissions=json.dumps(permissions),
        allKeys=json.dumps(ALL_COLUMN_KEYS),
    )

    out_dir = Path("frontend/test-results")
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 900})
        context.add_init_script(script=init_script)
        page = context.new_page()

        page.goto(f"{base_url}/translation-details", wait_until="domcontentloaded")
        page.wait_for_selector(".project-table .el-table__header", timeout=20000)
        page.wait_for_timeout(500)

        field_search_failures = check_field_search(
            page, "projects:write" in permissions or "*" in permissions
        )

        columns = page.eval_on_selector_all(
            ".project-table .el-table__header th .cell",
            """(cells) => cells.map((cell) => {
                const text = (cell.textContent || '').trim();
                const th = cell.closest('th');
                return {
                    text,
                    width: th ? Math.round(th.getBoundingClientRect().width) : 0,
                    contentWidth: Math.round(cell.scrollWidth),
                    cellWidth: Math.round(cell.clientWidth),
                    truncated: cell.scrollWidth > cell.clientWidth + 1
                };
            })""",
        )

        truncated = [c for c in columns if c["truncated"]]
        if truncated:
            names = "、".join(c["text"] for c in truncated)
            print(f"[✗] 以下表头被截断: {names}", file=sys.stderr)
        else:
            print(f"[✓] 全部 {len(columns)} 列表头完整显示，无截断")

        print(f"\n[列宽明细] 共 {len(columns)} 列")
        print(f"  {'表头':<22} {'列宽':>6} {'内容':>6} {'留白':>6}")
        for c in columns:
            slack = max(0, c["cellWidth"] - c["contentWidth"])
            slack_pct = round(slack / c["cellWidth"] * 100) if c["cellWidth"] else 0
            flag = "  ❌截断" if c["truncated"] else ""
            print(f"  {c['text']:<22} {c['width']:>5}px {c['contentWidth']:>5}px {slack_pct:>5}%{flag}")

        progress_cols = [c for c in columns if c["text"] in PROGRESS_LABELS]
        progress_wide = [c for c in progress_cols if c["width"] >= 140]
        if progress_wide:
            names = "、".join(c["text"] for c in progress_wide)
            print(f"[✗] 进度列未充分收缩(>=140): {names}", file=sys.stderr)
        elif progress_cols:
            print(f"[✓] 进度列已收缩: {', '.join(f'{c['text']}={c['width']}px' for c in progress_cols)}")

        screenshot = out_dir / "translation-details.png"
        page.screenshot(path=str(screenshot), full_page=True)
        print(f"\n[截图] {screenshot}")

        context.close()
        browser.close()

        return 1 if (truncated or progress_wide or field_search_failures) else 0


if __name__ == "__main__":
    sys.exit(main())
