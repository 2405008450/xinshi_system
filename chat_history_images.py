"""附件图片与正文截图共用筛选、计数和稳定游标；不加载截图二进制。"""
from uuid import UUID
from sqlalchemy import String,and_,or_,cast,func,inspect,literal,true,column,Text
from models import ChatProjectMessage as Message,ChatProjectAttachment as Attachment,ChatProjectMessageAttachment as Link


def image_query(db,message_query,keyword=''):
    from chat_history_search import _attachment_query
    images=_attachment_query(message_query,images=True,keyword=keyword)
    ordinary=images.with_entities(Message.id.label('message_id'),Message.sequence_no.label('sequence_no'),Message.created_at.label('created_at'),
        cast(Attachment.id,String).label('image_id'),literal('attachment').label('source'),Attachment.original_name.label('original_name'),
        Attachment.content_type.label('content_type'),Attachment.file_size.label('file_size'),literal(True).label('available'))
    from editor_screenshot_models import EditorScreenshot as Shot,EditorScreenshotBlob as Blob
    schema=inspect(db.connection())
    if not schema.has_table(Shot.__tablename__) or not schema.has_table(Blob.__tablename__):return ordinary.subquery()
    reference=literal('screenshot://')+func.replace(cast(Shot.id,String),'-','')
    linked=or_(func.replace(func.lower(func.coalesce(Message.content,'')),'-','').contains(reference),
        func.replace(func.lower(cast(Message.content_json,String)),'-','').contains(reference))
    if db.get_bind().dialect.name=='postgresql':
        from sqlalchemy.dialects.postgresql import ARRAY,UUID as PGUUID
        # 先从本次会话消息提取引用，再按截图主键查找，避免消息与整个截图库做模糊交叉匹配。
        pattern=r'screenshot://([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
        refs=func.regexp_matches(func.concat(Message.content,' ',cast(Message.content_json,Text)),pattern,'gi').table_valued(column('reference',ARRAY(Text))).render_derived().lateral()
        shots=message_query.join(refs,true()).join(Shot,Shot.id==cast(refs.c.reference[1],PGUUID(as_uuid=True)))
    else:
        shots=message_query.join(Shot,linked)
    shots=shots.outerjoin(Blob,Blob.sha256==Shot.blob_sha256).filter(
        or_(Blob.content_type.like('image/%'),and_(Shot.blob_sha256.is_(None),Shot.retention_kind=='chat')))
    # 同一截图同时以附件和正文引用保存时只计一次。
    duplicate=db.query(Link.message_id).join(Attachment,Attachment.id==Link.attachment_id).filter(Link.message_id==Message.id,
        func.replace(Attachment.storage_name,'-','')==literal('screenshot:')+func.replace(cast(Shot.id,String),'-','')).exists()
    shots=shots.filter(~duplicate)
    if keyword:
        from search_matching import keyword_contains,search_terms
        for term in search_terms(keyword):shots=shots.filter(or_(keyword_contains(Message.content,term),keyword_contains(literal('聊天截图'),term)))
    screenshots=shots.with_entities(Message.id.label('message_id'),Message.sequence_no.label('sequence_no'),Message.created_at.label('created_at'),
        cast(Shot.id,String).label('image_id'),literal('screenshot').label('source'),literal('聊天截图').label('original_name'),
        func.coalesce(Blob.content_type,'image/png').label('content_type'),func.coalesce(Blob.byte_size,0).label('file_size'),Shot.blob_sha256.is_not(None).label('available')).distinct()
    return ordinary.union_all(screenshots).subquery()


def page_images(db,images,project_type,cursor,limit):
    from chat_history_search import _sender,_message_cursor,_encode_cursor
    columns=images.c
    order=[columns.sequence_no.desc()] if project_type in ('annotation','direct') else [columns.created_at.desc(),columns.message_id.desc()]
    query=db.query(images)
    if cursor:
        image_id=str(cursor.get('image_id') or cursor.get('attachment_id') or '')
        try:UUID(image_id)
        except ValueError:
            from chat_history_search import ChatHistoryError
            raise ChatHistoryError('图片分页游标无效')
        # PostgreSQL UUID cast 有横线，SQLite cast 没有；统一排序和比较。
        image_id=image_id.replace('-','')
        key=func.replace(columns.image_id,'-','')
        older_image=or_(key<image_id,and_(key==image_id,columns.source<cursor.get('image_source','attachment')))
        if project_type in ('annotation','direct'):
            sequence=int(cursor['sequence_no']);query=query.filter(or_(columns.sequence_no<sequence,and_(columns.sequence_no==sequence,older_image)))
        else:
            from datetime import datetime
            created=datetime.fromisoformat(cursor['created_at']);mid=UUID(cursor['message_id'])
            query=query.filter(or_(columns.created_at<created,and_(columns.created_at==created,columns.message_id<mid),and_(columns.created_at==created,columns.message_id==mid,older_image)))
    rows=query.order_by(*order,func.replace(columns.image_id,'-','').desc(),columns.source.desc()).limit(limit+1).all()
    more=len(rows)>limit;rows=rows[:limit]
    messages={row.id:row for row in db.query(Message).filter(Message.id.in_([row.message_id for row in rows]))} if rows else {}
    from editor_screenshot_service import valid_references,signed_reference
    result=[]
    for row in rows:
        message=messages[row.message_id];image_id=UUID(row.image_id)
        attachment=dict(id=str(image_id),original_name=row.original_name,content_type=row.content_type,file_size=row.file_size,source=row.source,available=row.available)
        if row.source=='screenshot':
            valid=image_id in (valid_references(message.content)|valid_references(message.content_json))
            attachment['available']=bool(row.available and valid)
            if valid:attachment['screenshot_reference']=signed_reference(image_id)
        result.append(dict(**_sender(message),kind='image',attachment=attachment,url=None))
    next_cursor=None
    if more and rows:
        last=rows[-1];next_cursor=_encode_cursor(_message_cursor(messages[last.message_id],project_type,image_id=str(UUID(last.image_id)),image_source=last.source))
    return result,next_cursor
