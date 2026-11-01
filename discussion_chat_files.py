"""讨论附件复用现有附件表，以讨论专属文件名和消息引用校验访问。"""
import re
from uuid import UUID
from fastapi import HTTPException
from models import ChatProjectAttachment

PATTERN = re.compile(r'\[附件\]\(discussion-file://([0-9a-fA-F-]{36})\)')


def file_ids(content):
    try:
        return list(dict.fromkeys(UUID(value) for value in PATTERN.findall(content or '')))
    except ValueError:
        raise HTTPException(422, '附件引用无效')


def require_file(db, room_id, attachment_id):
    row = db.get(ChatProjectAttachment, attachment_id)
    if not row or not row.storage_name.startswith(f'discussion_{room_id.hex}_'):
        raise HTTPException(404, '讨论附件不存在')
    return row


def validate_files(db, user, room_id, content):
    ids = file_ids(content)
    from editor_screenshot_service import references
    if len(ids) + len(references(content)) > 9:
        raise HTTPException(422, '每条消息最多9个附件')
    for id in ids:
        if require_file(db, room_id, id).uploaded_by != user.id:
            raise HTTPException(403, '只能发送本人上传的讨论附件')
