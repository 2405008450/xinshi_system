"""本机人才概览发布验收：真实接口、只读页面交互和统计快照备份。"""
import argparse
from datetime import timedelta
import json
import re
from pathlib import Path
import socket
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backup', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('仅允许在本机项目执行')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    import main as application  # noqa: F401，注册 ORM 关系
    from database import SessionLocal
    from models import AppUser
    from interpretation_models import InterpretationLanguage
    from talent_overview_service import get_talent_overview
    from routers.auth import create_access_token

    with SessionLocal() as db:
        if args.backup:
            backup = {'overview': get_talent_overview(db), 'bindings': [
                {'id': str(item.id), 'key': item.talent_overview_key}
                for item in db.query(InterpretationLanguage).all()
            ]}
            (output / 'before.json').write_text(json.dumps(backup, ensure_ascii=False, default=str), encoding='utf-8')
            print('Overview and language bindings backed up')
            return
        user = db.query(AppUser).filter(AppUser.username == 'admin').one()
        # 短期验收凭证仅保存在内存，沿用该账号现有权限，不写入文件或日志。
        token = create_access_token({'sub': user.username, 'user_id': str(user.id)}, timedelta(minutes=15))

    def api(path):
        request = Request('http://127.0.0.1:8000' + path, headers={'Authorization': 'Bearer ' + token})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    api('/auth/session')
    print('Live authentication passed', flush=True)
    first = api('/talents/overview/pool-statistics')
    second = api('/talents/overview/pool-statistics')
    assert first == second, '重复刷新产生了额外变化'
    overview = first['overview']
    before = json.loads((output / 'before.json').read_text(encoding='utf-8'))['overview']
    old_keys = {row['overview_key'] for row in before['rows']}
    added = [row for row in overview['rows'] if row['overview_key'] not in old_keys]
    assert overview['grand_total'] == before['grand_total']
    assert overview['rows'][:len(before['rows'])] == before['rows']
    assert all(all(value is None for value in row['counts'].values()) for row in added)
    print(f'Live statistics passed: {len(added)} auto-added rows', flush=True)
    counts = {row['overview_key']: row['people_count'] for row in first['rows']}
    target = next((row for row in added if counts[row['overview_key']] > 0),
                  next(row for row in overview['rows'] if counts[row['overview_key']] > 0))

    from playwright.sync_api import sync_playwright, expect
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True, args=[
            '--no-proxy-server', '--host-resolver-rules=MAP oa.xinshify.com.cn 127.0.0.1',
        ])
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        context.add_init_script('localStorage.setItem("token", ' + json.dumps(token) + ');')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('https://oa.xinshify.com.cn/resource-management/talent-overview')
        expect(page.get_by_text('人才总库自动统计：', exact=True)).to_be_visible(timeout=30000)
        expect(page.get_by_role('button', name='刷新总库统计', exact=True)).to_be_enabled(timeout=30000)
        expect(page.locator('.pool-statistics-note')).not_to_contain_text('统计暂不可用')
        page.get_by_role('button', name='刷新总库统计', exact=True).click()
        expect(page.get_by_role('button', name='刷新总库统计', exact=True)).to_be_enabled()

        page.get_by_role('button', name='语种/方言筛选', exact=True).click()
        popover = page.locator('.column-header-filter-popover:visible')
        popover.get_by_placeholder('搜索语种/方言').fill(target['language'])
        popover.locator('label.el-checkbox').filter(has_text=re.compile('^' + re.escape(target['language']) + '$')).click()
        popover.get_by_role('button', name='确定', exact=True).click()
        rows = page.locator('.overview-table .el-table__body-wrapper tbody tr')
        expect(rows).to_have_count(1)
        expect(rows.first.locator('.pool-statistics-cell')).to_have_text(f"{counts[target['overview_key']]:,}")
        expected_total = f"{target['row_total']:,}"
        expect(rows.first.locator('td').last).to_have_text(expected_total)
        page.screenshot(path=str(output / 'overview-filtered.png'), full_page=True)

        page.get_by_role('button', name='编辑', exact=True).click()
        expect(page.get_by_role('button', name='刷新总库统计', exact=True)).to_be_disabled()
        if target in added:
            expect(rows.first.get_by_role('button', name='空', exact=True)).to_have_count(len(overview['columns']))
        page.get_by_role('button', name='取消', exact=True).click()
        page.get_by_role('button', name='语种/方言筛选', exact=True).click()
        popover.get_by_role('button', name='清空', exact=True).click()
        popover.get_by_role('button', name='确定', exact=True).click()
        expect(rows).to_have_count(len(overview['rows']))
        page.screenshot(path=str(output / 'overview-desktop.png'), full_page=True)
        page.set_viewport_size({'width': 760, 'height': 900})
        expect(page.get_by_role('button', name='刷新总库统计', exact=True)).to_be_visible()
        page.screenshot(path=str(output / 'overview-small.png'), full_page=True)
        page.reload()
        expect(rows).to_have_count(len(overview['rows']), timeout=30000)
        assert not errors, errors
        browser.close()
    report = {'passed': True, 'auto_added_rows': len(added), 'row_count': len(overview['rows']),
              'total_people': first['total_people'], 'source_total': overview['grand_total'],
              'pending_languages': len(first['unmatched']), 'browser_errors': errors}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
