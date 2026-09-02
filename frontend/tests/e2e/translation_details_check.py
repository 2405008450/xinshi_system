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
7. 验证展开子订单后仅保留当前母订单，并检查子订单低饱和背景；
8. 验证粘贴/TXT 预览、重复跳过、事务批量创建与行内改名，并清理测试数据；
9. 全页截图归档到 test-results/translation-details.png。

依赖：playwright(Python)、浏览器内核(已装)。
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import sync_playwright

# 与 ProjectDetails.vue 中 projectDetailItems 的 key 一致，用于在 localStorage 启用全部列。
ALL_COLUMN_KEYS = [
    "id", "orderNo", "projectName", "serviceContent", "taskType", "consultationId",
    "clientId", "subClientId", "clientShortName", "clientCode", "customerOrderNo",
    "projectManagerName", "clientManager", "managerContact", "projectStatus",
    "fileTypeSecondary", "projectFileTranslationDomainLevel1", "projectFileTranslationDomainLevel2",
    "projectFileTypeLevel1", "projectFileTypeLevel2", "projectFileFormat",
    "projectFileAttributeLevel1", "projectFileAttributeLevel2", "projectFileAttributeLevel3",
    "projectFileDifficulty", "projectContractType", "projectContractStatus", "quotationRequired",
    "quotationStatus", "quotationPath",
    "customerRequirementProfessional", "customerRequirementSpecial", "languagePair",
    "priority", "customerWordCount", "customerWordCountType", "internalWordCount",
    "internalWordCountType", "wordCount", "customerReceptionTime", "customerDeadlineTime",
    "sentToClientTime", "clientFeedback", "pmConfirmedBy", "majorProjectManagerConfirmation",
    "assignedTranslators", "translatorCompletionRemarks", "translatorAssignmentTime", "expectedTranslatorStatsMethod",
    "expectedTranslatorWordCount", "translatorDeliveryProgress", "preReviewQcProgress",
    "review1Progress", "review2Progress", "postReviewQcProgress", "layoutProgress",
    "consolidationProgress", "createdBy",
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

    word_count = locate("字数", "字数与预估", "wordCountSummary")
    active_tab = dialog.locator(".el-tabs__item.is-active").inner_text().strip()
    if active_tab != "基础信息":
        failures.append(f"字数与预估定位失败，当前 Tab 为“{active_tab}”")
    if "is-field-search-highlight" not in (word_count.get_attribute("class") or ""):
        failures.append("字数与预估定位后未高亮")
    if dialog.get_by_role("tab", name="分配与预估", exact=True).count():
        failures.append("仍存在已废弃的“分配与预估”页签")

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


def check_suborder_focus_mode(page) -> list[str]:
    """验证子订单展开后的单母订单聚焦、恢复及低饱和配色。"""
    failures = []
    project_rows = page.locator(
        ".project-table > .el-table__inner-wrapper > .el-table__body-wrapper "
        "> .el-scrollbar > .el-scrollbar__wrap > .el-scrollbar__view "
        "> table.el-table__body > tbody > tr.el-table__row"
    )
    expand_buttons = page.get_by_role("button", name="展开子订单", exact=True)
    initial_row_count = project_rows.count()
    if initial_row_count < 2 or not expand_buttons.count():
        print("[跳过] 当前页缺少可展开子订单或不足两个母订单，未执行聚焦模式验收")
        return failures

    expand_buttons.first.click()
    panel = page.locator(".sub-order-panel")
    panel.wait_for(state="visible", timeout=5000)

    if project_rows.count() != 1:
        failures.append("展开子订单后仍显示其他母订单")
    if page.get_by_role("button", name="收起子订单", exact=True).count() != 1:
        failures.append("展开后未提供唯一的收起子订单按钮")

    suborder_rows = panel.locator(".sub-order-table .el-table__body-wrapper tr.el-table__row")
    if not suborder_rows.count():
        failures.append("展开后未显示子订单数据行")

    panel_background = panel.evaluate("element => getComputedStyle(element).backgroundColor")
    header_background = panel.locator(
        ".sub-order-table .el-table__header-wrapper th.el-table__cell"
    ).first.evaluate("element => getComputedStyle(element).backgroundColor")
    row_background = panel.locator(
        ".sub-order-table .el-table__body-wrapper td.el-table__cell"
    ).first.evaluate("element => getComputedStyle(element).backgroundColor")
    if panel_background != "rgb(248, 250, 252)":
        failures.append(f"子订单面板背景色不符合预期：{panel_background}")
    if header_background != "rgb(241, 245, 249)":
        failures.append(f"子订单表头背景色不符合预期：{header_background}")
    if row_background != "rgb(248, 250, 252)":
        failures.append(f"子订单数据行背景色不符合预期：{row_background}")

    page.get_by_role("button", name="收起子订单", exact=True).click()
    panel.wait_for(state="hidden", timeout=5000)
    if project_rows.count() != initial_row_count:
        failures.append("收起子订单后未恢复原母订单列表")

    if failures:
        for failure in failures:
            print(f"[✗] 子订单聚焦：{failure}", file=sys.stderr)
    else:
        print("[✓] 子订单展开后单母订单聚焦，收起恢复列表，低饱和配色正确")
    return failures


def check_suborder_bulk_and_inline(page, can_write: bool, base_url: str, token: str, out_dir: Path) -> list[str]:
    """验证 TXT/粘贴预览、事务批量创建及子项目名称行内改名。"""
    failures = []
    if not can_write:
        print("[跳过] 当前账号无 projects:write 权限，未执行批量导入与行内改名验收")
        return failures

    expand_buttons = page.get_by_role("button", name="展开子订单", exact=True)
    if not expand_buttons.count():
        print("[跳过] 当前页没有可展开的子订单，未执行批量导入与行内改名验收")
        return failures

    created_ids = []
    upload_files = [
        out_dir / "suborder-filenames-utf16le-e2e.txt",
        out_dir / "suborder-filenames-gbk-e2e.txt",
        out_dir / "suborder-filenames-utf8-e2e.txt",
    ]
    stamp = uuid4().hex[:10]
    first_name = f"E2E 合同正文 {stamp}.docx"
    second_name = f"E2E 附件 {stamp}.xlsx"
    renamed_value = None
    original_name = None

    try:
        expand_buttons.first.click()
        panel = page.locator(".sub-order-panel")
        panel.wait_for(state="visible", timeout=5000)
        panel.get_by_role("button", name="导入文件名", exact=True).click()
        dialog = page.locator(".suborder-batch-create-dialog")
        dialog.wait_for(state="visible", timeout=5000)

        textarea = dialog.locator("textarea")
        textarea.fill(f"{first_name}\n{first_name.upper()}\n{'超长' * 128}")
        if "将新增 1" not in dialog.locator(".import-summary").inner_text():
            failures.append("粘贴内容的有效数量统计错误")
        if "重复 1" not in dialog.locator(".import-summary").inner_text():
            failures.append("粘贴内容未按忽略英文大小写识别重复名称")
        if "错误 1" not in dialog.locator(".import-summary").inner_text():
            failures.append("粘贴内容未识别超过 255 字符的名称")

        file_content = f"{first_name}\r\n{second_name}\r\n{first_name.upper()}\r\n"
        upload_files[0].write_bytes(b"\xff\xfe" + file_content.encode("utf-16le"))
        upload_files[1].write_bytes(file_content.encode("gbk"))
        upload_files[2].write_bytes(b"\xef\xbb\xbf" + file_content.encode("utf-8"))
        for index, upload_file in enumerate(upload_files):
            dialog.locator('input[type="file"]').set_input_files(str(upload_file))
            page.wait_for_function(
                "([selector, value]) => document.querySelector(selector)?.value.includes(value)",
                arg=[".suborder-batch-create-dialog textarea", second_name],
                timeout=5000,
            )
            if index < len(upload_files) - 1:
                dialog.locator(".el-upload-list__item-delete").click(force=True)
        summary_text = dialog.locator(".import-summary").inner_text()
        if "将新增 2" not in summary_text or "重复 1" not in summary_text or "错误 0" not in summary_text:
            failures.append(f"TXT 导入预览统计错误：{summary_text}")

        with page.expect_response(
            lambda response: response.request.method == "POST" and "/api/sub-orders/bulk" in response.url,
            timeout=15000,
        ) as response_info:
            dialog.get_by_role("button", name="确认导入 2 条", exact=True).click()
        response = response_info.value
        result = response.json()
        if response.status != 201:
            failures.append(f"批量创建接口返回 {response.status}")
        if result.get("created_count") != 2 or result.get("skipped_count") != 1:
            failures.append(f"批量创建结果数量错误：{result}")
        created_ids = [item["id"] for item in result.get("created", [])]
        dialog.wait_for(state="hidden", timeout=5000)

        inline_triggers = panel.locator(".inline-sub-project-name__trigger")
        if not inline_triggers.count():
            failures.append("子项目名称未渲染为可点击行内编辑控件")
        else:
            inline_trigger = inline_triggers.first
            original_name = inline_trigger.inner_text().strip()
            inline_trigger.click()
            inline_editor = panel.locator(".inline-sub-project-name").filter(has=page.locator("input")).first
            editor_input = inline_editor.locator("input")
            editor_input.fill(f"{original_name}-失焦测试")
            panel.locator(".sub-order-panel__meta").click()
            if not editor_input.is_visible():
                failures.append("行内改名失焦后意外自动保存或退出")
            editor_input.press("Escape")

            renamed_value = f"{original_name}-E2E改名"
            inline_trigger.click()
            inline_editor = panel.locator(".inline-sub-project-name").filter(has=page.locator("input")).first
            inline_editor.locator("input").fill(renamed_value)
            with page.expect_response(
                lambda response: response.request.method == "PUT" and "/api/sub-orders/" in response.url,
                timeout=10000,
            ):
                inline_editor.get_by_role("button", name="保存子项目名称", exact=True).click()
            panel.locator(".inline-sub-project-name__trigger").filter(has_text=renamed_value).wait_for(state="visible", timeout=5000)

            restore_trigger = panel.locator(".inline-sub-project-name__trigger").filter(has_text=renamed_value)
            restore_trigger.click()
            restore_editor = panel.locator(".inline-sub-project-name").filter(has=page.locator("input")).first
            restore_editor.locator("input").fill(original_name)
            restore_editor.get_by_role("button", name="保存子项目名称", exact=True).click()
            panel.locator(".inline-sub-project-name__trigger").filter(has_text=original_name).wait_for(state="visible", timeout=5000)
    except Exception as exc:
        failures.append(f"批量导入或行内改名交互异常：{exc}")
    finally:
        headers = {"Authorization": f"Bearer {token}"}
        if renamed_value and original_name:
            try:
                restore_lookup = page.request.get(
                    f"{base_url}/api/sub-orders/",
                    params={"project_name": renamed_value, "limit": 500},
                    headers=headers,
                )
                for item in restore_lookup.json() if restore_lookup.ok else []:
                    if item.get("sub_project_name") == renamed_value:
                        restored = page.request.put(
                            f"{base_url}/api/sub-orders/{item['id']}",
                            data={"sub_project_name": original_name},
                            headers=headers,
                        )
                        if not restored.ok:
                            failures.append(f"恢复原子项目名称失败：接口返回 {restored.status}")
            except Exception as exc:
                failures.append(f"恢复原子项目名称失败：{exc}")
        try:
            lookup = page.request.get(
                f"{base_url}/api/sub-orders/",
                params={"project_name": stamp, "limit": 500},
                headers=headers,
            )
            if lookup.ok:
                discovered_ids = [
                    item["id"] for item in lookup.json()
                    if item.get("sub_project_name") in {first_name, second_name}
                ]
                created_ids = list(dict.fromkeys([*created_ids, *discovered_ids]))
        except Exception as exc:
            failures.append(f"查询待清理测试数据失败：{exc}")
        for sub_order_id in created_ids:
            cleanup = page.request.delete(f"{base_url}/api/sub-orders/{sub_order_id}", headers=headers)
            if cleanup.status not in (204, 404):
                failures.append(f"测试数据清理失败：{sub_order_id} 返回 {cleanup.status}")
        for upload_file in upload_files:
            upload_file.unlink(missing_ok=True)
        page.goto(f"{base_url}/translation-details", wait_until="domcontentloaded")
        page.wait_for_selector(".project-table .el-table__header", timeout=20000)

    if failures:
        for failure in failures:
            print(f"[✗] 子订单批量导入/改名：{failure}", file=sys.stderr)
    else:
        print("[✓] TXT/粘贴预览、批量创建、重复跳过及行内改名交互正确")
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
        suborder_focus_failures = check_suborder_focus_mode(page)
        suborder_bulk_failures = check_suborder_bulk_and_inline(
            page,
            "projects:write" in permissions or "*" in permissions,
            base_url,
            auth.get("access_token", ""),
            out_dir,
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

        return 1 if (
            truncated or progress_wide or field_search_failures or suborder_focus_failures
            or suborder_bulk_failures
        ) else 0


if __name__ == "__main__":
    sys.exit(main())
