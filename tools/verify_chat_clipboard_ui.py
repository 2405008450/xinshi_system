"""本机真实聊天输入框粘贴验收；所有API及WS使用合成夹具。"""
import base64
import json
import re
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import expect
from verify_chat_phase_one_ui import run


def verify(page, workspace, contexts, errors, requests, output, me, other, annotation, translation, direct):
    output = output.parent / 'chat-clipboard-ui'; output.mkdir(exist_ok=True)
    uploaded, screenshots = [], []
    image = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
    def upload(route):
        req=route.request
        envelope=BytesParser(policy=default).parsebytes(('Content-Type: '+req.headers['content-type']+'\r\n\r\n').encode()+req.post_data_buffer)
        part=next(part for part in envelope.iter_parts() if part.get_filename())
        name=part.get_filename();uploaded.append(name)
        route.fulfill(status=201,json=dict(id=str(uuid4()),original_name=name,content_type=part.get_content_type(),file_size=len(part.get_payload(decode=True))))
    contexts[0].route(re.compile(r'/api/(project-chat/annotation|chat/direct)/[^/]+/files$'),upload)
    def screenshot(route):
        if route.request.method=='POST':
            sid=str(uuid4());screenshots.append(sid)
            route.fulfill(status=201,json=dict(id=sid,reference=f'![截图](screenshot://{sid})'));return
        route.fulfill(body=image,content_type='image/png')
    contexts[0].route(re.compile(r'/api/editor-screenshots(/[^/?]+)?(\?.*)?$'),screenshot)
    workspace.get_by_role('button',name='消息',exact=True).first.click()
    workspace.locator('.chat-workspace__session',has_text='阶段一标注').click()
    composer=page.locator('.project-chat-window:visible .group-composer')
    def clean():
        expect(composer.locator('.app-screenshot-tools')).to_have_count(0)
        expect(composer).not_to_contain_text('每条最多9个附件')
        expect(composer).not_to_contain_text('Enter发送')
        expect(composer).not_to_contain_text('聊天截图保留30天')
    def paste(files, items_only=False):
        return composer.locator('textarea').evaluate("""(input, data) => {
          const dt=new DataTransfer();
          for(const file of data.files){dt.items.add(new File([file.body||'test media'],file.name,{type:file.type||'application/octet-stream'}))}
          const event=new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:dt});
          if(data.itemsOnly)Object.defineProperty(event,'clipboardData',{value:{files:[],items:dt.items,getData:()=>''}});
          input.dispatchEvent(event);return event.defaultPrevented;
        }""",dict(files=files,itemsOnly=items_only))
    def exercise():
        clean()
        before=len(uploaded)
        assert paste([dict(name='粘贴视频.mp4'),dict(name='粘贴音频.mp3'),dict(name='粘贴文档.pdf',body='%PDF-1.4')])
        expect(composer.locator('.group-file-queue > div')).to_have_count(3)
        expect(composer.locator('.group-file-queue')).not_to_contain_text('上传中')
        assert len(uploaded)==before+3, '同一个文件不得重复上传'
        for _ in range(3):composer.get_by_role('button',name='移除',exact=True).first.click()
        assert paste([dict(name='items备用.txt',body='文字文件')],True)
        expect(composer.locator('.group-file-queue')).to_contain_text('待发送')
        composer.get_by_role('button',name='移除',exact=True).click()
        # 同一次粘贴包含图片和文件时也必须全部处理，而非被图片捕获逻辑截断。
        image_before=len(screenshots);file_before=len(uploaded)
        composer.locator('textarea').evaluate("""input=>{
          const canvas=document.createElement('canvas');canvas.width=2;canvas.height=2;
          const binary=atob(canvas.toDataURL('image/png').split(',')[1]);
          const bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));const dt=new DataTransfer();
          dt.items.add(new File([bytes],'截图.png',{type:'image/png'}));
          dt.items.add(new File(['report'],'混合粘贴.txt',{type:'text/plain'}));
          input.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:dt}));
        }""")
        expect(composer.locator('.screenshot-preview')).to_have_count(1)
        expect(composer.locator('.group-file-queue')).to_contain_text('待发送')
        assert len(screenshots)==image_before+1 and len(uploaded)==file_before+1
        clean()
        composer.get_by_role('button',name='移除',exact=True).click()
        composer.get_by_role('button',name='移除截图',exact=True).click()
        # 原生Ctrl+V仍可以粘贴纯文本。
        contexts[0].grant_permissions(['clipboard-read','clipboard-write'])
        page.evaluate("navigator.clipboard.writeText('纯文本粘贴正常')")
        composer.locator('textarea').focus();page.keyboard.press('Control+V')
        expect(composer.locator('textarea')).to_have_value('纯文本粘贴正常')
        expect(composer.locator('.group-file-queue')).to_have_count(0)
        composer.locator('textarea').fill('')
    exercise()
    composer.screenshot(path=str(output/'annotation-composer.png'))
    workspace.get_by_role('button',name='通讯录',exact=True).first.click()
    workspace.locator('.chat-contact',has_text='验收乙').first.click()
    expect(workspace.locator('.chat-workspace__session.is-active')).to_contain_text('验收乙')
    exercise()
    composer.screenshot(path=str(output/'direct-composer.png'))
    assert not errors,errors
    report=dict(checks=['标注与私聊无常驻说明','粘贴多个MP4/MP3/PDF自动上传且无重复','items备用读取','截图与文件混合粘贴','原生Ctrl+V纯文本'],uploads=uploaded,screenshots=len(screenshots),errors=errors)
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
    run(verify_layout=verify)
