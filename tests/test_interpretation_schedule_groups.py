"""时间段分组只在隔离 SQLite 中验证，不连接业务数据库。"""
from datetime import datetime
from uuid import uuid4
import pytest
from pydantic import ValidationError
from sqlalchemy import inspect
from tests.test_chat_participant_access import environment
from interpretation_models import InterpretationProject, InterpretationProjectTimeRange
from interpretation_schemas import InterpretationProjectCreate, InterpretationTimeRangeInput, InterpretationTimeRangeResponse
from interpretation_schedule_groups import InterpretationScheduleGroups, save, attach
from tools.apply_interpretation_schedule_groups_migration import apply_migration


def group(day=1, count=1, ids=None):
    ids = ids or [uuid4(),uuid4()]
    return dict(scheduled_start=datetime(2026,11,day,9),scheduled_end=datetime(2026,11,day,18),
        locations=[f'地点{i}' for i in range(7)],language_directions=[dict(language_ids=ids,required_count=count)])


def test_group_summaries_do_not_duplicate_same_direction_across_dates():
    ids=[uuid4(),uuid4()]
    payload=InterpretationProjectCreate(time_ranges=[group(1,1,ids),group(2,3,ids)])
    assert len(payload.locations)==7
    assert len(payload.language_directions)==1
    assert payload.language_directions[0].required_count==3
    assert payload.time_ranges[0].language_directions[0].required_count==1


@pytest.mark.parametrize('field,value', [('locations',[]),('language_directions',[])])
def test_each_group_needs_location_and_direction(field,value):
    raw=group();raw[field]=value
    with pytest.raises(ValidationError):InterpretationTimeRangeInput(**raw)


def test_duplicates_only_disallowed_within_one_group():
    raw=group();raw['language_directions']*=2
    with pytest.raises(ValidationError):InterpretationTimeRangeInput(**raw)


def test_group_storage_readback_and_idempotent_migration(environment):
    db,_=environment
    InterpretationScheduleGroups.__table__.drop(db.connection(),checkfirst=True)
    apply_migration(db.connection());apply_migration(db.connection())
    assert inspect(db.connection()).has_table(InterpretationScheduleGroups.__tablename__)
    project=InterpretationProject(id=uuid4(),order_no='IP-261101-999',project_name='分组测试')
    ranges=[InterpretationTimeRangeInput(**group(1)),InterpretationTimeRangeInput(**group(2))]
    project.time_ranges=[InterpretationProjectTimeRange(id=uuid4(),sequence_no=index+1,
        **item.model_dump(exclude={'locations','location_details','language_directions'})) for index,item in enumerate(ranges)]
    db.add(project);db.flush()
    save(db,project,ranges);db.commit();db.expire_all()
    attach(db,[project])
    actual=[InterpretationTimeRangeResponse.model_validate(item).model_dump(mode='json') for item in project.time_ranges]
    assert len(actual[0]['locations'])==7
    assert actual[0]['language_directions'][0]['language_ids']!=actual[1]['language_directions'][0]['language_ids']
    ranges[1].locations=['第二组新地点']
    save(db,project,ranges);db.commit();attach(db,[project])
    assert project.time_ranges[0].locations==[f'地点{i}' for i in range(7)]
    assert project.time_ranges[1].locations==['第二组新地点']
    assert db.query(InterpretationScheduleGroups).count()==1


def test_structured_location_round_trip_and_legacy_compatibility(environment):
    db,_=environment
    raw=group()
    raw['location_details']=[{'country_province':' 中国广东省 ', 'city':' 深圳市 ', 'address':' 南山区科苑路1号 '},
                             {'country_province':'法国', 'city':'巴黎', 'address':'会展中心'}]
    plan=InterpretationTimeRangeInput(**raw)
    assert plan.locations==['中国广东省 深圳市 南山区科苑路1号','法国 巴黎 会展中心']
    project=InterpretationProject(id=uuid4(),order_no='IP-ADDRESS',project_name='地点测试')
    project.time_ranges=[InterpretationProjectTimeRange(id=uuid4(),sequence_no=1,
        **plan.model_dump(exclude={'locations','location_details','language_directions'}))]
    db.add(project);db.flush();save(db,project,[plan]);db.commit();db.expire_all();attach(db,[project])
    restored=InterpretationTimeRangeResponse.model_validate(project.time_ranges[0])
    assert restored.location_details[0].city=='深圳市'
    assert restored.location_details[1].address=='会展中心'
    # 旧客户端未修改完整地址时保留结构；修改后按完整文本兼容。
    legacy=InterpretationTimeRangeInput(**{**raw,'location_details':None,'locations':plan.locations})
    save(db,project,[legacy]);db.commit();attach(db,[project])
    assert project.time_ranges[0].location_details[0]['city']=='深圳市'
    legacy.locations=['旧客户端修改地点'];save(db,project,[legacy]);db.commit();attach(db,[project])
    assert project.time_ranges[0].location_details is None
    assert project.time_ranges[0].locations==['旧客户端修改地点']


def test_blank_location_details_cannot_bypass_required_locations():
    raw=group();raw['location_details']=[{'city':'  '}]
    with pytest.raises(ValidationError):InterpretationTimeRangeInput(**raw)
