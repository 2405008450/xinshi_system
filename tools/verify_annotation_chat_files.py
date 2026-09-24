"""经授权验证局域网→云端附件链路，测试记录清理后输出待清理的测试文件清单。"""
import base64
import hashlib
import json
from pathlib import Path
import socket
import sys
from datetime import timedelta
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if socket.gethostname().upper() != 'WIN-LOLJ8UHT2G5':
    raise SystemExit('仅允许局域网调试机运行')
import main
import httpx
from database import SessionLocal
from models import AppUser, Role, RolePermission, UserRole, AppNotification, ChatProjectAttachment
from annotation_models import AnnotationProject
from routers.auth import create_access_token


def run():
    db = SessionLocal()
    marker = uuid4().hex[:10]
    role = Role(role_name='qa-files-' + marker)
    users = [AppUser(username=f'qa-files-{marker}-{i}', full_name=f'附件验收{i}', password_hash='disabled', is_active=True) for i in range(2)]
    project = AnnotationProject(order_no='QA-FILES-' + marker, project_name='附件链路验收', project_types=[])
    db.add_all([role, project, *users]); db.flush()
    db.add(RolePermission(role_id=role.id, permission_code='projects:read'))
    db.add_all(UserRole(role_id=role.id, user_id=user.id) for user in users); db.commit()
    user_ids, project_id, role_id = [u.id for u in users], project.id, role.id
    tokens = [create_access_token({'sub': u.username, 'user_id': str(u.id)}, expires_delta=timedelta(minutes=20)) for u in users]
    lan = 'http://127.0.0.1:8000'
    cloud = 'https://www.oa.xinshify.com.cn/api'
    root = f'/project-chat/annotation/{project.id}'
    artifacts, results = [], {}
    client = httpx.Client(timeout=90, trust_env=False)

    def req(method, url, index=0, **kwargs):
        return client.request(method, url, headers={'Authorization': 'Bearer ' + tokens[index]}, **kwargs)

    try:
        assert req('GET', cloud + '/auth/session').status_code == 200
        attachments = []
        for filename, content, mime in [
            ('qa-large.txt', b'x' * (20 * 1024 * 1024), 'text/plain'),
            ('qa-image.png', base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlWQAAAAASUVORK5CYII='), 'image/png'),
        ]:
            response = req('POST', lan + root + '/files', files={'file': (filename, content, mime)})
            assert response.status_code == 201, (response.status_code, response.text)
            attachment = response.json()
            row = db.get(ChatProjectAttachment, attachment['id'])
            artifacts.append({'storage_name': row.storage_name, 'sha256': hashlib.sha256(content).hexdigest()})
            assert not (ROOT / 'data/chat_uploads' / row.storage_name).exists(), '附件不应回退为本地存储'
            downloaded = req('GET', cloud + f'/project-chat/attachments/{row.id}')
            assert downloaded.status_code == 200
            assert hashlib.sha256(downloaded.content).hexdigest() == artifacts[-1]['sha256']
            attachments.append(attachment['id'])
        results['20mb_file_and_image_stored_in_cloud'] = True
        posted = req('POST', lan + root + '/messages', json={'content': '云端附件撤回验收', 'attachment_ids': attachments, 'client_message_id': str(uuid4())})
        assert posted.status_code == 201, posted.text
        message_id = posted.json()['id']
        reply = req('POST', lan + root + '/messages', index=1, json={'content': '引用附件', 'reply_to_message_id': message_id, 'client_message_id': str(uuid4())})
        assert reply.status_code == 201, reply.text
        assert req('PUT', lan + f'/project-chat/messages/{message_id}/favorite', index=1).status_code == 200
        for attachment_id in attachments:
            assert req('GET', lan + root + f'/files/{attachment_id}', index=1).status_code == 200
        assert req('POST', lan + root + f'/messages/{message_id}/recall').status_code == 200
        for attachment_id in attachments:
            for origin, suffix in [(lan, root + f'/files/{attachment_id}'), (cloud, f'/project-chat/attachments/{attachment_id}')]:
                response = req('GET', origin + suffix, index=1)
                assert response.status_code == 404, (response.status_code, response.text[:100])
        results['recalled_download_denied_on_lan_and_cloud'] = True
        timeline = req('GET', cloud + root + '/timeline', index=1).json()['items']
        quote = next(m for m in timeline if m['id'] == reply.json()['id'])
        assert quote['reply']['recalled'] and '云端附件撤回验收' not in quote['reply']['content']
        assert not req('GET', cloud + root + '/timeline?favorites_only=true', index=1).json()['items']
        results['quote_and_favorite_redacted_across_hosts'] = True
    finally:
        db.rollback()
        db.query(AppNotification).filter(AppNotification.recipient_user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(AnnotationProject).filter(AnnotationProject.id == project_id).delete(synchronize_session=False)
        db.query(UserRole).filter(UserRole.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete(synchronize_session=False)
        db.query(AppUser).filter(AppUser.id.in_(user_ids)).delete(synchronize_session=False)
        db.query(Role).filter(Role.id == role_id).delete(synchronize_session=False)
        db.commit(); db.close(); client.close()
        out = ROOT / '.tmp' / 'annotation-chat-ui'
        out.mkdir(parents=True, exist_ok=True)
        (out / 'cloud-test-files.json').write_text(json.dumps(artifacts), encoding='utf-8')
        (out / 'files-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps(results))


if __name__ == '__main__':
    run()
