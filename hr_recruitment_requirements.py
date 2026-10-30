"""行政部招聘需求：日期编号、并发版本、搜索与软删除；独立于招聘项目。"""
from datetime import date,datetime
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import String,Text,Integer,Date,DateTime,Boolean,Uuid,ForeignKey,Index,inspect,text,cast
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.exc import IntegrityError
from models import Base
from database import get_db
from routers.auth import get_current_user
from hr_access import require_hr
from chat_time import now,api_time
from search_matching import keyword_any


class RecruitmentRequirement(Base):
    __tablename__='hr_recruitment_requirement'
    __table_args__=(Index('ix_hr_recruitment_requirement_date','request_date','is_deleted'),)
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    client_id:Mapped[UUID]=mapped_column(Uuid,unique=True,nullable=False)
    demand_no:Mapped[str]=mapped_column(String(32),unique=True,nullable=False)
    request_date:Mapped[date]=mapped_column(Date,nullable=False)
    position:Mapped[str]=mapped_column(String(200),nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    headcount:Mapped[int]=mapped_column(Integer,nullable=False)
    details:Mapped[str]=mapped_column(Text,nullable=False)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    is_deleted:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    created_by:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    updated_by:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class RecruitmentRequirementCity(Base):
    __tablename__='hr_recruitment_requirement_city'
    requirement_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('hr_recruitment_requirement.id'),primary_key=True)
    city:Mapped[str]=mapped_column(String(100),nullable=False)


class RequirementFields(BaseModel):
    request_date:date
    recruitment_city:str=Field(default='',max_length=100)
    position:str=Field(min_length=1,max_length=200)
    reason:str=Field(min_length=1,max_length=2000)
    headcount:int=Field(ge=1,le=100000,strict=True)
    details:str=Field(min_length=1,max_length=20000)
    @field_validator('position','reason','details')
    @classmethod
    def trim(cls,value):
        if not value.strip():raise ValueError('请填写完整招聘需求')
        return value.strip()
    @field_validator('recruitment_city')
    @classmethod
    def trim_city(cls,value):return value.strip()
class RequirementCreate(RequirementFields):client_id:UUID
class RequirementUpdate(RequirementFields):revision:int=Field(ge=1)


def ready(db):return inspect(db.connection()).has_table(RecruitmentRequirement.__tablename__)
def allowed(db,user):
    require_hr(db,user)
    if not ready(db):raise HTTPException(503,'招聘需求表尚未初始化')
def serialize(row):return api_time({**{key:getattr(row,key) for key in ('id','demand_no','request_date','position','reason','headcount','details','revision','created_at','updated_at')},'recruitment_city':getattr(row,'recruitment_city','')})
def cities_ready(db):return inspect(db.connection()).has_table(RecruitmentRequirementCity.__tablename__)
def attach_cities(db,rows):
    ids=[row.id for row in rows]
    values={item.requirement_id:item.city for item in db.query(RecruitmentRequirementCity).filter(RecruitmentRequirementCity.requirement_id.in_(ids)).all()} if ids and cities_ready(db) else {}
    for row in rows:row.recruitment_city=values.get(row.id,'')
    return rows
def write_city(db,row,city):
    if not cities_ready(db):
        if city:raise HTTPException(503,'招聘城市表尚未初始化')
        return
    value=db.get(RecruitmentRequirementCity,row.id)
    if not city:
        if value:db.delete(value)
    else:
        if value is None:value=RecruitmentRequirementCity(requirement_id=row.id);db.add(value)
        value.city=city
    row.recruitment_city=city
def get_row(db,uid,lock=False):
    query=db.query(RecruitmentRequirement).filter_by(id=uid,is_deleted=False)
    row=(query.with_for_update().populate_existing() if lock else query).first()
    if not row:raise HTTPException(404,'招聘需求不存在或已删除')
    return attach_cities(db,[row])[0]


def list_rows(db,user,keyword='',page=1,limit=20):
    allowed(db,user)
    columns=[RecruitmentRequirement.demand_no,cast(RecruitmentRequirement.request_date,String),RecruitmentRequirement.position,RecruitmentRequirement.reason,RecruitmentRequirement.details,cast(RecruitmentRequirement.headcount,String)]
    query=db.query(RecruitmentRequirement)
    if cities_ready(db):query=query.outerjoin(RecruitmentRequirementCity,RecruitmentRequirementCity.requirement_id==RecruitmentRequirement.id);columns.append(RecruitmentRequirementCity.city)
    query=query.filter(RecruitmentRequirement.is_deleted.is_(False),keyword_any(columns,keyword))
    total=query.count()
    rows=query.order_by(RecruitmentRequirement.request_date.desc(),RecruitmentRequirement.created_at.desc(),RecruitmentRequirement.demand_no.desc()).offset((page-1)*limit).limit(limit).all()
    return {'items':[serialize(row) for row in attach_cities(db,rows)],'total':total}


def create(db,user,payload):
    allowed(db,user);day=payload.request_date
    if db.get_bind().dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(731947,:day)'),{'day':day.toordinal()})
    values=payload.model_dump(exclude={'client_id','recruitment_city'})
    existing=db.query(RecruitmentRequirement).filter_by(client_id=payload.client_id).first()
    if existing:
        attach_cities(db,[existing])
        if existing.created_by!=user.id or existing.is_deleted or existing.recruitment_city!=payload.recruitment_city or any(getattr(existing,key)!=value for key,value in values.items()):raise HTTPException(409,'提交标识已使用，请刷新后重试')
        return serialize(existing)
    prefix=f'RT-{day:%y%m%d}-'
    numbers=db.query(RecruitmentRequirement.demand_no).filter(RecruitmentRequirement.demand_no.like(prefix+'%')).all()
    number=max([int(value[len(prefix):]) for value, in numbers if value[len(prefix):].isdigit()] or [0])+1
    row=RecruitmentRequirement(id=uuid4(),client_id=payload.client_id,demand_no=f'{prefix}{number:03d}',**values,created_by=user.id,updated_by=user.id,revision=1,is_deleted=False,created_at=now(),updated_at=now())
    db.add(row)
    write_city(db,row,payload.recruitment_city)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'需求编号或提交标识发生冲突，请刷新后重试')
    return serialize(row)


def update(db,user,uid,payload):
    allowed(db,user);row=get_row(db,uid,True);values=payload.model_dump(exclude={'revision','recruitment_city'})
    city=payload.recruitment_city if 'recruitment_city' in payload.model_fields_set else row.recruitment_city
    if row.revision!=payload.revision:
        if row.recruitment_city==city and all(getattr(row,key)==value for key,value in values.items()):return serialize(row)
        raise HTTPException(409,'招聘需求已被其他人修改，请刷新后重试')
    for key,value in values.items():setattr(row,key,value)
    if 'recruitment_city' in payload.model_fields_set:write_city(db,row,city)
    row.revision+=1;row.updated_by=user.id;row.updated_at=now();db.commit();return serialize(row)


def delete(db,user,uid,revision):
    allowed(db,user);row=get_row(db,uid,True)
    if row.revision!=revision:raise HTTPException(409,'招聘需求已更新，请刷新后再删除')
    row.is_deleted=True;row.revision+=1;row.updated_by=user.id;row.updated_at=now();db.commit()
    return {'message':'招聘需求已删除'}


router=APIRouter(prefix='/hr-recruitment/requirements',tags=['hr-recruitment'])
@router.get('')
def listing(keyword:str='',page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(get_current_user)):return list_rows(db,user,keyword,page,limit)
@router.post('')
def creating(payload:RequirementCreate,db=Depends(get_db),user=Depends(get_current_user)):return create(db,user,payload)
@router.get('/{uid}')
def reading(uid:UUID,db=Depends(get_db),user=Depends(get_current_user)):
    allowed(db,user);return serialize(get_row(db,uid))
@router.put('/{uid}')
def updating(uid:UUID,payload:RequirementUpdate,db=Depends(get_db),user=Depends(get_current_user)):return update(db,user,uid,payload)
@router.delete('/{uid}')
def deleting(uid:UUID,revision:int=Query(ge=1),db=Depends(get_db),user=Depends(get_current_user)):return delete(db,user,uid,revision)
