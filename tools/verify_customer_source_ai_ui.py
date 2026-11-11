"""来源/关键词共用 AI 队列的真实组件验收；全部 API 模拟，不连接模型或业务库。"""
import json
import re
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = 'http://localhost:3000'


def run():
    compiled = urlopen(BASE + '/src/views/client/DataAnalysis.vue', timeout=20).read().decode()
    vue = re.search(r'from ["\']([^"\']*/vue\.js[^"\']*)', compiled).group(1)
    html = '''<!doctype html><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/node_modules/element-plus/dist/index.css"><div id="app"></div><script type="module">
import {createApp,h,ref} from VUE;import Analysis from '/src/views/client/DataAnalysis.vue';import Thoughts from '/src/views/schedule/components/ThoughtAssistant.vue';
const mode=ref('analysis');createApp({render:()=>h('main',{},[h('button',{onClick:()=>mode.value=mode.value==='analysis'?'thoughts':'analysis'},'切换个人思考测试'),mode.value==='analysis'?h(Analysis):h(Thoughts,{content:'个人思考正文'})])}).mount('#app');</script>'''.replace('from VUE', 'from ' + json.dumps(vue))
    state = {'enabled': True, 'automatic': True, 'large': False, 'reject_once': False, 'other_busy': False}
    submissions, cancellations, scopes, errors = [], [], [], []
    jobs = {'thoughts': {'id': 'personal-only', 'action': 'organize', 'scope': 'thoughts', 'state': 'succeeded', 'result': '个人思考专属结果', 'truncated': False, 'created_at': '2026-11-10T12:00:00+08:00'}}
    polls = {}

    def api(route):
        parsed = urlparse(route.request.url); path = parsed.path; params = parse_qs(parsed.query)
        status = 200
        if path == '/api/thoughts-ai/latest':
            scope = params.get('scope', ['thoughts'])[0]; scopes.append(scope)
            job = jobs.get(scope)
            if job and job['state'] in {'queued', 'running'}:
                polls[job['id']] = polls.get(job['id'], 0) + 1
                if state['automatic'] and polls[job['id']] >= 2:
                    job.update(state='succeeded', result='渠道分类建议：搜索引擎、转介绍。<script>不能执行</script>', truncated=True)
            result = {'enabled': state['enabled'], 'job': job, 'busy': state['other_busy'] or bool(job and job['state'] in {'queued', 'running'}), 'max_chars': 6000}
        elif path == '/api/thoughts-ai/jobs':
            data = route.request.post_data_json
            if state['reject_once']:
                state['reject_once'] = False; status = 503; result = {'detail': '测试：算力暂时不可用，请重试'}
            else:
                submissions.append(data)
                scope = data.get('scope', 'thoughts')
                result = {'id': 'job-' + str(len(submissions)), 'action': data['action'], 'scope': scope, 'state': 'queued', 'result': '', 'message': '正在排队', 'truncated': False, 'created_at': '2026-11-10T12:00:00+08:00'}
                jobs[scope] = result
                status = 202
        elif path.startswith('/api/thoughts-ai/jobs/') and path.endswith('/cancel'):
            job_id = path.split('/')[-2]; cancellations.append(job_id)
            result = next(value for value in jobs.values() if value['id'] == job_id)
            result.update(state='cancelled', result='', message='已取消')
        elif path == '/api/data-analysis/customer-sources':
            dimension = params.get('dimension', ['source'])[0]
            values = ['百度', '朋友介绍'] if dimension == 'source' else ['英语翻译', '日语口译']
            if state['large']: values = [f'关键词{i}' + '文本' * 120 for i in range(150)]
            sources = [{'source': value, 'values': [value], 'count': 2, 'client_count': 1} for value in values]
            result = {'total': len(sources) * 2, 'client_count': 2, 'undated_count': 0, 'sources': sources, 'periods': []}
        elif path.endswith('/records'):
            result = {'items': [{'id': 'qa', 'consultation_code': 'ZX-QA', 'client_name': '不应发送的客户全称', 'contact_name': '不应发送的联系人', 'client_source': '百度', 'source_keyword': '英语翻译'}], 'total': 1, 'page': 1}
        else:
            raise AssertionError('Unexpected API: ' + path)
        route.fulfill(status=status, content_type='application/json', body=json.dumps(result, ensure_ascii=False))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.add_init_script("localStorage.setItem('user_id','ai-isolated-qa');localStorage.setItem('token','ai-isolated-qa')")
        page.route(re.compile(r'^http://localhost:3000/api/'), api)
        page.route(BASE + '/customer-source-ai-test', lambda route: route.fulfill(content_type='text/html', body=html))
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/customer-source-ai-test')
        page.get_by_role('button', name='AI 分析与分类', exact=True).click()
        panel = page.get_by_role('region', name='AI来源分析')
        # section 的 accessible role 取决于浏览器；带 aria-label 的实际节点用于稳定断言。
        panel = page.locator('.source-ai-panel')
        submit = panel.get_by_role('button', name='开始分析与分类', exact=True)
        expect(submit).to_be_enabled()
        assert submissions == [] and scopes[-1] == 'customer_source'
        expect(panel).not_to_contain_text('个人思考专属结果')
        question_input = panel.locator('textarea')
        question_input.fill('按渠道性质归并')
        question_input.dispatch_event('keydown', {'key': 'Enter', 'isComposing': True})
        question_input.press('Shift+Enter')
        expect(question_input).to_have_value('按渠道性质归并\n')
        assert submissions == []
        question_input.press('Enter')
        expect(panel.get_by_role('status')).to_have_text('分析已完成', timeout=10000)
        question = panel.get_by_role('button', name=re.compile('按渠道性质归并'))
        answer = panel.get_by_role('region', name='答', exact=True)
        expect(question).to_have_attribute('aria-expanded', 'false')
        expect(answer).to_be_hidden()
        question.click()
        expect(answer).to_be_visible()
        expect(answer.locator('.source-ai-result-text')).to_contain_text('渠道分类建议')
        assert answer.bounding_box()['x'] > question.bounding_box()['x']
        assert submissions[0]['scope'] == 'customer_source' and submissions[0]['action'] == 'organize'
        assert all(text in submissions[0]['content'] for text in ['百度', '朋友介绍', '按渠道性质归并'])
        assert '不应发送' not in submissions[0]['content']
        expect(panel).to_contain_text('输出上限')
        expect(panel.locator('script')).to_have_count(0)
        question.click()
        expect(answer).to_be_hidden()
        page.get_by_text('按周', exact=True).click()
        expect(panel.locator('.source-ai-result-text')).to_have_count(0)
        assert len(submissions) == 1
        page.get_by_role('tab', name='关键词分析', exact=True).click()
        page.get_by_role('button', name='AI 分析与分类', exact=True).click()
        expect(submit).to_be_enabled()
        state['automatic'] = False
        submit.click()
        expect(panel.get_by_role('button', name='取消 AI 任务', exact=True)).to_be_visible()
        assert submissions[-1]['scope'] == 'source_keyword'
        assert '英语翻译' in submissions[-1]['content']
        panel.get_by_role('button', name='取消 AI 任务', exact=True).click()
        expect(panel).to_contain_text('已取消')
        state['reject_once'] = True
        submit.click()
        expect(panel).to_contain_text('测试：算力暂时不可用')
        state['large'] = True
        page.get_by_role('button', name='查询', exact=True).click()
        expect(panel).to_contain_text('6000 字上限')
        expect(submit).to_be_enabled()
        submit.click()
        expect(panel.get_by_role('button', name='取消 AI 任务', exact=True)).to_be_visible()
        assert len(submissions[-1]['content']) <= 6000
        current_id = jobs['source_keyword']['id']
        page.get_by_text('按月', exact=True).click()
        expect(panel.locator('.source-ai-result-text')).to_have_count(0)
        expect(submit).to_be_enabled()
        assert current_id in cancellations
        state['other_busy'] = True
        panel.get_by_role('button', name='刷新 AI 状态', exact=True).click()
        expect(submit).to_be_disabled(); expect(panel).to_contain_text('其他 AI 任务')
        state['other_busy'] = False; state['enabled'] = False
        panel.get_by_role('button', name='刷新 AI 状态', exact=True).click()
        expect(panel).to_contain_text('AI 服务尚未启用'); expect(submit).to_be_disabled()
        state['enabled'] = True
        panel.get_by_role('button', name='刷新 AI 状态', exact=True).click()
        expect(submit).to_be_enabled()
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.set_viewport_size({'width': 1440, 'height': 1000})
        page.get_by_role('button', name='切换个人思考测试', exact=True).click()
        expect(page.locator('.thought-assistant')).to_contain_text('个人思考专属结果')
        expect(page.locator('.thought-assistant')).not_to_contain_text('渠道分类建议')
        state['automatic'] = True
        page.get_by_role('button', name='帮我梳理', exact=True).click()
        expect(page.locator('.thought-assistant .result-text')).to_contain_text('渠道分类建议', timeout=10000)
        assert submissions[-1] == {'action': 'organize', 'content': '个人思考正文'}
        assert not errors, errors
        browser.close()
    print('PASS: 来源/关键词 AI、共用接口、作用域隔离、排队取消、筛选变更清理、长度预算、重试、小屏与个人思考回归（全部 API 模拟）')


if __name__ == '__main__': run()
