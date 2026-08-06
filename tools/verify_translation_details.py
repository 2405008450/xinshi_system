"""项目详情页(/translation-details)主表列宽验收脚本。

用已安装的 Python Playwright 驱动浏览器，登录后启用全部列，
校验收缩后的“相对固定”字段表头不被截断，并打印每列实际宽度与留白、截图存档。

用法（在项目根目录，使用全局 Python313 的 playwright）：
    set LOGIN_USERNAME=xxx
    set LOGIN_PASSWORD=xxx
    "C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" tools/verify_translation_details.py

可选环境变量：
    BASE_URL=http://localhost:3000  （默认即此前值）
    HEADED=1                         （非 0 时以有头模式启动，便于肉眼跟随）
"""
import os
import sys

from playwright.sync_api import sync_playwright, expect

# Windows 控制台默认 GBK，强制 UTF-8 避免中文报表乱码。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

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
    "assignedTranslators", "translatorAssignmentTime", "expectedTranslatorStatsMethod",
    "expectedTranslatorWordCount", "translatorDeliveryProgress", "preReviewQcProgress",
    "review1Progress", "review2Progress", "postReviewQcProgress", "layoutProgress",
    "consolidationProgress", "createdBy",
    "createdAt", "updatedAt",
]

PROGRESS_LABELS = ["译员交付进度", "审校前 QC", "审校 1", "审校 2", "审校后 QC", "排版进度", "整合进度"]


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
    # 用系统已装的 Edge/Chrome 通道，免去 playwright 下载专用浏览器内核。
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
        # 登录成功后会跳转到工作台等内页；等待主框架出现
        page.wait_for_url(lambda url: not url.endswith("/login"), timeout=15000)
        page.wait_for_selector(".el-menu, .el-card", timeout=15000)

        # 2) 在 localStorage 启用全部列（与 useTableColumns 的存储键一致），再进入页面
        page.evaluate(
            """(keys) => {
                const userId = localStorage.getItem('user_id') || localStorage.getItem('user_name') || 'anonymous';
                localStorage.setItem(`table-columns:translation-details-v2:${userId}`, JSON.stringify(keys));
            }""",
            ALL_COLUMN_KEYS,
        )
        page.goto(f"{base_url}/translation-details")
        page.wait_for_selector(".project-table .el-table__header", timeout=15000)
        page.wait_for_timeout(600)  # 让表头布局稳定

        # 3) 采集每列表头：文本、列宽、是否被截断
        columns = page.eval_on_selector_all(
            ".project-table .el-table__header th .cell",
            """(cells) => cells.map((cell) => {
                const text = (cell.textContent || '').trim();
                const truncated = cell.scrollWidth > cell.clientWidth + 1;
                const th = cell.closest('th');
                return {
                    text,
                    width: th ? Math.round(th.getBoundingClientRect().width) : 0,
                    contentWidth: Math.round(cell.scrollWidth),
                    cellWidth: Math.round(cell.clientWidth),
                    truncated,
                };
            })""",
        )

        # 4) 断言：所有表头完整显示
        truncated = [c for c in columns if c["truncated"]]
        print(f"\n[列宽明细] 共 {len(columns)} 列")
        for c in columns:
            slack = max(0, c["cellWidth"] - c["contentWidth"])
            slack_pct = round(slack / c["cellWidth"] * 100) if c["cellWidth"] else 0
            flag = "  ❌截断" if c["truncated"] else ""
            print(f"  {c['text']:<22} 列宽={c['width']:>4}px  内容={c['contentWidth']:>4}px  留白={slack_pct:>3}%{flag}")

        # 5) 进度类等“相对固定”列应已收缩（<140）
        label_map = {c["text"]: c for c in columns}
        failed = False
        if truncated:
            print(f"\n❌ 以下表头被截断: {', '.join(c['text'] for c in truncated)}")
            failed = True
        for label in PROGRESS_LABELS:
            col = label_map.get(label)
            if not col:
                continue
            if col["width"] >= 140:
                print(f"❌ {label} 未收缩：{col['width']}px（应 <140）")
                failed = True

        # 6) 截图存档
        os.makedirs("test-results", exist_ok=True)
        page.screenshot(path="test-results/translation-details.png", full_page=True)
        context.close()
        browser.close()

        if failed:
            print("\n验收未通过，请查看上方明细与 test-results/translation-details.png")
            return 1
        print("\n✅ 验收通过：表头无截断，进度等固定列已收缩。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
