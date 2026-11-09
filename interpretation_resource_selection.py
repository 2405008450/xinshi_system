"""口译人员选择来自人才总库，不要求人员预先登记某种能力。"""
from sqlalchemy import or_
from models import Translator
from resource_models import ResourcePerson
from talent_duplicate_service import active_query


def resolve_interpreter_resources(db, selected_ids, existing_ids=()):
    selected_ids=set(selected_ids)
    if not selected_ids:return {}
    people={row.id:row for row in active_query(db,db.query(ResourcePerson)).filter(ResourcePerson.id.in_(selected_ids)).all()}
    bridges=db.query(Translator).filter(or_(Translator.id.in_(selected_ids),Translator.resource_person_id.in_(selected_ids))).all()
    by_id={row.id:row for row in bridges}
    by_person={row.resource_person_id:row for row in bridges if row.resource_person_id}
    if any(value not in people and not (value in existing_ids and value in by_id) for value in selected_ids):
        raise ValueError('所选人员不在人才总库中或已被合并，请重新选择')
    resolved={}
    for value in selected_ids:
        person=people.get(value)
        if person is None:
            resolved[value]=value  # 旧安排继续保留，不要求重新登记能力。
            continue
        bridge=by_person.get(value) or by_id.get(value)
        if bridge is None:
            bridge=Translator(id=person.id,resource_person_id=person.id,translator_name=person.full_name,
                translator_code=person.resource_code,status=person.status,cooperation_type=person.cooperation_type,gender=person.gender)
            db.add(bridge)
        elif bridge.resource_person_id is None:
            bridge.resource_person_id=person.id
        elif bridge.resource_person_id!=person.id:
            raise ValueError('所选人员关联不一致，请重新选择')
        resolved[value]=bridge.id
    if len(set(resolved.values()))!=len(resolved):raise ValueError('同一人员不能重复安排')
    db.flush()
    return resolved
