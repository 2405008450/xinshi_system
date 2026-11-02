"""只读加载指定档案，拦截浏览器保存并在内存中校验，禁止业务写入。"""
import json
import sys
import functools
import http.server
import threading
import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: F401，注册 ORM
from database import SessionLocal
from models import AppUser
from resource_models import ResourcePerson
from resource_schemas import ResourcePersonDetailResponse, ResourcePersonUpdate
from routers.talents import read_talent
from sqlalchemy import text
from pydantic import ValidationError
from playwright.sync_api import sync_playwright, expect


def run(name, dist=None, legacy_draft=False):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if not Path(self.translate_path(self.path)).is_file() and not Path(self.path).suffix:
                self.path = '/index.html'
            super().do_GET()

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(dist or Path(__file__).resolve().parents[1] / 'frontend' / 'dist')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with SessionLocal() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        user = db.query(AppUser).filter(AppUser.username == 'admin').one()
        query = db.query(ResourcePerson)
        if name == '--legacy-domain-objects':
            query = query.filter(text("resource_person.archived_into_id IS NULL AND EXISTS (SELECT 1 FROM resource_written_translation_profile w, json_array_elements(w.domain_skills::json) value WHERE w.person_id=resource_person.id AND json_typeof(value)='object')"))
        else:
            query = query.filter(ResourcePerson.full_name == name)
        people = query.all()
        details = [ResourcePersonDetailResponse.model_validate(read_talent(p.id, db, user)).model_dump(mode='json') for p in people]
    assert details, '没有匹配档案'
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='msedge', headless=True)
        for index, detail in enumerate(details):
            if detail.get('archived_into_id'):
                print(json.dumps({'record_index':index,'archived_skipped':True}))
                continue
            captured = []
            context = browser.new_context(viewport={'width':1440,'height':1000})
            context.add_init_script("localStorage.setItem('token','isolated-ui-only')")

            def api(route):
                request = route.request
                path = urlparse(request.url).path.removeprefix('/api').rstrip('/')
                result = []
                if request.method not in ('GET', 'HEAD'):
                    if request.method == 'PUT' and path == '/talents/' + detail['id']:
                        try:
                            ResourcePersonUpdate.model_validate(request.post_data_json)
                            profile=request.post_data_json.get('resume_profile') or {}
                            assert all(isinstance(value,str) for value in profile.get('professional_domains',[])), '前端提交必须是领域文字列表'
                            if legacy_draft:
                                assert profile['versions']['en']['professional_domains']==['Law'], '外文旧草稿也必须规范化'
                            assert request.post_data_json.get('written_profile', {}).get('domain_skills') == (detail.get('written_profile') or {}).get('domain_skills'), '原领域技能和熟练程度必须保持不变'
                            captured.append([])
                            result = detail
                        except ValidationError as error:
                            issues = [{'loc':['body', *item['loc']], 'type':item['type'], 'msg':item['msg']} for item in error.errors()]
                            captured.append(issues)
                            route.fulfill(status=422,json={'detail':issues})
                            return
                    else:
                        route.fulfill(status=403,json={'detail':'只读验收禁止写入'})
                        return
                elif path == '/auth/session':
                    result = {'user_id':'isolated-ui','username':'UI验收','roles':['admin'],'permissions':['*']}
                elif path == '/talents/page':
                    result = {'items':[detail], 'total':1}
                elif path == '/talents/' + detail['id']:
                    result = detail
                elif path.startswith('/projects/languages'):
                    result = [{'id':row['language_id'],'code':str(i),'label':row.get('language_label') or '语种'} for i,row in enumerate(detail['language_skills'])]
                route.fulfill(status=200,content_type='application/json',body=json.dumps(result,ensure_ascii=False))

            context.route('**/api/**',api)
            page = context.new_page()
            page.goto(f'http://127.0.0.1:{server.server_port}/resource-management/talents')
            try:
                page.get_by_role('button',name='编辑',exact=True).first.click(timeout=15000)
            except Exception:
                print('UI:',page.locator('body').inner_text()[:2500],flush=True)
                raise
            dialog = page.locator('.talent-editor-dialog:visible')
            expect(dialog).to_be_visible()
            if legacy_draft:
                name_field=dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=re.compile('^中文姓名$'))).locator('input')
                original_name=name_field.input_value()
                name_field.fill(original_name+'隔离回归')
                name_field.fill(original_name)
                page.wait_for_timeout(500)
                dialog.get_by_role('button',name='取消',exact=True).click()
                expect(dialog).not_to_be_visible()
                page.evaluate('''detail=>{
                    const storageKey='form-drafts:talent:isolated-ui';
                    const drafts=JSON.parse(localStorage.getItem(storageKey));
                    const form=drafts['edit:'+detail.id].form;
                    const values=detail.written_profile?.domain_skills||[];
                    form.resumeProfile.professionalDomains=values;
                    form.resumeProfile.versions.en={name:'Isolated QA',professionalDomains:[{domain:'Law',level:'expert'}]};
                    localStorage.setItem(storageKey,JSON.stringify(drafts));
                }''',detail)
                page.get_by_role('button',name='编辑',exact=True).first.click()
                expect(dialog).to_be_visible()
            dialog.get_by_role('button',name='保存',exact=True).click()
            page.wait_for_timeout(1500)
            print(json.dumps({'record_index':index, 'captured':captured},ensure_ascii=False),flush=True)
            assert captured == [[]], '保存请求必须通过实际后端模型校验'
            context.close()
        browser.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('--dist-dir',type=Path)
    parser.add_argument('--legacy-draft',action='store_true')
    args=parser.parse_args()
    run(args.name,args.dist_dir,args.legacy_draft)
