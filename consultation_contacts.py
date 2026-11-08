"""咨询复用客户联系人名录；追加或更新同名联系人，不删除客户的其他联系人。"""
from client_contact_people import attach, replace_details
from concurrency import assert_fresh
from models import Client, SubClient
from schemas import ClientContactPersonInput
from chat_time import api_time


def owner_for(db, client_id, sub_client_id=None, lock=False):
    if not client_id:
        return None
    owner_type, owner_id = (SubClient, sub_client_id) if sub_client_id else (Client, client_id)
    query = db.query(owner_type).filter(owner_type.id == owner_id)
    if lock:
        query = query.with_for_update()
    owner = query.first()
    if not owner or (sub_client_id and owner.parent_client_id != client_id):
        raise ValueError('客户或子客户关联无效，请重新选择客户')
    return owner


def read_contacts(db, consultation):
    owner = owner_for(db, consultation.client_id, consultation.sub_client_id)
    if owner is None:
        consultation.contact_people = []
        consultation.contact_people_updated_at = None
        return
    attach(db, sub_clients=[owner]) if isinstance(owner, SubClient) else attach(db, clients=[owner])
    consultation.contact_people = owner.contact_people
    consultation.contact_people_updated_at = api_time(owner.updated_at)


def sync_contacts(db, client_id, sub_client_id, people, expected_updated_at=None):
    if not people:
        return
    owner = owner_for(db, client_id, sub_client_id, lock=True)
    if owner is None:
        raise ValueError('请先填写客户简称或选择客户，再保存联系人')
    attach(db, sub_clients=[owner]) if isinstance(owner, SubClient) else attach(db, clients=[owner])
    merged = [ClientContactPersonInput(**item) for item in owner.contact_people]
    positions = {item.name.casefold(): index for index, item in enumerate(merged)}
    seen = set()
    changed_existing = False
    for item in people:
        key = item.name.casefold()
        if key in seen:
            raise ValueError('同一客户的联系人姓名不能重复')
        seen.add(key)
        if key in positions:
            position = positions[key]
            if merged[position].model_dump() != item.model_dump():
                changed_existing = True
                merged[position] = item
        else:
            positions[key] = len(merged)
            merged.append(item)
    if len(merged) > 100:
        raise ValueError('每个客户最多维护100位联系人')
    if changed_existing:
        if expected_updated_at is None:
            raise ValueError('请重新选择客户以加载最新联系人后再修改')
        assert_fresh(owner, expected_updated_at)
    # 未变更的旧表单不回写客户，不改变客户版本或主联系人。
    if changed_existing or len(merged) != len(owner.contact_people):
        replace_details(db, owner, merged)
