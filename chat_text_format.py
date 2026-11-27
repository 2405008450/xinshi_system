"""聊天文字格式白名单；正文仍以纯文本保存，检索和提及不受影响。"""
from fastapi import HTTPException
from sqlalchemy import inspect
COLORS={'textColor':{'#dc2626','#2563eb'},'highlight':{'#dbeafe','#fef08a'},'underline':{'#111827','#dc2626','#2563eb'}}

def validate_format(content,document):
    try:return _validate_format(content,document)
    except (TypeError,ValueError,AttributeError,KeyError,RecursionError):raise HTTPException(422,'文字格式不正确')

def _validate_format(content,document):
    if document is None:return None
    if not isinstance(document,dict) or document.get('type')!='doc':raise HTTPException(422,'文字格式不正确')
    import json
    if len(json.dumps(document,ensure_ascii=False))>150000:raise HTTPException(422,'文字格式过大')
    runs=[]
    for i,block in enumerate(document.get('content',[])):
        if block.get('type')!='paragraph':raise HTTPException(422,'只支持聊天文字格式')
        if i:runs.append(dict(type='text',text='\n'))
        for node in block.get('content',[]):
            if node.get('type')!='text' or not isinstance(node.get('text'),str):raise HTTPException(422,'文字格式内容不正确')
            marks=[]
            for mark in node.get('marks',[]):
                kind=mark.get('type');color=(mark.get('attrs') or {}).get('color')
                if kind=='bold':marks.append(dict(type=kind))
                elif kind in COLORS and color in COLORS[kind]:marks.append(dict(type=kind,attrs=dict(color=color)))
                else:raise HTTPException(422,'不支持的文字格式或颜色')
            runs.append(dict(type='text',text=node['text'],marks=marks))
            if len(runs)>2000:raise HTTPException(422,'文字格式过多，请清除部分格式')
    text=''.join(r['text'] for r in runs)
    if text.strip()!=content.strip():raise HTTPException(422,'文字格式与消息正文不一致')
    # 接口既有规则去除首尾空白，同步修正格式文档，不移动正文中的格式范围。
    left=len(text)-len(text.lstrip());right=len(text.rstrip());offset=0;normalized=[]
    for run in runs:
        start=max(0,left-offset);end=min(len(run['text']),right-offset);offset+=len(run['text'])
        if end>start:normalized.append({**run,'text':run['text'][start:end]})
    return dict(type='doc',content=[dict(type='paragraph',content=normalized)]) if any(r.get('marks') for r in normalized) else None

def load_formats(db,ids):
    from discussion_chat_models import DiscussionMessageFormat as Format
    if not ids or not inspect(db.connection()).has_table(Format.__tablename__):return {}
    return {row.message_id:row.content_json for row in db.query(Format).filter(Format.message_id.in_(ids))}

def save_format(db,message_id,document):
    if document is None:return
    from discussion_chat_models import DiscussionMessageFormat as Format
    if not inspect(db.connection()).has_table(Format.__tablename__):raise HTTPException(503,'聊天文字格式尚未初始化，请联系管理员')
    db.add(Format(message_id=message_id,content_json=document))


FORMAT_FILTERS={
 'text_red':('textColor',['#dc2626','#b91c1c']), 'text_blue':('textColor',['#2563eb']),
 'highlight_blue':('highlight',['#dbeafe']), 'highlight_yellow':('highlight',['#fef08a','#fff59d']),
 'bold':('bold',None), 'underline_black':('underline',['#111827',None]),
 'underline_red':('underline',['#dc2626']), 'underline_blue':('underline',['#2563eb'])}

def format_condition(db,column,filters):
    from sqlalchemy import and_,or_,func,case,literal,cast
    codes=list(dict.fromkeys(filter(None,(filters or '').split(','))))
    if len(codes)>8 or any(code not in FORMAT_FILTERS for code in codes):raise HTTPException(422,'不支持的文字格式筛选')
    conditions=[]
    for code in codes:
        kind,colors=FORMAT_FILTERS[code]
        if db.get_bind().dialect.name=='postgresql':
            from sqlalchemy.dialects.postgresql import JSONPATH
            path='$.** ? (@.type == "'+kind+'"'
            if colors is not None:path+=' && ('+' || '.join('@.attrs.color == "'+color+'"' if color else '!exists(@.attrs.color)' for color in colors)+')'
            path+=')'
            conditions.append(func.jsonb_path_exists(column,cast(literal(path),JSONPATH)))
        else:
            tree=func.json_tree(column).table_valued('value','type').alias()
            node=case((tree.c.type=='object',tree.c.value),else_='{}')
            condition=func.json_extract(node,'$.type')==kind
            if colors is not None:condition=and_(condition,or_(*(func.json_extract(node,'$.attrs.color').is_(None) if color is None else func.json_extract(node,'$.attrs.color')==color for color in colors)))
            conditions.append(db.query(tree.c.value).filter(condition).exists())
    return and_(*conditions) if conditions else True
