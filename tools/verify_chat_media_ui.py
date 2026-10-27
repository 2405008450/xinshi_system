"""真实聊天页面音视频验收；全部 API/WS 使用合成夹具，不接触业务数据库。"""
import base64
import io
import json
import math
import re
import struct
import shutil
import subprocess
import wave
from email.parser import BytesParser
from email.policy import default
from uuid import uuid4
from playwright.sync_api import expect
from verify_chat_phase_one_ui import run


def verify(page, workspace, contexts, errors, requests, output, me, other, annotation, translation, direct):
    output = output.parent / 'chat-media-ui'; output.mkdir(exist_ok=True)
    rows = {annotation: [], direct: []}
    files = {}
    downloads = []
    with io.BytesIO() as buffer:
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(8000)
            wav.writeframes(b''.join(struct.pack('<h', int(math.sin(i * 440 * 2 * math.pi / 8000) * 1000)) for i in range(24000)))
        audio = buffer.getvalue()
    # 用浏览器自身的编码器生成可实际播放的 WebM，无需外部转码程序。
    video = base64.b64decode(page.evaluate("""async () => {
      const canvas=document.createElement('canvas');canvas.width=160;canvas.height=90;
      const ctx=canvas.getContext('2d'),stream=canvas.captureStream(10),chunks=[];
      const recorder=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp8'});
      const done=new Promise(resolve=>recorder.onstop=resolve);recorder.ondataavailable=e=>chunks.push(e.data);
      recorder.start();let tick=0;const timer=setInterval(()=>{ctx.fillStyle=tick++%2?'blue':'green';ctx.fillRect(0,0,160,90)},100);
      await new Promise(resolve=>setTimeout(resolve,2000));recorder.stop();await done;clearInterval(timer);stream.getTracks().forEach(t=>t.stop());
      const bytes=new Uint8Array(await new Blob(chunks).arrayBuffer());return btoa(String.fromCharCode(...bytes));
    }"""))
    fixture_dir = output / 'fixtures'; fixture_dir.mkdir(exist_ok=True)
    wav_path = fixture_dir / 'sample.wav'; wav_path.write_bytes(audio)
    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg, '验收真实MP4/MP3/M4A需要本机ffmpeg'
    for ext in ('mp3','m4a','mp4'):
        args = ['-f','lavfi','-i','color=c=blue:s=160x90:r=10','-t','2','-c:v','h264_mf','-pix_fmt','yuv420p'] if ext=='mp4' else ['-i',str(wav_path),'-ar','44100','-c:a','mp3_mf' if ext=='mp3' else 'aac','-b:a','128k']
        subprocess.run([ffmpeg,'-y','-loglevel','error',*args,str(fixture_dir / ('sample.'+ext))],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    extra = {ext:(fixture_dir / ('sample.'+ext)).read_bytes() for ext in ('mp3','m4a','mp4')}
    fail_once = {annotation:True, direct:True}
    def handle(route):
        req=route.request
        scope = direct if '/chat/direct/' in req.url else annotation
        suffix = req.url.split(scope + '/')[-1].split('?')[0]
        if suffix == 'read': route.fulfill(json={'last_read_sequence':100});return
        if suffix == 'timeline': route.fulfill(json={'items':rows[scope], 'has_more':False}); return
        if suffix == 'refresh': route.fulfill(json={'items':rows[scope]}); return
        if suffix.startswith('files/'):
            fid=suffix.split('/')[-1]; downloads.append(fid)
            route.fulfill(body=files[fid][1],content_type=files[fid][0]['content_type']);return
        if suffix == 'files':
            if fail_once[scope]:
                fail_once[scope]=False;route.fulfill(status=503,json={'detail':'模拟上传失败，请重试'});return
            envelope=BytesParser(policy=default).parsebytes(('Content-Type: '+req.headers['content-type']+'\r\n\r\n').encode()+req.post_data_buffer)
            part=next(envelope.iter_parts());data=part.get_payload(decode=True);name=part.get_filename();fid=str(uuid4())
            attachment=dict(id=fid,original_name=name,content_type={'wav':'audio/wav','webm':'video/webm','mp4':'video/mp4','mp3':'audio/mpeg','m4a':'audio/mp4'}[name.split('.')[-1]],file_size=len(data))
            files[fid]=(attachment,data);route.fulfill(status=201,json=attachment);return
        if suffix == 'messages':
            data=req.post_data_json
            row=dict(id=str(uuid4()),sender_user_id=me,sender_name='验收甲',content=data['content'],message_type='user',sequence_no=100+len(rows[scope]),created_at='2026-10-27T12:00:00+08:00',mentions=[],attachments=[files[fid][0] for fid in data['attachment_ids']],can_recall=True,acknowledgements=[])
            rows[scope].append(row);route.fulfill(status=201,json=row);return
        route.fallback()
    contexts[0].route(re.compile(r'/api/(project-chat/annotation|chat/direct)/('+annotation+'|'+direct+r')/(timeline|refresh|files|messages|read)(/|\?|$)'),handle)
    # 捕获 URL 的释放，用于确认切换和撤回后清理媒体缓存。
    page.evaluate("window.mediaRevoked=[];const revoke=URL.revokeObjectURL.bind(URL);URL.revokeObjectURL=url=>{window.mediaRevoked.push(url);revoke(url)}")
    workspace.get_by_role('button', name='消息', exact=True).first.click()
    workspace.locator('.chat-workspace__session',has_text='阶段一标注').click()
    chat=page.locator('.project-chat-window:visible .annotation-group')
    def exercise():
        before=len(downloads)
        chat.locator('.group-compose-tools input[type=file]').last.set_input_files([dict(name='音频验收.wav',mimeType='audio/wav',buffer=audio),dict(name='视频验收.webm',mimeType='video/webm',buffer=video),*[dict(name='格式验收.'+ext,mimeType='application/octet-stream',buffer=data) for ext,data in extra.items()]])
        expect(chat.locator('.group-file-queue')).to_contain_text('上传失败')
        chat.locator('.group-file-queue').get_by_role('button',name='重试',exact=True).click()
        expect(chat.locator('.group-file-queue')).not_to_contain_text('上传失败')
        expect(chat.locator('.group-file-queue')).to_contain_text('待发送')
        expect(chat.locator('.group-file-queue')).not_to_contain_text('上传中')
        chat.get_by_role('button',name='发送',exact=True).click()
        expect(chat.locator('.chat-media')).to_have_count(5)
        assert len(downloads)==before, '附件应按需加载'
        audio_card=chat.locator('.chat-media',has_text='音频验收.wav')
        audio_card.get_by_role('button',name='加载播放',exact=True).click()
        expect(audio_card.locator('audio')).to_be_visible()
        page.wait_for_function("document.querySelector('.annotation-group audio')?.readyState >= 1")
        audio_card.locator('audio').evaluate('(el)=>el.play()')
        assert audio_card.locator('audio').evaluate('(el)=>!el.paused')
        audio_card.locator('audio').evaluate('(el)=>{el.pause();el.currentTime=1}')
        assert audio_card.locator('audio').evaluate('(el)=>el.paused && el.currentTime===1')
        with page.expect_download() as saved:
            audio_card.get_by_role('button',name='下载',exact=True).click()
        assert saved.value.suggested_filename=='音频验收.wav'
        assert len(downloads)==before+1, '重复下载应复用Blob'
        video_card=chat.locator('.chat-media',has_text='视频验收.webm')
        video_card.get_by_role('button',name='加载播放',exact=True).click()
        expect(video_card.locator('video')).to_be_visible()
        page.wait_for_function("document.querySelector('.annotation-group video')?.readyState >= 1")
        video_card.locator('video').evaluate('(el)=>el.play()')
        assert video_card.locator('video').evaluate('(el)=>!el.paused')
        video_card.locator('video').evaluate('(el)=>el.pause()')
        for ext in extra:
            print('播放验收：'+ext,flush=True)
            card=chat.locator('.chat-media',has_text='格式验收.'+ext)
            card.get_by_role('button',name='加载播放',exact=True).click()
            player=card.locator('video' if ext=='mp4' else 'audio')
            player.evaluate('(el)=>new Promise((resolve,reject)=>{if(el.readyState>=1)return resolve();setTimeout(()=>reject(new Error(`媒体未就绪：${el.error?.code}`)),5000);el.onloadedmetadata=resolve;el.onerror=()=>reject(new Error(`播放错误：${el.error?.code}`))})')
            player.evaluate('(el)=>el.play()')
            assert player.evaluate('(el)=>!el.paused')
            player.evaluate('(el)=>el.pause()')
        page.screenshot(path=str(output/('annotation.png' if len(rows[direct])==0 else 'direct.png')))
    exercise()
    workspace.get_by_role('button',name='通讯录',exact=True).first.click()
    workspace.locator('.chat-contact',has_text='验收乙').first.click()
    expect(workspace.locator('.chat-workspace__session.is-active')).to_contain_text('验收乙')
    assert page.evaluate('window.mediaRevoked.length')>=5
    exercise()
    page.set_viewport_size(dict(width=390,height=740))
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(output/'mobile.png'))
    page.set_viewport_size(dict(width=1440,height=900))
    # 轮询 refresh 返回撤回后的消息，组件卸载立即释放播放器。
    rows[direct][0].update(recalled_at='2026-10-27T12:01:00+08:00',recall_label='验收甲撤回了一条消息',attachments=[])
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(chat.locator('audio')).to_have_count(0,timeout=20000)
    assert page.evaluate('window.mediaRevoked.length')>=6
    assert not errors,errors
    report=dict(checks=['标注与私聊纯音视频附件发送','按需加载','真实MP4/MP3/WAV/M4A/WebM播放暂停','上传失败重试','音频进度拖动','下载及缓存复用','切换及撤回释放Blob','小屏无横向溢出'],requests=len(downloads),errors=errors)
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__ == '__main__':
    run(verify_layout=verify)
