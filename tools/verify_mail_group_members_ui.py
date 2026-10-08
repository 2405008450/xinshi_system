"""在局域网 Vite 调试服务验证成员选择器，不修改业务数据。"""

from pathlib import Path
import subprocess
import time
import urllib.request

from playwright.sync_api import sync_playwright


def main():
    root = Path(__file__).resolve().parents[1] / "frontend"
    html = root / "qa_mail_members.html"
    script = root / "qa_mail_members.js"
    if html.exists() or script.exists():
        raise RuntimeError("校验临时文件已存在，请先检查")
    proc = None
    try:
        html.write_text('<div id="app"></div><script type="module" src="/qa_mail_members.js"></script>', encoding="utf-8")
        script.write_text('''
import { createApp, ref, h } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import Selector from './src/components/common/InternalMailRecipientSelector.vue'
createApp({
  components: { Selector },
  setup() {
    const users = ref([
      { id: 'active', full_name: '正常成员', is_active: true, email: 'active@example.com' },
      { id: 'inactive', full_name: '停用成员', is_active: false, email: 'old@example.com' },
      { id: 'empty', full_name: '空邮箱成员', is_active: true, email: null },
    ])
    const selected = ref([])
    return () => h('div', [
      h('button', { onClick: () => selected.value = ['active', 'inactive', 'empty', 'missing'] }, '载入历史成员'),
      h('button', { onClick: () => users.value[0].is_active = false }, '停用正常成员'),
      h(Selector, { modelValue: selected.value, users: users.value, 'onUpdate:modelValue': value => selected.value = value }),
      h('pre', { id: 'selection' }, JSON.stringify(selected.value)),
    ])
  },
}).use(ElementPlus).mount('#app')
''', encoding="utf-8")
        proc = subprocess.Popen(
            ['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '12227', '--strictPort'],
            cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for _ in range(30):
            if proc.poll() is not None:
                raise RuntimeError('Vite 校验服务启动失败')
            try:
                urllib.request.urlopen('http://127.0.0.1:12227/qa_mail_members.html', timeout=1)
                break
            except Exception:
                time.sleep(1)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="msedge")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("http://127.0.0.1:12227/qa_mail_members.html")
            page.get_by_role("button", name="载入历史成员").click()
            tags = page.locator(".selected-user-list .el-tag")
            assert tags.count() == 4
            assert "空邮箱成员（不可用）" in tags.all_inner_texts()
            tags.filter(has_text="空邮箱成员").locator(".el-tag__close").click()
            assert page.locator("#selection").inner_text() == '["active"]'
            page.get_by_role("button", name="管理成员", exact=True).click()
            assert page.locator(".user-card").count() == 1
            assert "正常成员" in page.locator(".user-card").inner_text()
            page.get_by_role("button", name="完成", exact=True).click()
            page.get_by_role("button", name="停用正常成员").click()
            assert page.locator("#selection").inner_text() == '[]'
            assert page.locator(".selected-badge").inner_text() == "已选 0 人"
            page.set_viewport_size({"width": 390, "height": 720})
            page.get_by_role("button", name="载入历史成员").click()
            tags.filter(has_text="不可用成员").locator(".el-tag__close").click()
            assert page.locator("#selection").inner_text() == '[]'
            assert not errors, errors
            browser.close()
        print("PASS: 历史停用、空邮箱及缺失成员可移除；不可用成员不可新增；停用后自动清理；小屏可操作")
    finally:
        if proc is not None:
            proc.terminate()
            proc.wait(timeout=10)
        html.unlink(missing_ok=True)
        script.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
