"""在本机 Vite 页面中挂载真实组件，全部 API 使用隔离响应，绝不发送真实邮件。"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = '''<!doctype html><html><head><meta charset="utf-8"></head><body><div id="app"></div>
<script type="module">
import { createApp, h, reactive, nextTick } from '/node_modules/.vite/deps/vue.js';
import { createRouter, createMemoryHistory } from 'QA_ROUTER_MODULE';
import AppForm from '/src/components/common/AppForm.vue';
import DraggableFormDialog from '/src/components/common/DraggableFormDialog.vue';
import TableActionButton from '/src/components/common/TableActionButton.vue';
const paths = {
 business: '/src/components/common/BusinessMailComposer.vue',
 consultation: '/src/views/client/Consultations.vue',
 manuscript: '/src/views/manuscript/ManuscriptArrangements.vue'
};
const kind = new URLSearchParams(location.search).get('kind');
const Component = (await import(paths[kind])).default;
const props = reactive(kind === 'business' ? { modelValue: true, projectType: 'translation', projectId: 'qa-project', 'onUpdate:modelValue': value => props.modelValue = value } : {});
const app = createApp({ render: () => h(Component, props) });
app.component('AppForm', AppForm).component('DraggableFormDialog', DraggableFormDialog).component('TableActionButton', TableActionButton);
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }] });
app.use(router);
app.mount('#app');
await nextTick();
window.qa = { state: app._instance.subTree.component.setupState, props, app };
</script></body></html>'''


def run():
    sys.stdout.reconfigure(encoding='utf-8')
    failures, checks, writes = [], [], []
    mode = {'send_fail': False, 'missing_image': False}
    source = urlopen('http://localhost:3000/src/router/index.js').read().decode('utf-8')
    router_module = re.search(r'from\s+"([^"]*vue-router[^\"]*)"', source).group(1)
    harness_html = HTML.replace('QA_ROUTER_MODULE', router_module)

    def api(route):
        request = route.request
        path = urlparse(request.url).path
        if request.method != 'GET':
            writes.append(path)
        if path.startswith('/api/mail-inline-images/') and path.endswith('/content'):
            if mode['missing_image']:
                route.fulfill(status=404, json={'detail': '图片不存在'})
            else:
                import base64
                route.fulfill(status=200, content_type='image/png', body=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jk1sAAAAASUVORK5CYII='))
            return
        if path == '/api/project-mails/preview':
            result = dict(subject='QA-001 系统主题', body='系统正文', body_html='', inline_images=[], order_no='QA-001',
                          can_send=True, to_users=[dict(user_id='recipient', email='qa@example.test')], cc_users=[], blocking_reasons=[])
        elif path == '/api/project-mails/' and request.method == 'POST':
            result = dict(status='failed' if mode['send_fail'] else 'sent', send_error='模拟失败')
        elif path == '/api/users/':
            result = [dict(id='recipient', is_active=True, email='qa@example.test', full_name='验收收件人')]
        elif path.endswith('/confirmation-preview'):
            result = dict(project_type='translation', order_no='QA-001', email_body='新的系统正文',
                          project_name='验收项目', language_pair='中文→英文', to_users=[], cc_users=[], can_send=True)
        elif path.endswith('/mail-preview'):
            result = dict(arrangement_id='qa-assignment', recipient_email='qa@example.test', subject='稿件系统主题',
                          body='稿件系统正文', body_html='', inline_images=[], dispatch_path='只读验收路径')
        elif path.endswith('/send'):
            if mode['send_fail']:
                result = dict(failed_count=1, sent_count=1, skipped_count=0)
            else:
                result = dict(failed_count=0, sent_count=1, skipped_count=0)
        elif path.endswith('/status'):
            result = dict(configured=True, mode='smtp')
        elif path.endswith('/page'):
            result = dict(items=[], total=0)
        elif path.endswith('/context'):
            result = dict(active_projects={'items': [dict(id='qa-project', translation_project_id='qa-project', file_name='验收.docx', can_manage_manuscript=True)]}, translators=[])
        elif path.endswith('/unread-count'):
            result = dict(count=0)
        else:
            result = []
        route.fulfill(status=200, json=result)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True, args=['--disable-features=LocalNetworkAccessChecks'])
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        context.add_init_script("localStorage.setItem('user_id', localStorage.getItem('user_id') || 'qa-user'); localStorage.setItem('user_roles', '[\"admin\"]'); localStorage.setItem('user_permissions', '[\"*\"]')")
        context.route(re.compile(r'^http://localhost:3000/api/'), api)
        context.route('**/__mail_draft_qa__?*', lambda route: route.fulfill(content_type='text/html', body=harness_html))
        page = context.new_page()
        page.on('pageerror', lambda error: (failures.append(str(error)), print(str(error), flush=True)))
        page.on('requestfailed', lambda request: print(request.url, request.failure, flush=True))
        page.on('console', lambda message: print(message.text, flush=True) if message.type == 'error' else None)

        def mount(kind):
            page.goto(f'http://localhost:3000/__mail_draft_qa__?kind={kind}')
            page.wait_for_function('window.qa && Object.keys(window.qa.state).length > 0', timeout=15000)

        def cached(key):
            return page.evaluate('(key) => JSON.parse(localStorage.getItem("mail-drafts:qa-user") || "{}")[key] || null', key)

        def close_business():
            page.evaluate('qa.props.modelValue = false')
            page.wait_for_timeout(350)

        def open_business():
            page.evaluate('qa.props.modelValue = true')
            page.wait_for_function('!qa.state.loading')

        mount('business')
        page.wait_for_function('!qa.state.loading && qa.state.form.body === "系统正文"')
        page.wait_for_timeout(350)
        dialog = page.locator('.business-mail-dialog')
        initial = dialog.bounding_box()
        title = page.get_by_text('内部项目邮件预览', exact=True).bounding_box()
        page.mouse.move(title['x'] + 15, title['y'] + 10)
        page.mouse.down()
        page.mouse.move(title['x'] + 135, title['y'] + 70, steps=8)
        page.mouse.up()
        moved = dialog.bounding_box()
        assert moved['x'] > initial['x'] + 50
        page.mouse.move(moved['x'] + 100, moved['y'] + 15)
        page.mouse.down()
        page.mouse.move(1800, 1300, steps=8)
        page.mouse.up()
        bounded = dialog.bounding_box()
        assert bounded['x'] >= 0 and bounded['y'] >= 0
        assert bounded['x'] + bounded['width'] <= 1441
        assert bounded['y'] + bounded['height'] <= 1001
        page.get_by_role('button', name='关闭窗口', exact=True).click()
        page.wait_for_timeout(350)
        open_business()
        page.wait_for_timeout(350)
        reopened = dialog.bounding_box()
        assert abs(reopened['x'] - initial['x']) < 2 and abs(reopened['y'] - initial['y']) < 2, (initial, reopened)
        checks.append('邮件弹窗可拖动、视口边界、关闭及重新打开复位')
        page.locator('.tiptap').fill('用户编辑正文')
        close_business()
        assert cached('project:translation:qa-project')['fields']['body'] == '用户编辑正文'
        open_business()
        expect(page.locator('.tiptap')).to_contain_text('用户编辑正文')
        expect(page.get_by_text('未发送的邮件草稿', exact=False)).to_be_visible()
        page.reload()
        page.wait_for_function('window.qa && !qa.state.loading && qa.state.form.body === "用户编辑正文"')
        checks.append('项目邮件关闭、重新打开与刷新恢复')

        page.get_by_role('button', name='恢复系统默认内容').click()
        page.wait_for_function('qa.state.form.body === "系统正文"')
        assert cached('project:translation:qa-project') is None
        checks.append('恢复系统默认内容')

        # 恢复图片时必须重新取内容，不能使用上一次页面的 Blob URL。
        page.evaluate('''() => {
          qa.state.form.body = '含图草稿';
          qa.state.form.bodyHtml = '<p>含图草稿</p><img src="" data-mail-image-id="qa-image">';
          qa.state.form.inlineImages = [{ id: 'qa-image', original_name: '验收.png', file_size: 10 }];
        }''')
        close_business()
        open_business()
        expect(page.locator('.tiptap img')).to_be_visible()
        assert page.locator('.tiptap img').get_attribute('src').startswith('blob:')
        assert 'blob:' not in json.dumps(cached('project:translation:qa-project'))
        checks.append('正文图片恢复、Blob URL 重新生成')
        close_business()
        mode['missing_image'] = True
        page.reload()
        page.wait_for_function('window.qa && !qa.state.loading && qa.state.form.inlineImages.length === 0')
        expect(page.locator('.tiptap img')).to_have_count(0)
        expect(page.get_by_text('部分草稿图片已失效，请重新插入')).to_be_visible()
        checks.append('失效图片移除并提示')
        mode['missing_image'] = False

        page.locator('.tiptap').fill('发送失败保留正文')
        mode['send_fail'] = True
        page.evaluate('qa.state.submitMail()')
        page.wait_for_timeout(500)
        assert cached('project:translation:qa-project') is not None
        mode['send_fail'] = False
        page.evaluate('qa.state.submitMail()')
        page.wait_for_function('!qa.props.modelValue')
        assert cached('project:translation:qa-project') is None
        checks.append('模拟发送失败保留、成功清除且关闭不复活')

        open_business()
        page.locator('.tiptap').fill('账号 A 的私有草稿')
        close_business()
        page.evaluate('localStorage.setItem("user_id", "qa-other")')
        open_business()
        page.wait_for_function('qa.state.form.body === "系统正文"')
        page.evaluate('localStorage.setItem("user_id", "qa-user")')
        close_business()
        checks.append('切换用户草稿隔离')

        mount('consultation')
        page.evaluate('''async () => {
          qa.state.confirmationContext.consultationId = 'qa-consultation';
          qa.state.confirmationDialogVisible = true;
          qa.state.applyConfirmationPreview({ project_type: 'translation', order_no: 'QA-001', email_body: '咨询系统正文' });
        }''')
        page.locator('.tiptap').fill('咨询手工正文')
        page.evaluate('qa.state.applyConfirmationPreview({ project_type: "translation", order_no: "QA-002", email_body: "刷新后的正文" })')
        expect(page.locator('.tiptap')).to_contain_text('咨询手工正文')
        page.evaluate('qa.state.confirmationDialogVisible = false')
        page.wait_for_timeout(350)
        assert cached('consultation:qa-consultation')['fields']['emailBody'] == '咨询手工正文'
        page.reload()
        page.wait_for_function('window.qa')
        page.evaluate('''() => {
          qa.state.confirmationContext.consultationId = 'qa-consultation';
          qa.state.confirmationDialogVisible = true;
          qa.state.applyConfirmationPreview({ project_type: 'translation', order_no: 'QA-002', email_body: '新系统正文' });
        }''')
        expect(page.locator('.tiptap')).to_contain_text('咨询手工正文')
        checks.append('咨询手工正文防覆盖、关闭及刷新恢复')

        mount('manuscript')
        page.evaluate('''async () => {
          qa.state.selectedProject = { id: 'qa-project', translation_project_id: 'qa-project', file_name: '验收.docx', can_manage_manuscript: true };
          qa.state.mailStatus.configured = true;
          await qa.state.openMailPreviewDialog({ id: 'qa-batch', can_manage_manuscript: true }, { id: 'qa-assignment', selected_files: [] });
        }''')
        expect(page.locator('.tiptap')).to_be_visible()
        page.locator('.tiptap').fill('稿件单封手工正文')
        page.evaluate('qa.state.mailSendPreviewDialogVisible = false')
        page.wait_for_timeout(350)
        assert cached('manuscript:assignment:qa-assignment')['fields']['body'] == '稿件单封手工正文'
        page.evaluate('''async () => {
          await qa.state.openMailPreviewDialog({ id: 'qa-batch', can_manage_manuscript: true }, { id: 'qa-assignment', selected_files: [] });
        }''')
        expect(page.locator('.tiptap')).to_contain_text('稿件单封手工正文')
        page.evaluate('qa.state.mailSendPreviewDialogVisible = false')
        page.wait_for_timeout(350)
        checks.append('稿件单封关闭、销毁后恢复')

        page.evaluate('''async () => {
          await qa.state.openMailPreviewDialog({ id: 'qa-batch', can_manage_manuscript: true }, { id: 'qa-assignment', selected_files: [] }, 'batch');
          qa.state.mailSendPreview.preview.body = '批量手工正文';
          qa.state.mailSendPreviewDialogVisible = false;
        }''')
        page.wait_for_timeout(350)
        assert cached('manuscript:batch:qa-batch')['fields']['body'] == '批量手工正文'
        page.evaluate('''async () => {
          await qa.state.openMailPreviewDialog({ id: 'qa-batch', can_manage_manuscript: true }, { id: 'qa-assignment', selected_files: [] }, 'batch');
        }''')
        assert page.evaluate('qa.state.mailSendPreview.preview.body') == '批量手工正文'
        assert page.evaluate('qa.state.mailBatchOriginalBody') == '稿件系统正文'
        mode['send_fail'] = True
        page.evaluate('qa.state.sendBatch(qa.state.mailSendPreview.dispatch)')
        assert cached('manuscript:batch:qa-batch') is not None
        mode['send_fail'] = False
        page.evaluate('qa.state.sendBatch(qa.state.mailSendPreview.dispatch)')
        assert cached('manuscript:batch:qa-batch') is None
        checks.append('稿件批量基线、恢复、部分失败保留和全成功清除')
        assert not [path for path in writes if '/mail-inline-images/' in path], writes
        assert not failures, failures
        print(json.dumps({'checks': checks, 'errors': failures, 'mocked_writes': len(writes)}, ensure_ascii=False, indent=2))
        browser.close()


if __name__ == '__main__':
    run()
