"""群聊新增好友按日记账，与人才概览在同一事务内按差额同步。"""
import copy
import re
from datetime import date, datetime
from uuid import UUID, uuid4
from typing import Literal
from fastapi import HTTPException
from pydantic import Field, StrictInt
from sqlalchemy.dialects.postgresql import insert
from interpretation_models import InterpretationLanguage
from language_catalog import normalize_language_search_text
from resource_development_models import DevelopmentFriendDaily as Daily, DevelopmentAudit as Audit
from resource_development_schemas import CleanModel
from resource_development_service import audit, snapshot, user_name, can_delegate, lock_writes
from talent_overview_models import TalentOverviewSnapshot
from talent_overview_service import get_talent_overview, load_talent_overview_data, _storage_payload, resolve_overview_for_language, _validate_language_identifiers


class FriendLine(CleanModel):
    channel: Literal['wechat', 'enterprise']
    column_key: str = Field(min_length=1, max_length=80)
    language_value: str = Field(min_length=1, max_length=100)
    language_type: Literal['language', 'dialect'] = 'language'
    overview_key: str = Field(default='', max_length=80)
    count: StrictInt | None = Field(default=None, ge=0, le=1000000)


class FriendWrite(CleanModel):
    revision: int = Field(default=0, ge=0)
    rows: list[FriendLine] = Field(default_factory=list, max_length=300)


class FriendAccountWrite(CleanModel):
    name: str = Field(min_length=1, max_length=60)
    channel: Literal['wechat', 'enterprise']


def require_writer(db, user):
    if not can_delegate(db, user):
        raise HTTPException(403, '每日共享统计需要资源开拓代录或管理员权限')


def accounts(data):
    result = []
    for c in data['columns']:
        if not (re.match(r'^HR\d+', c['label'], re.I) or c['label'].startswith(('微信·', '企微·'))):
            continue
        channel = 'enterprise' if '企微' in c['label'] else 'wechat'
        result.append({'key': c['key'], 'label': c['label'], 'channel': channel})
    return result


def locked_overview(db):
    db.execute(insert(TalentOverviewSnapshot).values(id=1, payload=_storage_payload(load_talent_overview_data()), revision=1).on_conflict_do_nothing(index_elements=['id']))
    return db.query(TalentOverviewSnapshot).filter_by(id=1).with_for_update().populate_existing().one()


def get_options(db, user):
    data = get_talent_overview(db)
    languages = []
    for l in db.query(InterpretationLanguage).filter_by(is_active=True).order_by(InterpretationLanguage.label):
        matched, mode = resolve_overview_for_language(l, data=data)
        languages.append({'id': str(l.id), 'label': l.label, 'language_type': l.language_type,
                          'overview_key': matched['overview_key'] if matched else '', 'overview_label': matched['language'] if matched else '', 'match_type': mode})
    return {'accounts': accounts(data), 'languages': languages, 'overview_rows': [{'key': r['overview_key'], 'label': r['language']} for r in data['rows']], 'can_write': can_delegate(db, user)}


def totals(rows):
    return {ch: sum(r.get('count') or 0 for r in rows if r['channel'] == ch) for ch in ['wechat', 'enterprise']}


def serialize(db, row, day, user, detail=True):
    result = {'work_date': day.isoformat(), 'revision': row.revision if row else 0, 'rows': row.rows if row else [],
              'totals': totals(row.rows if row else []), 'updated_at': row.updated_at if row else None,
              'updated_by_name': user_name(db, row.updated_by) if row else '', 'can_write': can_delegate(db, user)}
    if detail:
        result['audit'] = [{'at': x.created_at, 'actor': user_name(db, x.actor_id), 'totals': totals(x.after.get('rows', []))} for x in db.query(Audit).filter_by(entity_id=row.id).order_by(Audit.created_at.desc())] if row else []
    return result


def add_account(db, user, payload):
    require_writer(db, user); lock_writes(db)
    snap = locked_overview(db); data = copy.deepcopy(snap.payload)
    name = payload.name.strip()
    if payload.channel == 'wechat' and '企微' in name:
        raise HTTPException(422, '普通微信账号名不能带企微，请选择企业微信')
    normalized = re.sub(r'\s+', '', name).casefold()
    short_input = re.fullmatch(r'(hr\d+)(?:企微|微信)?', normalized)
    if short_input:
        normalized = short_input[1]
    for item in accounts(data):
        short = re.match(r'^HR\d+', item['label'], re.I)
        if item['channel'] == payload.channel and normalized in {re.sub(r'\s+', '', item['label']).casefold(), short[0].casefold() if short else '', item['label'].split('·', 1)[-1].casefold()}:
            return item
    label = ('企微·' if payload.channel == 'enterprise' else '微信·') + name
    if len(data['columns']) >= 100: raise HTTPException(422, '人才概览账号列已达上限')
    key = 'col-' + str(uuid4()); group = 'wecom' if payload.channel == 'enterprise' else 'sheet'
    column = {'key': key, 'label': label, 'group': group, 'width': 120}
    position = next((i for i,c in enumerate(data['columns']) if c['group'] == 'wecom'), len(data['columns'])) if group == 'sheet' else len(data['columns'])
    data['columns'].insert(position, column)
    for r in data['rows']: r['counts'][key] = None
    snap.payload = data; snap.revision += 1; snap.updated_by = user.id; snap.updated_at = datetime.now()
    db.add(Audit(entity_id=uuid4(), entity_type='friend_account', actor_id=user.id, action='create', before={}, after=column))
    db.flush()
    return {'key': key, 'label': label, 'channel': payload.channel}


def save_daily(db, user, day, payload):
    require_writer(db, user); lock_writes(db)
    old = db.query(Daily).filter_by(work_date=day).with_for_update().one_or_none()
    # 修订号阻止整日表单被其他人的旧草稿覆盖；重复提交不重复记账。
    if (old.revision if old else 0) != payload.revision:
        if old and [{k:r.get(k) for k in FriendLine.model_fields} for r in old.rows] == [r.model_dump() for r in payload.rows]:
            return old
        raise HTTPException(409, '这一天已被其他人更新，请重新加载后再保存')
    snap = locked_overview(db); data = copy.deepcopy(snap.payload)
    account_map = {a['key']: a for a in accounts(data)}
    normalized_rows = []; applied = []; seen = set(); created_overview_keys = set()
    for i, line in enumerate(payload.rows):
        account = account_map.get(line.column_key)
        if not account or account['channel'] != line.channel: raise HTTPException(422, f'第{i+1}行账号与微信/企微类别不一致')
        try: language_id = UUID(line.language_value)
        except ValueError: language_id = None
        lang = db.get(InterpretationLanguage, language_id) if language_id else None
        if language_id and (not lang or not lang.is_active): raise HTTPException(422, f'第{i+1}行语种已失效')
        if not lang:
            key = normalize_language_search_text(line.language_value)
            matches = [l for l in db.query(InterpretationLanguage) if normalize_language_search_text(l.label) == key]
            if matches:
                lang = matches[0]
                if not lang.is_active: raise HTTPException(422, f'第{i+1}行语种已停用，请先在字典中恢复')
            else:
                lang = InterpretationLanguage(id=uuid4(), label=line.language_value, language_type=line.language_type, is_custom=True, is_active=True, created_by=user.id, updated_by=user.id)
                db.add(lang); db.flush()
        matched, mode = resolve_overview_for_language(lang, data=data)
        if matched and line.overview_key and line.overview_key != matched['overview_key'] and not (line.overview_key == '__new__' and matched['overview_key'] in created_overview_keys):
            raise HTTPException(422, f'第{i+1}行已有确定的语种映射，请重新加载')
        if not matched:
            if mode == 'ambiguous': raise HTTPException(422, f'第{i+1}行语种存在多个别名映射，请先整理字典')
            matched = next((r for r in data['rows'] if r['overview_key'] == line.overview_key), None)
            if not matched and line.overview_key == '__new__':
                if len(data['rows']) >= 500: raise HTTPException(422, '人才概览语种已达上限')
                matched = {'overview_key': 'row-' + str(uuid4()), 'language': lang.label, 'aliases': [], 'updated_at': None, 'counts': {c['key']: None for c in data['columns']}}
                data['rows'].append(matched)
                try:
                    _validate_language_identifiers(data['rows'])
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
                created_overview_keys.add(matched['overview_key'])
            if not matched: raise HTTPException(422, f'第{i+1}行语种未匹配，请选择概览语种或明确新增一行')
            lang.talent_overview_key = matched['overview_key']; lang.updated_by = user.id
        cell = (matched['overview_key'], line.column_key)
        if cell in seen: raise HTTPException(422, f'第{i+1}行与前面账号、概览语种重复，请合并人数')
        seen.add(cell)
        normalized_rows.append({**line.model_dump(), 'language_value': str(lang.id), 'language_type': lang.language_type, 'overview_key': matched['overview_key'], 'language_label': lang.label, 'account_label': account['label']})
        applied.append({'overview_key': cell[0], 'column_key': cell[1], 'count': line.count or 0})
    delta = {}
    for sign, entries in [(-1, old.applied if old else []), (1, applied)]:
        for item in entries:
            key = (item['overview_key'], item['column_key']); delta[key] = delta.get(key, 0) + sign * item['count']
    by_key = {r['overview_key']: r for r in data['rows']}
    for (rk, ck), amount in delta.items():
        if not amount: continue
        target = by_key.get(rk)
        if not target or ck not in target['counts']: raise HTTPException(409, '原关联的概览单元格已不存在，请先核实')
        value = (target['counts'][ck] or 0) + amount
        if value < 0: raise HTTPException(409, '概览人数不足以扣回原统计，可能被手动修改，请先核实')
        target['counts'][ck] = value; target['updated_at'] = max(target.get('updated_at') or '', day.isoformat())
    before = snapshot(old) if old else None
    row = old or Daily(id=uuid4(), work_date=day, created_by=user.id, revision=0)
    row.rows = normalized_rows; row.applied = applied; row.revision += 1; row.updated_by = user.id; row.updated_at = datetime.now()
    if not old: db.add(row)
    snap.payload = data; snap.revision += 1; snap.updated_by = user.id; snap.updated_at = datetime.now()
    audit(db, user, row, 'update' if old else 'create', before)
    db.flush()
    return row

