"""构建产物的语种地区交互验收；全部 API 拦截为测试数据，不连接业务数据库。"""
import copy
import json
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def run():
    if socket.gethostname().upper() != 'PC' or ROOT != Path(r'E:\xinshi_system'):
        raise SystemExit('只允许在本机项目目录运行隔离验收')
    out = ROOT / '.tmp' / 'annotation-language-regions-ui'
    out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    base_url = f'http://127.0.0.1:{port}'
    root_id, leaf_id, language_id, other_id, client_id, user_id, area_id = [str(uuid4()) for _ in range(7)]
    now = '2026-10-17T16:00:00+08:00'
    regions = [dict(city='广州', district='越秀区', street=None),
               dict(city='佛山', district='禅城区', street='祖庙街道')]
    languages = [dict(id=language_id, label='粤语'), dict(id=other_id, label='英语')]
    language_items = [dict(id=str(uuid4()), source_language_id=language_id,
        source_language_label='粤语', display='粤语', sequence_no=1, regions=regions),
        dict(id=str(uuid4()), source_language_id=other_id,
        source_language_label='英语', display='英语', sequence_no=2, regions=[])]
    template = dict(project_name='语种地区验收项目', project_types=['audio_collection'], task_description='语音采集',
        client_id=client_id, client_short_name='验收客户', client_full_name='验收客户全称', client_code='QA',
        client_manager_id=user_id, client_manager_name='验收人员', task_dispatched_at=now,
        project_status='trial_preparation', priority='medium', status_effective_on=now, created_at=now,
        updated_at=now, language_items=language_items, language_items_display='粤语；英语', price_items=[],
        assignees=[], role_assignments=[], custom_values={}, parent_project_id=None, child_count=0,
        child_status_counts={}, area_id=None, area_labels=[], inheritance_overrides=[])
    orders = {root_id: {**copy.deepcopy(template), 'id': root_id, 'order_no': 'AP-REGIONS-QA', 'order_level': 0},
        leaf_id: {**copy.deepcopy(template), 'id': leaf_id, 'order_no': 'AP-REGIONS-QA.001.001',
            'order_level': 2, 'parent_project_id': root_id, 'parent_order_no': 'AP-REGIONS-QA.001',
            'area_id': area_id, 'area_labels': ['测试片区'], 'language_items': copy.deepcopy(language_items[:1]),
            'language_items_display': '粤语'}}
    session = dict(id=user_id, username='region-qa', full_name='验收人员', roles=['admin'], permissions=['projects:read', 'projects:write'])
    saves, creates, errors = [], [], []
    regions_enabled = True
    reserve_fails = True

    def api(route):
        request = route.request
        url = urlparse(request.url)
        path = url.path.removeprefix('/api')
        query = parse_qs(url.query)
        result, status = [], 200
        if path == '/openapi.json':
            result = {
                'components': {'schemas': {'AnnotationLanguageItemInput': {'properties': {'regions': {'type': 'array'}}}}},
                'paths': {
                    '/projects/annotation/areas': {'get': {}},
                    '/projects/annotation/page': {'get': {'parameters': [
                        {'name': 'order_scope', 'schema': {'enum': ['grandchild']}}]}},
                },
            }
            if not regions_enabled:
                result['components']['schemas']['AnnotationLanguageItemInput']['properties'] = {}
        elif path == '/auth/session':
            result = session
        elif path == '/projects/annotation/language-reserves/lookup':
            if reserve_fails:
                return route.fulfill(status=503, json=dict(detail='隔离验收：人才储备不可用'))
            result = dict(items=[dict(language_id=lang['id'], matched=True, overview_language=lang['label'],
                total=37, updated_at='2026-10-17') for lang in languages])
        elif path == '/projects/annotation/page':
            scope = query.get('order_scope', ['parent'])[0]
            rows = [row for row in orders.values() if row['order_level'] == (2 if scope == 'grandchild' else 0)]
            result = dict(items=rows, total=len(rows))
        elif path.endswith('/children') and request.method == 'GET':
            result = dict(items=[], total=0)
        elif path == '/projects/annotation/' and request.method == 'POST':
            payload = request.post_data_json
            creates.append(payload)
            project_id = str(uuid4())
            row = {**copy.deepcopy(template), **payload, 'id': project_id, 'order_no': 'AP-REGIONS-NEW', 'order_level': 0}
            for index, item in enumerate(row['language_items']):
                item.update(id=str(uuid4()), sequence_no=index + 1,
                    source_language_label=next(lang['label'] for lang in languages if lang['id'] == item['source_language_id']))
                item['display'] = item['source_language_label']
            orders[project_id] = row
            result, status = row, 201
        elif path.startswith('/projects/annotation/') and path.rsplit('/', 1)[-1] in orders:
            row = orders[path.rsplit('/', 1)[-1]]
            if request.method == 'PUT':
                payload = request.post_data_json
                saves.append(copy.deepcopy(payload))
                previous = {item['id']: item for item in row['language_items']}
                row.update(payload)
                for index, item in enumerate(row['language_items']):
                    original = previous.get(item.get('id'), {})
                    item.update(id=item.get('id') or str(uuid4()), sequence_no=index + 1,
                        source_language_label=original.get('source_language_label', '粤语'),
                        display=original.get('display', '粤语'))
            result = row
        elif path == '/projects/annotation/areas':
            result = [dict(id=area_id, label='测试片区')]
        elif path == '/projects/languages':
            result = languages
        elif path.startswith('/clients'):
            result = [dict(id=client_id, client_short_name='验收客户', client_name='验收客户全称', client_code='QA', sub_clients=[])]
        elif path.startswith('/users') or 'role-candidates' in path or path == '/projects/annotation/manager-options':
            result = [dict(id=user_id, username='region-qa', full_name='验收人员', is_active=True)]
        elif 'source-statuses' in path:
            result = {}
        elif path.endswith('/folder-changes'):
            result = dict(created_folders=[], renamed_folders=[], deleted_folder_ids=[])
        route.fulfill(status=status, json=result)

    log = (out / 'preview.log').open('w', encoding='utf-8')
    process = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1',
        '--port', str(port), '--strictPort'], cwd=ROOT / 'frontend', stdout=log,
        stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(50):
            if process.poll() is not None:
                raise RuntimeError((out / 'preview.log').read_text(encoding='utf-8'))
            try:
                urlopen(base_url, timeout=1).close()
                break
            except OSError:
                time.sleep(.2)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel='chrome')
            context = browser.new_context(viewport=dict(width=1440, height=900))
            context.route('**/api/**', api)
            context.add_init_script("localStorage.setItem('token','mock-only');localStorage.setItem('user_name','region-qa')")
            page = context.new_page()
            page.set_default_timeout(12000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            editor = page.locator('.annotation-editor-dialog:visible')
            popover = page.locator('.annotation-language-detail-popover:visible')

            # 列表只打开一层语种小窗，人才储备失败仍展示地区，多语种在窗内切换。
            page.goto(base_url + '/annotation-details')
            page.locator('.annotation-table .language-reserve-link').first.click()
            expect(popover).to_be_visible()
            expect(popover).to_contain_text('越秀区')
            expect(popover).to_contain_text('祖庙街道')
            expect(popover).to_contain_text('人才储备加载失败')
            expect(page.locator('.el-popover:visible')).to_have_count(1)
            popover.get_by_role('button', name='英语', exact=True).click()
            expect(popover).to_contain_text('未设置地区要求')
            expect(popover).not_to_contain_text('越秀区')
            popover.get_by_role('button', name='粤语', exact=True).click()
            expect(popover).to_have_css('opacity', '1')
            page.screenshot(path=str(out / 'language-popover.png'), full_page=True)
            page.mouse.click(700, 30)
            expect(popover).not_to_be_visible()

            reserve_fails = False
            page.reload()
            page.locator('.annotation-table .language-reserve-link').first.click()
            expect(popover).to_contain_text('储备合计')
            expect(popover).to_contain_text('未经地区筛选')
            expect(popover).to_contain_text('越秀区')
            expect(popover).to_have_css('opacity', '1')
            page.screenshot(path=str(out / 'language-popover-success.png'), full_page=True)
            page.mouse.click(700, 30)
            expect(popover).not_to_be_visible()

            # 新建下级订单预览带入来源地区，修改预览不会写回上级。
            page.locator('.annotation-table .table-expand-button').first.click()
            page.locator('.order-children-toolbar').get_by_role('button', name='新增子订单', exact=True).first.click()
            child_editor = page.locator('.annotation-child-create-dialog:visible')
            expect(child_editor).to_be_visible()
            expect(child_editor.get_by_role('textbox', name='粤语 地区1 城市', exact=True)).to_have_value('广州')
            child_editor.get_by_role('textbox', name='粤语 地区1 城市', exact=True).fill('下级独立城市')
            assert orders[root_id]['language_items'][0]['regions'][0]['city'] == '广州'
            child_editor.get_by_role('button', name='取消', exact=True).click()
            expect(child_editor).not_to_be_visible()
            page.locator('.annotation-table .table-expand-button').first.click()

            # 详情复用同一语种小窗。
            page.get_by_text('查看详情', exact=True).first.click()
            detail = page.locator('.annotation-detail-popover:visible')
            expect(detail).to_be_visible()
            detail.locator('.language-reserve-link').click()
            expect(popover).to_contain_text('越秀区')
            page.mouse.click(700, 30)
            expect(popover).not_to_be_visible()

            # 编辑支持多地区、字段搜索和清空；底部操作栏不随正文滚动。
            page.goto(base_url + f'/annotation-details?projectId={root_id}&openEditor=1')
            expect(editor).to_be_visible()
            expect(editor.get_by_role('textbox', name='粤语 地区1 城市', exact=True)).to_have_value('广州')
            expect(editor.get_by_role('textbox', name='粤语 地区2 街道', exact=True)).to_have_value('祖庙街道')
            editor.get_by_role('textbox', name='粤语 地区1 城市', exact=True).fill(' 广州 ')
            editor.get_by_role('textbox', name='粤语 地区1 街道', exact=True).fill('北京街道')
            region_editor = editor.locator('.language-regions-editor').first
            region_editor.get_by_role('button', name='添加地区', exact=True).click()
            editor.get_by_role('textbox', name='粤语 地区3 街道', exact=True).fill('只填街道')
            # 全空行不进入保存载荷。
            region_editor.get_by_role('button', name='添加地区', exact=True).click()
            search = editor.locator('.el-dialog__header input')
            search.fill('街道')
            suggestions = page.locator('.el-autocomplete-suggestion:visible')
            expect(suggestions).to_contain_text('街道')
            suggestions.get_by_text(re.compile('街道')).first.click()
            expect(editor.get_by_role('textbox', name='粤语 地区1 街道', exact=True)).to_be_focused()
            footer = editor.locator('.el-dialog__footer')
            before = footer.bounding_box()
            editor.locator('.el-dialog__body').evaluate('(element)=>element.scrollTop=element.scrollHeight')
            after = footer.bounding_box()
            assert abs(before['y'] - after['y']) < 2
            footer.get_by_role('button', name='保存', exact=True).click()
            expect(editor).not_to_be_visible()
            assert len(saves[-1]['language_items'][0]['regions']) == 3
            assert saves[-1]['language_items'][0]['regions'][0]['city'] == '广州'
            assert saves[-1]['language_items'][0]['regions'][2] == dict(city=None, district=None, street='只填街道')
            assert saves[-1]['language_items'][1]['regions'] == []

            # 保存后重新打开列表小窗看到新数据。
            page.locator('.annotation-table .language-reserve-link').first.click()
            expect(popover).to_contain_text('北京街道')
            page.mouse.click(700, 30)
            expect(popover).not_to_be_visible()
            page.goto(base_url + f'/annotation-details?projectId={root_id}&openEditor=1')
            expect(editor).to_be_visible()
            region_editor = editor.locator('.language-regions-editor').first
            for _ in range(3):
                region_editor.get_by_role('button', name=re.compile('删除粤语地区')).first.click()
            footer.get_by_role('button', name='保存', exact=True).click()
            expect(editor).not_to_be_visible()
            assert saves[-1]['language_items'][0]['regions'] == []

            # 弹窗可拖动且保持视口边界，重开后回到预设位置。
            page.goto(base_url + f'/annotation-details?projectId={root_id}&openEditor=1')
            expect(editor).to_be_visible()
            expect(editor).to_have_css('animation-name', 'none')
            original = editor.bounding_box()
            header = editor.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x'] + 20, header['y'] + 20)
            page.mouse.down()
            page.mouse.move(5000, 5000, steps=10)
            page.mouse.up()
            moved = editor.bounding_box()
            assert moved['x'] >= -1 and moved['y'] >= -1 and moved['x'] + moved['width'] <= 1441 and moved['y'] + moved['height'] <= 901, moved
            editor.get_by_role('button', name='关闭此对话框').click()
            expect(editor).not_to_be_visible()
            page.goto(base_url + f'/annotation-details?projectId={root_id}&openEditor=1')
            expect(editor).to_be_visible()
            expect(editor).to_have_css('animation-name', 'none')
            reset = editor.bounding_box()
            assert abs(reset['x'] - original['x']) < 2 and abs(reset['y'] - original['y']) < 2, (original, reset)
            editor.get_by_role('button', name='关闭此对话框').click()
            expect(editor).not_to_be_visible()

            # 新增态：只选择语种，所有地区留空也能保存。
            page.get_by_role('button', name='新增标注项目', exact=True).click()
            expect(editor).to_be_visible()
            editor.get_by_placeholder('可手工填写，或根据客户、方向和类型生成').fill('仅语种必填验收')
            editor.get_by_placeholder('请输入具体任务', exact=True).fill('地区可全部留空')
            editor.get_by_placeholder('选择已有客户，或直接输入新客户简称').fill('验收客户')
            editor.locator('.el-dialog__header').click(position=dict(x=20, y=20))
            editor.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=re.compile('^项目类型$'))).locator('.el-select').click()
            page.get_by_role('option', name='音频采集', exact=True).click()
            editor.locator('.el-dialog__header').click(position=dict(x=20,y=20))
            editor.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=re.compile('^客户经理$'))).locator('.el-select').click()
            page.get_by_role('option', name=re.compile('验收人员')).click()
            editor.locator('.language-row .el-select').nth(1).click()
            page.get_by_role('option', name='粤语', exact=True).click()
            expect(editor.get_by_role('textbox', name='粤语 地区1 城市', exact=True)).to_be_visible()
            dispatched = editor.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=re.compile('^任务派发时间$'))).locator('input')
            dispatched.fill('2026-10-17 16:00')
            dispatched.press('Enter')
            editor.get_by_text('待定', exact=True).click()
            footer.get_by_role('button', name='保存', exact=True).click()
            expect(editor).not_to_be_visible()
            assert creates[-1]['language_items'][0]['regions'] == []

            # 三级订单语种只读，地区仍可独立修改；小屏幕下保持单列和固定操作栏。
            page.set_viewport_size(dict(width=540, height=760))
            page.goto(base_url + f'/annotation-child-orders?orderScope=grandchild&projectId={leaf_id}&openEditor=1')
            expect(editor).to_be_visible()
            language_field = editor.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=re.compile('^语种方向$')))
            expect(language_field.locator('input').first).to_have_attribute('readonly', '')
            city = editor.get_by_role('textbox', name='粤语 地区1 城市', exact=True)
            city.fill('深圳')
            row = editor.locator('.language-region-row').first
            row.scroll_into_view_if_needed()
            expect(city).to_be_in_viewport()
            expect(editor).to_have_css('opacity', '1')
            page.screenshot(path=str(out / 'small-screen-regions.png'), full_page=True)
            inputs = row.locator('.el-input').evaluate_all('elements=>elements.map(element=>({x:element.getBoundingClientRect().x,y:element.getBoundingClientRect().y}))')
            assert len({round(item['x']) for item in inputs}) == 1 and inputs[1]['y'] > inputs[0]['y']
            box = editor.bounding_box()
            assert box['width'] <= 508 and box['x'] >= 0
            for position in [0, 300, 100000]:
                editor.locator('.el-dialog__body').evaluate('(element,position)=>element.scrollTop=position', position)
                expect(footer.get_by_role('button', name='保存', exact=True)).to_be_in_viewport()
            page.screenshot(path=str(out / 'small-screen-editor.png'), full_page=True)
            footer.get_by_role('button', name='保存', exact=True).click()
            expect(editor).not_to_be_visible()
            assert saves[-1]['language_items'][0]['regions'][0]['city'] == '深圳'

            # 多条地区只在小窗内部滚动，不改变主表格高度。
            page.set_viewport_size(dict(width=1440, height=900))
            orders[root_id]['language_items'][0]['regions'] = [dict(city=f'城市{index}', district='测试区', street='测试街道') for index in range(30)]
            page.goto(base_url + '/annotation-details')
            table_before = page.locator('.annotation-table').bounding_box()
            page.locator('.annotation-table .language-reserve-link').first.click()
            expect(popover).to_be_visible()
            content = popover.locator('.annotation-language-detail-content')
            sizes = content.evaluate('(element)=>({height:element.clientHeight,scroll:element.scrollHeight})')
            assert sizes['height'] <= 560 and sizes['scroll'] > sizes['height'], sizes
            table_after = page.locator('.annotation-table').bounding_box()
            assert abs(table_before['height'] - table_after['height']) < 1
            page.locator('.annotation-table .language-reserve-link').first.click()
            expect(popover).not_to_be_visible()

            # 旧版后端不能接收地区时隐藏录入，防止填写后被忽略。
            regions_enabled = False
            page.goto(base_url + f'/annotation-details?projectId={root_id}&openEditor=1')
            expect(editor).to_be_visible()
            expect(editor.locator('.language-regions-editor')).to_have_count(0)
            expect(page.get_by_text('当前后端尚未启用语种地区，暂不能录入城市、区县、街道；其他项目字段仍可正常使用。', exact=True)).to_be_visible()
            footer.get_by_role('button', name='保存', exact=True).click()
            expect(editor).not_to_be_visible()
            assert 'regions' not in saves[-1]['language_items'][0]
            assert not errors, errors
            browser.close()
        print(json.dumps(dict(passed=True, checks=['列表与详情地区小窗', '语种切换', '储备失败隔离',
            '多地区与空行', '清空与刷新', '字段搜索', '新增仅语种必填', '三级订单独立地区', '小屏单列与固定操作栏',
            '拖拽边界及重开复位', '地区小窗内部滚动', '旧后端兼容']), ensure_ascii=False))
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()


if __name__ == '__main__':
    run()
