r"""笔译、口译、招聘截图回归；所有 API 均拦截，仅使用本机前端。

运行：.venv\Scripts\python.exe frontend/tests/e2e/project_progress_screenshots_check.py
"""
import asyncio
import base64
import json
import os
import re
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

from playwright.async_api import async_playwright, expect
from annotation_progress_screenshots_check import HARNESS, ORIGIN, PROJECT, ROWS, REF, IMAGE_IDS, SIGNATURE, STAMP, png


def harness_html(version):
    html = re.sub(r"const paths = \{.*?\n\};", """const paths = {
 interpretation:'/src/views/project/interpretation/InterpretationProjectDetails.vue',
 recruitment:'/src/views/project/RecruitmentProjects.vue',
 translation:'/src/views/project/translation/TranslationProjects.vue',
 translator:'/src/views/project/translation/components/TranslatorCompletionPopover.vue'
};""", HARNESS, flags=re.S)
    html = re.sub(r"const props = \{.*?\}\[mode\];", """window.savedDetails=[];
const props=mode==='translator'?{
 translators:[{arrangementId:'assignment-1',translatorName:'测试译员',returnTime:'2026-10-27 12:00:00',completionRemarks:rows[0].changeNote}],
 editable:true,save:async details=>{window.savedDetails.push(details);return details}
}:{};""", html, flags=re.S)
    html = html.replace("if(mode==='comparison') target.value.open(project);", """window.state=target.value.$.setupState;
if(mode==='interpretation'||mode==='recruitment') await window.state.openProgress(project);
if(mode==='translator') document.querySelector('#app').style.margin='200px 0 0 800px';
if(mode==='translation') {
 window.state.selectedProjectRow=project;
 window.state.projectList=[project];
 window.state.currentProjectId=project.id;
 await window.state.ensureWorkflowState('project',project.id);
 window.state.activeTab='logs';
}
""")
    return re.sub(r"(/node_modules/\.vite/deps/[^']+\.js)'", rf"\1?v={version}'", html)


async def run():
    with urlopen(f"{ORIGIN}/src/views/project/RecruitmentProjects.vue") as response:
        version = re.search(r"/vue-router\.js\?v=([\w-]+)", response.read().decode()).group(1)
    html = harness_html(version)
    workflow = {"currentStageKey": "layout", "difficulty": "normal", "fileEditable": True,
                "projectStatus": "in_progress", "stageNotes": {},
                "effectiveStages": [{"key": "layout", "title": "排版", "role": "排版专员"},
                                    {"key": "completed", "title": "完成", "role": "-"}],
                "transitionLog": [{"at": STAMP, "note": ROWS[0]["changeNote"], "description": "测试流程记录"}]}
    recruitment = [dict(row, note=row["changeNote"], occurredAt=STAMP, isSystem=False) for row in ROWS]
    writes, unexpected, errors = [], [], []
    gate, upload_started = asyncio.Event(), asyncio.Event()
    fail_upload = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel=os.getenv("BROWSER_CHANNEL", "msedge"))
        context = await browser.new_context(viewport={"width": 1440, "height": 1000}, service_workers="block")
        page = await context.new_page()
        page.on("pageerror", lambda error: (errors.append(str(error)), print(f"浏览器错误: {error}", flush=True)))

        async def api(route):
            path = urlparse(route.request.url).path.removeprefix('/api')
            method = route.request.method
            if path == '/editor-screenshots' and method == 'POST':
                upload_started.set()
                await gate.wait()
                await route.fulfill(status=500 if fail_upload else 201, json={"detail": "模拟上传失败"} if fail_upload else
                                    {"id": IMAGE_IDS[3], "reference": f"screenshot://{IMAGE_IDS[3]}#{SIGNATURE}"})
                return
            if path.startswith('/editor-screenshots/'):
                if path.endswith(IMAGE_IDS[2]):
                    await route.fulfill(status=404, json={"detail": "截图不存在"})
                else:
                    await route.fulfill(content_type='image/png', body=png())
                return
            if method != 'GET':
                payload = route.request.post_data_json
                if path == '/projects/interpretation/test-project/status':
                    writes.append(payload); result = PROJECT
                elif path.startswith('/projects/recruitment/test-project/progress'):
                    writes.append(payload)
                    result = dict(recruitment[0], note=payload['note'])
                    recruitment[0] = result
                elif path in ['/workflow/test-project/transition', '/workflow/test-project/rollback']:
                    writes.append(payload)
                    workflow['stageNotes'] = {"layout": payload['note']}
                    workflow['transitionLog'][0]['note'] = payload['note']
                    result = workflow
                else:
                    unexpected.append(f"{method} {path}")
                    await route.fulfill(status=403, json={"detail": "隔离验收禁止未声明的写入"})
                    return
            elif path.endswith('/status-history'):
                result = ROWS
            elif path.endswith('/progress'):
                result = recruitment
            elif path in ['/projects/interpretation/test-project', '/projects/recruitment/test-project']:
                result = PROJECT
            elif path == '/workflow/test-project':
                result = workflow
            elif path.endswith('/page'):
                result = {"items": [], "total": 0}
            else:
                result = []
            await route.fulfill(json=result)

        await context.route(f"{ORIGIN}/api/**", api)
        await context.route('**/__project_screenshot_test*', lambda route: route.fulfill(content_type='text/html', body=html))

        async def open_mode(mode):
            await page.goto(f"{ORIGIN}/__project_screenshot_test?mode={mode}")
            await page.wait_for_function('window.testReady===true')

        async def check_display(root):
            await expect(root.locator('.screenshot-preview img').first).to_be_visible()
            assert 'screenshot://' not in await root.inner_text()
            await root.locator('.screenshot-preview img').first.click()
            await expect(page.locator('.el-image-viewer__wrapper')).to_be_visible()
            await page.locator('.el-image-viewer__close').click()

        async def paste_and_save(input_box, button):
            gate.clear(); upload_started.clear()
            await input_box.evaluate("""(el,data)=>{
 const bytes=Uint8Array.from(atob(data),c=>c.charCodeAt(0)), transfer=new DataTransfer();
 transfer.items.add(new File([bytes],'测试.png',{type:'image/png'}));
 el.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:transfer}));
}""", base64.b64encode(png()).decode())
            await asyncio.wait_for(upload_started.wait(), 10)
            before = len(writes)
            await button.evaluate('el=>{el.click();el.click()}')
            await expect(button).to_have_class(re.compile('is-loading'))
            assert len(writes) == before
            label=(await button.inner_text()).strip()
            gate.set()
            await page.wait_for_function("label=>!Array.from(document.querySelectorAll('button')).some(el=>el.textContent.trim()===label&&el.classList.contains('is-loading'))", arg=label)
            if fail_upload:
                assert len(writes) == before
            else:
                assert len(writes) == before + 1
                assert IMAGE_IDS[3] in json.dumps(writes[-1])

        await open_mode('interpretation')
        await check_display(page.locator('.progress-timeline'))
        await paste_and_save(page.locator('.progress-entry-form textarea'), page.get_by_role('button', name='添加具体进度', exact=True))
        print('PASS 口译：历史截图、放大、纯图片提交、等待上传、重复提交保护', flush=True)

        await open_mode('recruitment')
        await check_display(page.locator('.progress-dialog .el-timeline'))
        await paste_and_save(page.locator('.progress-create textarea'), page.get_by_role('button', name='添加记录', exact=True))
        await page.locator('.progress-dialog .el-timeline-item').first.get_by_role('button', name='编辑', exact=True).click()
        await page.locator('.progress-edit-form textarea').fill('编辑保留草稿')
        fail_upload = True
        await paste_and_save(page.locator('.progress-edit-form textarea'), page.get_by_role('button', name='保存修改', exact=True))
        await expect(page.locator('.progress-edit-form textarea')).to_have_value('编辑保留草稿')
        fail_upload = False
        await paste_and_save(page.locator('.progress-edit-form textarea'), page.get_by_role('button', name='保存修改', exact=True))
        await expect(page.locator('.progress-edit-form')).to_have_count(0)
        await page.set_viewport_size({"width": 600, "height": 700})
        footer = page.locator('.progress-dialog .el-dialog__footer')
        before = await footer.bounding_box()
        await page.locator('.progress-dialog .el-dialog__body').evaluate('el=>el.scrollTop=el.scrollHeight')
        assert abs((await footer.bounding_box())['y'] - before['y']) < 2
        await page.screenshot(path=os.path.join(tempfile.gettempdir(), 'recruitment-progress-screenshots.png'))
        dialog=page.locator('.progress-dialog')
        original=await dialog.bounding_box()
        handle=await dialog.locator('.app-window-drag-strip').bounding_box()
        await page.mouse.move(handle['x']+15,handle['y']+3)
        await page.mouse.down();await page.mouse.move(-300,-300,steps=8);await page.mouse.up()
        moved=await dialog.bounding_box()
        assert moved['x']>=0 and moved['y']>=0 and abs(moved['y']-original['y'])>5
        await dialog.get_by_role('button',name='关闭窗口',exact=True).click()
        await expect(dialog).to_be_hidden()
        await page.evaluate('project=>window.state.openProgress(project)', PROJECT)
        await page.wait_for_function("y=>Math.abs(document.querySelector('.progress-dialog').getBoundingClientRect().y-y)<3", arg=original['y'])
        print('PASS 招聘：新增/编辑截图、上传失败保留、重试、小屏固定操作栏', flush=True)

        await page.set_viewport_size({"width": 1440, "height": 1000})
        await open_mode('translation')
        await check_display(page.locator('.log-note'))
        await paste_and_save(page.locator('.stage-handover textarea'), page.get_by_role('button', name='完成本阶段并提交', exact=True))
        await check_display(page.locator('.readonly-note'))
        await page.evaluate('window.state.rollbackDialogVisible=true')
        await paste_and_save(page.get_by_placeholder('请输入打回原因，支持粘贴截图'), page.get_by_role('button', name='确认打回', exact=True))
        print('PASS 笔译流程：日志、交接备注、上传等待、打回原因截图', flush=True)

        await open_mode('translator')
        await page.locator('.translator-return-trigger').click()
        await check_display(page.locator('.translator-completion-panel'))
        await page.locator('.translator-completion-panel textarea').fill('译员完成情况')
        # 该字段上限为 255 字符，先移除一张旧图，为新的签名引用留出空间。
        await page.locator('.translator-completion-panel [aria-label="移除截图"]').last.click()
        gate.clear(); upload_started.clear()
        # 此控件通过父页面回调保存；记录回调结果验证上传后才读取草稿。
        await page.locator('.translator-completion-panel input[type=file]').set_input_files(
            {"name": "测试.png", "mimeType": "image/png", "buffer": png()})
        await asyncio.wait_for(upload_started.wait(), 10)
        await page.get_by_role('button', name='保存', exact=True).click()
        assert await page.evaluate('window.savedDetails.length') == 0
        gate.set()
        await page.wait_for_function('window.savedDetails.length===1')
        assert IMAGE_IDS[3] in json.dumps(await page.evaluate('window.savedDetails'))
        assert not errors, errors
        assert not unexpected, unexpected
        print('PASS 笔译任务完成情况：截图展示及上传等待；全部请求使用模拟接口', flush=True)
        await browser.close()


if __name__ == '__main__':
    asyncio.run(run())
