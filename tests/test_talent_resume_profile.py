from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Column,MetaData,Table,Uuid,create_engine
from sqlalchemy.orm import Session

from resource_schemas import ResourcePersonUpdate
from talent_resume_profile import TalentResumeProfile,TalentResumeProfileInput,read_resume_profile,save_resume_profile

@pytest.fixture
def resume_db():
    import main
    engine=create_engine('sqlite:///:memory:')
    meta=MetaData()
    people=Table('resource_person',meta,Column('id',Uuid,primary_key=True))
    users=Table('app_user',meta,Column('id',Uuid,primary_key=True))
    TalentResumeProfile.__table__.to_metadata(meta)
    meta.create_all(engine)
    with Session(engine) as db:
        person=SimpleNamespace(id=uuid4(),education_experiences=[],annotation_experience='旧资料')
        actor=SimpleNamespace(id=uuid4())
        db.execute(people.insert().values(id=person.id));db.execute(users.insert().values(id=actor.id))
        yield db,person,actor
    engine.dispose()

def test_native_versions_and_legacy_summary_round_trip(resume_db):
    db,person,actor=resume_db
    payload=ResourcePersonUpdate(full_name='测试',resume_profile={'interpretation':[{'period':'2022-06 – 2024-03','organization':'会议公司','position':'口译员','description':'会议交传'}], 'versions':{'en':{'name':'Alice','gender':'female'},'ar':{'name':'ليلى','skills':'ترجمة'}},'cat_tools':['memoQ',' memoq ','Trados Studio']})
    save_resume_profile(db,person,payload,actor);db.flush()
    result=read_resume_profile(db,person.id)
    assert result['versions']['ar']['name']=='ليلى'
    assert result['cat_tools']==['memoQ','Trados Studio']
    assert person.interpretation_experience=='2022-06 – 2024-03 · 会议公司 · 口译员\n会议交传'
    assert person.annotation_experience=='旧资料'
    assert result['revision']==1
    again=ResourcePersonUpdate(full_name='测试',resume_profile=result)
    save_resume_profile(db,person,again,actor)
    assert person.resume_profile.revision==1
    again.resume_profile.versions['en'].name='Bob'
    save_resume_profile(db,person,again,actor)
    assert person.resume_profile.revision==2
    with pytest.raises(HTTPException) as error:save_resume_profile(db,person,payload,actor)
    assert error.value.status_code==409

def test_education_period_tracks_real_child_id(resume_db):
    db,person,actor=resume_db
    child=SimpleNamespace(id=uuid4());person.education_experiences=[child]
    payload=ResourcePersonUpdate(full_name='测试',education_experiences=[{'education_level':'junior_secondary','institution':'学校','period':'2010-09 – 2013-06'}],resume_profile={})
    save_resume_profile(db,person,payload,actor);db.flush()
    assert read_resume_profile(db,person.id)['education_periods']=={str(child.id):'2010-09 – 2013-06'}
    assert person.resume_profile.revision==1

def test_empty_profile_does_not_create_record(resume_db):
    db,person,actor=resume_db
    save_resume_profile(db,person,ResourcePersonUpdate(full_name='测试',resume_profile={'versions':{'ar':{}}}),actor)
    db.flush();assert read_resume_profile(db,person.id) is None

def test_versions_cannot_hold_shared_business_or_unknown_locale():
    for value in [{'versions':{'en':{'settlement':{'bank_account':'secret'}}}},{'versions':{'xx':{'name':'bad'}}},{'internships':[{'id':(row:=uuid4())},{'id':row}]}]:
        with pytest.raises(ValidationError):TalentResumeProfileInput(**value)

def test_new_table_migration_is_idempotent(resume_db):
    db,_,_=resume_db
    from tools.apply_talent_resume_profile_migration import apply_migration
    apply_migration(db.connection());apply_migration(db.connection())
