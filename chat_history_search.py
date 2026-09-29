"""项目沟通历史检索：全部消息、图片、链接和文件共用同一套筛选与游标。"""
import base64
import datetime as dt
import json
import re
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from models import (
    ChatProjectAttachment,
    ChatProjectMessage,
    ChatProjectMessageAttachment,
    ChatProjectMessageFavorite,
)

LINK_REGEX = r'https?://|www\.'
URL_RE = re.compile(r'(https?://[^\s<>"\']+|www\.[^\s<>"\']+)', re.IGNORECASE)
TRAILING_URL_CHARS = '.,;:!?)]}\'"。，、；：！？）》」』】〉'
KIND_ALIASES = {'all': 'message', 'message': 'message', 'image': 'image', 'link': 'link', 'file': 'file'}


class ChatHistoryError(ValueError):
    """检索参数无法执行，由路由转换为 400。"""


def extract_urls(content: str) -> list[str]:
    found = []
    for match in URL_RE.finditer(content or ''):
        url = match.group(0).rstrip(TRAILING_URL_CHARS)
        if url and url not in found:
            found.append(url)
    return found


def _ilike_pattern(keyword: str) -> str:
    escaped = keyword.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{escaped}%'


def _encode_cursor(payload: dict) -> str:
    raw = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode_cursor(value: str) -> dict:
    try:
        data = json.loads(base64.urlsafe_b64decode(value.encode()))
    except Exception as exc:
        raise ChatHistoryError('分页游标无效') from exc
    if not isinstance(data, dict):
        raise ChatHistoryError('分页游标无效')
    return data


def _summary(text: str, limit: int = 140) -> str:
    compact = ' '.join((text or '').split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + '…'


def _filtered_messages(
    db: Session,
    *,
    project_type: str,
    project_id: UUID,
    user_id: UUID,
    sender_user_id: UUID | None,
    date_from: dt.datetime | None,
    date_to: dt.datetime | None,
    favorites_only: bool,
    include_user_messages: bool,
):
    query = db.query(ChatProjectMessage).filter(ChatProjectMessage.recalled_at.is_(None))
    if project_type == 'annotation':
        query = query.filter(ChatProjectMessage.annotation_project_id == project_id)
    elif project_type == 'translation':
        query = query.filter(ChatProjectMessage.project_id == project_id)
        if not include_user_messages:
            query = query.filter(ChatProjectMessage.message_type != 'user')
    else:
        raise ChatHistoryError('不支持的项目类型')
    if sender_user_id:
        query = query.filter(ChatProjectMessage.sender_user_id == sender_user_id)
    if date_from:
        query = query.filter(ChatProjectMessage.created_at >= date_from)
    if date_to:
        query = query.filter(ChatProjectMessage.created_at <= date_to)
    if favorites_only:
        query = query.filter(ChatProjectMessage.favorites.any(ChatProjectMessageFavorite.user_id == user_id))
    return query


def _with_text_keyword(query, keyword: str):
    pattern = _ilike_pattern(keyword)
    name_match = ChatProjectMessage.attachment_links.any(
        ChatProjectMessageAttachment.attachment.has(
            ChatProjectAttachment.original_name.ilike(pattern, escape='\\')
        )
    )
    return query.filter(or_(ChatProjectMessage.content.ilike(pattern, escape='\\'), name_match))


def _attachment_query(message_query, *, images: bool, keyword: str):
    query = message_query.join(
        ChatProjectMessageAttachment,
        ChatProjectMessageAttachment.message_id == ChatProjectMessage.id,
    ).join(
        ChatProjectAttachment,
        ChatProjectAttachment.id == ChatProjectMessageAttachment.attachment_id,
    )
    if images:
        query = query.filter(ChatProjectAttachment.content_type.ilike('image/%'))
    else:
        query = query.filter(~ChatProjectAttachment.content_type.ilike('image/%'))
    if keyword:
        pattern = _ilike_pattern(keyword)
        query = query.filter(or_(
            ChatProjectMessage.content.ilike(pattern, escape='\\'),
            ChatProjectAttachment.original_name.ilike(pattern, escape='\\'),
        ))
    return query


def _link_query(message_query, keyword: str):
    query = message_query.filter(ChatProjectMessage.content.op('~*')(LINK_REGEX))
    if keyword:
        query = query.filter(ChatProjectMessage.content.ilike(_ilike_pattern(keyword), escape='\\'))
    return query


def _message_cursor(message: ChatProjectMessage, project_type: str, **extra) -> dict:
    if project_type == 'annotation':
        payload = {'sequence_no': int(message.sequence_no or 0)}
    else:
        payload = {
            'created_at': message.created_at.isoformat() if message.created_at else '',
            'message_id': str(message.id),
        }
    payload.update(extra)
    return payload


def _order_messages(query, project_type: str):
    if project_type == 'annotation':
        return query.order_by(ChatProjectMessage.sequence_no.desc(), ChatProjectMessage.id.desc())
    return query.order_by(ChatProjectMessage.created_at.desc(), ChatProjectMessage.id.desc())


def _before_message(query, project_type: str, cursor: dict, *, inclusive: bool):
    if project_type == 'annotation':
        sequence_no = int(cursor['sequence_no'])
        if inclusive:
            return query.filter(ChatProjectMessage.sequence_no <= sequence_no)
        return query.filter(ChatProjectMessage.sequence_no < sequence_no)
    created_at = dt.datetime.fromisoformat(cursor['created_at'])
    message_id = UUID(cursor['message_id'])
    older = or_(
        ChatProjectMessage.created_at < created_at,
        and_(ChatProjectMessage.created_at == created_at, ChatProjectMessage.id < message_id),
    )
    if inclusive:
        older = or_(older, and_(ChatProjectMessage.created_at == created_at, ChatProjectMessage.id == message_id))
    return query.filter(older)


def _same_message(message: ChatProjectMessage, cursor: dict, project_type: str) -> bool:
    if project_type == 'annotation':
        return int(message.sequence_no or 0) == int(cursor.get('sequence_no', -1))
    return (
        (message.created_at.isoformat() if message.created_at else '') == cursor.get('created_at')
        and str(message.id) == cursor.get('message_id')
    )


def _sender(message: ChatProjectMessage) -> dict:
    return {
        'message_id': message.id,
        'sequence_no': int(message.sequence_no or 0),
        'sender_user_id': message.sender_user_id,
        'sender_name': message.sender_name,
        'created_at': message.created_at,
        'summary': _summary(message.content),
    }


def _attachment_payload(attachment: ChatProjectAttachment) -> dict:
    return {
        'id': attachment.id,
        'original_name': attachment.original_name,
        'content_type': attachment.content_type,
        'file_size': int(attachment.file_size or 0),
    }


def _page_messages(query, project_type: str, cursor: dict | None, limit: int):
    paged = _order_messages(query, project_type)
    if cursor:
        paged = _before_message(paged, project_type, cursor, inclusive=False)
    rows = paged.limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [{**_sender(row), 'kind': 'message', 'attachment': None, 'url': None} for row in rows]
    next_cursor = _encode_cursor(_message_cursor(rows[-1], project_type)) if has_more and rows else None
    return items, next_cursor


def _page_attachments(query, project_type: str, cursor: dict | None, limit: int, kind: str):
    ordered = query
    if project_type == 'annotation':
        ordered = ordered.order_by(ChatProjectMessage.sequence_no.desc(), ChatProjectAttachment.id.desc())
    else:
        ordered = ordered.order_by(
            ChatProjectMessage.created_at.desc(),
            ChatProjectMessage.id.desc(),
            ChatProjectAttachment.id.desc(),
        )
    if cursor:
        attachment_id = UUID(cursor['attachment_id'])
        if project_type == 'annotation':
            sequence_no = int(cursor['sequence_no'])
            ordered = ordered.filter(or_(
                ChatProjectMessage.sequence_no < sequence_no,
                and_(ChatProjectMessage.sequence_no == sequence_no, ChatProjectAttachment.id < attachment_id),
            ))
        else:
            created_at = dt.datetime.fromisoformat(cursor['created_at'])
            message_id = UUID(cursor['message_id'])
            ordered = ordered.filter(or_(
                ChatProjectMessage.created_at < created_at,
                and_(ChatProjectMessage.created_at == created_at, ChatProjectMessage.id < message_id),
                and_(
                    ChatProjectMessage.created_at == created_at,
                    ChatProjectMessage.id == message_id,
                    ChatProjectAttachment.id < attachment_id,
                ),
            ))
    rows = ordered.with_entities(ChatProjectMessage, ChatProjectAttachment).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = []
    for message, attachment in rows:
        payload = _sender(message)
        if not payload['summary']:
            payload['summary'] = attachment.original_name
        payload.update(kind=kind, attachment=_attachment_payload(attachment), url=None)
        items.append(payload)
    next_cursor = None
    if has_more and rows:
        message, attachment = rows[-1]
        next_cursor = _encode_cursor(_message_cursor(message, project_type, attachment_id=str(attachment.id)))
    return items, next_cursor


def _page_links(query, project_type: str, cursor: dict | None, limit: int):
    items = []
    inclusive = cursor is not None
    guard = 0
    batch_size = max(limit, 30)
    while len(items) <= limit and guard < 30:
        guard += 1
        batch_query = query
        if cursor:
            batch_query = _before_message(batch_query, project_type, cursor, inclusive=inclusive)
        batch = _order_messages(batch_query, project_type).limit(batch_size).all()
        if not batch:
            break
        for message in batch:
            urls = extract_urls(message.content or '')
            start = 0
            if cursor and inclusive and _same_message(message, cursor, project_type):
                start = int(cursor.get('url_index', -1)) + 1
            for index in range(start, len(urls)):
                payload = _sender(message)
                payload.update(kind='link', attachment=None, url=urls[index], summary=urls[index])
                items.append((payload, message, index))
                if len(items) > limit:
                    kept = items[:limit]
                    last_payload, last_message, last_index = kept[-1]
                    next_cursor = _encode_cursor(_message_cursor(last_message, project_type, url_index=last_index))
                    return [item for item, _message, _index in kept], next_cursor
        last = batch[-1]
        cursor = _message_cursor(last, project_type, url_index=10**9)
        inclusive = False
        if len(batch) < batch_size:
            break
    return [item for item, _message, _index in items], None


def _link_total(query) -> int:
    total = 0
    for (content,) in query.order_by(None).with_entities(ChatProjectMessage.content).all():
        total += len(extract_urls(content or ''))
    return total


def search_chat_history(
    db: Session,
    *,
    project_type: str,
    project_id: UUID,
    user_id: UUID,
    kind: str = 'all',
    keyword: str | None = None,
    sender_user_id: UUID | None = None,
    date_from: dt.datetime | None = None,
    date_to: dt.datetime | None = None,
    favorites_only: bool = False,
    cursor: str | None = None,
    limit: int = 30,
    include_user_messages: bool = True,
) -> dict:
    normalized_kind = KIND_ALIASES.get(kind or 'all')
    if normalized_kind is None:
        raise ChatHistoryError('不支持的检索类型')
    safe_limit = min(max(int(limit or 30), 1), 50)
    keyword_text = (keyword or '').strip()
    decoded = _decode_cursor(cursor) if cursor else None
    filters = dict(
        project_type=project_type,
        project_id=project_id,
        user_id=user_id,
        sender_user_id=sender_user_id,
        date_from=date_from,
        date_to=date_to,
        favorites_only=favorites_only,
        include_user_messages=include_user_messages,
    )
    messages = _with_text_keyword(_filtered_messages(db, **filters), keyword_text) if keyword_text else _filtered_messages(db, **filters)
    images = _attachment_query(_filtered_messages(db, **filters), images=True, keyword=keyword_text)
    files = _attachment_query(_filtered_messages(db, **filters), images=False, keyword=keyword_text)
    links = _link_query(_filtered_messages(db, **filters), keyword_text)
    totals = {
        'all': messages.order_by(None).count(),
        'image': images.order_by(None).with_entities(func.count(ChatProjectAttachment.id)).scalar() or 0,
        'file': files.order_by(None).with_entities(func.count(ChatProjectAttachment.id)).scalar() or 0,
        'link': _link_total(links),
    }
    if normalized_kind == 'image':
        items, next_cursor = _page_attachments(images, project_type, decoded, safe_limit, 'image')
        total = totals['image']
    elif normalized_kind == 'file':
        items, next_cursor = _page_attachments(files, project_type, decoded, safe_limit, 'file')
        total = totals['file']
    elif normalized_kind == 'link':
        items, next_cursor = _page_links(links, project_type, decoded, safe_limit)
        total = totals['link']
    else:
        items, next_cursor = _page_messages(messages, project_type, decoded, safe_limit)
        total = totals['all']
    return {'items': items, 'total': total, 'totals': totals, 'next_cursor': next_cursor}
