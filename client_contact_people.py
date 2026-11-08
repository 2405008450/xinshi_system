"""客户与子客户的多联系人名录，供项目选择并同步新增姓名。"""
from uuid import UUID, uuid4
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, inspect, or_
from sqlalchemy.orm import Session
from sqlalchemy import Text
from models import Base, Client, SubClient
from annotation_progress_time import business_now


class ClientContactPerson(Base):
    __tablename__ = 'client_contact_person'
    __table_args__ = (
        CheckConstraint('(client_id IS NOT NULL AND sub_client_id IS NULL) OR (client_id IS NULL AND sub_client_id IS NOT NULL)', name='ck_client_contact_person_owner'),
        UniqueConstraint('client_id','normalized_name',name='uq_client_contact_person_client_name'),
        UniqueConstraint('sub_client_id','normalized_name',name='uq_client_contact_person_sub_name'),
    )
    id = Column(Uuid, primary_key=True, default=uuid4)
    client_id = Column(Uuid, ForeignKey('client.id', ondelete='CASCADE'), index=True)
    sub_client_id = Column(Uuid, ForeignKey('sub_client.id', ondelete='CASCADE'), index=True)
    contact_name = Column(String(100), nullable=False)
    normalized_name = Column(String(100), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=business_now, onupdate=business_now)


class ClientContactPersonDetail(Base):
    __tablename__ = 'client_contact_person_detail'
    person_id = Column(Uuid, ForeignKey('client_contact_person.id', ondelete='CASCADE'), primary_key=True)
    contact_method = Column(Text, nullable=False, default='')
    description = Column(Text, nullable=False, default='')


def attach_details(db, owner, people=None, details=None):
    people = people if people is not None else [row for row in owner_rows(db,owner) if row.is_active]
    if details is None:
        details = {}
        if people and inspect(db.connection()).has_table(ClientContactPersonDetail.__tablename__):
            details = {row.person_id:row for row in db.query(ClientContactPersonDetail).filter(ClientContactPersonDetail.person_id.in_([p.id for p in people])).all()}
    owner.contact_people = [dict(name=p.contact_name,contact_method=details[p.id].contact_method if p.id in details else (owner.manager_contact or '') if index==0 else '',description=details[p.id].description if p.id in details else '') for index,p in enumerate(people)]
    if not people:
        owner.contact_people = [dict(name=name,contact_method=(owner.manager_contact or '') if index==0 else '',description='') for index,name in enumerate(owner.contact_names)]


def replace_details(db, owner, people):
    if not inspect(db.connection()).has_table(ClientContactPersonDetail.__tablename__):raise ValueError('客户联系人详情表尚未初始化')
    names=[p.name.strip() for p in people]
    if len({name.casefold() for name in names})!=len(names):raise ValueError('同一客户的联系人姓名不能重复')
    replace(db,owner,names);db.flush()
    existing={p.normalized_name:p for p in owner_rows(db,owner)}
    for value in people:
        person=existing[value.name.strip().casefold()]
        detail=db.get(ClientContactPersonDetail,person.id)
        if detail is None:detail=ClientContactPersonDetail(person_id=person.id);db.add(detail)
        detail.contact_method=value.contact_method or '';detail.description=value.description or ''
    owner.manager_contact=people[0].contact_method or ''


def ready(db):
    if 'client_contact_people_ready' not in db.info:
        db.info['client_contact_people_ready'] = inspect(db.connection()).has_table(ClientContactPerson.__tablename__)
    return db.info['client_contact_people_ready']


def normalize_names(names):
    result=[];seen=set()
    if len(names or [])>100: raise ValueError('每个客户最多维护100位联系人')
    for raw in names or []:
        name=str(raw or '').strip()
        if not name: raise ValueError('请填写每位客户联系人的姓名')
        if len(name)>100: raise ValueError('客户联系人姓名不能超过100个字符')
        key=name.casefold()
        if key not in seen:result.append(name);seen.add(key)
    return result


def owner_rows(db, owner):
    column=ClientContactPerson.sub_client_id if isinstance(owner,SubClient) else ClientContactPerson.client_id
    return db.query(ClientContactPerson).filter(column==owner.id).order_by(ClientContactPerson.position,ClientContactPerson.id).all()


def names_for(db, owner):
    rows=[row.contact_name for row in owner_rows(db,owner) if row.is_active] if ready(db) else []
    if rows:return rows
    legacy=str(owner.client_manager or '').strip()
    return [legacy] if legacy else []


def attach(db, clients=(), sub_clients=()):
    owners=[*clients,*sub_clients]
    for client in clients:owners.extend(client.sub_clients or [])
    unique={('sub' if isinstance(owner,SubClient) else 'client',owner.id):owner for owner in owners}
    records={};people_by_owner={};details={}
    if unique and ready(db):
        client_ids=[key[1] for key in unique if key[0]=='client'];sub_ids=[key[1] for key in unique if key[0]=='sub']
        rows=db.query(ClientContactPerson).filter(ClientContactPerson.is_active.is_(True),or_(ClientContactPerson.client_id.in_(client_ids),ClientContactPerson.sub_client_id.in_(sub_ids))).order_by(ClientContactPerson.position,ClientContactPerson.id).all()
        for row in rows:
            key=('sub',row.sub_client_id) if row.sub_client_id else ('client',row.client_id)
            records.setdefault(key,[]).append(row.contact_name)
            people_by_owner.setdefault(key,[]).append(row)
        if rows and inspect(db.connection()).has_table(ClientContactPersonDetail.__tablename__):
            details={row.person_id:row for row in db.query(ClientContactPersonDetail).filter(ClientContactPersonDetail.person_id.in_([p.id for p in rows])).all()}
    for key,owner in unique.items():
        owner.contact_names=records.get(key) or ([owner.client_manager] if owner.client_manager else [])
        attach_details(db,owner,people_by_owner.get(key,[]),details)


def replace(db, owner, names):
    names=normalize_names(names)
    if not names:raise ValueError('请至少填写一位客户联系人')
    if not ready(db):raise ValueError('客户联系人名录表尚未初始化')
    db.query(type(owner).id).filter(type(owner).id==owner.id).with_for_update().first()
    existing={row.normalized_name:row for row in owner_rows(db,owner)}
    active={name.casefold() for name in names}
    for row in existing.values():row.is_active=row.normalized_name in active
    for position,name in enumerate(names):
        key=name.casefold();row=existing.get(key)
        if not row:
            row=ClientContactPerson(client_id=None if isinstance(owner,SubClient) else owner.id,sub_client_id=owner.id if isinstance(owner,SubClient) else None,normalized_name=key)
            db.add(row)
        row.contact_name=name;row.position=position;row.is_active=True;row.updated_at=business_now()
    owner.client_manager=names[0]
    owner.contact_names=names
    owner.updated_at=business_now().replace(tzinfo=None)


def ensure(db, owner, name, *, reactivate=True):
    name=normalize_names([name])[0]
    if not ready(db):raise ValueError('客户联系人名录表尚未初始化')
    db.query(type(owner).id).filter(type(owner).id==owner.id).with_for_update().first()
    rows=owner_rows(db,owner)
    found=next((row for row in rows if row.normalized_name==name.casefold()),None)
    if found and (found.is_active or not reactivate):return
    names=[row.contact_name for row in rows if row.is_active]
    legacy=str(owner.client_manager or '').strip()
    if legacy and legacy.casefold() not in {item.casefold() for item in names}:names.insert(0,legacy)
    replace(db,owner,[*names,name])
