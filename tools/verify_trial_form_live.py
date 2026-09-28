"""真实试采页面 → TestClient → 独立 PostgreSQL；下拉基础数据使用同库种子。

不启动 Uvicorn、不触发正式后端启动任务。数据库事务在测试结束后回滚。
"""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import time
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
fixture = runpy.run_path(str(root / 'tests/test_form_postgres_regression.py'))['form_api'].__wrapped__()
ctx = next(fixture)
from interpretation_models import InterpretationLanguage
from annotation_models import AnnotationProjectLanguageItem
from resource_models import ResourceAnnotationLanguageSkill

language = InterpretationLanguage(id=uuid4(), label='回归语种')
ctx.db.add(language)
ctx.db.flush()
direction = AnnotationProjectLanguageItem(id=uuid4(), project_id=ctx.project.id, sequence_no=1, source_language_id=language.id)
ctx.db.add(direction)
ctx.db.add(ResourceAnnotationLanguageSkill(person_id=ctx.people[0].id, source_language_id=language.id))
ctx.db.commit()
project = {'id': str(ctx.project.id), 'orderNo': ctx.project.order_no, 'projectName': ctx.project.project_name,
           'languageItems': [{'id': str(direction.id), 'display': language.label, 'sourceLanguageId': str(language.id)}]}
person = {'id': str(ctx.people[0].id), 'fullName': ctx.people[0].full_name, 'resourceCode': ctx.people[0].resource_code,
          'annotationLanguageSkills': [{'sourceLanguageId': str(language.id)}]}
frontend = root / 'frontend'
(frontend / 'qa-live.html').write_text('<div id="app"></div><script type="module" src="/qa-live.js"></script>', encoding='utf-8')
(frontend / 'qa-live.js').write_text('''import {createApp} from 'vue';
import {createRouter,createWebHistory} from 'vue-router';
import ElementPlus from 'element-plus'; import 'element-plus/dist/index.css';
import Page from './src/views/project/AnnotationTrials.vue';
import AppForm from './src/components/common/AppForm.vue';
const router=createRouter({history:createWebHistory(),routes:[{path:'/qa-live.html',component:Page}]});
createApp(Page).use(router).use(ElementPlus).component('AppForm',AppForm).mount('#app');''', encoding='utf-8')
log = (frontend / 'qa-live-vite.log').open('wb')
proc = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '12220', '--strictPort'],
                        cwd=frontend, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
results = root / 'form-regression-results'
results.mkdir(exist_ok=True)
writes = []
try:
    for _ in range(40):
        try:
            urlopen('http://127.0.0.1:12220/qa-live.html', timeout=1)
            break
        except OSError:
            time.sleep(1)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        page.context.tracing.start(screenshots=True, snapshots=True)
        page.add_init_script("localStorage.setItem('user_roles','[\"admin\"]')")

        def route(request):
            parsed = urlsplit(request.request.url)
            if not parsed.path.startswith('/api/'):
                return request.continue_()
            path = parsed.path[4:]
            if path == '/projects/annotation/':
                return request.fulfill(json=[project])
            if path == '/projects/annotation/' + project['id']:
                return request.fulfill(json=project)
            if path == '/talent-options/':
                return request.fulfill(json=[person])
            if path.startswith('/annotation-ops/'):
                response = ctx.client.request(request.request.method, path + ('?' + parsed.query if parsed.query else ''),
                                              content=request.request.post_data, headers={'content-type': 'application/json'})
                if request.request.method in {'POST', 'PUT'}:
                    writes.append({'method': request.request.method, 'path': path, 'status': response.status_code})
                return request.fulfill(status=response.status_code, body=response.content, content_type='application/json')
            return request.fulfill(json=[])

        page.route('**/api/**', route)
        try:
            page.goto('http://127.0.0.1:12220/qa-live.html?projectId=' + project['id'])
            page.get_by_role('button', name='新增候选', exact=True).click()
            dialog = page.locator('.trial-editor-dialog')
            dialog.wait_for()
            field = lambda name: dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label', has_text=name))
            dialog.get_by_role('button', name='保存', exact=True).click()
            page.wait_for_timeout(400)
            assert not writes
            field('人员').locator('.el-select').click()
            page.get_by_role('option').filter(has_text=person['fullName']).click()
            field('报价金额').locator('input').fill('12')
            field('计费单位').locator('.el-select').click()
            page.get_by_role('option', name='条', exact=True).click()
            dialog.get_by_role('button', name='保存', exact=True).evaluate('(el)=>{el.click();el.click()}')
            dialog.wait_for(state='hidden')
            assert [item['status'] for item in writes] == [201], writes
            rows = ctx.client.get('/annotation-ops/trials', params={'project_id': project['id']}).json()
            assert len(rows) == 1 and float(rows[0]['quote_amount']) == 12
            page.get_by_role('button', name='编辑', exact=True).first.click()
            dialog.wait_for()
            assert float(field('报价金额').locator('input').input_value()) == 12
            field('总体评分').locator('input').fill('8')
            dialog.get_by_role('button', name='保存', exact=True).click()
            dialog.wait_for(state='hidden')
            rows = ctx.client.get('/annotation-ops/trials', params={'project_id': project['id']}).json()
            assert len(rows) == 1 and rows[0]['overall_score'] == 8
            page.screenshot(path=str(results / 'trial-live-saved.png'))
            print('LIVE UI PASS: required/create/double-click/edit/readback')
        except Exception:
            page.screenshot(path=str(results / 'trial-live-failed.png'))
            raise
        finally:
            (results / 'trial-live-requests.json').write_text(json.dumps(writes, indent=2), encoding='utf-8')
            page.context.tracing.stop(path=str(results / 'trial-live-trace.zip'))
            browser.close()
finally:
    subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
    log.close()
    fixture.close()
