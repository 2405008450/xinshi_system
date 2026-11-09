"""在本机 Vite 中验收真实组件与 SSH 推理；所有笔记 API 隔离，不写业务库。"""
import json
import os
from pathlib import Path
import socket
import sys
import time
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import expect, sync_playwright
import thoughts_ai_service as service


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    assert socket.gethostname().upper() == 'PC' and ROOT == Path(r'E:\xinshi_system')
    run_id = uuid4().hex
    os.environ['THOUGHTS_AI_ENABLED'] = 'true'
    os.environ['THOUGHTS_AI_QUEUE_PATH'] = str(ROOT / '.tmp' / f'thoughts-qa-{run_id}.sqlite3')
    owner = str(uuid4())
    fixture = ROOT / 'frontend' / f'thoughts-qa-{run_id}.html'
    fixture.write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><div id="app" style="padding:16px;max-width:1000px;margin:auto"></div><script type="module">
import {createApp} from 'vue';
import MyThoughts from '/src/views/schedule/components/MyThoughts.vue';
import 'element-plus/dist/index.css';
createApp(MyThoughts).mount('#app');
</script></html>''', encoding='utf-8')
    drafts = {'payload': None, 'revision': 0}
    counts = {'ai_submissions': 0, 'note_saves': 0}
    errors = []

    def api(route):
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path
        if not path.startswith('/api/'):
            route.continue_()
            return
        data = request.post_data_json if request.method == 'POST' else None
        if path == '/api/thoughts-ai/latest':
            result = service.latest(owner)
        elif path == '/api/thoughts-ai/jobs':
            counts['ai_submissions'] += 1
            result = service.create(owner, service.ThoughtRequest(**data))
        elif path.startswith('/api/thoughts-ai/jobs/') and path.endswith('/cancel'):
            result = service.cancel(owner, path.split('/')[-2])
        elif path == '/api/editor-drafts' and request.method == 'GET':
            params = parse_qs(parsed.query)
            result = {'namespace': params['namespace'][0], 'key': params['key'][0], **drafts, 'updated_at': None}
        elif path == '/api/editor-drafts/batch':
            result = []
            for item in data['drafts']:
                counts['note_saves'] += 1
                drafts['payload'] = item['payload']
                drafts['revision'] += 1
                result.append({'namespace': item['namespace'], 'key': item['key'], 'revision': drafts['revision'], 'updated_at': None})
        else:
            raise AssertionError(f'Unexpected API request: {request.method} {path}')
        route.fulfill(status=202 if path == '/api/thoughts-ai/jobs' else 200, json=result)

    checks = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel='msedge')
            context = browser.new_context(viewport={'width': 1280, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
            context.route('**/api/**', api)
            context.add_init_script(f"localStorage.setItem('token','isolated-ai-qa');localStorage.setItem('user_id','{owner}')")
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://localhost:3000/{fixture.name}')
            note = page.get_by_role('textbox', name='我的思考与发散内容')
            submit = page.get_by_role('button', name='帮我梳理', exact=True)
            expect(submit).to_be_disabled()
            original = '验收示例：需要统一项目沟通记录，先收集分散信息的案例，再试行统一记录流程。'
            note.fill(original)
            expect(submit).to_be_enabled()
            page.wait_for_timeout(4200)
            assert counts['ai_submissions'] == 0 and counts['note_saves'] > 0
            checks.append('笔记自动保存不会触发推理')
            start = time.monotonic()
            submit.click()
            note.fill(original + '\n生成期间补充：先在一个小项目验证。')
            expect(page.locator('.result-text')).not_to_be_empty(timeout=120000)
            duration = round(time.monotonic() - start, 2)
            expect(note).to_have_value(original + '\n生成期间补充：先在一个小项目验证。')
            assert counts['ai_submissions'] == 1
            checks.append('真实 SSH 推理且生成期间编辑不会被覆盖')
            page.get_by_role('button', name='复制结果', exact=True).click()
            expect(page.get_by_text('结果已复制', exact=True)).to_be_visible()
            copied = page.evaluate('navigator.clipboard.readText()')
            assert copied.replace('\r\n', '\n') == page.locator('.result-text').text_content().replace('\r\n', '\n')
            page.get_by_role('button', name='追加到笔记', exact=True).click()
            assert '生成期间补充' in note.input_value() and '【帮我梳理】' in note.input_value()
            expect(page.get_by_role('button', name='已追加到笔记', exact=True)).to_be_disabled()
            checks.append('复制、追加与防重复追加')
            page.wait_for_timeout(4200)
            saved_note = note.input_value()
            page.reload()
            expect(note).to_have_value(saved_note)
            expect(page.locator('.result-text')).not_to_be_empty()
            checks.append('刷新恢复笔记与最近 AI 结果')
            page.set_viewport_size({'width': 390, 'height': 844})
            section = page.locator('.thought-assistant')
            section.scroll_into_view_if_needed()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            section.screenshot(path=str(ROOT / '.tmp/thoughts-ai-mobile.png'))
            checks.append('390px 小屏无横向溢出')
            note.fill('字' * 6001)
            expect(submit).to_be_disabled()
            expect(page.get_by_text('当前文字 6001 字，请精简到 6000 字以内再提交。')).to_be_visible()
            checks.append('输入预算明确提示且阻止超限提交')
            note.fill('取消验收：梳理项目资料归档步骤。')
            submit.click()
            page.get_by_role('button', name='取消任务', exact=True).click()
            expect(page.locator('.assistant-result')).to_contain_text('已取消', timeout=120000)
            checks.append('取消任务且不追加取消结果')
            browser.close()
        assert not errors, errors
        print(json.dumps({'passed': checks, 'real_generation_seconds': duration, **counts}, ensure_ascii=False))
    finally:
        fixture.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
