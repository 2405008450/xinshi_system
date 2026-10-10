"""实际 Vue 页面 + FastAPI + 隔离 PostgreSQL；所有 /api 请求拦截到测试客户端。"""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from test_annotation_customer_progress import environment, api_client, add


def test_customer_progress_browser_workflow(environment):
    from playwright.sync_api import sync_playwright, expect
    db, users, parent, child, _engine = environment
    client = api_client(db, users[0])
    chat_response = client.post(f'/project-chat/annotation/{parent.id}/messages', json={'content':'客户预计周五确认报价', 'client_message_id':str(uuid4())})
    assert chat_response.status_code in (200, 201), chat_response.text
    for index in range(14):
        add(db, parent, users[0], f'历史客户反馈 {index}', f'2026-10-09T{index + 1:02d}:30:00+08:00')
    output = Path(__file__).resolve().parents[1] / '.tmp' / 'customer-progress-ui'
    output.mkdir(parents=True, exist_ok=True)
    page_errors, api_errors, held_saves = [], [], []
    hold_customer_save = False
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width':1252,'height':884}, timezone_id='America/Los_Angeles')
        info = {'token':'isolated-test-token', 'user_id':str(users[0].id), 'user_name':users[0].username,
                'user_full_name':users[0].full_name, 'user_permissions':json.dumps(['projects:read','projects:write']), 'user_roles':'[]'}
        context.add_init_script('Object.entries('+json.dumps(info)+').forEach(([key,value])=>localStorage.setItem(key,value))')
        def route_api(route):
            request = route.request
            split = urlsplit(request.url)
            # 任何业务请求都只进入本轮隔离数据库；不使用日常代理后端。
            assert split.path.startswith('/api/')
            path = split.path[4:] + ('?' + split.query if split.query else '')
            print(f'UI API {request.method} {split.path[4:]}', flush=True)
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
            expect(dialog).to_be_visible()
            expect(dialog.locator('.progress-track-switch .el-radio-button').filter(has_text='项目进度')).to_have_class(re.compile('is-active'))
            project_note = dialog.locator('.progress-entry-panel textarea').first
            project_note.fill('项目线独立草稿')
            dialog.get_by_text('客户进度', exact=True).first.click()
            customer = dialog.locator('.customer-progress')
            customer_note = customer.locator('textarea')
            customer_note.fill('客户线独立草稿')
            dialog.get_by_text('项目进度', exact=True).first.click()
            expect(project_note).to_have_value('项目线独立草稿')
            dialog.get_by_text('客户进度', exact=True).first.click()
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
            expect(dialog.locator('.progress-track-switch input').first).to_be_disabled()
            expect(customer.get_by_role('button', name='添加客户进度', exact=True)).to_be_disabled()
            dialog.locator('.el-dialog__headerbtn').click()
            expect(dialog).to_be_visible()
            assert len(held_saves) == 1
            held_saves.pop().fulfill(status=500, content_type='application/json', body=json.dumps({'detail':'隔离测试模拟保存失败'}))
            expect(customer.get_by_role('button', name='添加客户进度', exact=True)).to_be_enabled()
            expect(customer_note).to_have_value('客户等待确认报价')
            hold_customer_save = False
            customer.get_by_role('button', name='添加客户进度', exact=True).click()
            expect(customer_note).to_have_value('')
            expect(customer.locator('.progress-child-note').filter(has_text='客户等待确认报价')).to_be_visible()
            assert db.query(__import__('annotation_ops_models').AnnotationProjectStatusHistory).count() == 0
            # 保存只清除客户草稿，项目草稿保留；编辑覆盖版本而不新增记录。
            target = customer.locator('.el-timeline-item').filter(has_text='客户等待确认报价')
            target.get_by_role('button', name='编辑', exact=True).click()
            customer_note.fill('客户已确认报价')
            customer.get_by_role('button', name='保存客户进度', exact=True).click()
            expect(customer_note).to_have_value('')
            expect(customer.locator('.el-timeline-item').filter(has_text='客户已确认报价')).to_contain_text('修改人')
            # 聊天内容进入当前客户线，目标项目线已有草稿时必须确认追加。
            dialog.get_by_role('tab', name='项目沟通').click()
            message = dialog.locator('.group-message').filter(has_text='客户预计周五确认报价')
            expect(message).to_be_visible()
            message.locator('.el-checkbox').click()
            dialog.get_by_role('button', name=re.compile('转进度')).click()
            expect(customer_note).to_have_value(re.compile('客户预计周五确认报价'))
            customer.get_by_role('button', name='转到项目进度', exact=True).click()
            expect(page.locator('.el-message-box')).to_contain_text('项目进度已有草稿')
            page.get_by_role('button', name='追加并转入', exact=True).click()
            expect(project_note).to_have_value(re.compile(r'项目线独立草稿[\s\S]*客户预计周五确认报价'))
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
            page.mouse.move(header['x']+15, header['y']+15); page.mouse.down(); page.mouse.move(1240,870,steps=12); page.mouse.up()
            dragged = dialog.bounding_box()
            assert dragged['x'] >= -1 and dragged['y'] >= -1 and dragged['x']+dragged['width'] <= 1253 and dragged['y']+dragged['height'] <= 885
            dialog.locator('.el-dialog__headerbtn').click()
            expect(dialog).not_to_be_visible()
            page.get_by_role('button', name=parent.project_name, exact=True).click()
            expect(dialog).to_be_visible()
            dialog.locator('.el-dialog__header').hover()
            restored = dialog.bounding_box()
            assert abs(restored['x']-initial['x']) < 2 and abs(restored['y']-884*0.05) < 2
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
            expect(dialog.locator('.customer-progress')).to_be_visible()
            target = dialog.locator('.customer-progress .el-timeline-item').filter(has_text='客户已确认报价')
            target.get_by_role('button', name='删除', exact=True).click()
            deletion = page.get_by_role('dialog', name='删除客户进度', exact=True)
            expect(deletion).to_be_visible()
            deletion.get_by_role('button', name='确认删除').click()
            expect(deletion).to_contain_text('请填写删除原因')
            deletion.locator('textarea').fill('隔离验收删除')
            deletion.get_by_role('button', name='确认删除').click()
            expect(deletion).not_to_be_visible()
            expect(dialog.locator('.customer-progress .progress-child-note').filter(has_text='客户已确认报价')).to_have_count(0)
            dialog.get_by_role('button', name='关闭', exact=True).click()
            # 检索客户线并打开上下文，记录定位带所属线。
            page.get_by_role('button', name='进度记录', exact=True).click()
            search_dialog = page.locator('.annotation-progress-search-dialog')
            expect(search_dialog).to_be_visible()
            search_dialog.get_by_placeholder('检索项目进度、客户进度或状态变更说明').fill('历史客户反馈')
            search_dialog.get_by_role('button', name='查询', exact=True).click()
            expect(search_dialog.locator('.progress-search-item').first).to_contain_text('客户进度')
            search_dialog.locator('.progress-search-item').first.get_by_role('button', name='查看上下文').click()
            expect(dialog.locator('.customer-progress')).to_be_visible()
            expect(dialog.locator('.customer-progress .is-progress-search-target')).to_have_count(1)
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
            assert not page_errors, page_errors
            assert not api_errors, api_errors
        except Exception:
            page.screenshot(path=str(output/'failure.png'), full_page=True)
            (output/'failure.html').write_text(page.content(), encoding='utf-8')
            (output/'errors.json').write_text(json.dumps({'page':page_errors,'api':api_errors}, ensure_ascii=False, indent=2), encoding='utf-8')
            raise
        finally:
            context.close(); browser.close(); client.close()
