"""验收真实个人中心页面，全部业务 API 使用合成数据拦截。"""
import json
import socket
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://localhost:3000'


def run():
    assert socket.gethostname().upper() == 'PC' and ROOT == Path(r'E:\xinshi_system')
    output = ROOT / '.tmp' / 'personal-password-ui'
    output.mkdir(parents=True, exist_ok=True)
    submissions = []
    mode = ['error']
    session = dict(user_id='11111111-1111-1111-1111-111111111111', username='password-qa',
                   full_name='改密验收', roles=[], permissions=[])

    def handle(route):
        request = route.request
        path = urlparse(request.url).path.removeprefix('/api').rstrip('/')
        status, result = 200, {}
        if path == '/auth/session':
            result = session
        elif path == '/auth/mail-account':
            result = dict(email='qa@example.test', is_bound=False, is_verified=False, verified_at=None)
        elif path == '/auth/captcha/required':
            result = dict(required=False)
        elif path == '/auth/password':
            submissions.append(request.post_data_json)
            if mode[0] == 'error':
                status = 400
                result = dict(detail=[dict(loc=['body', 'current_password'],
                                          msg='当前密码不正确', type='value_error')])
            else:
                route.fulfill(status=204, body='')
                return
        elif path == '/chat/sessions':
            result = dict(items=[], total=0, mention_total=0, phase_one_enabled=True)
        elif path == '/notifications/unread-count':
            result = dict(count=0, business_unread_count=0, chat_unread_count=0)
        elif request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            raise AssertionError(f'未授权的测试请求：{request.method} {path}')
        route.fulfill(status=status, content_type='application/json', body=json.dumps(result, ensure_ascii=False))

    with sync_playwright() as playwright:
        print('启动本机浏览器。', flush=True)
        browser = playwright.chromium.launch(headless=True, channel='msedge')
        context = browser.new_context(viewport={'width': 1440, 'height': 1050})
        context.route(BASE + '/api/**', handle)
        context.route_web_socket('**/api/notifications/ws*', lambda websocket: websocket.on_message(lambda _: None))
        context.add_init_script("""if (location.pathname !== '/login') {
            localStorage.setItem('token', 'synthetic-password-test');
            localStorage.setItem('user_id', '11111111-1111-1111-1111-111111111111');
            localStorage.setItem('user_roles', '[]'); localStorage.setItem('user_permissions', '[]');
            localStorage.setItem('columns:password-qa', 'keep');
        }""")
        page = context.new_page()
        page.set_default_timeout(12000)
        page.on('pageerror', lambda error: print('页面错误：' + str(error)))
        print('打开个人中心。', flush=True)
        page.goto(BASE + '/profile', wait_until='domcontentloaded', timeout=12000)
        form = page.locator('.password-form')
        try:
            expect(form).to_be_visible()
        except AssertionError:
            print('验收页面：' + page.url)
            print(page.locator('body').inner_text()[:1500])
            page.screenshot(path=output / 'failure.png', full_page=True)
            raise
        inputs = form.locator('input')
        page.screenshot(path=output / 'initial.png', full_page=True)
        print('页面已加载，检查必填与密码长度。', flush=True)
        submit = form.get_by_role('button', name='修改密码', exact=True)
        submit.click()
        expect(form.get_by_text('请输入当前密码', exact=True)).to_be_visible()
        expect(inputs.nth(0)).to_be_focused()
        assert not submissions
        inputs.nth(0).fill('OldPwd23')
        inputs.nth(1).fill('short')
        inputs.nth(2).fill('short')
        submit.click()
        expect(form.get_by_text('新密码长度应为 8 到 128 个字符')).to_be_visible()
        assert not submissions
        inputs.nth(1).fill('NewPwd45')
        inputs.nth(2).fill('Mismatch')
        submit.click()
        expect(form.get_by_text('两次输入的新密码不一致')).to_be_visible()
        assert not submissions
        inputs.nth(2).fill('NewPwd45')
        print('检查服务端错误定位。', flush=True)
        submit.click()
        expect(form.get_by_text('当前密码不正确', exact=True)).to_be_visible()
        expect(inputs.nth(0)).to_be_focused()
        assert len(submissions) == 1
        form.get_by_role('button', name='清空', exact=True).click()
        print('检查清空及小屏布局。', flush=True)
        for index in range(3):
            expect(inputs.nth(index)).to_have_value('')
        expect(form.locator('.is-error')).to_have_count(0)
        page.screenshot(path=output / 'desktop.png', full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        expect(form).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        submit.scroll_into_view_if_needed()
        expect(submit).to_be_in_viewport()
        page.screenshot(path=output / 'mobile.png', full_page=True)
        for index, value in enumerate(['OldPwd23', 'NewPwd45', 'NewPwd45']):
            inputs.nth(index).fill(value)
        mode[0] = 'success'
        print('检查成功后重新登录。', flush=True)
        submit.click()
        page.wait_for_url(BASE + '/login')
        expect(page.get_by_text('密码修改成功，请使用新密码重新登录', exact=True)).to_be_visible()
        assert len(submissions) == 2 and submissions[-1] == dict(
            current_password='OldPwd23', new_password='NewPwd45', confirm_password='NewPwd45')
        assert page.evaluate("localStorage.getItem('token')") is None
        assert page.evaluate("localStorage.getItem('user_id')") is None
        assert page.evaluate("localStorage.getItem('columns:password-qa')") == 'keep'
        browser.close()
    print('个人中心验收通过：错误定位、长度与重复校验、清空、小屏布局、改密后重新登录。')


if __name__ == '__main__':
    run()
