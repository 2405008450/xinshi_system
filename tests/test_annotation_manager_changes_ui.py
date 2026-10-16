"""真实页面使用隔离数据库处理全部接口，绝不写入日常业务库。"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from test_annotation_manager_changes import environment, reader_client, project_managers, inherited_project


def test_reader_manager_selection_reason_cancel_drag_and_history(environment):
    from playwright.sync_api import sync_playwright, expect
    db, users, parent, child, _ = environment
    inherited_project(db, users, parent, child)
    from models import AppUser
    from uuid import uuid4
    db.add_all(AppUser(username='manager-scroll-'+uuid4().hex,password_hash='disabled',full_name=f'滚动候选人{index:02d}',is_active=True) for index in range(18))
    db.commit()
    client = reader_client(db, users[0])
    errors, mutations = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width':1360,'height':900}, timezone_id='America/Los_Angeles')
        info = {'token':'isolated-manager-test','user_id':str(users[0].id),'user_name':users[0].username,
                'user_full_name':users[0].full_name,'user_permissions':json.dumps(['projects:read']),'user_roles':'[]'}
        context.add_init_script('if(!localStorage.getItem("token")) Object.entries('+json.dumps(info)+').forEach(([key,value])=>localStorage.setItem(key,value))')
        def route_api(route):
            request = route.request; split = urlsplit(request.url)
            assert split.path.startswith('/api/')
            path = split.path[4:] + ('?' + split.query if split.query else '')
            if request.method in {'PATCH','PUT','POST','DELETE'}:
                mutations.append((request.method,path,request.post_data))
            response = client.request(request.method,path,content=request.post_data_buffer,
                headers={k:v for k,v in request.headers.items() if k.lower() in {'content-type','authorization'}})
            if response.status_code >= 500:
                errors.append((path,response.status_code,response.text[:300]))
            route.fulfill(status=response.status_code,body=response.content,headers={'content-type':response.headers.get('content-type','application/json')})
        context.route(re.compile(r'^http://localhost:3000/api/'),route_api)
        page = context.new_page()
        page.route_web_socket(re.compile(r'^ws://localhost:3000/api/'),lambda socket:None)
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.set_default_timeout(15000)
        output = Path(__file__).resolve().parents[1]/'.tmp'/'annotation-manager-ui'
        output.mkdir(parents=True,exist_ok=True)
        try:
            page.goto(f'http://localhost:3000/annotation-details?projectId={parent.id}',wait_until='networkidle')
            page.get_by_role('button',name='字段设置',exact=True).click()
            page.locator('.table-column-settings-popover:visible .el-checkbox').filter(has_text='客户经理').click()
            page.get_by_placeholder('订单号、项目名称、类型/状态、客户/联系人等').click()
            controls = page.locator('.annotation-table .inline-manager-select:visible')
            expect(controls).to_have_count(2)
            expect(controls.nth(0)).to_be_visible()
            assert page.get_by_role('button',name='新增标注项目',exact=True).count() == 0
            # 选择或关闭下拉均只暂存，确认后才提交；首次分配免原因。
            controls.nth(1).click()
            dropdown = page.locator('.el-select-dropdown:visible')
            expect(page.locator('.el-popper.annotation-manager-select-popper:visible')).not_to_have_class(re.compile('el-zoom-in-top-enter-active'))
            footer = dropdown.locator('.el-select-dropdown__footer')
            expect(footer.get_by_role('button',name='确认项目经理调整',exact=True)).to_be_disabled()
            # 只有人员列表滚动，底部确认和取消始终可见。
            scroll = dropdown.locator('.el-select-dropdown__wrap')
            original_footer = footer.bounding_box()
            scroll.evaluate('element => { element.scrollTop = element.scrollHeight }')
            assert scroll.evaluate('element => element.scrollTop') > 0
            expect(footer.get_by_role('button',name='取消项目经理调整',exact=True)).to_be_visible()
            assert abs(footer.bounding_box()['y'] - original_footer['y']) < 4
            scroll.evaluate('element => { element.scrollTop = 0 }')
            dropdown.get_by_text(users[1].full_name,exact=True).click()
            dropdown.get_by_text(users[2].full_name,exact=True).click()
            assert not any('/managers' in path for _,path,_ in mutations)
            page.get_by_placeholder('订单号、项目名称、类型/状态、客户/联系人等').click()
            expect(dropdown).not_to_be_visible()
            expect(page.locator('.annotation-manager-reason-dialog')).not_to_be_visible()
            assert not any('/managers' in path for _,path,_ in mutations)
            expect(page.get_by_role('button',name='确认项目经理调整',exact=True)).not_to_be_visible()
            controls.nth(1).click()
            expect(dropdown.locator('.manager-selection-count')).to_have_text('已选 2 人')
            expect(dropdown.locator('.el-select-dropdown__item.is-selected')).to_have_count(2)
            # 即便正在搜索，Esc 也直接收起；重新打开后草稿仍在。
            controls.nth(1).locator('input').fill('客户')
            page.keyboard.press('Escape')
            expect(dropdown).not_to_be_visible()
            assert not any('/managers' in path for _,path,_ in mutations)
            controls.nth(1).click()
            expect(dropdown.locator('.manager-selection-count')).to_have_text('已选 2 人')
            page.screenshot(path=str(output/'manager-dropdown-footer.png'),full_page=True)
            expect(page.get_by_role('button',name='确认项目经理调整',exact=True)).to_be_visible()
            with page.expect_response(lambda response:'/managers' in response.url and response.request.method=='PATCH'):
                page.get_by_role('button',name='确认项目经理调整',exact=True).click()
            expect(dropdown).not_to_be_visible()
            expect(page.locator('.annotation-manager-reason-dialog')).not_to_be_visible()
            assert project_managers(client.get(f'/projects/annotation/{parent.id}').json()) == {str(users[1].id),str(users[2].id)}
            # 点 X 不立即弹窗；取消草稿无写入；客户经理也采用相同的暂存规则。
            controls.nth(1).locator('.el-tag__close').first.click()
            dialog = page.locator('.annotation-manager-reason-dialog')
            expect(dialog).not_to_be_visible()
            controls.nth(1).click()
            expect(page.get_by_role('button',name='确认项目经理调整',exact=True)).to_be_visible()
            assert sum('/managers' in path for _,path,_ in mutations) == 1
            page.get_by_role('button',name='取消项目经理调整',exact=True).click()
            expect(dropdown).not_to_be_visible()
            expect(page.get_by_role('button',name='确认项目经理调整',exact=True)).not_to_be_visible()
            controls.nth(0).click()
            page.locator('.el-select-dropdown:visible').get_by_text(users[1].full_name,exact=True).click()
            expect(page.get_by_role('button',name='确认客户经理调整',exact=True)).to_be_visible()
            expect(dialog).not_to_be_visible()
            page.get_by_role('button',name='取消客户经理调整',exact=True).click()
            assert client.get(f'/projects/annotation/{parent.id}').json()['client_manager_id'] is None
            # 真正确认移除时才填写原因；取消弹窗恢复原值。
            controls.nth(1).locator('.el-tag__close').first.click()
            controls.nth(1).click()
            page.get_by_role('button',name='确认项目经理调整',exact=True).click()
            expect(dropdown).not_to_be_visible()
            expect(dialog).to_be_visible()
            dialog.get_by_role('button',name='确认调整',exact=True).click()
            expect(dialog.get_by_text('请填写调整原因',exact=True)).to_be_visible()
            original = dialog.bounding_box()
            header = dialog.locator('.el-dialog__header').bounding_box()
            page.mouse.move(header['x']+35,header['y']+20); page.mouse.down(); page.mouse.move(header['x']+155,header['y']+90,steps=8); page.mouse.up()
            moved = dialog.bounding_box()
            assert moved['x'] > original['x']+60
            page.mouse.move(moved['x']+35,moved['y']+20); page.mouse.down(); page.mouse.move(-900,-900,steps=8); page.mouse.up()
            bounded = dialog.bounding_box()
            assert bounded['x'] >= -1 and bounded['y'] >= -1
            dialog.locator('.el-dialog__headerbtn').click()
            expect(dialog).not_to_be_visible()
            assert project_managers(client.get(f'/projects/annotation/{parent.id}').json()) == {str(users[1].id),str(users[2].id)}
            # 移除旧人后继续选择新人，整个换人过程只确认一次、只提交一次。
            controls.nth(1).locator('.el-tag__close').first.click()
            expect(dialog).not_to_be_visible()
            controls.nth(1).click()
            page.locator('.el-select-dropdown:visible').get_by_text(users[0].full_name,exact=True).click()
            page.get_by_placeholder('订单号、项目名称、类型/状态、客户/联系人等').click()
            expect(dropdown).not_to_be_visible()
            expect(dialog).not_to_be_visible()
            assert sum('/managers' in path for _,path,_ in mutations) == 1
            controls.nth(1).click()
            page.screenshot(path=str(output/'pending-manager-change.png'),full_page=True)
            page.get_by_role('button',name='确认项目经理调整',exact=True).click()
            expect(dialog).to_be_visible()
            expect(dialog.locator('.manager-change-summary')).not_to_contain_text('未分配')
            page.wait_for_function('expected => {const box=document.querySelector(".annotation-manager-reason-dialog").getBoundingClientRect();return Math.abs(box.x-expected.x)<3 && Math.abs(box.y-expected.y)<3}',arg=original)
            reopened = dialog.bounding_box()
            assert abs(reopened['x']-original['x']) < 3 and abs(reopened['y']-original['y']) < 3
            dialog.locator('textarea').fill('页面验收：调整项目分工')
            with page.expect_response(lambda response:'/managers' in response.url and response.request.method=='PATCH'):
                dialog.get_by_role('button',name='确认调整',exact=True).click()
            expect(dialog).not_to_be_visible()
            assert sum('/managers' in path for _,path,_ in mutations) == 2
            assert project_managers(client.get(f'/projects/annotation/{parent.id}').json()) == {str(users[0].id),str(users[2].id)}
            page.get_by_role('button',name='交接',exact=True).click()
            transfer = page.locator('.annotation-manager-transfer-dialog')
            expect(transfer.get_by_role('tab',name='变更记录')).to_be_visible()
            assert transfer.get_by_role('tab',name='批量交接').count() == 0
            expect(transfer.get_by_text('页面验收：调整项目分工',exact=True).first).to_be_visible()
            expect(transfer.get_by_text(f'操作人：{users[0].full_name}',exact=True).first).to_be_visible()
            transfer.get_by_role('button',name='高级筛选',exact=True).click()
            advanced = page.locator('.manager-log-advanced-popover')
            expect(advanced).to_be_visible()
            advanced.get_by_role('button',name='关闭',exact=True).click()
            expect(advanced).not_to_be_visible()
            page.screenshot(path=str(output/'reader-history.png'),full_page=True)
            transfer.get_by_role('button',name='关闭',exact=True).click()
            # 小屏重新打开仍在视口内。
            page.set_viewport_size({'width':820,'height':650})
            controls.nth(1).locator('.el-tag__close').first.click()
            controls.nth(1).click()
            page.get_by_role('button',name='确认项目经理调整',exact=True).click()
            expect(dialog).to_be_visible()
            box = dialog.bounding_box()
            assert box['x'] >= 0 and box['x']+box['width'] <= 821
            dialog.get_by_role('button',name='取消',exact=True).click()
            # 管理员仍可使用批量交接，接收人不要求任何特定角色。
            from models import Role, RolePermission, UserRole
            admin_role = Role(role_name='超级管理员')
            db.add(admin_role); db.flush()
            db.add_all([UserRole(user_id=users[0].id,role_id=admin_role.id),RolePermission(role_id=admin_role.id,permission_code='*')]); db.commit()
            page.evaluate('localStorage.setItem("user_roles",JSON.stringify(["超级管理员"]));localStorage.setItem("user_permissions",JSON.stringify(["*"]))')
            page.set_viewport_size({'width':1360,'height':900})
            page.goto(f'http://localhost:3000/annotation-details?projectId={parent.id}',wait_until='networkidle')
            page.get_by_role('button',name='交接',exact=True).click()
            expect(transfer.get_by_role('tab',name='变更记录')).to_have_attribute('aria-selected','true')
            transfer.get_by_role('tab',name='批量交接').click()
            expect(transfer.locator('.manager-transfer-form .el-select')).to_have_count(2)
            transfer.locator('.manager-transfer-form .el-select').nth(1).click()
            expect(page.locator('.el-select-dropdown:visible').get_by_text(users[0].full_name,exact=True)).to_be_visible()
            page.keyboard.press('Escape')
            transfer.get_by_role('button',name='取消',exact=True).click()
            # 编辑表单的经理变更也要求原因，并与主表单正确保持嵌套层级。
            page.goto(f'http://localhost:3000/annotation-details?projectId={parent.id}&openEditor=1',wait_until='networkidle')
            editor = page.locator('.annotation-editor-dialog')
            expect(editor).to_be_visible()
            client_field = editor.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=re.compile('^客户经理$')))
            client_field.locator('.el-select').click()
            page.locator('.el-select-dropdown:visible').get_by_text(users[2].full_name,exact=True).click()
            editor.get_by_role('button',name='保存',exact=True).click()
            # 客户经理此前未分配，首次保存免原因；随后更换需说明原因。
            expect(editor).not_to_be_visible()
            page.goto(f'http://localhost:3000/annotation-details?projectId={parent.id}&openEditor=1',wait_until='networkidle')
            expect(editor).to_be_visible()
            client_field.locator('.el-select').click()
            page.locator('.el-select-dropdown:visible').get_by_text(users[1].full_name,exact=True).click()
            editor.get_by_role('button',name='保存',exact=True).click()
            expect(dialog).to_be_visible()
            dialog.locator('textarea').fill('编辑表单：客户对接调整')
            with page.expect_response(lambda response:response.request.method=='PUT' and f'/annotation/{parent.id}' in response.url):
                dialog.get_by_role('button',name='确认调整',exact=True).click()
            expect(editor).not_to_be_visible()
            assert client.get(f'/projects/annotation/{parent.id}').json()['client_manager_id'] == str(users[1].id)
            assert not errors, errors
        except Exception:
            page.screenshot(path=str(output/'failure.png'),full_page=True)
            raise
        finally:
            context.close(); browser.close()
