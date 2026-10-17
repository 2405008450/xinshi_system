"""标注主列表地区展示及检索验收；拦截全部 API，不读写业务数据库。"""
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
        raise SystemExit('只允许在本机项目目录执行隔离验收')
    out = ROOT / '.tmp' / 'annotation-region-list-ui'
    out.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    base_url = f'http://127.0.0.1:{port}'
    language_id, other_id, user_id, area_id = [str(uuid4()) for _ in range(4)]
    languages = [dict(id=language_id,label='粤语'),dict(id=other_id,label='英语')]
    language_items = [dict(id=str(uuid4()),source_language_id=language_id,source_language_label='粤语',
        sequence_no=1,display='粤语',regions=[dict(city='广州',district='越秀区',street='北京街道'),
        dict(city='佛山',district='禅城区',street='祖庙街道')]),
        dict(id=str(uuid4()),source_language_id=other_id,source_language_label='英语',sequence_no=2,
        display='英语',regions=[dict(city='广州',district='天河区',street='天河街道')])]
    template = dict(project_name='地区展示验收',project_types=['audio_collection'],task_description='地区展示验收',
        language_items=language_items,language_items_display='粤语；英语',area_labels=[],language_region=None,
        project_status='trial_preparation',priority='medium',parent_project_id=None,order_level=0,
        child_count=0,child_status_counts={},custom_values={},role_assignments=[],assignees=[],price_items=[],
        created_at='2026-10-17T17:00:00+08:00',updated_at='2026-10-17T17:00:00+08:00')
    orders = [{**copy.deepcopy(template),'id':str(uuid4()),'order_no':'AP-LIST-001'}]
    partial = {**copy.deepcopy(template),'id':str(uuid4()),'order_no':'AP-LIST-002'}
    partial['language_items'][0]['regions']=[dict(district='白云区')]
    partial['language_items']=partial['language_items'][:1]
    orders.append(partial)
    legacy = {**copy.deepcopy(template),'id':str(uuid4()),'order_no':'AP-LIST-003',
        'language_region':'肇庆原地区','area_labels':['华南片区'],'area_id':area_id}
    legacy['language_items'][0]['regions']=[]
    legacy['language_items']=legacy['language_items'][:1]
    orders.append(legacy)
    for index in range(8):
        extra = {**copy.deepcopy(partial),'id':str(uuid4()),'order_no':f'AP-LIST-{index+4:03}'}
        extra['language_items'][0]['regions']=[dict(city='珠海',district='香洲区')]
        orders.append(extra)
    queries, mutations, errors, delayed = [], [], [], []
    support_filters = True
    support_regions = True

    def selected_rows(query):
        filters = json.loads(query.get('field_filters',['{}'])[0])
        terms = {key.removeprefix('region_'):value['value'] for key,value in filters.items() if key.startswith('region_')}
        rows = orders
        if terms:
            rows = [row for row in rows if any(all(str(value) in str(region.get(key) or '') for key,value in terms.items())
                for item in row['language_items'] for region in item.get('regions',[]))]
        if 'language_region' in filters:
            rows = [row for row in rows if filters['language_region']['value'] in (row.get('language_region') or '')]
        if query.get('area_ids'):
            rows = [row for row in rows if row.get('area_id') in query['area_ids']]
        return rows

    def api(route):
        request = route.request
        url = urlparse(request.url)
        path = url.path.removeprefix('/api')
        query = parse_qs(url.query)
        result = []
        if request.method not in ('GET','HEAD') and path != '/projects/annotation/language-reserves/lookup':
            mutations.append((request.method,path))
        if path == '/auth/session':
            result = dict(id=user_id,username='region-list-qa',full_name='地区验收',roles=['admin'],permissions=['projects:read','projects:write'])
        elif path == '/openapi.json':
            result = {'components':{'schemas':{'AnnotationLanguageItemInput':{'properties':{'regions':{}} if support_regions else {}}}},'paths':{
                '/projects/annotation/areas':{'get':{}},
                '/projects/annotation/page':{'get':{'parameters':[{'name':'order_scope','schema':{'enum':['grandchild']}}]}}}}
            if support_filters:
                result['paths']['/projects/annotation/page']['get']['x-annotation-region-filters']=['city','district','street']
        elif path == '/projects/annotation/page':
            queries.append(query)
            if '旧结果' in query.get('field_filters',[''])[0]:
                delayed.append(route)
                return
            rows = selected_rows(query)
            skip,limit = int(query.get('skip',[0])[0]),int(query.get('limit',[10])[0])
            result = dict(items=rows[skip:skip+limit],total=len(rows))
        elif path == '/projects/annotation/language-reserves/lookup':
            result = dict(items=[])
        elif path == '/projects/annotation/areas':
            result = [dict(id=area_id,label='华南片区')]
        elif path == '/projects/languages':
            result = languages
        elif path.endswith('/children'):
            result = dict(items=[],total=0)
        elif path.startswith('/projects/annotation/') and any(row['id'] == path.rsplit('/',1)[-1] for row in orders):
            result = next(row for row in orders if row['id'] == path.rsplit('/',1)[-1])
        elif 'source-statuses' in path:
            result = {}
        route.fulfill(status=200,json=result)

    log=(out/'preview.log').open('w',encoding='utf-8')
    process=subprocess.Popen(['node','node_modules/vite/bin/vite.js','preview','--host','127.0.0.1','--port',str(port),'--strictPort'],
        cwd=ROOT/'frontend',stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(50):
            if process.poll() is not None:
                raise RuntimeError((out/'preview.log').read_text(encoding='utf-8'))
            try:
                urlopen(base_url,timeout=1).close()
                break
            except OSError:
                time.sleep(.2)
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,channel='chrome')
            context=browser.new_context(viewport=dict(width=1500,height=960))
            context.route('**/api/**',api)
            context.add_init_script("""localStorage.setItem('token','mock-only');localStorage.setItem('user_name','region-list-qa');
                if(!localStorage.getItem('table-columns:annotation-details-v6:region-list-qa'))
                  localStorage.setItem('table-columns:annotation-details-v6:region-list-qa',JSON.stringify(['projectName','languageItemsDisplay','areaLabels','languageRegion','taskSubmittedAt']));""")
            page=context.new_page()
            page.set_default_timeout(12000)
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base_url+'/annotation-details')
            switch=page.get_by_role('button',name='地区显示层级',exact=True)
            popup=page.locator('.annotation-region-summary-popover:visible')
            expect(switch).to_have_text('城市')
            expect(page.locator('.annotation-region-summary-link').first).to_contain_text('广州')
            expect(page.locator('.annotation-region-summary-link').nth(1)).to_contain_text('未填写城市')
            expect(page.locator('.annotation-region-summary-link').nth(2)).to_contain_text('原地区：肇庆原地区')
            expect(switch).to_have_count(1)

            # 切换只更新展示，默认层级刷新后保留；完整路径按语种展示。
            before=len(queries)
            switch.click()
            page.get_by_role('menuitem',name='区县',exact=True).click()
            expect(page.locator('.annotation-region-summary-link').first).to_contain_text('越秀区')
            assert len(queries)==before
            page.reload()
            expect(switch).to_have_text('区县')
            page.locator('.annotation-region-summary-link').first.click()
            expect(popup).to_contain_text('广州')
            expect(popup).to_contain_text('祖庙街道')
            expect(popup).to_contain_text('英语')
            expect(popup).to_have_css('opacity','1')
            page.screenshot(path=str(out/'region-details.png'),full_page=True)
            page.mouse.click(1000,900)
            expect(popup).not_to_be_visible()
            switch.click()
            page.get_by_role('menuitem',name='街道',exact=True).click()
            expect(page.locator('.annotation-region-summary-link').first).to_contain_text('北京街道')

            # 第 2 页执行筛选时回到第 1 页，400ms 防抖、回车与清空均可用。
            page.locator('.el-pagination .el-pager li').filter(has_text='2').click()
            expect(page.locator('.el-pagination .el-pager li.is-active')).to_have_text('2')
            page.get_by_role('button',name='地区筛选',exact=True).click()
            funnel=page.locator('.column-header-filter-popover:visible')
            city=funnel.get_by_placeholder('筛选城市',exact=True)
            before=len(queries)
            city.fill('广')
            city.fill('广州')
            expect(page.locator('.el-pagination .el-pager li.is-active')).to_have_text('1')
            assert len(queries)==before+1
            assert queries[-1].get('skip')==['0']
            assert json.loads(queries[-1]['field_filters'][0])['region_city']['value']=='广州'
            expect(page.locator('.annotation-region-summary-link')).to_have_count(1)
            expect(page.get_by_role('button',name='地区筛选',exact=True)).to_have_class(re.compile('is-active'))
            district=funnel.get_by_placeholder('筛选区县',exact=True)
            district.fill('越秀')
            district.press('Enter')
            page.mouse.click(1000,900)
            expect(funnel).not_to_be_visible()
            assert json.loads(queries[-1]['field_filters'][0])['region_district']['value']=='越秀'
            page.get_by_role('button',name='地区筛选',exact=True).click()
            funnel=page.locator('.column-header-filter-popover:visible')
            funnel.get_by_role('button',name='清除本组筛选',exact=True).click()
            expect(page.locator('.annotation-region-summary-link')).to_have_count(10)
            expect(page.get_by_role('button',name='地区筛选',exact=True)).not_to_have_class(re.compile('is-active'))
            city=funnel.get_by_placeholder('筛选城市',exact=True)
            city.fill('旧结果')
            page.wait_for_timeout(500)
            assert delayed
            city.fill('广州')
            expect(page.locator('.annotation-region-summary-link')).to_have_count(1)
            for pending in delayed:
                try:
                    pending.fulfill(status=200,json=dict(items=[legacy],total=1))
                except Exception:
                    pass  # 已取消的请求不可再次回传。
            expect(page.locator('.annotation-region-summary-link').first).to_contain_text('北京街道')
            city=funnel.get_by_placeholder('筛选城市',exact=True)
            before=len(queries)
            city.fill('')
            page.wait_for_timeout(150)
            assert len(queries)>before
            expect(page.locator('.annotation-region-summary-link')).to_have_count(10)
            funnel.get_by_placeholder('筛选街道',exact=True).fill('祖庙')
            funnel.get_by_role('button',name='确定',exact=True).click()
            expect(page.locator('.annotation-region-summary-link')).to_have_count(1)
            page.get_by_role('button',name='重置',exact=True).click()
            expect(page.locator('.annotation-region-summary-link')).to_have_count(10)
            expect(switch).to_have_text('街道')

            # 字段设置合并旧列，允许全部取消和恢复默认。
            page.get_by_role('button',name='字段设置',exact=True).click()
            settings=page.locator('.el-popover:visible').filter(has_text='地区（城市/区县/街道）')
            expect(settings.get_by_text('语言地区',exact=True)).to_have_count(0)
            expect(settings.get_by_text('片区',exact=True)).to_have_count(0)
            region_checkbox=settings.locator('.el-checkbox').filter(has_text='地区（城市/区县/街道）')
            region_checkbox.click()
            expect(switch).to_have_count(0)
            region_checkbox.click()
            expect(switch).to_be_visible()
            while settings.locator('.el-checkbox.is-checked').count():
                settings.locator('.el-checkbox.is-checked').first.click()
            expect(switch).to_have_count(0)
            expect(page.get_by_text('查看详情',exact=True).first).to_be_visible()
            settings.get_by_role('button',name='恢复默认',exact=True).click()
            expect(switch).to_be_visible()
            expect(switch).to_have_text('街道')
            page.mouse.click(1000,900)

            # 小屏及多地区滚动不改变主列表高度。
            orders[0]['language_items'][0]['regions']=[dict(city=f'城市{i}',district=f'区县{i}',street=f'街道{i}') for i in range(35)]
            page.reload()
            page.set_viewport_size(dict(width=560,height=780))
            region_cell=page.locator('.annotation-region-summary-link').first
            region_cell.scroll_into_view_if_needed()
            region_cell.click()
            expect(popup).to_be_visible()
            bounds=popup.bounding_box()
            assert bounds['x']>=0 and bounds['x']+bounds['width']<=561,bounds
            sizes=popup.locator('.annotation-region-summary-content').evaluate('(element)=>({height:element.clientHeight,scroll:element.scrollHeight})')
            assert sizes['height']<=560 and sizes['scroll']>sizes['height'],sizes
            expect(popup).to_have_css('opacity','1')
            page.screenshot(path=str(out/'region-small-screen.png'),full_page=True)

            # 旧后端保留原地区检索，不提交不支持的城市字段。
            support_filters=False
            support_regions=False
            page.set_viewport_size(dict(width=1500,height=960))
            page.reload()
            page.get_by_role('button',name='地区筛选',exact=True).click()
            funnel=page.locator('.column-header-filter-popover:visible')
            expect(funnel.get_by_placeholder('筛选城市',exact=True)).to_have_count(0)
            funnel.get_by_placeholder('筛选原语言地区',exact=True).fill('肇庆')
            funnel.get_by_role('button',name='确定',exact=True).click()
            expect(page.locator('.annotation-region-summary-link')).to_have_count(1)
            assert 'region_city' not in json.loads(queries[-1].get('field_filters',['{}'])[0])
            expect(page.locator('.annotation-region-summary-link').first).to_contain_text('原地区：肇庆原地区')
            page.locator('.annotation-region-summary-link').first.click()
            expect(popup).to_contain_text('华南片区')
            expect(popup).to_contain_text('原语言地区')
            page.mouse.click(1000,900)
            expect(popup).not_to_be_visible()
            page.get_by_role('button',name='地区筛选',exact=True).click()
            funnel=page.locator('.column-header-filter-popover:visible')
            funnel.get_by_role('button',name='清除本组筛选',exact=True).click()
            expect(page.locator('.annotation-region-summary-link')).to_have_count(10)
            before=len(queries)
            funnel.locator('.el-checkbox').filter(has_text='华南片区').click()
            funnel.get_by_role('button',name='取消',exact=True).click()
            assert len(queries)==before
            page.get_by_role('button',name='地区筛选',exact=True).click()
            expect(funnel.locator('.el-checkbox.is-checked')).to_have_count(0)
            funnel.locator('.el-checkbox').filter(has_text='华南片区').click()
            funnel.get_by_role('button',name='确定',exact=True).click()
            expect(page.locator('.annotation-region-summary-link')).to_have_count(1)
            assert queries[-1].get('area_ids')==[area_id]
            assert not mutations,mutations
            assert not errors,errors
            expect(page.locator('.annotation-editor-dialog:visible')).to_have_count(0)
            browser.close()
        print(json.dumps(dict(passed=True,checks=['城市区县街道切换与持久化','完整地区与原数据','分页防抖回车清空及重置',
            '旧响应保护','公共分组漏斗及计数','旧列配置迁移','小屏与内部滚动','旧后端兼容','全程未打开编辑弹窗']),ensure_ascii=False))
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()


if __name__=='__main__':
    run()
