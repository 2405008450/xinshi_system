"""真实聊天页面图片验收；所有 API/WS 拦截，图片处理使用纯函数，不连接数据库。"""
import hashlib
import json
import re
import sys
from email.parser import BytesParser
from email.policy import default
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image
from playwright.sync_api import expect
from verify_chat_phase_one_ui import run

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_image_policy import normalize_chat_image, ORIGINAL_MAX_BYTES


def verify(page, workspace, contexts, errors, requests, output, me, other, annotation, translation, direct):
    output = output.parent / 'chat-original-images-ui'
    output.mkdir(exist_ok=True)
    buffer = BytesIO()
    Image.new('RGBA', (2600, 80), (10, 90, 160, 120)).save(buffer, 'PNG')
    original = buffer.getvalue()
    large = original + b'\0' * (ORIGINAL_MAX_BYTES + 1 - len(original))
    stored, uploads = {}, []

    def screenshot(route):
        if route.request.method == 'POST':
            request = route.request
            envelope = BytesParser(policy=default).parsebytes(
                ('Content-Type: ' + request.headers['content-type'] + '\r\n\r\n').encode() + request.post_data_buffer)
            part = next(part for part in envelope.iter_parts() if part.get_filename())
            content = part.get_payload(decode=True)
            uploads.append(content)
            data, mime = normalize_chat_image(content, part.get_content_type())
            sid = str(uuid4())
            stored[sid] = (data, mime)
            route.fulfill(status=201, json=dict(id=sid, reference=f'screenshot://{sid}', size=len(data), contentType=mime))
        else:
            sid = route.request.url.split('/editor-screenshots/')[1].split('?')[0]
            data, mime = stored[sid]
            route.fulfill(body=data, content_type=mime)

    contexts[0].route(re.compile(r'/api/editor-screenshots(/[^/?]+)?(\?.*)?$'), screenshot)
    workspace.get_by_role('button', name='消息', exact=True).first.click()
    workspace.locator('.chat-workspace__session', has_text='阶段一标注').click()
    composer = page.locator('.project-chat-window:visible .group-composer')
    for source in (original, large):
        composer.locator('input[type=file]').first.set_input_files(dict(name='原图验收.png', mimeType='image/png', buffer=source))
        expect(composer.locator('.group-image-status')).to_have_text('待发送')
        assert uploads[-1] == source, '前端必须传递原始文件，不得缩放或重编码'
        thumbnail = composer.locator('.screenshot-preview .el-image img')
        expect(thumbnail).to_be_visible()
        assert thumbnail.evaluate('(img) => img.naturalWidth') == 2600
        thumbnail.click()
        viewer = page.locator('.el-image-viewer__img')
        expect(viewer).to_be_visible()
        assert viewer.evaluate('(img) => img.naturalWidth') == 2600
        page.keyboard.press('Escape')
        composer.get_by_role('button', name='发送', exact=True).click()
        expect(composer.locator('.group-image-card')).to_have_count(0)
        message_image = page.locator('.group-message--own .screenshot-preview .el-image img').last
        expect(message_image).to_be_visible()
        message_image.click()
        expect(viewer).to_be_visible()
        assert viewer.evaluate('(img) => img.naturalWidth') == 2600
        page.keyboard.press('Escape')
    results = list(stored.values())
    assert results[0][0] == original
    assert results[1][1] == 'image/webp' and len(results[1][0]) <= ORIGINAL_MAX_BYTES
    page.screenshot(path=str(output / 'preview.png'))
    assert not errors, errors
    report = dict(checks=['上传字节不变', '2600像素原图保存', '超10MB原尺寸压缩', '待发送与发送后预览完整存储图片'],
                  original_sha256=hashlib.sha256(original).hexdigest(), stored_sizes=[len(data) for data, _ in results], errors=errors)
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    run(verify_layout=verify)
