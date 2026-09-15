# -*- coding: utf-8 -*-
"""聊天小窗端到端联调：双账号 发送→提醒→点击开窗→回复 闭环 + 桌面通知点击。"""
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:12213"
API = "http://127.0.0.1:8000"
TOKEN_ADMIN = open("ui_token.tmp", encoding="utf-8").read().strip()
TOKEN_WANGLU = open("ui_token2.tmp", encoding="utf-8").read().strip()
TARGET_ORDER = "AP-260915-001"


def session(token):
    req = urllib.request.Request(f"{API}/auth/session", headers={"Authorization": f"Bearer {token}"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))


def inject(page, token, info):
    page.goto(f"{BASE}/login", wait_until="load")
    script = """([token, info]) => {
        localStorage.setItem('token', token);
        localStorage.setItem('user_id', info.user_id);
        localStorage.setItem('user_name', info.username);
        localStorage.setItem('user_full_name', info.full_name || info.username);
        localStorage.setItem('user_roles', JSON.stringify(info.roles || []));
        localStorage.setItem('user_permissions', JSON.stringify(info.permissions || []));
    }"""
    for _ in range(5):
        try:
            page.evaluate(script, [token, info])
            return
        except Exception:
            time.sleep(1.5)
    page.evaluate(script, [token, info])


def open_chat_from_list(page):
    page.goto(f"{BASE}/annotation-details", wait_until="domcontentloaded")
    row = page.locator(".el-table__row", has_text=TARGET_ORDER).first
    row.wait_for(timeout=20000)
    row.get_by_role("button", name="沟通").click()
    page.locator(".project-chat-window").first.wait_for(timeout=10000)


def send_with_mention(page, text, mention_name):
    win = page.locator(".project-chat-window").first
    win.locator(".chat-composer__at").click()
    select = page.locator(".el-popover:visible .el-select").first
    select.click()
    page.locator(".el-select-dropdown:visible .el-select-dropdown__item", has_text=mention_name).first.click()
    page.keyboard.press("Escape")
    textarea = win.locator("textarea").first
    textarea.fill(text)
    textarea.press("Enter")


def main():
    admin = session(TOKEN_ADMIN)
    wanglu = session(TOKEN_WANGLU)
    results = {}
    run_id = str(int(time.time()))[-6:]
    msg1 = f"E2E闭环{run_id}：请查收对齐结果 @admin"
    msg2 = f"E2E闭环{run_id}：桌面通知触发消息"
    reply = f"E2E闭环{run_id}：收到，我这边开始复核"

    # 清空历史未读，避免旧提醒卡片干扰
    req = urllib.request.Request(
        f"{API}/notifications/read-all",
        method="POST",
        headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False)
        ctx_a = browser.new_context(permissions=["notifications"])
        ctx_b = browser.new_context(permissions=["notifications"])
        page_a = ctx_a.new_page()
        page_b = ctx_b.new_page()
        errors_a = []
        page_a.on("pageerror", lambda e: errors_a.append(str(e)))

        # 桌面通知构造监听（admin 侧，页面加载后直接补丁；应用运行时读取 window.Notification）
        inject(page_a, TOKEN_ADMIN, admin)
        inject(page_b, TOKEN_WANGLU, wanglu)
        open_chat_from_list(page_a)
        open_chat_from_list(page_b)
        page_a.evaluate(
            """() => {
                window.__desktopNotifs = [];
                const Orig = window.Notification;
                const Wrapped = function(title, opts) {
                    const n = new Orig(title, opts);
                    window.__desktopNotifs.push({ title, body: opts && opts.body, instance: n });
                    return n;
                };
                Wrapped.permission = Orig.permission;
                Wrapped.requestPermission = () => Promise.resolve('granted');
                window.Notification = Wrapped;
            }"""
        )

        # 1. 王露 @admin 发消息
        send_with_mention(page_b, msg1, "admin")

        # 2. admin 收到右上角提醒卡片并点击
        card = page_a.locator(".el-notification.mention-notification")
        card.wait_for(state="visible", timeout=15000)
        cards_before = card.count()
        results["mention_card_shown"] = True
        results["mention_card_has_close"] = card.first.locator(".el-notification__closeBtn").count() == 1
        results["mention_card_hint"] = "点击打开沟通" in card.first.inner_text()
        url_before = page_a.url
        card.first.locator(".el-notification__content").click()
        time.sleep(2)
        results["url_unchanged_after_card_click"] = page_a.url == url_before
        results["card_closed_after_click"] = card.count() < cards_before or not card.first.is_visible()
        win_a = page_a.locator(".project-chat-window", has_text=TARGET_ORDER).first
        results["chat_window_visible"] = win_a.is_visible()

        # 3. admin 在小窗里回复
        textarea = win_a.locator("textarea").first
        textarea.fill(reply)
        textarea.press("Enter")
        own = win_a.locator(".chat-conversation-item--own .chat-bubble", has_text=reply)
        own.first.wait_for(timeout=10000)
        results["reply_sent_own_bubble"] = True

        # 4. 王露窗口实时收到回复（左侧气泡）
        got = page_b.locator(".project-chat-window .chat-bubble", has_text=reply)
        got.first.wait_for(timeout=15000)
        results["wanglu_received_reply"] = True
        print("STAGE1:", json.dumps(results, ensure_ascii=False))

        # 5. 桌面通知：先关掉所有残余提醒卡片，再由 admin 在铃铛面板启用
        for _ in range(5):
            closes = page_a.locator(".el-notification.mention-notification .el-notification__closeBtn")
            if not closes.count():
                break
            closes.first.click()
            time.sleep(0.6)
        page_a.locator(".notification-trigger").click()
        enable_btn = page_a.locator(".desktop-notification-card button", has_text="启用")
        if enable_btn.count():
            enable_btn.first.click()
            time.sleep(1.5)
            dialog = page_a.locator(".el-message-box")
            if dialog.count() and dialog.first.is_visible():
                dialog.get_by_role("button", name="知道了").click()
                time.sleep(0.8)
        page_a.keyboard.press("Escape")
        results["notif_hook_ready"] = page_a.evaluate("() => Array.isArray(window.__desktopNotifs)")
        results["desktop_state"] = page_a.evaluate(
            """() => ({
                permission: window.Notification && window.Notification.permission,
                secure: window.isSecureContext,
                pref: localStorage.getItem('desktop_notifications_enabled:' + (localStorage.getItem('user_id') || ''))
            })"""
        )
        # 王露再发一条 @admin
        print("STAGE2-DIAG:", json.dumps({"hook": results.get("notif_hook_ready"), "state": results.get("desktop_state")}, ensure_ascii=False))
        send_with_mention(page_b, msg2, "admin")
        try:
            page_a.wait_for_function(
                "() => Array.isArray(window.__desktopNotifs) && window.__desktopNotifs.length > 0",
                timeout=15000,
            )
            results["desktop_notification_created"] = True
        except Exception:
            results["desktop_notification_created"] = False
            print("STAGE2-FAIL-DIAG:", json.dumps({
                "hook": page_a.evaluate("() => Array.isArray(window.__desktopNotifs)"),
                "pref": page_a.evaluate("() => Object.keys(localStorage).filter(k => k.startsWith('desktop_notifications'))"),
                "mention_cards": page_a.locator(".el-notification.mention-notification").count(),
            }, ensure_ascii=False))
            raise
        notif_count_before = page_a.evaluate("() => window.__desktopNotifs.length")
        url_before2 = page_a.url
        # 模拟用户点击 Windows 通知
        page_a.evaluate(
            """() => {
                const list = window.__desktopNotifs;
                const last = list[list.length - 1];
                last.instance.onclick({ preventDefault() {} });
            }"""
        )
        time.sleep(2)
        results["desktop_click_url_unchanged"] = page_a.url == url_before2
        results["desktop_click_focuses_chat"] = page_a.locator(".project-chat-window", has_text=TARGET_ORDER).first.is_visible()
        results["desktop_notif_count"] = notif_count_before

        results["page_errors"] = errors_a
        browser.close()

    print(json.dumps(results, ensure_ascii=False, indent=2))
    failed = [k for k, v in results.items() if v is False]
    print("FAILED:" + ",".join(failed) if failed else "ALL PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SCRIPT ERROR: {type(exc).__name__}: {exc}")
