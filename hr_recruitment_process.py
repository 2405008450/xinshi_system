"""招聘过程：关联需求同步城市岗位，面试与意愿条件校验，是否入职仅预留。"""
from datetime import datetime,date
from uuid import UUID,uuid4
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,StrictBool,ConfigDict,model_validator,field_validator
from sqlalchemy import Uuid,ForeignKey,String,Text,DateTime,Date,Boolean,Integer,Index,inspect
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy.exc import IntegrityError
from models import Base
from database import get_db
from routers.auth import get_current_user
from hr_access import require_hr
from chat_time import now,api_time
from search_matching import keyword_any
from hr_recruitment_requirements import RecruitmentRequirement as Requirement,RecruitmentRequirementCity as City


class HrRecruitmentCandidate(Base):
    __tablename__='hr_recruitment_candidate'
    __table_args__=(Index('ix_hr_recruitment_candidate_requirement','requirement_id','is_deleted'),)
    id:Mapped[UUID]=mapped_column(Uuid,primary_key=True,default=uuid4)
    client_id:Mapped[UUID]=mapped_column(Uuid,unique=True,nullable=False)
    requirement_id:Mapped[UUID]=mapped_column(Uuid,ForeignKey('hr_recruitment_requirement.id'),nullable=False)
    applicant_name:Mapped[str]=mapped_column(String(200),nullable=False)
    first_interview_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    first_interview_done:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    first_result:Mapped[str]=mapped_column(Text,nullable=False,default='')
    second_interview_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    second_interview_done:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    second_result:Mapped[str]=mapped_column(Text,nullable=False,default='')
    willingness:Mapped[str]=mapped_column(String(30),nullable=False,default='')
    willingness_reason:Mapped[str]=mapped_column(Text,nullable=False,default='')
    onboarding_date:Mapped[date|None]=mapped_column(Date)
    actual_onboarded:Mapped[bool|None]=mapped_column(Boolean,nullable=True)
    revision:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    is_deleted:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    created_by:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    updated_by:Mapped[UUID]=mapped_column(Uuid,ForeignKey('app_user.id'),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=now)


class CandidateFields(BaseModel):
    model_config=ConfigDict(extra='forbid')
    requirement_id:UUID
    applicant_name:str=Field(min_length=1,max_length=200)
    first_interview_at:datetime|None=None
    first_interview_done:StrictBool=False
    first_result:str=Field(default='',max_length=10000)
    second_interview_at:datetime|None=None
    second_interview_done:StrictBool=False
    second_result:str=Field(default='',max_length=10000)
    willingness:Literal['','candidate_withdrew','company_declined','yes']=''
    willingness_reason:str=Field(default='',max_length=2000)
    onboarding_date:date|None=None
    @field_validator('applicant_name')
    @classmethod
    def name(cls,value):
        if not value.strip():raise ValueError('请填写应聘人姓名')
        return value.strip()
    @field_validator('first_interview_at','second_interview_at')
    @classmethod
    def local(cls,value):
        if value is not None and value.tzinfo is None:raise ValueError('面试时间须携带+08:00时区')
        return api_time(value) if value is not None else None
    @model_validator(mode='after')
    def conditional(self):
        for stage,label in [('first','一面'),('second','二面')]:
            done=getattr(self,f'{stage}_interview_done');result=getattr(self,f'{stage}_result').strip()
            if done and (getattr(self,f'{stage}_interview_at') is None or not result):raise ValueError(f'已{label}须填写{label}时间及{label}结果')
            setattr(self,f'{stage}_result',result if done else '')
        self.willingness_reason=self.willingness_reason.strip()
        if self.willingness in ('candidate_withdrew','company_declined'):
            if not self.willingness_reason:raise ValueError('候选人放弃或信实放弃须填写原因')
            if self.onboarding_date is not None:raise ValueError('放弃时不能填写入职时间')
        elif self.willingness=='yes':
            if self.onboarding_date is None:raise ValueError('入职意愿为是时须填写入职时间')
            if self.willingness_reason:raise ValueError('入职意愿为是时不填写放弃原因')
        elif self.onboarding_date is not None or self.willingness_reason:raise ValueError('待确认意愿不填写入职时间或放弃原因')
        return self
class CandidateCreate(CandidateFields):client_id:UUID
class CandidateUpdate(CandidateFields):revision:int=Field(ge=1)


def allowed(db,user):
    require_hr(db,user)
    if not all(inspect(db.connection()).has_table(name) for name in (HrRecruitmentCandidate.__tablename__,Requirement.__tablename__,City.__tablename__)):raise HTTPException(503,'招聘过程或招聘城市表尚未初始化')


def source(db,uid,existing_id=None):
    row=db.get(Requirement,uid)
    if not row or (row.is_deleted and uid!=existing_id):raise HTTPException(422,'请选择有效招聘需求')
    return row


def serialize(db,row,requirement=None,city=None):
    requirement=requirement or db.get(Requirement,row.requirement_id)
    if city is None:
        value=db.get(City,row.requirement_id);city=value.city if value else ''
    fields=('id','requirement_id','applicant_name','first_interview_at','first_interview_done','first_result','second_interview_at','second_interview_done','second_result','willingness','willingness_reason','onboarding_date','actual_onboarded','revision','created_at','updated_at')
    return api_time({**{key:getattr(row,key) for key in fields},'demand_no':requirement.demand_no,'recruitment_city':city,'position':requirement.position,'requirement_deleted':requirement.is_deleted})


def listing(db,user,keyword='',page=1,limit=20):
    allowed(db,user)
    query=db.query(HrRecruitmentCandidate,Requirement,City.city).join(Requirement,Requirement.id==HrRecruitmentCandidate.requirement_id).outerjoin(City,City.requirement_id==Requirement.id).filter(HrRecruitmentCandidate.is_deleted.is_(False),keyword_any([Requirement.demand_no,City.city,Requirement.position,HrRecruitmentCandidate.applicant_name,HrRecruitmentCandidate.first_result,HrRecruitmentCandidate.second_result,HrRecruitmentCandidate.willingness_reason],keyword))
    total=query.count();values=query.order_by(HrRecruitmentCandidate.updated_at.desc(),HrRecruitmentCandidate.id.desc()).offset((page-1)*limit).limit(limit).all()
    return {'items':[serialize(db,row,requirement,city or '') for row,requirement,city in values],'total':total}


def same(row,values):
    for key,value in values.items():
        current=getattr(row,key)
        if key.endswith('_at') and current is not None:current=api_time(current)
        if current!=value:return False
    return True


def create(db,user,payload):
    allowed(db,user);source(db,payload.requirement_id)
    values=payload.model_dump(exclude={'client_id'})
    old=db.query(HrRecruitmentCandidate).filter_by(client_id=payload.client_id).first()
    if old:
        if old.created_by!=user.id or old.is_deleted or not same(old,values):raise HTTPException(409,'提交标识已使用，请刷新后重试')
        return serialize(db,old)
    row=HrRecruitmentCandidate(id=uuid4(),client_id=payload.client_id,**values,actual_onboarded=None,revision=1,is_deleted=False,created_by=user.id,updated_by=user.id,created_at=now(),updated_at=now());db.add(row)
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'重复提交，请刷新招聘过程列表')
    return serialize(db,row)


def update(db,user,uid,payload):
    allowed(db,user)
    row=db.query(HrRecruitmentCandidate).filter_by(id=uid,is_deleted=False).with_for_update().populate_existing().first()
    if row is None:raise HTTPException(404,'招聘过程不存在或已删除')
    source(db,payload.requirement_id,row.requirement_id)
    values=payload.model_dump(exclude={'revision'})
    if row.revision!=payload.revision:
        if same(row,values):return serialize(db,row)
        raise HTTPException(409,'招聘过程已被其他人修改，请刷新后重试')
    for key,value in values.items():setattr(row,key,value)
    row.revision+=1;row.updated_by=user.id;row.updated_at=now();db.commit();return serialize(db,row)


def delete(db,user,uid,revision):
    allowed(db,user);row=db.query(HrRecruitmentCandidate).filter_by(id=uid,is_deleted=False).with_for_update().populate_existing().first()
    if not row:raise HTTPException(404,'招聘过程不存在或已删除')
    if row.revision!=revision:raise HTTPException(409,'招聘过程已更新，请刷新后删除')
    row.is_deleted=True;row.revision+=1;row.updated_by=user.id;row.updated_at=now();db.commit();return {'message':'招聘过程已删除'}


router=APIRouter(prefix='/hr-recruitment/process',tags=['hr-recruitment'])
@router.get('')
def list_endpoint(keyword:str='',page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(get_current_user)):return listing(db,user,keyword,page,limit)
@router.post('')
def create_endpoint(payload:CandidateCreate,db=Depends(get_db),user=Depends(get_current_user)):return create(db,user,payload)
@router.put('/{uid}')
def update_endpoint(uid:UUID,payload:CandidateUpdate,db=Depends(get_db),user=Depends(get_current_user)):return update(db,user,uid,payload)
@router.delete('/{uid}')
def delete_endpoint(uid:UUID,revision:int=Query(ge=1),db=Depends(get_db),user=Depends(get_current_user)):return delete(db,user,uid,revision)
