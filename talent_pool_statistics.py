"""自动补齐共享语种行，人才总库人数独立统计，不写入来源数量。"""

import copy
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import String, case, cast, func, literal, select, union_all
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from interpretation_models import InterpretationLanguage
from resource_models import ResourceLanguageSkill, ResourcePerson
from talent_overview_models import TalentOverviewSnapshot
from talent_overview_service import (
    ENGLISH_NATIVE_LABEL, INVALID_OVERVIEW_CATALOG_LABELS, NON_LANGUAGE_OVERVIEW_ROWS,
    _storage_payload, _with_totals, get_talent_overview, load_talent_overview_data,
    resolve_overview_for_language,
    _overview_indexes,
)


def append_pool_language_rows(data, languages):
    """只补实际登记的语种；来源单元格保持空白，已有行与数据原样保留。"""
    result = copy.deepcopy(data)
    bindings = {}
    indexes = _overview_indexes(result)
    for language in sorted(languages, key=lambda item: (item.label, str(item.id))):
        if language.label in INVALID_OVERVIEW_CATALOG_LABELS | NON_LANGUAGE_OVERVIEW_ROWS:
            continue
        row, match_type = resolve_overview_for_language(language, data=result, indexes=indexes)
        if match_type == 'ambiguous':
            # 有冲突的历史别名不能自动猜测归属，保留在待核对列表。
            continue
        if row is None:
            row = {
                'overview_key': f'row-{uuid5(NAMESPACE_URL, "talent-language:" + str(language.id))}',
                'language': language.label,
                'aliases': list(dict.fromkeys(alias.alias for alias in (language.aliases or []) if alias.is_active)),
                'updated_at': None,
                'counts': {column['key']: None for column in result['columns']},
            }
            result['rows'].append(row)
            indexes = _overview_indexes(result)
        bindings[language.id] = row['overview_key']
    return _with_totals(result), bindings


def get_synced_talent_overview(db, *, include_wecom=False):
    """串行补齐并保存共享快照，修订号防止并发旧草稿覆盖新增行。"""
    snapshot = db.query(TalentOverviewSnapshot).filter(TalentOverviewSnapshot.id == 1).first()
    languages = db.query(InterpretationLanguage).filter(
        InterpretationLanguage.id.in_(db.query(ResourceLanguageSkill.language_id)),
    ).options(selectinload(InterpretationLanguage.aliases)).order_by(InterpretationLanguage.id).all()
    if snapshot is not None:
        data, bindings = append_pool_language_rows(snapshot.payload, languages)
        if len(data['rows']) == len(snapshot.payload['rows']) and all(
            not bindings.get(language.id) or language.talent_overview_key == bindings[language.id]
            for language in languages
        ):
            # 已同步的常规读取不争抢行锁，也不提交一次无变化的写事务。
            return get_talent_overview(db, include_wecom=include_wecom)
    db.execute(pg_insert(TalentOverviewSnapshot).values(
        id=1, payload=_storage_payload(load_talent_overview_data()), revision=1,
    ).on_conflict_do_nothing(index_elements=['id']))
    snapshot = db.query(TalentOverviewSnapshot).filter(
        TalentOverviewSnapshot.id == 1,
    ).with_for_update().populate_existing().one()
    # 等待锁期间目录可能变化；在锁内重新核对，避免沿用旧映射。
    languages = db.query(InterpretationLanguage).filter(
        InterpretationLanguage.id.in_(db.query(ResourceLanguageSkill.language_id)),
    ).options(selectinload(InterpretationLanguage.aliases)).populate_existing().order_by(InterpretationLanguage.id).all()
    data, bindings = append_pool_language_rows(snapshot.payload, languages)
    if len(data['rows']) != len(snapshot.payload['rows']):
        snapshot.payload = _storage_payload(data)
        snapshot.revision += 1
    for language in languages:
        key = bindings.get(language.id)
        if key and language.talent_overview_key != key:
            language.talent_overview_key = key
    db.commit()
    return get_talent_overview(db, include_wecom=include_wecom)


def summarize_language_people(data, languages, skills, total_people):
    """同一档案在同一概览语种内只计一次，跨语种分别计数。"""
    people_by_key = {row['overview_key']: set() for row in data['rows']}
    native_key = next((row['overview_key'] for row in data['rows']
                       if row['language'] == ENGLISH_NATIVE_LABEL), None)
    indexes = _overview_indexes(data)
    resolved = {item.id: resolve_overview_for_language(item, data=data, indexes=indexes)[0] for item in languages}
    labels = {item.id: item.label for item in languages}
    unmatched = {}
    with_language = set()
    for person_id, language_id, role in skills:
        with_language.add(person_id)
        row = resolved.get(language_id)
        if row:
            people_by_key[row['overview_key']].add(person_id)
            if row['language'] == '英语' and role == 'native' and native_key:
                people_by_key[native_key].add(person_id)
        else:
            unmatched.setdefault(language_id, set()).add(person_id)
    return {
        'total_people': total_people,
        'with_language_people': len(with_language),
        'without_language_people': total_people - len(with_language),
        'rows': [{'overview_key': key, 'people_count': len(people)} for key, people in people_by_key.items()],
        'unmatched': [{'language': labels.get(key, '未知语种'), 'people_count': len(people)}
                      for key, people in unmatched.items()],
    }


def get_pool_language_statistics(db):
    data = get_synced_talent_overview(db, include_wecom=True)
    languages = db.query(InterpretationLanguage).options(selectinload(InterpretationLanguage.aliases)).all()
    return {**aggregate_language_people(db, data, languages), 'overview': data}


def aggregate_language_people(db, data, languages):
    """数据库内按人才去重，只传回语种汇总；多个目录别名仍合并到同一概览行。"""
    from talent_duplicate_service import active_query
    indexes = _overview_indexes(data)
    resolved = {item.id: resolve_overview_for_language(item, data=data, indexes=indexes)[0] for item in languages}
    bindings = {identifier: 'row:' + row['overview_key'] for identifier, row in resolved.items() if row}
    skills = active_query(db, db.query(ResourceLanguageSkill.person_id, ResourceLanguageSkill.language_id,
                                      ResourceLanguageSkill.role).join(ResourcePerson)).subquery()
    bucket = case(bindings, value=skills.c.language_id,
                  else_=literal('unmatched:') + cast(skills.c.language_id, String)) if bindings else (
                      literal('unmatched:') + cast(skills.c.language_id, String))
    contributions = [select(skills.c.person_id.label('person_id'), bucket.label('bucket')),
                     select(skills.c.person_id, literal('all'))]
    native_key = next((row['overview_key'] for row in data['rows'] if row['language'] == ENGLISH_NATIVE_LABEL), None)
    english_ids = [identifier for identifier, row in resolved.items() if row and row['language'] == '英语']
    if native_key and english_ids:
        contributions.append(select(skills.c.person_id, literal('row:' + native_key)).where(
            skills.c.language_id.in_(english_ids), skills.c.role == 'native'))
    combined = union_all(*contributions).subquery()
    counts = dict(db.query(combined.c.bucket, func.count(func.distinct(combined.c.person_id))).group_by(combined.c.bucket).all())
    total = active_query(db, db.query(func.count(ResourcePerson.id))).scalar()
    labels = {str(item.id): item.label for item in languages}
    labels.update({item.id.hex: item.label for item in languages if hasattr(item.id, 'hex')})
    with_language = counts.get('all', 0)
    return {'total_people': total, 'with_language_people': with_language,
            'without_language_people': total - with_language,
            'rows': [{'overview_key': row['overview_key'], 'people_count': counts.get('row:' + row['overview_key'], 0)}
                     for row in data['rows']],
            'unmatched': [{'language': labels.get(key.removeprefix('unmatched:'), '未知语种'), 'people_count': count}
                          for key, count in counts.items() if key.startswith('unmatched:')]}
