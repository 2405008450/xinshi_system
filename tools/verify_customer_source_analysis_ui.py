"""分析页、客户来源页签和咨询类型 UI；所有 API 在浏览器中拦截，禁止业务写入。"""
import json
import re
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE + '/src/views/client/DataAnalysis.vue', timeout=30).read().decode()
    vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
    consultation_compiled = urlopen(BASE + '/src/views/client/Consultations.vue', timeout=30).read().decode()
    router_url = re.search(r'from ["\']([^"\']*/vue-router\.js[^"\']*)', consultation_compiled).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import {createRouter,createWebHistory} from ROUTER;import Analysis from '/src/views/client/DataAnalysis.vue';import Clients from '/src/views/client/Clients.vue';import Consultations from '/src/views/client/Consultations.vue';import AppForm from '/src/components/common/AppForm.vue';import Dialog from '/src/components/common/DraggableFormDialog.vue';
const mode=ref('analysis');const app=createApp({render:()=>h('div',{},[...['analysis','clients','consultations'].map(value=>h('button',{onClick:()=>mode.value=value},value)),h(mode.value==='analysis'?Analysis:mode.value==='clients'?Clients:Consultations)])});app.component('AppForm',AppForm);app.component('DraggableFormDialog',Dialog);app.use(createRouter({history:createWebHistory(),routes:[{path:'/source-analysis-test',component:{render:()=>null}},{path:'/data-analysis',component:{render:()=>null}}]}));app.mount('#app');</script>'''.replace('from VUE', 'from ' + json.dumps(vue)).replace('from ROUTER', 'from ' + json.dumps(router_url))
    client = {'id': '00000000-0000-4000-8000-000000000001', 'client_code': 'CL-QA', 'client_name': '隔离测试客户', 'client_short_name': '隔离测试', 'sub_clients': [], 'updated_at': '2026-11-07T12:00:00+08:00'}
    client.update(contact_people=[{'name': '原联系人', 'contact_method': '13800000000', 'description': '原有说明'}], contact_names=['原联系人'], manager_contact='13800000000')
    calls, writes, errors, submissions, consultations = [], [], [], [], []
    labels = {'source': '百度', 'method': '电话', 'type': '同传设备租赁', 'keyword': '英语翻译', 'status': 'success', 'type_status': json.dumps(['同传设备租赁', 'success'], ensure_ascii=False)}

    def api(route):
        url = urlparse(route.request.url); path = url.path; params = parse_qs(url.query)
        calls.append((path, params))
        if route.request.method not in {'GET', 'HEAD'}:
            writes.append(path)
        if 'sources' in path:
            dimension = params.get('dimension', ['source'])[0]; key = labels[dimension]
            if path.endswith('/records'):
                result = {'items': [{'id': 'qa-consultation', 'consultation_code': 'ZX-QA-001', 'client_name': client['client_name'], 'client_source': '百度', 'source_keyword': '英语翻译', 'consultation_type': '同传设备租赁', 'consultation_method': 'phone', 'status': 'success', 'consultation_time': '2026-11-07T12:00:00+08:00', 'consultation_description': '测试长文本' * 600}], 'total': 1, 'page': 1}
            else:
                values = ['同传设备租赁', 'success'] if dimension == 'type_status' else [key]
                period = {'day': '2026-11-07', 'week': '2026-11-02', 'month': '2026-11-01'}[params.get('granularity', ['day'])[0]]
                result = {'total': 1, 'client_count': 1, 'undated_count': 0, 'sources': [{'source': key, 'values': values, 'count': 1, 'client_count': 1}], 'periods': [{'period': period, 'count': 1, 'sources': {key: 1}}]}
        elif path == '/api/consultations/' and route.request.method == 'POST':
            payload = route.request.post_data_json; submissions.append(payload)
            client['contact_people'] = payload['contact_people']; client['contact_names'] = [item['name'] for item in payload['contact_people']]
            result = dict(payload, id='00000000-0000-4000-8000-000000000003', consultation_code='ZX-QA-002', updated_at='2026-11-07T13:00:00+08:00', contact_people_updated_at=client['updated_at'])
            consultations.append(result)
        elif path == '/api/consultations/page': result = {'items': consultations, 'total': len(consultations)}
        elif path.endswith('/work-report'): result = {'completed': True}
        elif path == f"/api/clients/{client['id']}": result = client
        elif path == '/api/clients/page': result = {'items': [client], 'total': 1}
        elif path in ['/api/clients/', '/api/clients/options']: result = [client]
        elif path.endswith('/page'): result = {'items': [], 'total': 0}
        elif path == '/api/business-numbers/reserve': result = {'token': '00000000-0000-4000-8000-000000000002', 'number': 'ZX-QA-002'}
        elif path.endswith('/editor-drafts'): result = {'payload': None, 'revision': 0}
        else: result = []
        route.fulfill(content_type='application/json', body=json.dumps(result, ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge')
        page = browser.new_page(viewport={'width': 1440, 'height': 1000}, timezone_id='America/Los_Angeles')
        page.add_init_script("localStorage.setItem('user_id','qa');localStorage.setItem('user_roles','[\"admin\"]');localStorage.setItem('user_permissions','[\"consultations:read\",\"consultations:write\",\"clients:read\",\"clients:write\"]')")
        page.route(re.compile(r'^http://localhost:3000/api/'), api)
        page.route(BASE + '/source-analysis-test', lambda route: route.fulfill(content_type='text/html', body=html))
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/source-analysis-test')
        expect(page.get_by_text('客户来源分布', exact=False)).to_be_visible()
        panel = page.locator('.source-analysis:visible')
        panel.get_by_role('button', name='百度', exact=True).click()
        expect(panel.locator('.source-record-heading')).to_contain_text('百度')
        page.get_by_role('button', name='查看详情', exact=True).click()
        popover = page.locator('.customer-source-detail:visible')
        expect(popover).to_contain_text('2026年11月07日 12:00')
        expect(popover.locator('.source-detail-scroll')).to_have_css('max-height', '560px')
        assert popover.locator('.source-detail-scroll').evaluate('(node)=>node.scrollHeight>node.clientHeight'), popover.locator('.source-detail-scroll').evaluate('(n)=>({scroll:n.scrollHeight,height:n.clientHeight,width:n.clientWidth})')
        assert popover.get_attribute('data-popper-placement').startswith('left')
        page.get_by_text('数据分析', exact=True).click()
        for label, dimension in [('咨询方式分析', 'method'), ('咨询类型分析', 'type'), ('关键词分析', 'keyword'), ('咨询状态分析', 'status'), ('咨询类型 × 咨询状态', 'type_status')]:
            page.get_by_role('tab', name=label, exact=True).click()
            expect(page.locator('.source-analysis:visible .el-table').first).to_contain_text('1')
            assert any(params.get('dimension') == [dimension] for _, params in calls)
        panel = page.locator('.source-analysis:visible')
        grid = panel.locator('.el-table').nth(1)
        expect(grid).to_contain_text('同传设备租赁')
        grid.get_by_role('button', name='1', exact=True).click()
        expect(panel.locator('.source-record-heading')).to_contain_text('同传设备租赁 / 已确认')
        assert json.loads(next(params['source'][0] for path, params in reversed(calls) if path.endswith('/records') and 'source' in params)) == ['同传设备租赁', 'success']
        panel.get_by_text('按周', exact=True).click()
        expect(panel).to_contain_text('2026-11-02 起一周')
        panel.locator('.el-table').nth(2).get_by_role('button', name='1', exact=True).first.click()
        expect(panel.locator('.source-record-heading')).to_contain_text('2026-11-02 起一周')
        assert any(params.get('start') == ['2026-11-02'] and params.get('end') == ['2026-11-08'] for _, params in calls)
        panel.get_by_text('按月', exact=True).click()
        expect(panel.locator('.el-table').nth(2)).to_contain_text('2026-11')
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.set_viewport_size({'width': 1440, 'height': 1000})
        page.get_by_role('button', name='clients', exact=True).click()
        page.get_by_role('button', name='编辑', exact=True).first.click()
        dialog = page.locator('.el-dialog:visible')
        dialog.get_by_role('tab', name='客户来源', exact=True).click()
        expect(dialog.locator('.source-analysis')).to_contain_text('百度')
        assert any(path == f"/api/clients/{client['id']}/sources" for path, _ in calls)
        dialog.get_by_role('button', name='关闭窗口', exact=True).click()
        page.get_by_role('button', name='新增客户', exact=True).click()
        dialog = page.locator('.el-dialog:visible')
        dialog.get_by_role('tab', name='客户来源', exact=True).click()
        expect(dialog).to_contain_text('请先保存客户')
        dialog.get_by_role('button', name='关闭窗口', exact=True).click()
        page.get_by_role('button', name='consultations', exact=True).click()
        page.get_by_role('button', name='新增咨询', exact=True).click()
        dialog = page.locator('.el-dialog:visible').first
        item = dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=re.compile('^咨询类型$'))).first
        item.locator('.el-select').click()
        for value in ['同传设备租赁', '翻译耳机', '翻译软件/平台']:
            expect(page.get_by_role('option', name=value, exact=True)).to_be_visible()
        page.get_by_role('option', name='（音视频）转录/字幕项目', exact=True).click()
        expect(dialog.locator('.consultation-subtitle-notice')).to_contain_text('该类项目属于标注类项目，可转交标注项目部同事')
        expect(dialog.locator('.consultation-subtitle-notice')).to_have_class(re.compile('el-alert--warning'))
        item.locator('.el-select').click()
        page.get_by_role('option', name='同传设备租赁', exact=True).click()
        expect(dialog.locator('.consultation-subtitle-notice')).to_have_count(0)
        def field(label):
            return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=re.compile('^' + label + '$'))).first
        field('客户简称').locator('input').fill('隔离测试')
        page.locator('.el-autocomplete-suggestion:visible').get_by_text('隔离测试', exact=True).click()
        expect(dialog.get_by_role('textbox', name='客户联系人1', exact=True)).to_have_value('原联系人')
        dialog.get_by_role('button', name='添加客户联系人', exact=True).click()
        dialog.get_by_role('textbox', name='客户联系人2', exact=True).fill('第二位联系人')
        dialog.get_by_role('textbox', name='联系人2联系方式', exact=True).fill('second@example.test')
        dialog.get_by_role('textbox', name='联系人2说明', exact=True).fill('采购负责人')
        dialog.get_by_role('button', name='添加客户联系人', exact=True).click()
        dialog.get_by_role('textbox', name='客户联系人3', exact=True).fill('第三位联系人')
        dialog.get_by_role('textbox', name='联系人3联系方式', exact=True).fill('13900000000')
        field('客户来源').locator('input').fill('百度')
        field('咨询描述').locator('textarea').fill('测试设备租赁需求')
        field('咨询方式').locator('.el-select').click(); page.get_by_role('option', name='电话', exact=True).click()
        field('咨询状态').locator('.el-select').click(); page.get_by_role('option', name='未成交', exact=True).click()
        reason_dialog = page.locator('.consultation-failure-dialog:visible')
        expect(reason_dialog).to_be_visible()
        original_position = reason_dialog.bounding_box()
        header = reason_dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 35, header['y'] + 15); page.mouse.down(); page.mouse.move(header['x'] + 150, header['y'] + 55); page.mouse.up()
        assert reason_dialog.bounding_box()['x'] > original_position['x'] + 50
        header = reason_dialog.locator('.el-dialog__header').bounding_box()
        page.mouse.move(header['x'] + 35, header['y'] + 15); page.mouse.down(); page.mouse.move(-2000, -2000); page.mouse.up()
        assert reason_dialog.bounding_box()['x'] >= -1 and reason_dialog.bounding_box()['y'] >= -1
        reason_dialog.get_by_role('button', name='取消', exact=True).click()
        expect(reason_dialog).not_to_be_visible(); expect(field('咨询状态')).to_contain_text('跟进中')
        field('咨询状态').locator('.el-select').click(); page.get_by_role('option', name='未成交', exact=True).click()
        reason_dialog = page.locator('.consultation-failure-dialog:visible')
        assert abs(reason_dialog.bounding_box()['x'] - original_position['x']) < 2
        reason_dialog.locator('.el-select').click()
        for reason in ['价格高', '反应慢', '处理速度不符合客户要求', '无法满足客户要求', '自动放弃', '已找其他公司', '对信实不满意', '一次跟进客户未回应', '多次跟进客户未回应', '自定义添加']:
            expect(page.get_by_role('option', name=reason, exact=True)).to_have_count(1)
        page.get_by_role('option', name='无法满足客户要求', exact=True).click()
        reason_dialog.get_by_role('button', name='确定', exact=True).click()
        expect(reason_dialog.locator('textarea')).to_be_focused()
        reason_dialog.locator('textarea').fill('无法提供客户指定设备')
        reason_dialog.get_by_role('button', name='确定', exact=True).click()
        expect(reason_dialog).not_to_be_visible(); expect(field('咨询状态')).to_contain_text('无法提供客户指定设备')
        dialog.get_by_role('button', name='修改原因', exact=True).click()
        reason_dialog = page.locator('.consultation-failure-dialog:visible')
        reason_dialog.locator('.el-select').click(); page.get_by_role('option', name='一次跟进客户未回应', exact=True).click()
        reason_dialog.locator('textarea').fill('')
        reason_dialog.get_by_role('button', name='确定', exact=True).click()
        expect(reason_dialog).not_to_be_visible()
        body = dialog.locator('.el-dialog__body')
        for position in [0, 300, 99999]:
            body.evaluate('(node, position)=>node.scrollTop=position', position)
            footer = dialog.locator('.el-dialog__footer').bounding_box()
            assert 0 <= footer['y'] and footer['y'] + footer['height'] <= 1001
        dialog.locator('.el-dialog__footer').get_by_role('button', name='保存', exact=True).click()
        expect(dialog).not_to_be_visible()
        assert len(submissions) == 1, submissions
        assert len(submissions[0]['contact_people']) == 3
        assert submissions[0]['contact_people'][1]['description'] == '采购负责人'
        assert submissions[0]['failure_reason'] == {'reason': '一次跟进客户未回应', 'details': ''}
        page.get_by_role('button', name='编辑', exact=True).first.click()
        dialog = page.locator('.consultation-dialog:visible')
        expect(dialog.get_by_role('textbox', name='客户联系人3', exact=True)).to_have_value('第三位联系人')
        expect(dialog).to_contain_text('一次跟进客户未回应')
        dialog.get_by_role('button', name='关闭窗口', exact=True).click()
        page.get_by_role('button', name='数据分析', exact=True).click()
        expect(page).to_have_url(BASE + '/data-analysis')
        assert not errors, errors
        assert not any('/data-analysis/' in path or '/sources' in path for path in writes), writes
        browser.close()
    print('PASS: 六类分析、客户来源、三类新咨询类型、多联系人、未成交原因校验与取消、弹窗拖动复位及固定底部；接口全模拟。')


if __name__ == '__main__': run()
