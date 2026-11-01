"""基于章节的通用简历补充字段归类；不依赖姓名、不调用模型、不写数据库。"""
from __future__ import annotations

import re
from uuid import NAMESPACE_URL,uuid5

HEADINGS = {
    'self_assessment': ('自我评价','个人评价','自我介绍','个人优势','self assessment','self-assessment','personal profile','about me','profile'),
    'job_intention': ('求职意向','求职目标','职业目标','career objectives','career objective','objective'),
    'other_skills': ('其他技能','个人技能','it技能','软件技能','软件','other skills','additional skills and achievements','software','technical skills'),
    'interests': ('兴趣爱好','个人爱好','爱好','interests','hobbies','hobby'),
    'awards_honors': ('奖励和荣誉','奖项与荣誉','获奖经历','荣誉奖励','honors','honors & awards','awards','awards and honors'),
    'training': ('培训经历','培训经验','training','professional training'),
    'campus_positions': ('校内职务','校园职务','学生工作','campus positions','campus activities'),
    'campus_awards': ('校内奖励','校园奖励','campus awards'),
    'professional_domains': ('专业领域','擅长领域','areas of expertise','fields of expertise','specializations'),
}
BOUNDARIES = ('教育经历','教育背景','教育历史','工作经历','工作经验','实习经历','语言能力','语言水平','资格证书','证书','基本信息','个人信息','联系方式','联系信息','求职经历','education','employment history','employement history','work experience','voluntary work','language skills','certificates','contact details','services','lingue','education background')
ENTRY_KEYS = {'training','campus_positions','campus_awards'}


def heading(value: str) -> str:
    text=re.sub(r'^\s*[\d一二三四五六七八九十]+[.、\-－）)]\s*','',value)
    return re.sub(r'\s+',' ',text.strip(' \t:：·●•')).casefold()


def section_blocks(lines: list[dict]) -> list[dict]:
    """必须传入已经确认属于同一人的有序行；未知标题宁可不分类。"""
    aliases={heading(label):key for key,labels in HEADINGS.items() for label in labels}
    stops={heading(label) for label in BOUNDARIES}
    blocks=[];active=None
    for row in lines:
        value=row['text'];key=heading(value)
        inline=re.match(r'^\s*([^:：]{1,60})[:：]\s*(\S.*)$',value)
        inline_key=aliases.get(heading(inline[1])) if inline else None
        if inline_key:
            # 表格中的“字段：值”只消费这一行，不能继续吞入下一行学校或联系方式。
            blocks.append({'field':inline_key,'heading_line':row['id'],'lines':[{**row,'content_text':inline[2]}]})
            active=None
        elif key in aliases:
            active={'field':aliases[key],'heading_line':row['id'],'lines':[]};blocks.append(active)
        elif key in stops:
            active=None
        elif active is not None and value.strip():
            active['lines'].append(row)
    # 某些PDF文本层把自评标题排在正文后面。仅在尾部空标题及明显不同的
    # 项目符号/冒号结构同时成立时恢复，避免把普通获奖条目猜成自评。
    if len(blocks)>=2 and blocks[-1]['field']=='self_assessment' and not blocks[-1]['lines'] and blocks[-2]['field']=='awards_honors':
        previous=blocks[-2]['lines']
        split=next((i for i,row in enumerate(previous) if re.match(r'^\s*●\s*[^：:]{2,20}[：:]',row['text'])),None)
        if split is not None:
            blocks[-1]['lines']=previous[split:]
            blocks[-1]['reading_order_recovered']=True
            blocks[-2]['lines']=previous[:split]
    return [block for block in blocks if block['lines']]


def extract_sections(lines: list[dict], source_hash: str) -> dict:
    sections={};evidence={};flags=[]
    for block in section_blocks(lines):
        key=block['field'];rows=block['lines'];text='\n'.join(r.get('content_text',r['text']) for r in rows)
        if len(text)>20000:
            flags.append(f'{key}:section_over_budget_keep_source');continue
        ids=[row['id'] for row in rows]
        proof={'heading_line':block['heading_line'],'line_ids':ids,'quote':'\n'.join(r['text'] for r in rows)}
        if block.get('reading_order_recovered'):
            proof['reading_order_recovered']=True
            flags.append('self_assessment:heading_after_body_check_layout')
        if key in ENTRY_KEYS:
            # 日期开头开启新事件，正文不摘要；边界模糊时作为一条保留，而不猜单位或岗位。
            groups=[]
            for row in rows:
                if not groups or re.match(r'^\s*\d{4}[年./-]\d',row['text']):groups.append([])
                groups[-1].append(row)
            if len(groups)+len(sections.get(key,[]))>100:
                flags.append(f'{key}:too_many_events_keep_source');continue
            for group in groups:
                index=len(sections.setdefault(key,[]))
                sections[key].append({'id':str(uuid5(NAMESPACE_URL,source_hash+':'+key+':'+','.join(str(r['id']) for r in group))),
                    'description':'\n'.join(r['text'] for r in group)})
                evidence[f'{key}.{index}']={**proof,'line_ids':[r['id'] for r in group],'quote':'\n'.join(r['text'] for r in group)}
        elif key=='professional_domains':
            values=[v.strip() for v in re.split(r'\s+[－–-]\s+|[－；;\n]',text) if v.strip()]
            combined=list(dict.fromkeys(sections.get(key,[])+values))
            if len(combined)>100:
                flags.append('professional_domains:too_many_keep_source')
            else:
                old=evidence.get(key)
                sections[key]=combined
                evidence[key]={**proof,'line_ids':(old['line_ids'] if old else [])+ids,'quote':'\n'.join(v for v in [(old or {}).get('quote'),proof['quote']] if v)}
        else:
            combined='\n'.join(v for v in [sections.get(key,''),text] if v)
            if len(combined)>20000:flags.append(f'{key}:combined_over_budget_keep_source');continue
            sections[key]=combined
            old=evidence.get(key)
            evidence[key]={'heading_line':block['heading_line'],'line_ids':(old['line_ids'] if old else [])+ids,'quote':'\n'.join(v for v in [(old or {}).get('quote'),proof['quote']] if v)}
    return {'fields':sections,'evidence':evidence,'review_flags':flags}
