"""侧边栏导航美化验收：截图展开/折叠两种状态，并实测激活项样式。

用法：
    set UI_TOKEN=<jwt>
    "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" tools/verify_sidebar_ui.py

可选环境变量：BASE_URL（默认 http://localhost:5173）、OUT_DIR（默认 test-results）
"""
import os
import sys

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5173")
TOKEN = os.environ.get("UI_TOKEN", "")
USER_ID = "ba92e52a-f517-48a4-a422-1688f2afe067"
OUT_DIR = os.environ.get("OUT_DIR", "test-results")


def inject(page):
    page.evaluate(
        """(args) => {
            localStorage.setItem('token', args.token);
            localStorage.setItem('user_id', args.userId);
            localStorage.setItem('user_name', 'admin');
            localStorage.setItem('user_full_name', 'admin');
            localStorage.setItem('user_roles', JSON.stringify(['超级管理员']));
            localStorage.setItem('user_permissions', JSON.stringify(['*']));
        }""",
        {"token": TOKEN, "userId": USER_ID},
    )


def main() -> int:
    if not TOKEN:
        print("缺少环境变量 UI_TOKEN", file=sys.stderr)
        return 1
    os.makedirs(OUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        context = browser.new_context(viewport={"width": 1600, "height": 900})
        page = context.new_page()
        page.on("pageerror", lambda e: print("[pageerror]", str(e)[:200]))

        page.goto(f"{BASE_URL}/login")
        inject(page)
        page.goto(f"{BASE_URL}/consultations")
        for attempt in range(3):
            try:
                page.wait_for_selector(".sidebar-menu .el-menu-item.is-active", timeout=15000)
                break
            except Exception:
                if "/login" in page.url or attempt == 2:
                    if attempt == 2:
                        raise
                    inject(page)
                    page.goto(f"{BASE_URL}/consultations")
        page.wait_for_timeout(600)

        # 展开项目管理子菜单，看树形引导线
        page.locator(".el-sub-menu__title", has_text="项目管理").click()
        page.wait_for_timeout(500)

        # 实测关键样式
        checks = page.evaluate(
            """() => {
                const active = document.querySelector('.sidebar-menu .el-menu-item.is-active');
                const logo = document.querySelector('.logo-mark');
                const version = document.querySelector('.sidebar-version');
                const groupLabel = document.querySelector('.menu-group-label');
                const subMenu = document.querySelector('.el-sub-menu.is-opened .el-menu');
                const subLine = subMenu ? getComputedStyle(subMenu, '::before') : null;
                const activeBar = active ? getComputedStyle(active, '::before') : null;
                return {
                    activeBg: active ? getComputedStyle(active).backgroundImage : null,
                    activeBarShadow: activeBar ? activeBar.boxShadow : null,
                    logoSrc: logo ? logo.getAttribute('src') : null,
                    versionText: version ? version.textContent.trim() : null,
                    groupLabelText: groupLabel ? groupLabel.textContent.trim() : null,
                    subLineWidth: subLine ? subLine.width : null,
                };
            }"""
        )
        for k, v in checks.items():
            print(f"[check] {k}: {v}")

        page.locator(".sidebar").screenshot(path=os.path.join(OUT_DIR, "sidebar-expanded.png"))

        # 折叠态
        page.locator(".collapse-btn").click()
        page.wait_for_timeout(500)
        page.locator(".sidebar").screenshot(path=os.path.join(OUT_DIR, "sidebar-collapsed.png"))

        browser.close()
    print("截图输出：", os.path.join(OUT_DIR, "sidebar-expanded.png"), "/", "sidebar-collapsed.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
