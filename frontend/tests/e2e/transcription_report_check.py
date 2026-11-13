"""在隔离端口验证报告的 Nginx 响应头及 Firefox/Chromium 嵌入交互。"""

import argparse
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nginx', required=True, type=Path)
    parser.add_argument('--dist', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--chromium', type=Path)
    parser.add_argument('--firefox', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    dist = args.dist.resolve()
    assert (dist / 'reports/minority-transcription-20261113/综合分析报告.html').is_file()
    nginx = args.nginx.resolve()
    report_path = '/reports/minority-transcription-20261113/综合分析报告.html'
    # 使用业务组件的真实 iframe 属性，保持沙箱隔离及相对明细地址。
    component = (root / 'frontend/src/views/project/AnnotationTranscriptionReport.vue').read_text(encoding='utf-8')
    sandbox = re.search(r'sandbox="([^"]+)"', component).group(1)
    (dist / 'report-qa.html').write_text(
        f'<meta charset="utf-8"><iframe title="报告验收" src="{report_path}" '
        f'sandbox="{sandbox}" style="width:100%;height:900px"></iframe>', encoding='utf-8')
    results = []
    with sync_playwright() as playwright:
        for index, config_path in enumerate(['frontend/nginx.conf', 'nginx.conf', 'deploy/nginx-lan.conf']):
            source = (root / config_path).read_text(encoding='utf-8')
            report_location = re.search(
                r'location \^~ /reports/minority-transcription-20261113/ \{[^}]+\}', source).group(0)
            # 保留站点的真实默认响应头，覆盖旧配置时本测试应直接失败。
            headers = '\n'.join(re.findall(r'^\s*add_header [^\n]+', source, re.M)[:5])
            inherit = 'add_header_inherit merge;' if 'add_header_inherit merge;' in source else ''
            port = 13427 + index
            prefix = output / str(index)
            prefix.mkdir(exist_ok=True)
            (prefix / 'logs').mkdir(exist_ok=True)
            (prefix / 'temp').mkdir(exist_ok=True)
            config = prefix / 'nginx.conf'
            config.write_text(
                f'events {{}} http {{ include "{(nginx.parent / "conf/mime.types").as_posix()}"; '
                f'server {{ listen 127.0.0.1:{port}; root "{dist.as_posix()}"; {inherit}\n'
                f'{headers}\n{report_location}\nlocation / {{ try_files $uri =404; }} }} }}', encoding='utf-8')
            command = [str(nginx), '-p', prefix.as_posix() + '/', '-c', config.as_posix()]
            subprocess.run(command + ['-t'], check=True, capture_output=True)
            process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW)
            origin = f'http://127.0.0.1:{port}'
            try:
                for attempt in range(50):
                    try:
                        with urllib.request.urlopen(origin + '/report-qa.html') as response:
                            assert response.headers['X-Frame-Options'] == 'DENY'
                        break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError('隔离 Nginx 未就绪')
                for name in ['chromium', 'firefox']:
                    executable = getattr(args, name)
                    browser = getattr(playwright, name).launch(
                        headless=True, executable_path=str(executable.resolve()) if executable else None)
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('console', lambda message: errors.append(message.text)
                            if message.type == 'error' and ('Content Security Policy' in message.text
                                                          or 'Refused to' in message.text) else None)
                    page.goto(origin + '/report-qa.html')
                    frame = page.frame_locator('iframe')
                    frame.locator('#bestChart svg').wait_for()
                    assert frame.locator('#languages tr').count() > 1
                    toggle = frame.locator('#sourcePathsToggle')
                    toggle.click()
                    assert frame.locator('#sourcePathsContent').is_visible()
                    toggle.click()
                    assert not frame.locator('#sourcePathsContent').is_visible()
                    frame.locator('#search').fill('韩语')
                    page.wait_for_timeout(500)
                    assert frame.locator('#languages').inner_text().find('韩语') >= 0
                    # 点击真实语种，确认沙箱中按相对路径加载明细脚本。
                    frame.locator('[data-chart-code="ko_kr"]').click()
                    frame.locator('#details > details').first.wait_for()
                    frame.locator('#details > details > summary').first.click()
                    assert frame.locator('#details .pair').first.is_visible()
                    assert not errors, errors
                    page.screenshot(path=str(prefix / f'{name}.png'))
                    results.append({'config': config_path, 'browser': name, 'status': 'passed'})
                    browser.close()
            finally:
                subprocess.run(command + ['-s', 'quit'], capture_output=True)
                process.wait(timeout=15)
    (output / 'result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__':
    main()
