"""实际 Vue 页面 + FastAPI + 隔离 PostgreSQL；所有 /api 请求拦截到测试客户端。"""

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from test_annotation_customer_progress import environment, api_client, add


def test_customer_progress_browser_workflow(environment):
    from playwright.sync_api import sync_playwright, expect
    db, users, parent, child, _engine = environment
    client = api_client(db, users[0])
    from annotation_ops_models import AnnotationProjectStatusHistory
    # 构造香港本地时间的创建节点，供历史节点定位验收使用。
    db.add(AnnotationProjectStatusHistory(project_id=parent.id, to_status='trial_preparation',
        effective_on=datetime(2026, 10, 16, 18, 0), changed_by=users[0].id, entry_kind='status'))
    db.commit()
    chat_response = client.post(f'/project-chat/annotation/{parent.id}/messages', json={'content':'客户预计周五确认报价', 'client_message_id':str(uuid4())})
    assert chat_response.status_code in (200, 201), chat_response.text
    for index in range(14):
        add(db, parent, users[0], f'历史客户反馈 {index}', f'2026-10-09T{index + 1:02d}:30:00+08:00')
    output = Path(__file__).resolve().parents[1] / '.tmp' / 'customer-progress-ui'
    output.mkdir(parents=True, exist_ok=True)
    page_errors, api_errors, held_saves, writes = [], [], [], []
    hold_customer_save = False
    fail_next_customer_load = True
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width':954,'height':884}, timezone_id='America/Los_Angeles')
        info = {'token':'isolated-test-token', 'user_id':str(users[0].id), 'user_name':users[0].username,
                'user_full_name':users[0].full_name, 'user_permissions':json.dumps(['projects:read','projects:write']), 'user_roles':'[]'}
        context.add_init_script('Object.entries('+json.dumps(info)+').forEach(([key,value])=>localStorage.setItem(key,value))')
        def route_api(route):
            nonlocal fail_next_customer_load
            request = route.request
            split = urlsplit(request.url)
            # 任何业务请求都只进入本轮隔离数据库；不使用日常代理后端。
            assert split.path.startswith('/api/')
            path = split.path[4:] + ('?' + split.query if split.query else '')
            print(f'UI API {request.method} {split.path[4:]}', flush=True)
            if fail_next_customer_load and request.method == 'GET' and split.path.endswith('/customer-progress'):
                fail_next_customer_load = False
                route.fulfill(status=503, content_type='application/json', body=json.dumps({'detail':'隔离测试模拟加载失败'}))
                return
            if request.method in {'POST', 'PATCH', 'PUT', 'DELETE'}:
                writes.append((request.method, path, request.post_data_json))
            if hold_customer_save and request.method == 'POST' and split.path.endswith('/customer-progress'):
                held_saves.append(route)
                return
            response = client.request(request.method, path, content=request.post_data_buffer,
                                      headers={key:value for key,value in request.headers.items() if key.lower() in {'content-type','authorization'}})
            if response.status_code >= 500:
                api_errors.append((path, response.status_code, response.text[:300]))
            route.fulfill(status=response.status_code, body=response.content, headers={'content-type':response.headers.get('content-type','application/json')})
        context.route(re.compile(r'^http://localhost:3000/api/'), route_api)
        page = context.new_page()
        # 保留本地模拟 WebSocket，不连接日常服务；同步回调中 close 会阻塞当前 Playwright 版本。
        page.route_web_socket(re.compile(r'^ws://localhost:3000/api/'), lambda socket: None)
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.set_default_timeout(15000)
        try:
            print('UI: 打开标注页面', flush=True)
            page.goto('http://localhost:3000/annotation-details', wait_until='networkidle')
            print('UI: 查询项目', flush=True)
            page.get_by_placeholder('订单号、项目名称、类型/状态、客户/联系人等').fill(parent.order_no)
            page.get_by_role('button', name='查询', exact=True).first.click()
            expect(page.get_by_role('button', name=parent.project_name, exact=True)).to_be_visible()
            assert page.locator('th').filter(has_text='最新客户进度').count() == 0
            page.get_by_role('button', name=parent.project_name, exact=True).click()
            print('UI: 双线草稿', flush=True)
            dialog = page.locator('.annotation-progress-dialog')
            def choose_track(label, completed=True):
                selector = dialog.locator('.annotation-progress-track-select:visible')
                expect(selector.get_by_role('combobox')).to_be_enabled()
                selector.click()
                list_id = selector.get_by_role('combobox').get_attribute('aria-controls')
                page.locator('#' + list_id).get_by_role('option').filter(has_text=label).click()
                if completed:
                    expect(dialog.locator('.annotation-progress-track-select:visible')).to_contain_text(label)
                    expect(dialog.locator('.annotation-progress-track-select:visible').get_by_role('combobox')).to_be_enabled()
            def choose_mode(label):
                expect(dialog.locator('.progress-entry-mode input').first).to_be_enabled()
                dialog.locator('.progress-entry-mode').get_by_text(label, exact=True).click()
                expect(dialog.locator('.progress-entry-mode .el-radio-button').filter(has_text=label)).to_have_class(re.compile('is-active'))
            expect(dialog).to_be_visible()
            expect(dialog.locator('.progress-history-header')).to_have_text('项目进度记录')
            expect(dialog.locator('.progress-history-header .el-radio-group')).to_have_count(0)
            expect(dialog.locator('.progress-track-switch')).to_have_count(0)
            expect(dialog.locator('.annotation-progress-track-select:visible')).to_contain_text('项目进度')
            project_note = dialog.locator('.progress-entry-panel textarea').first
            project_entry = dialog.locator('.progress-entry-panel').first
            project_note.fill('项目线独立草稿')
            project_entry.locator('.el-date-editor input').fill('2026-10-16 18:45')
            project_entry.locator('.el-date-editor input').press('Enter')
            choose_mode('切换状态')
            expect(project_note).to_have_value('')
            project_note.fill('状态变更独立草稿')
            project_entry.locator('.el-select').first.click()
            page.get_by_role('option', name='试标中', exact=True).click()
            expect(project_entry.locator('.progress-current-status')).to_have_text('当前状态：试标准备')
            choose_mode('补充进度')
            expect(project_note).to_have_value('项目线独立草稿')
            expect(project_entry.locator('.el-date-editor input')).to_have_value('2026-10-16 18:45')
            expect(project_entry.get_by_role('button', name='添加项目进度', exact=True)).to_be_visible()
            dialog.locator('.progress-stage-add').first.click()
            expect(project_note).to_have_value('项目线独立草稿')
            expect(project_entry.locator('.el-date-editor input')).to_have_value('2026-10-16 18:45')
            choose_track('客户进度', completed=False)
            expect(page.locator('.el-message').filter(has_text='隔离测试模拟加载失败')).to_be_visible()
            expect(dialog.locator('.annotation-progress-track-select:visible')).to_contain_text('项目进度')
            expect(project_note).to_have_value('项目线独立草稿')
            expect(project_entry.locator('.el-date-editor input')).to_have_value('2026-10-16 18:45')
            choose_track('客户进度')
            customer = dialog.locator('.customer-progress-entry')
            customer_history = dialog.locator('.customer-progress-history')
            expect(dialog.locator('.progress-history-header b')).to_have_text('客户进度记录')
            expect(dialog.locator('.progress-timeline')).not_to_be_visible()
            customer_note = customer.locator('textarea')
            expect(customer_note).to_have_value('项目线独立草稿')
            expect(customer.locator('.el-date-editor input')).to_have_value('2026-10-16 18:45')
            customer_note.fill('客户线独立草稿')
            choose_track('项目进度')
            expect(project_note).to_have_value('客户线独立草稿')
            expect(project_entry.locator('.el-date-editor input')).to_have_value('2026-10-16 18:45')
            choose_track('客户进度')
            expect(customer_note).to_have_value('客户线独立草稿')
            dialog.get_by_role('button', name='关闭', exact=True).click()
            expect(page.locator('.el-message-box')).to_contain_text('未保存')
            page.get_by_role('button', name='继续填写', exact=True).click()
            expect(customer_note).to_have_value('客户线独立草稿')
            customer_note.fill('客户等待确认报价')
            customer.locator('.el-date-editor input').fill('2026-10-10 17:30:00')
            customer.locator('.el-date-editor input').press('Enter')
            hold_customer_save = True
            customer.get_by_role('button', name='添加客户进度', exact=True).click()
            expect(dialog.locator('.annotation-progress-track-select:visible').get_by_role('combobox')).to_be_disabled()
            expect(customer.get_by_role('button', name='添加客户进度', exact=True)).to_be_disabled()
            footer_submit = dialog.locator('.el-dialog__footer').get_by_role('button', name='添加客户进度', exact=True)
            expect(footer_submit).to_be_disabled()
            footer_submit.evaluate('(element)=>element.click()')
            dialog.locator('.el-dialog__headerbtn').click()
            expect(dialog).to_be_visible()
            assert len(held_saves) == 1
            held_saves.pop().fulfill(status=500, content_type='application/json', body=json.dumps({'detail':'隔离测试模拟保存失败'}))
            expect(customer.get_by_role('button', name='添加客户进度', exact=True)).to_be_enabled()
            expect(customer_note).to_have_value('客户等待确认报价')
            hold_customer_save = False
            customer.get_by_role('button', name='添加客户进度', exact=True).click()
            expect(customer_note).to_have_value('')
            expect(customer_history.locator('.progress-child-note').filter(has_text='客户等待确认报价')).to_be_visible()
            assert db.query(AnnotationProjectStatusHistory).count() == 1
            choose_track('项目进度')
            expect(project_note).to_have_value('')
            choose_mode('切换状态')
            expect(project_note).to_have_value('状态变更独立草稿')
            expect(project_entry.locator('.el-select').first).to_contain_text('试标中')
            choose_mode('补充进度')
            project_note.fill('项目线独立草稿')
            # 将状态草稿转到客户线，补充进度草稿仍独立保留。
            choose_mode('切换状态')
            choose_track('客户进度')
            target = customer_history.locator('.el-timeline-item').filter(has_text='客户等待确认报价')
            target.get_by_role('button', name='编辑', exact=True).click()
            page.get_by_role('button', name='放弃并编辑', exact=True).click()
            customer_note.fill('客户已确认报价')
            # 编辑已保存客户记录时不能转成一条新项目进度。
            choose_track('项目进度', completed=False)
            expect(page.get_by_text('请先保存或取消客户进度编辑，再切换进度归属', exact=True)).to_be_visible()
            expect(dialog.locator('.annotation-progress-track-select:visible')).to_contain_text('客户进度')
            expect(customer_note).to_have_value('客户已确认报价')
            customer.get_by_role('button', name='保存客户进度', exact=True).click()
            expect(customer_note).to_have_value('')
            expect(customer_history.locator('.el-timeline-item').filter(has_text='客户已确认报价')).to_contain_text('修改人')
            # 聊天内容进入当前客户线，目标项目线已有草稿时必须确认追加。
            dialog.get_by_role('tab', name='项目沟通').click()
            message = dialog.locator('.group-message').filter(has_text='客户预计周五确认报价')
            expect(message).to_be_visible()
            message.locator('.el-checkbox').click()
            dialog.get_by_role('button', name=re.compile('转进度')).click()
            expect(customer_note).to_have_value(re.compile('客户预计周五确认报价'))
            current_note = customer_note.input_value()
            current_time = customer.locator('.el-date-editor input').input_value()
            customer_note.fill('甲' * 10000)
            choose_track('项目进度', completed=False)
            expect(page.get_by_text(re.compile('合并后的具体进度超过 10000 字'))).to_be_visible()
            expect(customer_note).to_have_value('甲' * 10000)
            customer_note.fill(current_note)
            choose_track('项目进度', completed=False)
            expect(page.locator('.el-message-box')).to_contain_text('项目进度已有草稿')
            page.get_by_role('button', name='取消切换', exact=True).click()
            expect(customer_note).to_have_value(re.compile('客户预计周五确认报价'))
            expect(customer.locator('.el-date-editor input')).to_have_value(current_time)
            choose_track('项目进度', completed=False)
            expect(page.locator('.el-message-box')).to_contain_text('节点时间使用当前填写')
            page.get_by_role('button', name='追加并切换', exact=True).click()
            expect(project_note).to_have_value(re.compile(r'项目线独立草稿[\s\S]*客户预计周五确认报价'))
            expect(project_entry.locator('.el-date-editor input')).to_have_value(current_time)
            expect(customer_note).to_have_value('')
            dialog.get_by_role('button', name='转到客户进度', exact=True).click()
            expect(customer_note).to_have_value(re.compile('项目线独立草稿'))
            customer_note.fill('')
            # 长时间线只滚动正文，拖拽不越界，关闭按钮仍可用。
            body = dialog.locator('.el-dialog__body')
            footer_before = dialog.locator('.el-dialog__footer').bounding_box()
            body.evaluate('(element)=>element.scrollTop=element.scrollHeight')
            assert abs(dialog.locator('.el-dialog__footer').bounding_box()['y'] - footer_before['y']) < 1
            body.evaluate('(element)=>element.scrollTop=0')
            dialog.locator('.el-dialog__header').hover()
            initial = dialog.bounding_box()
            header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x']+15, header['y']+15); page.mouse.down(); page.mouse.move(945,870,steps=12); page.mouse.up()
            dragged = dialog.bounding_box()
            assert dragged['x'] >= -1 and dragged['y'] >= -1 and dragged['x']+dragged['width'] <= 955 and dragged['y']+dragged['height'] <= 885
            dialog.locator('.el-dialog__headerbtn').click()
            expect(page.locator('.el-message-box')).to_contain_text('未保存')
            page.get_by_role('button', name='继续填写', exact=True).click()
            expect(dialog).to_be_visible()
            choose_track('项目进度')
            choose_mode('切换状态')
            expect(project_note).to_have_value('')
            project_note.fill('关闭保护状态草稿')
            dialog.locator('.el-dialog__headerbtn').click()
            page.get_by_role('button', name='放弃并关闭', exact=True).click()
            expect(dialog).not_to_be_visible()
            page.get_by_role('button', name=parent.project_name, exact=True).click()
            expect(dialog).to_be_visible()
            dialog.locator('.el-dialog__header').hover()
            restored = dialog.bounding_box()
            assert abs(restored['x']-initial['x']) < 2 and abs(restored['y']-884*0.05) < 2
            # 两处提交同时触发只能写一次；隐藏模式的空字段不阻断当前提交。
            expect(project_note).to_have_value('')
            project_note.fill('实际项目补充进度')
            choose_track('客户进度')
            customer_note.fill('状态切换期间保留的客户草稿')
            choose_track('项目进度')
            choose_mode('切换状态')
            project_entry.locator('.el-select').first.click()
            page.get_by_role('option', name='试标中', exact=True).click()
            project_entry.get_by_role('button', name='确认切换项目状态', exact=True).click()
            expect(project_entry).to_contain_text('请填写变更说明')
            expect(project_note).to_be_focused()
            project_note.fill('确认进入试标中')
            status_writes_before = len([item for item in writes if item[1].endswith('/status')])
            dialog.evaluate("element=>Array.from(element.querySelectorAll('button')).filter(button=>button.textContent.trim()==='确认切换项目状态').forEach(button=>button.click())")
            expect(project_entry.locator('.progress-current-status')).to_have_text('当前状态：试标中')
            expect(project_note).to_have_value('')
            expect(project_entry.locator('.el-form-item.is-error')).to_have_count(0)
            assert len([item for item in writes if item[1].endswith('/status')]) == status_writes_before + 1
            status_write = [item for item in writes if item[1].endswith('/status')][-1][2]
            assert status_write['progress_only'] is False and status_write['effective_on'].endswith('+08:00')
            choose_mode('补充进度')
            expect(project_note).to_have_value('状态切换期间保留的客户草稿')
            project_note.fill('实际项目补充进度')
            project_entry.get_by_role('button', name='添加项目进度', exact=True).click()
            expect(project_note).to_have_value('')
            expect(dialog.locator('.progress-child-note').filter(has_text='实际项目补充进度')).to_be_visible()
            progress_write = [item for item in writes if item[1].endswith('/status')][-1][2]
            assert progress_write['progress_only'] is True
            db.expire_all()
            assert parent.project_status == 'trial_in_progress'
            assert db.query(AnnotationProjectStatusHistory).count() == 3
            choose_track('客户进度')
            expect(customer_note).to_have_value('')
            choose_track('项目进度')
            expect(project_entry.locator('.el-form-item.is-error')).to_have_count(0)
            page.set_viewport_size({'width':1130,'height':884})
            selector_box = project_entry.locator('.annotation-progress-track-select').bounding_box()
            note_box = project_note.bounding_box()
            assert selector_box['x'] + selector_box['width'] <= note_box['x']
            expect(page.locator('.el-message')).to_have_count(0)
            page.screenshot(path=str(output/'project-progress-desktop.png'), full_page=True, animations='disabled')
            page.set_viewport_size({'width':390,'height':844})
            expect(project_entry.get_by_role('button', name='添加项目进度', exact=True)).to_be_visible()
            expect(dialog.locator('.el-dialog__footer').get_by_role('button', name='添加项目进度', exact=True)).to_be_visible()
            selector_box = project_entry.locator('.annotation-progress-track-select').bounding_box()
            note_box = project_note.bounding_box()
            assert selector_box['y'] + selector_box['height'] <= note_box['y']
            assert abs(selector_box['x'] - note_box['x']) <= 1
            for button in project_entry.locator('.progress-entry-actions').get_by_role('button').all():
                bounds = button.bounding_box()
                assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= 390
            page.screenshot(path=str(output/'project-progress-mobile.png'), full_page=True, animations='disabled')
            page.set_viewport_size({'width':954,'height':884})
            dialog.get_by_role('button', name='关闭', exact=True).click()
            # 可选字段立即更新并刷新持久化，默认组合不增加客户列。
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings = page.locator('.table-column-settings-popover')
            settings.locator('.el-checkbox').filter(has_text='最新客户进度').click()
            settings.locator('.el-checkbox').filter(has_text='客户进度时间').click()
            page.get_by_role('button', name='字段设置', exact=True).click()
            expect(page.get_by_role('button', name='客户已确认报价', exact=True)).to_be_visible()
            page.reload(wait_until='networkidle')
            expect(page.locator('th').filter(has_text='最新客户进度')).to_be_visible()
            page.get_by_role('button', name='客户已确认报价', exact=True).click()
            expect(customer_history).to_be_visible()
            target = customer_history.locator('.el-timeline-item').filter(has_text='客户已确认报价')
            target.get_by_role('button', name='删除', exact=True).click()
            deletion = page.get_by_role('dialog', name='删除客户进度', exact=True)
            expect(deletion).to_be_visible()
            deletion.get_by_role('button', name='确认删除').click()
            expect(deletion).to_contain_text('请填写删除原因')
            deletion.locator('textarea').fill('隔离验收删除')
            deletion.get_by_role('button', name='确认删除').click()
            expect(deletion).not_to_be_visible()
            expect(customer_history.locator('.progress-child-note').filter(has_text='客户已确认报价')).to_have_count(0)
            dialog.get_by_role('button', name='关闭', exact=True).click()
            # 检索客户线并打开上下文，记录定位带所属线。
            page.get_by_role('button', name='进度记录', exact=True).click()
            search_dialog = page.locator('.annotation-progress-search-dialog')
            expect(search_dialog).to_be_visible()
            search_dialog.get_by_placeholder('检索项目进度、客户进度或状态变更说明').fill('历史客户反馈')
            search_dialog.get_by_role('button', name='查询', exact=True).click()
            expect(search_dialog.locator('.progress-search-item').first).to_contain_text('客户进度')
            search_dialog.locator('.progress-search-item').first.get_by_role('button', name='查看上下文').click()
            expect(customer_history).to_be_visible()
            expect(customer_history.locator('.is-progress-search-target')).to_have_count(1)
            dialog.locator('.el-dialog__body').evaluate('(element)=>element.scrollTop=0')
            expect(page.locator('.el-message')).to_have_count(0)
            page.screenshot(path=str(output/'customer-progress-desktop.png'), full_page=True, animations='disabled')
            page.set_viewport_size({'width':390,'height':844})
            expect(dialog.get_by_role('button', name='关闭', exact=True)).to_be_visible()
            small = dialog.bounding_box()
            assert small['width'] <= 358 and small['y']+small['height'] <= 845
            page.screenshot(path=str(output/'customer-progress-mobile.png'), full_page=True, animations='disabled')
            dialog.get_by_role('button', name='关闭', exact=True).click()
            # 同一浏览器切换用户：新用户使用默认列，原用户配置仍保留。
            page.set_viewport_size({'width':1252,'height':884})
            client = api_client(db, users[1])
            page.reload(wait_until='networkidle')
            expect(page.locator('th').filter(has_text='最新客户进度')).to_have_count(0)
            client = api_client(db, users[0])
            page.reload(wait_until='networkidle')
            expect(page.locator('th').filter(has_text='最新客户进度')).to_be_visible()
            page.get_by_role('button', name='字段设置', exact=True).click()
            settings.get_by_role('button', name='恢复默认', exact=True).click()
            expect(page.locator('th').filter(has_text='最新客户进度')).to_have_count(0)
            page.get_by_role('button', name='字段设置', exact=True).click()
            # 只读用户仍可统一切换两类历史，页面不出现填写和提交入口。
            from models import Role, RolePermission, UserRole
            readonly_role = Role(role_name='progress-readonly-' + uuid4().hex[:8])
            db.add(readonly_role); db.flush()
            db.add(RolePermission(role_id=readonly_role.id, permission_code='projects:read'))
            db.add(UserRole(role_id=readonly_role.id, user_id=users[2].id)); db.commit()
            client = api_client(db, users[2])
            page.reload(wait_until='networkidle')
            page.get_by_role('button', name=parent.project_name, exact=True).click()
            expect(dialog.locator('.progress-history-header .annotation-progress-track-select')).to_be_visible()
            expect(dialog.locator('.progress-entry-panel')).to_have_count(0)
            expect(dialog.get_by_role('button', name='添加项目进度', exact=True)).to_have_count(0)
            choose_track('客户进度')
            expect(dialog.locator('.progress-history-header b')).to_have_text('客户进度记录')
            expect(customer_history.locator('.progress-child-note').first).to_be_visible()
            expect(customer_history.get_by_role('button', name='编辑', exact=True)).to_have_count(0)
            dialog.get_by_role('button', name='关闭', exact=True).click()
            assert not page_errors, page_errors
            assert not api_errors, api_errors
        except Exception:
            page.screenshot(path=str(output/'failure.png'), full_page=True)
            (output/'failure.html').write_text(page.content(), encoding='utf-8')
            (output/'errors.json').write_text(json.dumps({'page':page_errors,'api':api_errors}, ensure_ascii=False, indent=2), encoding='utf-8')
            raise
        finally:
            context.close(); browser.close(); client.close()
