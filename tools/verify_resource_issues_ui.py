"""真实构建及隔离接口的浏览器验收；禁止连接日常服务端口。"""
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from playwright.sync_api import expect, sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE=os.getenv('ISSUE_UI_BASE','')
OUTPUT=Path(os.getenv('ISSUE_UI_OUTPUT', str(ROOT/'.tmp/resource-issues-qa')))


def run():
    if os.getenv('RESOURCE_ISSUES_QA')!='1' or urlparse(BASE).hostname!='localhost' or urlparse(BASE).port in {None,3000,8000}:
        raise SystemExit('仅允许专用本机隔离服务')
    errors=[];requests=[];results=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,channel='msedge')
        def context_for(actor='collector',width=1440,height=900):
            context=browser.new_context(viewport=dict(width=width,height=height),timezone_id='America/Los_Angeles')
            context.add_init_script(f"localStorage.setItem('token','isolated-issue-{actor}');localStorage.setItem('user_roles','[]')")
            page=context.new_page();page.set_default_timeout(10000)
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('request',lambda request:requests.append((request.method,request.url)))
            page.goto(BASE+'/resource-management/resource-development?section=issues')
            expect(page.get_by_role('tab',name='开拓问题',exact=True)).to_be_visible()
            expect(page.locator('.issue-panel .el-table__body-wrapper tr.el-table__row').first).to_be_visible()
            return context,page
        context,page=context_for()
        headers={'Authorization':'Bearer isolated-issue-collector'}
        path='/resource-development/issues'
        def api(method,route,data=None,actor='collector'):
            response=context.request.fetch(BASE+'/api'+route,method=method,data=data,headers={'Authorization':f'Bearer isolated-issue-{actor}'})
            assert response.ok,f'{method} {route}: {response.status} {response.text()}'
            return response.json()
        fixtures=api('GET','/qa/fixtures')
        def rows():return page.locator('.issue-panel .el-table__body-wrapper tr.el-table__row')
        search=page.get_by_placeholder('内容、来源、提出人、执行人、进展、备注')
        def filter_to(value):
            search.fill(value);expect(rows()).to_have_count(1);expect(rows().first).to_contain_text(value)
        def item(dialog,label):return dialog.locator('.el-form-item').filter(has=page.locator('.el-form-item__label',has_text=label)).first
        def choose(dialog,label,value):
            control=item(dialog,label).locator('.el-select');control.click()
            menu_id=control.get_by_role('combobox').get_attribute('aria-controls')
            try:
                expect(control.get_by_role('combobox')).to_have_attribute('aria-expanded','true')
                page.wait_for_timeout(350)
                page.locator(f'#{menu_id}').get_by_role('option',name=value,exact=True).click();page.keyboard.press('Escape')
            except Exception:
                page.screenshot(path=str(OUTPUT/'failure.png'))
                (OUTPUT/'failure.html').write_text(page.content(),encoding='utf-8')
                raise
        def button(dialog,label):return dialog.get_by_role('button',name=label,exact=True)
        def footer(dialog):
            for position in (0,300,100000):
                dialog.locator('.el-dialog__body').evaluate('(el,value)=>el.scrollTop=value',position)
                box=dialog.locator('.el-dialog__footer').bounding_box()
                assert box and box['y']>=0 and box['y']+box['height']<=page.viewport_size['height']+1
            dialog.locator('.el-dialog__body').evaluate('el=>el.scrollTop=0')
        def drag(dialog):
            page.wait_for_timeout(350)
            content=dialog.locator('.el-dialog');header=dialog.locator('.dialog-field-search-header__title');box=header.bounding_box();before=content.bounding_box()
            # 普通窗口标题可拖动，避开右侧字段搜索控件。
            x=box['x']+box['width']*.5;y=box['y']+box['height']*.5
            page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+60,y+30,steps=8);page.mouse.up()
            moved=content.bounding_box();assert abs(moved['x']-before['x'])>20 or abs(moved['y']-before['y'])>15
            box=header.bounding_box();page.mouse.move(box['x']+box['width']*.5,box['y']+box['height']*.5);page.mouse.down();page.mouse.move(5000,5000,steps=12);page.mouse.up()
            final=content.bounding_box();assert final['x']>=-1 and final['y']>=-1 and final['x']+final['width']<=page.viewport_size['width']+1 and final['y']+final['height']<=page.viewport_size['height']+1
            return before
        expect(rows()).to_have_count(20)
        before=len([r for r in requests if r[0]=='GET' and '/issues?' in r[1]])
        search.fill('验收问题23');page.wait_for_timeout(120)
        assert len([r for r in requests if r[0]=='GET' and '/issues?' in r[1]])==before
        expect(rows()).to_have_count(1)
        search.fill('');expect(rows()).to_have_count(20)
        results.append('搜索防抖与清空立即查询')
        # 默认字段、全部取消、恢复默认和刷新持久化。
        page.get_by_role('button',name='字段设置',exact=True).click()
        settings=page.locator('.el-popover:visible').filter(has=page.get_by_role('button',name='恢复默认',exact=True))
        for checkbox in settings.locator('.el-checkbox').all():
            if checkbox.locator('input').is_checked():checkbox.click()
        expect(page.locator('.issue-panel .el-table__header-wrapper th')).to_have_count(3)
        settings.locator('.el-checkbox').filter(has_text='备注').click()
        page.get_by_role('heading',name='开拓问题',exact=True).click();page.reload()
        expect(page.locator('.issue-panel .el-table__header-wrapper').get_by_text('备注',exact=True)).to_be_visible()
        page.get_by_role('button',name='字段设置',exact=True).click();page.get_by_role('button',name='恢复默认',exact=True).click();page.get_by_role('heading',name='开拓问题',exact=True).click()
        results.append('字段全部取消、恢复默认和持久化')
        # 高级条件的弹出不改变主表位置，关闭保留条件，重置清空。
        table_y=page.locator('.issue-panel .el-table').bounding_box()['y']
        page.get_by_role('button',name='高级筛选',exact=True).click()
        advanced=page.locator('.issue-advanced:visible');expect(advanced).to_be_visible()
        assert abs(page.locator('.issue-panel .el-table').bounding_box()['y']-table_y)<1
        choose(advanced,'任务状态','进行中');expect(rows()).to_have_count(0)
        button(advanced,'关闭').click();expect(page.get_by_role('button',name='高级筛选（1）',exact=True)).to_be_visible()
        page.get_by_role('button',name='重置',exact=True).click();expect(rows()).to_have_count(20)
        results.append('高级筛选悬浮、计数、关闭保留及重置')
        filter_to('验收问题00')
        page.get_by_role('button',name='查看详情',exact=True).click();detail=page.locator('.issue-detail-popover:visible')
        expect(detail.get_by_text('开拓问题详情',exact=True)).to_be_visible()
        assert detail.get_attribute('data-popper-placement').startswith('left')
        assert detail.locator('.el-descriptions').first.evaluate('el=>getComputedStyle(el).display')
        assert detail.locator('.issue-detail-body').evaluate('el=>el.scrollHeight>el.clientHeight')
        page.screenshot(path=str(OUTPUT/'details.png'))
        page.get_by_role('heading',name='开拓问题',exact=True).click()
        page.get_by_role('button',name='编辑',exact=True).click();editor=page.get_by_role('dialog',name='编辑开拓问题',exact=True)
        expect(editor).to_be_visible();footer(editor);original=drag(editor)
        editor.locator('.el-dialog__headerbtn').click();expect(editor).not_to_be_visible()
        page.get_by_role('button',name='编辑',exact=True).click();expect(editor).to_be_visible()
        expect(editor.locator('.el-loading-mask:visible')).to_have_count(0);page.wait_for_timeout(350)
        reset=editor.locator('.el-dialog').bounding_box();assert abs(reset['x']-original['x'])<2 and abs(reset['y']-original['y'])<2
        field_search=editor.get_by_placeholder('搜索字段，如客户名称、项目类型、手机号')
        if not field_search.count():field_search=editor.locator('.dialog-field-search-header input')
        if not field_search.count():field_search=editor.locator('.el-dialog__header input')
        field_search.fill('备注');page.get_by_role('option').filter(has_text='备注').first.click()
        expect(editor.locator('.is-dialog-field-search-highlight')).to_be_visible()
        expect(item(editor,'备注').locator('textarea')).to_be_focused();page.wait_for_timeout(350)
        located=item(editor,'备注').bounding_box();body_bounds=editor.locator('.el-dialog__body').bounding_box()
        assert located['y']>=body_bounds['y']-1 and located['y']+located['height']<=body_bounds['y']+body_bounds['height']+1
        page.screenshot(path=str(OUTPUT/'editor.png'))
        button(editor,'取消').click();expect(editor).not_to_be_visible()
        results.append('详情左向小窗、内部滚动、编辑弹窗拖动边界、复位和字段定位')
        # 新任务校验定位、编辑任务、完成日期、嵌套弹窗。
        page.get_by_role('button',name='后续安排',exact=True).click();tasks_dialog=page.get_by_role('dialog',name='后续安排',exact=True)
        button(tasks_dialog,'新增后续任务').click();task_editor=page.get_by_role('dialog',name='新增后续任务',exact=True)
        expect(task_editor).to_be_visible();footer(task_editor);button(task_editor,'保存').click()
        expect(item(task_editor,'安排内容')).to_have_class(__import__('re').compile('is-error'))
        expect(item(task_editor,'安排内容').locator('textarea')).to_be_focused()
        item(task_editor,'安排内容').locator('textarea').fill('新增任务验收')
        choose(task_editor,'执行人','验收执行人');choose(task_editor,'实际进度','已完成')
        assert item(task_editor,'实际完成日期').locator('input').input_value()
        button(task_editor,'保存').click();expect(task_editor).not_to_be_visible()
        expect(tasks_dialog.get_by_text('新增任务验收',exact=True)).to_be_visible()
        card=tasks_dialog.locator('.issue-task-card').filter(has_text='新增任务验收');button(card,'编辑任务').click()
        task_editor=page.get_by_role('dialog',name='编辑后续任务',exact=True);footer(task_editor)
        choose(task_editor,'实际进度','进行中');button(task_editor,'保存').click();expect(task_editor).not_to_be_visible()
        expect(card.get_by_text('进行中',exact=True)).to_be_visible()
        page.screenshot(path=str(OUTPUT/'tasks.png'));button(tasks_dialog,'关闭').click()
        results.append('多任务新增编辑、必填定位、完成日期与重新打开、嵌套焦点')
        # 外部修订触发409，页面保留草稿并通过显式确认重新加载。
        original_row=api('GET',path+'?keyword=验收问题00')['items'][0]
        page.get_by_role('button',name='编辑',exact=True).click();editor=page.get_by_role('dialog',name='编辑开拓问题',exact=True)
        expect(editor.locator('.el-loading-mask:visible')).to_have_count(0)
        item(editor,'内容').locator('textarea').fill('并发冲突时保留的草稿')
        api('PUT',path+'/'+original_row['id'],dict(content=original_row['content'],remarks='外部修订验收',revision=original_row['revision']))
        button(editor,'保存').click();expect(editor.get_by_text('记录已被其他人修改，当前草稿已保留。请复制需要保留的内容，或重新加载后编辑。')).to_be_visible()
        expect(item(editor,'内容').locator('textarea')).to_have_value('并发冲突时保留的草稿')
        button(editor,'重新加载').click();button(page.locator('.el-message-box:visible'),'确定').click()
        expect(item(editor,'备注').locator('textarea')).to_have_value('外部修订验收')
        button(editor,'取消').click();expect(editor).not_to_be_visible();results.append('实际409冲突草稿保留及显式重新加载')
        # 三种真实聊天窗口均走公共收录表单。
        for index,kind in enumerate(('translation','annotation','direct')):
            filter_to(f'验收问题{index:02d}')
            page.get_by_role('button',name='查看详情',exact=True).click();detail=page.locator('.issue-detail-popover:visible')
            detail.get_by_role('button').filter(has_text={'translation':'笔译项目沟通','annotation':'标注项目沟通','direct':'私聊'}[kind]).click()
            window=page.locator('.project-chat-window').filter(has=page.locator('[data-message-id="'+fixtures['messages'][kind]+'"]')).last
            expect(window).to_be_visible()
            message=window.locator('[data-message-id="'+fixtures['messages'][kind]+'"]');message.hover()
            message.get_by_role('button',name='收录到开拓问题',exact=True).click()
            page.get_by_role('menuitem',name='想法类',exact=True).click()
            collector=page.get_by_role('dialog',name='收录到开拓问题',exact=True)
            expect(collector).to_be_visible();footer(collector)
            assert item(collector,'类别').locator('input').input_value()=='想法类'
            assert item(collector,'提出人').locator('input').input_value()=='验收提出人'
            assert item(collector,'类别').locator('input').get_attribute('readonly') is not None
            item(collector,'内容').locator('textarea').fill(f'菜单收录-{kind}')
            button(collector,'保存').click();expect(collector).not_to_be_visible()
            window.get_by_role('button',name='关闭项目沟通',exact=True).click()
            page.get_by_role('heading',name='开拓问题',exact=True).click()
        results.append('笔译、标注和私聊四类菜单及自动带入')
        # 无资源权限执行人只见问题页签，不请求日志，配置按用户隔离。
        start_request=len(requests)
        executor_context,executor_page=context_for('executor')
        expect(executor_page.get_by_role('tab',name='开拓日志',exact=True)).to_have_count(0)
        expect(executor_page.get_by_role('tab',name='每日安排',exact=True)).to_have_count(0)
        assert not any('/resource-development/options' in url or '/resource-development/days' in url for _,url in requests[start_request:])
        expect(executor_page.locator('.issue-panel .el-table__header-wrapper').get_by_text('内容',exact=True)).to_be_visible()
        executor_page.get_by_role('button',name='后续安排',exact=True).first.click()
        executor_tasks=executor_page.get_by_role('dialog',name='后续安排',exact=True)
        expect(executor_tasks.get_by_role('button',name='新增后续任务',exact=True)).to_have_count(0)
        executor_tasks.get_by_role('button',name='更新进度',exact=True).first.click()
        executor_editor=executor_page.get_by_role('dialog',name='编辑后续任务',exact=True)
        expect(executor_editor.locator('.el-form-item').filter(has_text='安排内容').locator('textarea')).to_have_attribute('readonly','')
        executor_editor.get_by_role('button',name='取消',exact=True).click();executor_tasks.get_by_role('button',name='关闭',exact=True).click()
        executor_context.close();results.append('无资源权限的关联人员入口及执行人字段限制、用户列配置隔离')
        # 并发重试仍只创建一份记录。
        payload=dict(source_message_id=fixtures['messages']['direct'],category='execution',content='并发收录验收')
        def concurrent(_):
            req=Request(BASE+'/api'+path,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer isolated-issue-collector','Content-Type':'application/json'})
            with urlopen(req) as response:return json.load(response)
        with ThreadPoolExecutor(max_workers=2) as pool:collected=list(pool.map(concurrent,range(2)))
        assert collected[0]['id']==collected[1]['id'] and sum(bool(r['already_collected']) for r in collected)==1
        results.append('真实并发重复收录幂等')
        # 小屏仍只滚动表单内容，固定底栏始终可见。
        page.set_viewport_size(dict(width=390,height=844));filter_to('验收问题00')
        page.get_by_role('button',name='编辑',exact=True).click();editor=page.get_by_role('dialog',name='编辑开拓问题',exact=True)
        expect(editor.locator('.el-loading-mask:visible')).to_have_count(0);page.wait_for_timeout(350)
        footer(editor);box=editor.locator('.el-dialog').bounding_box();assert box['x']>=0 and box['x']+box['width']<=390 and box['y']+box['height']<=845
        page.screenshot(path=str(OUTPUT/'mobile.png'));button(editor,'取消').click();page.set_viewport_size(dict(width=1440,height=900))
        results.append('390×844小屏表单及固定底栏')
        # 真实修订冲突产生部分删除失败，成功项移除、失败项保留选择。
        search.fill('验收问题2');page.wait_for_timeout(600);expect(rows()).to_have_count(4)
        page.get_by_role('button',name='删除管理',exact=True).click()
        selected=api('GET',path+'?keyword=验收问题2')['items'][:2]
        for row in rows().all()[:2]:row.locator('.el-checkbox').click()
        api('PUT',path+'/'+selected[0]['id'],dict(content=selected[0]['content'],remarks='模拟其他人修改',revision=selected[0]['revision']))
        page.get_by_role('button',name='删除所选（2）',exact=True).click();confirm=page.locator('.el-message-box:visible');confirm.locator('input').fill('删除');button(confirm,'确定删除').click()
        expect(rows()).to_have_count(3)
        expect(page.get_by_text('已选 1 条',exact=True)).to_be_visible()
        page.get_by_role('button',name='退出',exact=True).click();results.append('批量删除部分失败、失败选择保留和成功刷新')
        # 将记录缩减到21条，最后一页删除后自动返回有效页码。
        remaining=api('GET',path+'?limit=100')['items']
        for row in remaining[21:]:api('DELETE',path+'/'+row['id']+'?revision='+str(row['revision']))
        search.fill('');page.get_by_role('button',name='查询',exact=True).click();expect(rows()).to_have_count(20)
        page.locator('.issue-panel .el-pagination').get_by_role('button',name='下一页').click();expect(rows()).to_have_count(1)
        page.get_by_role('button',name='删除管理',exact=True).click();rows().first.locator('.el-checkbox').click()
        page.get_by_role('button',name='删除所选（1）',exact=True).click();button(page.locator('.el-message-box:visible'),'确定删除').click();expect(rows()).to_have_count(20)
        results.append('单条删除及末页回退')
        expect(page.locator('.issue-panel .el-loading-mask:visible')).to_have_count(0)
        for close in page.locator('.el-notification__closeBtn:visible').all():close.click()
        page.wait_for_timeout(3500)
        page.screenshot(path=str(OUTPUT/'list.png'),full_page=True)
        assert not errors,errors
        (OUTPUT/'ui-report.json').write_text(json.dumps(dict(passed=results,page_errors=errors),ensure_ascii=False,indent=2),encoding='utf-8')
        context.close();browser.close()
    print(json.dumps(results,ensure_ascii=False))


if __name__=='__main__':run()
