"""招聘项目(/recruitment-details) UI 验收脚本：编辑弹窗留白 + 订单号详情弹层。

用法：
    set UI_TOKEN=<jwt>
    "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" tools/verify_recruitment_ui.py

可选环境变量：BASE_URL（默认 http://localhost:3000）、HEADED=1、OUT_DIR（默认 test-results）
"""
import os
import sys

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000")
TOKEN = os.environ.get("UI_TOKEN", "")
USER_ID = "ba92e52a-f517-48a4-a422-1688f2afe067"
HEADED = os.environ.get("HEADED", "0") != "0"
OUT_DIR = os.environ.get("OUT_DIR", "test-results")


def main() -> int:
    if not TOKEN:
        print("缺少环境变量 UI_TOKEN", file=sys.stderr)
        return 1
    os.makedirs(OUT_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not HEADED, channel="msedge")
        context = browser.new_context(viewport={"width": 1600, "height": 900})
        page = context.new_page()
        page.on("console", lambda m: print("[console]", m.type, m.text[:160]) if m.type in ("error", "warning") else None)
        page.on("response", lambda r: print("[resp]", r.status, r.url[:100]) if "/api/" in r.url and r.status >= 400 else None)
        page.on("pageerror", lambda e: print("[pageerror]", str(e)[:200]))

        page.goto(f"{BASE_URL}/login")
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

        page.goto(f"{BASE_URL}/recruitment-details")
        for attempt in range(3):
            try:
                page.wait_for_selector(".recruitment-list-table .el-table__row", timeout=15000)
                break
            except Exception:
                if "/login" in page.url or attempt == 2:
                    if attempt == 2:
                        raise
                    print(f"第 {attempt + 1} 次进入被重定向({page.url})，重试…")
                    page.evaluate(
                        """(args) => {
                            localStorage.setItem('token', args.token);
                            localStorage.setItem('user_id', args.userId);
                            localStorage.setItem('user_roles', JSON.stringify(['超级管理员']));
                            localStorage.setItem('user_permissions', JSON.stringify(['*']));
                        }""",
                        {"token": TOKEN, "userId": USER_ID},
                    )
                    page.goto(f"{BASE_URL}/recruitment-details")
        page.wait_for_timeout(500)

        # ---------- 1. 订单号详情弹层 ----------
        page.locator(".order-cell .business-clickable-cell").first.click()
        page.wait_for_selector(".business-detail-popover", timeout=10000)
        page.wait_for_timeout(400)
        popover = page.locator(".business-detail-popover").first
        metrics = page.evaluate(
            """() => {
                const popper = document.querySelector('.business-detail-popover');
                const labels = [...popper.querySelectorAll('.el-descriptions__label')].map((el) => ({
                    text: (el.textContent || '').trim(),
                    width: Math.round(el.getBoundingClientRect().width),
                    height: Math.round(el.getBoundingClientRect().height),
                    wrapped: el.getBoundingClientRect().height > 30,
                }));
                const r = popper.getBoundingClientRect();
                return { popperWidth: Math.round(r.width), labels };
            }"""
        )
        print("[详情弹层] popper 宽度:", metrics["popperWidth"])
        for lab in metrics["labels"]:
            flag = "  ⚠换行" if lab["wrapped"] else ""
            print(f"  标签 {lab['text']:<14} 宽={lab['width']:>3}px 高={lab['height']:>3}px{flag}")
        popover.screenshot(path=f"{OUT_DIR}/recruit_detail_popover.png")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ---------- 2. 编辑弹窗 ----------
        page.locator(".recruitment-list-table button[aria-label='编辑']").first.click()
        page.wait_for_selector(".recruitment-editor", timeout=10000)
        page.wait_for_timeout(500)

        m = page.evaluate(
            """() => {
                const dialog = document.querySelector('.recruitment-editor');
                const header = dialog.querySelector('.el-dialog__header');
                const body = dialog.querySelector('.el-dialog__body');
                const editorBody = dialog.querySelector('.editor-body');
                const footer = dialog.querySelector('.el-dialog__footer');
                const section = dialog.querySelector('.form-section');
                const h3 = section ? section.querySelector('h3') : null;
                const label = dialog.querySelector('.el-form-item__label');
                const d = dialog.getBoundingClientRect();
                const rel = (el) => { const r = el.getBoundingClientRect(); return { left: Math.round(r.left - d.left), right: Math.round(d.right - r.right), width: Math.round(r.width) }; };
                const s = section ? section.getBoundingClientRect() : null;
                const cs = (el) => el ? getComputedStyle(el) : null;
                return {
                    dialog: { left: Math.round(d.left), width: Math.round(d.width) },
                    chain: { header: rel(header), body: rel(body), editorBody: rel(editorBody), form: rel(dialog.querySelector('.el-form')), section: rel(section), footer: rel(footer) },
                    headerPad: cs(header) ? [cs(header).paddingLeft, cs(header).paddingRight] : null,
                    bodyPad: cs(body) ? [cs(body).paddingLeft, cs(body).paddingRight] : null,
                    editorBodyPad: cs(editorBody) ? [cs(editorBody).paddingLeft, cs(editorBody).paddingRight, cs(editorBody).paddingTop, cs(editorBody).paddingBottom] : null,
                    footerPad: cs(footer) ? [cs(footer).paddingLeft, cs(footer).paddingRight] : null,
                    sectionRect: s ? { left: Math.round(s.left - d.left), right: Math.round(d.right - s.right) } : null,
                    sectionPad: cs(section) ? [cs(section).paddingLeft, cs(section).paddingRight] : null,
                    h3Pad: cs(h3) ? [cs(h3).paddingLeft, cs(h3).paddingRight] : null,
                    labelWidth: label ? Math.round(label.getBoundingClientRect().width) : null,
                };
            }"""
        )
        print("[编辑弹窗] 度量:")
        print("  dialog:", m["dialog"])
        print("  chain(距dialog左/右):", m["chain"])
        print("  header padding L/R:", m["headerPad"])
        print("  body padding L/R:", m["bodyPad"])
        print("  editor-body padding L/R/T/B:", m["editorBodyPad"])
        print("  footer padding L/R:", m["footerPad"])
        print("  section 距 dialog 左/右:", m["sectionRect"], "section padding L/R:", m["sectionPad"])
        print("  h3 padding L/R:", m["h3Pad"], " label 宽:", m["labelWidth"])

        dialog = page.locator(".recruitment-editor")
        dialog.screenshot(path=f"{OUT_DIR}/recruit_editor_top.png")
        page.evaluate("() => { const el = document.querySelector('.recruitment-editor .editor-body'); el.scrollTop = el.scrollHeight; }")
        page.wait_for_timeout(300)
        dialog.screenshot(path=f"{OUT_DIR}/recruit_editor_bottom.png")

        context.close()
        browser.close()
    print("截图已保存到", OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
