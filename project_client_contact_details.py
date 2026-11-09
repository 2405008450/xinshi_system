"""项目表单复用客户联系人详情；带版本校验，保存时不改写无权查看的联系方式。"""
import hashlib
import json
from sqlalchemy import inspect
from fastapi import HTTPException
from models import Client,SubClient
from client_contact_people import ClientContactPerson,ClientContactPersonDetail,attach,ensure,owner_rows
from annotation_progress_time import business_now

DETAIL_FIELDS={'client_contact_method','client_contact_description','client_contact_version'}


def detail_version(method,description):
    return hashlib.sha256(json.dumps([method or '',description or ''],ensure_ascii=False).encode()).hexdigest()


def contact_details(db,owner):
    attach(db,sub_clients=[owner]) if isinstance(owner,SubClient) else attach(db,clients=[owner])
    return [dict(item,version=detail_version(item['contact_method'],item['description'])) for item in owner.contact_people]


def save_project_contact_details(db,data):
    supplied={key:data.pop(key,None) for key in DETAIL_FIELDS}
    if supplied['client_contact_version'] is None:return
    name=str(data.get('contact_name') or '').strip()
    if not name:raise ValueError('请先填写客户联系人姓名')
    owner=db.get(SubClient,data['sub_client_id']) if data.get('sub_client_id') else db.get(Client,data.get('client_id'))
    if not owner:raise ValueError('请先选择或填写客户')
    if isinstance(owner,SubClient) and owner.parent_client_id!=data.get('client_id'):raise ValueError('子客户不属于当前客户')
    if not inspect(db.connection()).has_table(ClientContactPersonDetail.__tablename__):raise ValueError('客户联系人详情表尚未初始化')
    db.query(type(owner).id).filter_by(id=owner.id).with_for_update().first()
    before=next((item for item in contact_details(db,owner) if item['name'].casefold()==name.casefold()),None)
    expected=supplied['client_contact_version']
    if expected!=(before['version'] if before else 'new') and not (expected=='new' and before and not before['contact_method'] and not before['description']):raise HTTPException(409,'客户联系人资料已更新，请重新选择联系人后再保存')
    visible=db.info.get('client_contacts_visible',False)
    incoming=supplied['client_contact_method']
    if not visible and incoming is not None:raise HTTPException(403,'仅客户部、销售部和行政部可维护客户联系方式')
    ensure(db,owner,name);db.flush()
    person=next(row for row in owner_rows(db,owner) if row.normalized_name==name.casefold())
    detail=db.get(ClientContactPersonDetail,person.id)
    if detail is None:detail=ClientContactPersonDetail(person_id=person.id,contact_method=before['contact_method'] if before else '',description=before['description'] if before else '');db.add(detail)
    if visible and incoming is not None:detail.contact_method=incoming
    if supplied['client_contact_description'] is not None:detail.description=supplied['client_contact_description']
    if owner.contact_names and owner.contact_names[0].casefold()==name.casefold():owner.manager_contact=detail.contact_method
    moment=business_now()
    person.updated_at=moment
    owner.updated_at=moment.replace(tzinfo=None)
