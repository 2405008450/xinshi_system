"""用户授权的同名且个人联系方式相同核重；只处理无歧义子组，复用原始资料留存。"""
import itertools
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func

from resource_models import ResourcePerson
from resource_service import get_talent_project_situations
from talent_duplicate_models import TalentDuplicateOperation
from talent_duplicate_schemas import DuplicateReviewCommit
from talent_duplicate_service import (PLACEHOLDERS, active_query, name_key, require_ready,
    contact_usage_index, _load_people, _pair_decisions, _decision_query, _merge_values, preview, commit,
    digest, merge_audit, operation_result)
from talent_name_merge_service import _automatic_request, _ordered

RULE = 'same-name-personal-contact-v1'
POLICY = '仅合并同名且有共同有效个人联系方式、无身份冲突和人工区分/暂缓结论的独立子组；不做链式合并。主档非空值保留、缺失补充、全部来源留档；已有语种角色分别保留，不自动取最高熟练度或启用能力；同角色及能力状态冲突留待人工。'


def metadata(db, key=None):
    columns = [ResourcePerson.id, ResourcePerson.full_name, ResourcePerson.resource_code, ResourcePerson.gender,
               ResourcePerson.birth_date, ResourcePerson.birth_year_month, ResourcePerson.created_at]
    query = active_query(db, db.query(*columns))
    if key is not None:
        query = query.filter(func.resource_person_duplicate_name_key(ResourcePerson.full_name) == key)
    return [SimpleNamespace(**dict(row._mapping)) for row in query.all()]


def _identity_conflict(members):
    genders = {str(p.gender).strip().lower() for p in members if p.gender and str(p.gender).strip().lower() not in PLACEHOLDERS}
    genders = {'男' if v in {'male','m','男'} else '女' if v in {'female','f','女'} else v for v in genders}
    months = {str(p.birth_year_month or p.birth_date)[:7] for p in members if p.birth_year_month or p.birth_date}
    days = {str(p.birth_date) for p in members if p.birth_date}
    return len(genders) > 1 or len(months) > 1 or len(days) > 1


def find_candidates(people, usage):
    """共同账号必须覆盖整个子组，且不被其他姓名主档共用；重叠分量整体待核。"""
    grouped, candidates, skipped = {}, [], []
    for person in people:
        key = name_key(person.full_name)
        if key and key not in PLACEHOLDERS and any(char.isalpha() for char in key):
            grouped.setdefault(key, []).append(person)
    by_id = {str(p.id): p for p in people}
    for key, members in sorted(grouped.items()):
        if len(members) < 2:
            continue
        ids = {str(p.id) for p in members}
        tokens = {}
        graph = {id:set() for id in ids}
        for id in ids:
            for kind, values in usage.by_person.get(id, {}).items():
                for value in values:
                    owners = usage.get((kind,value),set())
                    if len(owners) >= 2 and owners <= ids:
                        tokens.setdefault((kind,value),set()).update(owners)
        for owners in tokens.values():
            for a,b in itertools.combinations(owners,2):
                graph[a].add(b);graph[b].add(a)
        seen = set()
        for root in sorted(ids):
            if root in seen or not graph[root]:
                continue
            pending, component = [root],set()
            while pending:
                current = pending.pop()
                if current not in component:
                    component.add(current);pending.extend(graph[current]-component)
            seen.update(component)
            selected = [by_id[id] for id in sorted(component)]
            shared = [(kind,value) for (kind,value),owners in tokens.items() if component <= owners]
            reason = ('identity_conflict' if _identity_conflict(selected) else
                      'overlapping_or_transitive_contacts' if not shared else
                      'too_many_records' if len(component)>100 else None)
            base = dict(key=key,person_ids=sorted(component),codes=[p.resource_code for p in selected])
            if reason:
                skipped.append(dict(base,reason=reason));continue
            evidence = [{'kind':kind,'identifier_sha256':digest([kind,value])} for kind,value in sorted(shared)]
            # 版本覆盖整个同名组和共用范围；并发新增/编辑后必须重新预览。
            version = digest({'rule':RULE,'members':[dict(id=str(p.id),name=p.full_name,gender=p.gender,
                birth_date=str(p.birth_date or ''),birth_month=str(p.birth_year_month or '')) for p in sorted(members,key=lambda p:str(p.id))],
                'contacts':{id:{kind:sorted((value,sorted(usage.get((kind,value),set()))) for value in values)
                    for kind,values in usage.by_person.get(id,{}).items()} for id in sorted(ids)}})
            candidates.append(dict(base,version=version,evidence=evidence))
    return dict(rule=RULE,policy=POLICY,candidates=candidates,skipped=skipped)


def discover(db):
    require_ready(db)
    return find_candidates(metadata(db),contact_usage_index(db))


def preview_candidate(db, candidate):
    require_ready(db)
    usage = contact_usage_index(db)
    current = find_candidates(metadata(db,candidate['key']),usage)
    found = next((item for item in current['candidates'] if item['person_ids'] == candidate['person_ids']),None)
    if not found or found['version'] != candidate['version']:
        raise HTTPException(409,'同名成员、联系方式或身份信息已变化，请重新扫描')
    loaded = _load_people(db,[UUID(id) for id in candidate['person_ids']])
    if len(loaded) != len(candidate['person_ids']) or any(p.archived_into_id for p in loaded.values()):
        raise HTTPException(409,'候选档案已变化或已归档')
    decisions = _pair_decisions(list(loaded.values()),_decision_query(db).filter_by(name_key=candidate['key']).order_by(TalentDuplicateOperation.created_at,TalentDuplicateOperation.id).all(),usage)
    if decisions:
        raise HTTPException(422,'子组已有有效人工区分或暂缓结论，不自动覆盖')
    situations = get_talent_project_situations(db,list(loaded))
    people = _ordered(list(loaded.values()),situations)
    _,_,conflicts = _merge_values(people,people[0],{},preserve_language_roles=True)
    for conflict in conflicts:
        if ':' not in conflict['key']:
            continue
        # 来源备注和顺序不是身份/能力状态冲突；相同语种的不同既有角色分别保留。
        descriptive={'remarks','priority','language_label','source_language_label','target_language_label','display'}
        variants=[{k:v for k,v in option['value'].items() if k not in descriptive} for option in conflict['options']]
        if len({digest(value) for value in variants})>1:
            raise HTTPException(422,'存在同角色熟练度或业务明细状态冲突，留待人工确认')
    request = _automatic_request(people,preserve_language_roles=True)
    request.note = '用户授权按同名且个人联系方式相同直接合并；主档非空值保留，缺失补充，其他冲突原值与来源完整留档。'
    result = preview(db,request)
    audit = merge_audit(result,request.decisions)
    audit.update(rule=RULE,policy=POLICY,evidence=found['evidence'])
    return dict(preview_token=result['preview_token'],automatic_request=request.model_dump(mode='json'),audit=audit,
                archive_ids=result['archive_ids'],target_id=result['target_id'],candidate=found)


def commit_candidate(db,candidate,preview_token,idempotency_key,actor):
    request_hash = digest(dict(candidate=candidate,preview_token=preview_token,idempotency_key=idempotency_key))
    def previous_result():
        previous=db.query(TalentDuplicateOperation).filter_by(idempotency_key=idempotency_key).first()
        if previous:
            if previous.actor_id != actor.id or previous.decisions.get('contact_merge_request_hash') != request_hash:
                raise HTTPException(409,'幂等键已用于其他处理')
            return operation_result(previous)
        return None
    previous=previous_result()
    if previous:
        return previous
    from talent_wechat_accounts import lock_account_writes
    lock_account_writes(db)
    previous=previous_result()
    if previous:
        return previous
    current=preview_candidate(db,candidate)
    if current['preview_token'] != preview_token:
        raise HTTPException(409,'资料或业务关联已变化，请重新预览')
    payload=DuplicateReviewCommit(**current['automatic_request'],preview_token=preview_token,idempotency_key=idempotency_key)
    return commit(db,payload,actor,audit_metadata={'merge_audit':current['audit'],'contact_merge_request_hash':request_hash,
        'contact_merge':{'rule':RULE,'candidate':candidate,'policy':POLICY},
        'review_context':{'mode':'user_authorized_contact_rule','rule':RULE,'agent_report':None}})
