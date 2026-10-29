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

def test_annotation_workload_round_trip_and_localized_version(resume_db):
    db,person,actor=resume_db
    payload=ResourcePersonUpdate(full_name='标注测试',resume_profile={'annotation':[{'organization':'甲方公司','position':'图像标注','workload':' 5000条 / 100小时 '}], 'versions':{'en':{'annotation':[{'organization':'Client','position':'Image annotation','workload':'5,000 items'}]}}})
    save_resume_profile(db,person,payload,actor);db.flush()
    result=read_resume_profile(db,person.id)
    assert result['annotation'][0]['workload']=='5000条 / 100小时'
    assert result['versions']['en']['annotation'][0]['workload']=='5,000 items'
    assert person.annotation_experience=='甲方公司 · 图像标注 · 5000条 / 100小时'
    again=ResourcePersonUpdate(full_name='标注测试',resume_profile=result)
    save_resume_profile(db,person,again,actor)
    assert person.resume_profile.revision==1

def test_workload_only_row_is_not_discarded(resume_db):
    db,person,actor=resume_db
    save_resume_profile(db,person,ResourcePersonUpdate(full_name='标注测试',resume_profile={'annotation':[{'workload':'100小时'}]}),actor)
    db.flush()
    result=read_resume_profile(db,person.id)
    assert result['annotation'][0]['workload']=='100小时'
    assert person.annotation_experience=='100小时'
    with pytest.raises(ValidationError):TalentResumeProfileInput(annotation=[{'workload':'量'*256}])

def test_resume_year_is_independent_per_language_and_can_be_cleared(resume_db):
    db,person,actor=resume_db
    payload=ResourcePersonUpdate(full_name='年份测试',resume_profile={'resume_year':' 2026 ','versions':{'en':{'resume_year':'2025'},'ar':{'resume_year':'٢٠٢٤'}}})
    save_resume_profile(db,person,payload,actor);db.flush()
    result=read_resume_profile(db,person.id)
    assert result['resume_year']=='2026'
    assert result['versions']['en']['resume_year']=='2025'
    assert result['versions']['ar']['resume_year']=='٢٠٢٤'
    omitted=ResourcePersonUpdate(full_name='年份测试',resume_profile={'revision':1,'cat_tools':['memoQ']})
    save_resume_profile(db,person,omitted,actor);db.flush()
    assert read_resume_profile(db,person.id)['resume_year']=='2026'
    cleared=ResourcePersonUpdate(full_name='年份测试',resume_profile={'revision':2,'resume_year':' '})
    save_resume_profile(db,person,cleared,actor);db.flush()
    result=read_resume_profile(db,person.id)
    assert result['resume_year'] is None
    assert result['versions']['en']['resume_year']=='2025'
    with pytest.raises(ValidationError):TalentResumeProfileInput(resume_year='年'*51)

def test_empty_resume_year_does_not_create_profile(resume_db):
    db,person,actor=resume_db
    save_resume_profile(db,person,ResourcePersonUpdate(full_name='年份测试',resume_profile={'resume_year':''}),actor)
    db.flush();assert read_resume_profile(db,person.id) is None
