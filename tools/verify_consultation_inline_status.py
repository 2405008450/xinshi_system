"""新咨询管理(/consultations)列表内联切换「咨询状态」验收脚本。

验证列表状态标签可点击、下拉包含全部状态选项，且当前状态带勾选标记。
默认不做任何数据修改；设置 TOGGLE=1 时会对第一行做一次
「跟进中/重点跟进/未成交」之间的安全往返切换（不会触碰有副作用的「已确认」）。

用法（在项目根目录，使用全局 Python313 的 playwright）：
    set LOGIN_USERNAME=xxx
    set LOGIN_PASSWORD=xxx
    "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" tools/verify_consultation_inline_status.py

可选环境变量：
    BASE_URL=http://localhost:3000
    HEADED=1      （非 0 时以有头模式启动，便于肉眼跟随）
    TOGGLE=1      （非 0 时执行一次真实的状态往返切换）
"""
import os
import sys

from playwright.sync_api import sync_playwright

# Windows 控制台默认 GBK，强制 UTF-8 避免中文报表乱码。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

STATUS_OPTIONS = ["跟进中", "重点跟进", "未成交", "已确认"]
# 「已确认」会触发项目生成等副作用，往返切换只在安全状态之间进行。
SAFE_STATUSES = ["跟进中", "重点跟进", "未成交"]


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
    do_toggle = os.environ.get("TOGGLE", "0") != "0"
    channel = os.environ.get("BROWSER_CHANNEL", "msedge")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not headed, slow_mo=120 if headed else 0, channel=channel
        )
        context = browser.new_context(viewport={"width": 1600, "height": 900})
        page = context.new_page()

        # 1) 登录
        page.goto(f"{base_url}/login")
        page.fill("input[placeholder='请输入用户名']", username)
        page.fill("input[placeholder='请输入密码']", password)
        page.get_by_role("button", name="登录").click()
        page.wait_for_url(lambda url: not url.endswith("/login"), timeout=15000)

        # 2) 进入新咨询管理页，等待表格渲染
        page.goto(f"{base_url}/consultations")
        page.wait_for_selector(".consultations-card .el-table__row", timeout=15000)

        failed = False

        # 3) 状态标签应为可点击的下拉触发器
        tag_count = page.locator(".status-switch-tag").count()
        print(f"[检查1] 状态标签(可点击)数量: {tag_count}")
        if tag_count == 0:
            print("❌ 未找到可点击的状态标签")
            failed = True
        else:
            # 4) 点击第一个状态标签，验证下拉选项
            original_text = page.locator(".status-switch-tag").first.inner_text().strip()
            page.locator(".status-switch-tag").first.click()
            page.wait_for_selector(".el-dropdown-menu", timeout=5000)
            option_texts = page.eval_on_selector_all(
                ".el-dropdown-menu .status-option-row .status-option-tag",
                "(els) => els.map((el) => el.textContent.trim())",
            )
            print(f"[检查2] 下拉选项: {option_texts}（当前状态: {original_text}）")
            missing = [s for s in STATUS_OPTIONS if s not in option_texts]
            if missing:
                print(f"❌ 下拉缺少状态选项: {missing}")
                failed = True
            check_count = page.locator(
                ".el-dropdown-menu .status-option-row .status-current-icon"
            ).count()
            print(f"[检查3] 当前状态勾选标记数量: {check_count}（应为 1）")
            if check_count != 1:
                failed = True

            # 5) 可选：安全状态之间做一次往返切换
            if do_toggle and not failed:
                target = next(
                    (s for s in SAFE_STATUSES if s != original_text), None
                )
                if not target:
                    print("[检查4] 跳过往返切换：没有可用的安全目标状态")
                else:
                    print(f"[检查4] 往返切换: {original_text} -> {target} -> {original_text}")
                    page.get_by_text(target, exact=True).click()
                    page.wait_for_timeout(800)
                    new_text = page.locator(".status-switch-tag").first.inner_text().strip()
                    if target not in new_text:
                        print(f"❌ 切换后状态未更新: {new_text}")
                        failed = True
                    else:
                        # 切回原状态
                        page.locator(".status-switch-tag").first.click()
                        page.wait_for_selector(".el-dropdown-menu", timeout=5000)
                        page.get_by_text(original_text, exact=True).click()
                        page.wait_for_timeout(800)
                        restored = page.locator(".status-switch-tag").first.inner_text().strip()
                        if original_text not in restored:
                            print(f"❌ 状态未切回: {restored}")
                            failed = True
                        else:
                            print("✅ 往返切换成功，数据已还原")
            elif not do_toggle:
                # 关闭下拉（按 ESC）
                page.keyboard.press("Escape")
                print("[检查4] 未设置 TOGGLE=1，跳过真实切换（只读验收）")

        # 6) 截图存档
        os.makedirs("test-results", exist_ok=True)
        page.screenshot(path="test-results/consultations-inline-status.png", full_page=True)
        context.close()
        browser.close()

        if failed:
            print("\n验收未通过，请查看上方明细与 test-results/consultations-inline-status.png")
            return 1
        print("\n✅ 验收通过：列表状态可直接点击切换，下拉选项完整。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
