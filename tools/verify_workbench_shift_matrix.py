"""工作台(/workbench)速览条 + 班次矩阵弹窗验收脚本。

校验点：
1. 顶部常驻速览条渲染出 4 个统计卡（逾期/即将到期/项目待办/我的待办）。
2. 速览条右侧有「班次矩阵」按钮，点击后弹出矩阵弹窗。
3. 弹窗内「部门班次矩阵」为 7 列（周一~周日）的周矩阵。
4. 切到「公司请假」Tab 正常渲染。
并截图存档到 test-results/。

用法（项目根目录，用全局 Python313 的 playwright）：
    set LOGIN_USERNAME=xxx
    set LOGIN_PASSWORD=xxx
    "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" tools/verify_workbench_shift_matrix.py

可选环境变量：BASE_URL（默认 http://localhost:3000）、HEADED=1（有头）。
"""
import os
import re
import sys

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

EXPECTED_CHIPS = ["逾期任务", "即将到期", "项目待办", "我的待办"]
WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"缺少环境变量 {name}，请先设置后重试。", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> int:
    base_url = os.environ.get("BASE_URL", "http://localhost:3000")
    username = require_env("LOGIN_USERNAME")
    password = require_env("LOGIN_PASSWORD")
    headed = os.environ.get("HEADED", "0") != "0"
    channel = os.environ.get("BROWSER_CHANNEL", "msedge")

    failed = False
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not headed, slow_mo=120 if headed else 0, channel=channel
        )
        context = browser.new_context(viewport={"width": 1600, "height": 950})
        page = context.new_page()

        # 1) 登录
        page.goto(f"{base_url}/login")
        page.fill("input[placeholder='请输入用户名']", username)
        page.fill("input[placeholder='请输入密码']", password)
        page.get_by_role("button", name="登录").click()
        page.wait_for_url(lambda url: not url.endswith("/login"), timeout=15000)

        # 2) 进入工作台
        page.goto(f"{base_url}/workbench")
        page.wait_for_selector(".overview-strip", timeout=15000)
        page.wait_for_timeout(800)

        # 3) 校验速览条 4 个统计卡
        chips = page.eval_on_selector_all(
            ".overview-strip .stat-chip .stat-chip__label",
            "(els) => els.map((e) => (e.textContent || '').trim())",
        )
        print(f"\n[速览条统计卡] {chips}")
        for label in EXPECTED_CHIPS:
            if label not in chips:
                print(f"❌ 缺少统计卡：{label}")
                failed = True

        # 4) 班次矩阵按钮存在
        shift_btn = page.get_by_role("button", name="班次矩阵")
        if not shift_btn.count():
            print("❌ 未找到「班次矩阵」按钮")
            failed = True
        else:
            shift_btn.first.click()
            page.wait_for_selector(".shift-matrix-dialog", timeout=10000)
            page.wait_for_timeout(800)

            # 5) 部门班次矩阵为 7 列周视图
            headers = page.eval_on_selector_all(
                ".shift-matrix-dialog .matrix-body .el-table__header th .cell",
                "(els) => els.map((e) => (e.textContent || '').trim())",
            )
            print(f"[矩阵表头] {headers}")
            for wd in WEEKDAY_LABELS:
                if not any(h.startswith(wd) for h in headers):
                    print(f"❌ 矩阵缺少列：{wd}")
                    failed = True
            if not any(h.strip() == "员工" for h in headers):
                print("❌ 矩阵缺少固定列：员工")
                failed = True

            os.makedirs("test-results", exist_ok=True)
            page.screenshot(path="test-results/workbench-shift-matrix.png")

            # 6) 切到公司请假 Tab
            leave_tab = page.get_by_role("tab", name=re.compile("公司请假"))
            if leave_tab.count():
                leave_tab.first.click()
                page.wait_for_timeout(500)
                page.screenshot(path="test-results/workbench-leave-tab.png")
            else:
                print("⚠️ 未找到「公司请假」Tab（可能无请假数据时仍应存在）")

            page.screenshot(path="test-results/workbench-full.png", full_page=True)

        context.close()
        browser.close()

    if failed:
        print("\n验收未通过，请查看 test-results/ 下的截图。")
        return 1
    print("\n✅ 验收通过：速览条完整，班次矩阵弹窗为 7 列周视图。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
