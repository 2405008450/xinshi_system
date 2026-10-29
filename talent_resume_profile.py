"""结构化经历、CAT 工具及多语言简历；不改变人员主表结构。"""
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, Uuid
from sqlalchemy.orm import mapped_column

from business_time import BUSINESS_TIMEZONE
from models import Base

FOREIGN_RESUME_LOCALES = {'ar','ja','ko','fr','de','es','pt','it','ru','uk','tr','fa','hi','bn','ur','ta','id','ms','th','vi','km','lo','my','fil','nl','pl','cs','ro','hu','sv','da','no','fi','el','he','sw'}
WORK_FIELDS = {'annotation':'annotation_experience','interpretation':'interpretation_experience','translation':'translation_experience','other':'other_experience'}


class ResumeExperienceEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    period: str | None = Field(default=None,max_length=100)
    organization: str | None = Field(default=None,max_length=255)
    position: str | None = Field(default=None,max_length=255)
    description: str | None = None
    degree: str | None = Field(default=None,max_length=50)

    @field_validator('period','organization','position','description','degree',mode='before')
    @classmethod
    def trim(cls,value):
        return value.strip() or None if isinstance(value,str) else value


class ResumeLanguageVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None,max_length=255)
    professional_title: str | None = Field(default=None,max_length=255)
    gender: Literal['male','female','unknown','undisclosed'] | None = None
    birth_date: str | None = Field(default=None,max_length=20)
    nationality: str | None = Field(default=None,max_length=255)
    residence: str | None = Field(default=None,max_length=500)
    native_place: str | None = Field(default=None,max_length=255)
    employment_status: Literal['student','employed','freelance','seeking','retired','other'] | None = None
    highest_education: str | None = Field(default=None,max_length=50)
    height: str | None = Field(default=None,max_length=255)
    eyesight: str | None = Field(default=None,max_length=255)
    languages: list[str] = Field(default_factory=list,max_length=100)
    language_notes: str | None = Field(default=None,max_length=20000)
    certificates: str | None = Field(default=None,max_length=20000)
    skills: str | None = Field(default=None,max_length=20000)
    cat_tools: list[str] = Field(default_factory=list,max_length=50)
    educations: list[ResumeExperienceEntry] = Field(default_factory=list,max_length=100)
    internships: list[ResumeExperienceEntry] = Field(default_factory=list,max_length=100)
    annotation: list[ResumeExperienceEntry] = Field(default_factory=list,max_length=100)
    interpretation: list[ResumeExperienceEntry] = Field(default_factory=list,max_length=100)
    translation: list[ResumeExperienceEntry] = Field(default_factory=list,max_length=100)
    other: list[ResumeExperienceEntry] = Field(default_factory=list,max_length=100)

    @field_validator('name','professional_title','birth_date','nationality','residence','native_place','height','eyesight','language_notes','certificates','skills',mode='before')
    @classmethod
    def trim(cls,value):
        return value.strip() or None if isinstance(value,str) else value


class TalentResumeProfileInput(BaseModel):
    revision: int = Field(default=0,ge=0)
    internships: list[ResumeExperienceEntry] | None = Field(default=None,max_length=100)
    annotation: list[ResumeExperienceEntry] | None = Field(default=None,max_length=100)
    interpretation: list[ResumeExperienceEntry] | None = Field(default=None,max_length=100)
    translation: list[ResumeExperienceEntry] | None = Field(default=None,max_length=100)
    other: list[ResumeExperienceEntry] | None = Field(default=None,max_length=100)
    cat_tools: list[str] | None = Field(default=None,max_length=50)
    versions: dict[str,ResumeLanguageVersion] | None = None

    @field_validator('cat_tools')
    @classmethod
    def tools(cls,value):
        if value is None:return value
        result=[];seen=set()
        for item in value:
            item=item.strip()
            if len(item)>100:raise ValueError('CAT 工具名称最多100字')
            if item and item.casefold() not in seen:result.append(item);seen.add(item.casefold())
        return result

    @field_validator('versions')
    @classmethod
    def locales(cls,value):
        if value is not None and not set(value)<={'en',*FOREIGN_RESUME_LOCALES}:
            raise ValueError('不支持的简历语言')
        return value

    @model_validator(mode='after')
    def entries(self):
        for name in ['internships',*WORK_FIELDS]:
            entries=getattr(self,name)
            if entries is not None and len({item.id for item in entries})!=len(entries):
                raise ValueError('经历明细包含重复行')
        return self


class TalentResumeProfileResponse(TalentResumeProfileInput):
    education_periods: dict[str,str] = Field(default_factory=dict)


class TalentResumeProfile(Base):
    __tablename__='talent_resume_profile'
    __table_args__=(CheckConstraint('revision >= 1',name='ck_talent_resume_profile_revision'),)
    person_id=mapped_column(Uuid,ForeignKey('resource_person.id',ondelete='CASCADE'),primary_key=True)
    revision=mapped_column(Integer,nullable=False,default=1)
    data=mapped_column(JSON,nullable=False,default=dict)
    updated_by=mapped_column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=mapped_column(DateTime(timezone=True),nullable=False)


def read_resume_profile(db,person_id):
    row=db.get(TalentResumeProfile,person_id)
    return TalentResumeProfileResponse.model_validate({**row.data,'revision':row.revision}).model_dump() if row else None


def _entry_present(row):
    return any(row.get(key) for key in ['period','organization','position','description','degree'])


def save_resume_profile(db,person,payload,actor,*,allow_cat=True):
    if payload.resume_profile is None:return
    submitted=payload.resume_profile
    row=db.query(TalentResumeProfile).filter(TalentResumeProfile.person_id==person.id).with_for_update().first()
    if row is not None and submitted.revision!=row.revision:
        raise HTTPException(409,'简历资料已被修改，请重新打开后核对；当前输入已保留')
    if row is None and submitted.revision!=0:raise HTTPException(409,'简历资料已变化，请重新打开后核对')
    previous=dict(row.data) if row else {}
    normalized=submitted.model_dump(mode='json',exclude={'revision'})
    updates={key:value for key,value in normalized.items() if key in submitted.model_fields_set and value is not None}
    if not allow_cat:updates.pop('cat_tools',None)
    for key in ['internships',*WORK_FIELDS]:
        if key in updates:updates[key]=[entry for entry in updates[key] if _entry_present(entry)]
    if 'versions' in updates:
        updates['versions']={locale:version for locale,version in updates['versions'].items() if any(version.values())}
    # 子表记录已由原有同步逻辑维护；时间段仅作补充，不迁移、猜测旧日期。
    db.flush()
    periods=dict(previous.get('education_periods') or {})
    education=list(person.education_experiences or [])
    known={item.id for item in payload.education_experiences if item.id is not None}
    newly_created=iter([item for item in education if item.id not in known])
    by_id={item.id:item for item in education}
    for source in payload.education_experiences:
        target=by_id.get(source.id) if source.id else next(newly_created,None)
        if target is not None and 'period' in source.model_fields_set:
            if source.period:periods[str(target.id)]=source.period
            else:periods.pop(str(target.id),None)
            target.__dict__['period']=source.period
    periods={key:value for key,value in periods.items() if key in {str(item.id) for item in education}}
    if periods or previous.get('education_periods'):updates['education_periods']=periods
    for key,field in WORK_FIELDS.items():
        if key in updates:
            chunks=[]
            for entry in updates[key]:
                header=' · '.join(entry.get(name) or '' for name in ['period','organization','position']).strip(' ·')
                chunks.append('\n'.join(value for value in [header,entry.get('description')] if value))
            setattr(person,field,'\n\n'.join(chunks) or None)
    merged={**previous,**updates}
    if row is None:
        if not any(merged.values()):return
        row=TalentResumeProfile(person_id=person.id,revision=1);db.add(row)
    elif merged==previous:
        person.__dict__['resume_profile']=TalentResumeProfileResponse.model_validate({**merged,'revision':row.revision})
        return
    else:row.revision+=1
    row.data=merged;row.updated_by=getattr(actor,'id',None);row.updated_at=datetime.now(BUSINESS_TIMEZONE)
    person.__dict__['resume_profile']=TalentResumeProfileResponse.model_validate({**merged,'revision':row.revision})
