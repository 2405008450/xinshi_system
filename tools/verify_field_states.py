"""表单字段「可编辑/只读」配色验收脚本。

后端跑在局域网另一台机器上（frontend/.env 的 VITE_API_PROXY_TARGET），
本机无法自签 token 过校验，因此不走业务弹窗，而是在已加载全部应用样式的
页面里注入真实的 Element Plus DOM 结构，实测层叠后的计算样式。

验证对象正是本次改动的三处：theme.css 的变量、common.css 的
.field-readonly/.field-locked、App.vue 的 hover/focus 规则。

用法：
    "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" tools/verify_field_states.py

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
HEADED = os.environ.get("HEADED", "0") != "0"
OUT_DIR = os.environ.get("OUT_DIR", "test-results")

# 真实 Element Plus 2.x 输入框 DOM 结构
HARNESS = """() => {
    const box = document.createElement('div');
    box.id = 'field-state-harness';
    box.style.cssText = 'position:fixed;top:0;left:0;z-index:99999;width:520px;padding:24px;background:#fff;display:flex;flex-direction:column;gap:16px';

    const mk = (id, outerClass, extraInputClass, attrs, value, icon) => `
      <div>
        <label style="display:block;color:#475569;font-size:13px;font-weight:500;margin-bottom:6px">${id}</label>
        <div class="el-input ${outerClass}" id="wrap-${id}">
          <div class="el-input__wrapper" id="wrapper-${id}">
            <input class="el-input__inner ${extraInputClass}" id="inner-${id}" ${attrs} value="${value}" placeholder="保存后自动生成">
            ${icon ? `<span class="el-input__suffix"><span class="el-input__suffix-inner"><i class="el-icon" id="icon-${id}">${icon}</i></span></span>` : ''}
          </div>
        </div>
      </div>`;

    // el-icon 内是继承 currentColor 的单色 SVG，用等价占位图形保证截图能反映真实颜色
    const svg = (d) => `<svg viewBox="0 0 1024 1024" width="1em" height="1em" fill="currentColor"><path d="${d}"/></svg>`;
    const WAND = 'M512 64l96 224 224 96-224 96-96 224-96-224L192 384l224-96z';
    const LOCK = 'M768 448h-64V320a192 192 0 10-384 0v128h-64a64 64 0 00-64 64v384a64 64 0 0064 64h512a64 64 0 0064-64V512a64 64 0 00-64-64zM384 320a128 128 0 11256 0v128H384z';

    box.innerHTML =
      mk('editable', '', '', '', '客户简称示例', '') +
      mk('readonly', '', '', 'readonly', 'KH20260827-003', svg(WAND)) +
      mk('locked', 'is-disabled', '', 'disabled', '', svg(LOCK));

    // 只读与锁定态需要外层语义 class（业务代码里由 ReadonlyField 组件加）
    document.body.appendChild(box);
    document.getElementById('wrap-readonly').classList.add('field-readonly');
    document.getElementById('wrap-locked').classList.add('field-locked');
    return true;
}"""


def rel_luminance(rgb):
    def chan(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (chan(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg, bg):
    l1, l2 = rel_luminance(fg), rel_luminance(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def parse_rgb(value):
    nums = value.replace("rgba(", "").replace("rgb(", "").rstrip(")").split(",")[:3]
    return tuple(int(float(n)) for n in nums)


def to_hex(rgb):
    return "#" + "".join(f"{c:02X}" for c in rgb)


def probe(page, key):
    return page.evaluate(
        """(key) => {
            const wrapper = document.getElementById('wrapper-' + key);
            const inner = document.getElementById('inner-' + key);
            const ws = getComputedStyle(wrapper), is = getComputedStyle(inner);
            return {
                bg: ws.backgroundColor,
                boxShadow: ws.boxShadow,
                fg: is.webkitTextFillColor || is.color,
                cursor: is.cursor,
                readonly: inner.readOnly,
                disabled: inner.disabled,
                icon: !!document.getElementById('icon-' + key),
            };
        }""",
        key,
    )


def check(name, data, expect_bg, expect_fg, expect_cursor, min_ratio):
    bg, fg = parse_rgb(data["bg"]), parse_rgb(data["fg"])
    ratio = contrast(fg, bg)
    bg_hex, fg_hex = to_hex(bg), to_hex(fg)

    problems = []
    if bg_hex.upper() != expect_bg.upper():
        problems.append(f"底色期望 {expect_bg} 实为 {bg_hex}")
    if fg_hex.upper() != expect_fg.upper():
        problems.append(f"文字期望 {expect_fg} 实为 {fg_hex}")
    if data["cursor"] != expect_cursor:
        problems.append(f"光标期望 {expect_cursor} 实为 {data['cursor']}")
    if min_ratio and ratio < min_ratio:
        problems.append(f"对比度 {ratio:.2f}:1 低于要求 {min_ratio}:1")

    flag = "OK  " if not problems else "FAIL"
    print(f"  [{flag}] {name}")
    print(f"         底色 {bg_hex}  文字 {fg_hex}  对比度 {ratio:5.2f}:1  "
          f"光标 {data['cursor']}  readonly={data['readonly']} disabled={data['disabled']} 图标={data['icon']}")
    for p in problems:
        print(f"         ↳ {p}")
    return not problems


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    passed = True

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not HEADED, channel="msedge")
        page = browser.new_context(viewport={"width": 1000, "height": 700}).new_page()
        page.on("pageerror", lambda e: print("[pageerror]", str(e)[:200]))

        # 登录页已加载 element-plus/index.css + theme.css + common.css + App.vue 全局样式
        page.goto(f"{BASE_URL}/login")
        page.wait_for_selector(".el-input__wrapper", timeout=20000)
        page.wait_for_timeout(400)

        # 确认变量已生效，否则后面的断言没有意义
        var_readonly = page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--field-bg-readonly').trim()"
        )
        var_input_text = page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--el-input-text-color').trim()"
        )
        print(f"\ntheme.css 变量：--field-bg-readonly={var_readonly!r}  --el-input-text-color={var_input_text!r}")
        if not var_readonly:
            print("  [FAIL] --field-bg-readonly 未定义，theme.css 改动未生效")
            return 2

        page.evaluate(HARNESS)
        page.wait_for_timeout(300)

        print("\n三态实测（页面真实层叠结果）：")
        passed &= check("可编辑        白底深字", probe(page, "editable"), "#FFFFFF", "#111827", "text", 4.5)
        passed &= check("只读·系统生成  灰底可读字", probe(page, "readonly"), "#F1F5F9", "#475569", "default", 4.5)
        passed &= check("只读·条件锁定  灰底淡字", probe(page, "locked"), "#F1F5F9", "#94A3B8", "not-allowed", 0)

        # 禁用输入框 hover 不应给出可编辑的边框反馈
        before = probe(page, "locked")["boxShadow"]
        page.locator("#wrapper-locked").hover()
        page.wait_for_timeout(200)
        after = probe(page, "locked")["boxShadow"]
        hover_ok = before == after
        print(f"\n  [{'OK  ' if hover_ok else 'FAIL'}] 禁用输入框 hover 不改变边框（App.vue :not(.is-disabled) 修正）")
        if not hover_ok:
            print(f"         ↳ hover 前 {before}\n         ↳ hover 后 {after}")
        passed &= hover_ok

        page.locator("#field-state-harness").screenshot(path=f"{OUT_DIR}/field-states.png")
        print(f"\n截图：{OUT_DIR}/field-states.png")
        browser.close()

    print("\n结论：" + ("全部通过" if passed else "存在未通过项，见上方 FAIL"))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
