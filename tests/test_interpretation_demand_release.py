from datetime import datetime
from uuid import uuid4
from sqlalchemy import inspect
from interpretation_demand_release import DemandReleaseRequest, InterpretationDemandReleaseOffice, choose_office, build_release, generate
from interpretation_models import InterpretationLanguage
from tests.test_chat_participant_access import environment


def payload():
    ids=[uuid4(),uuid4()]
    return DemandReleaseRequest(request_key=uuid4(),project_name='2026年12月9日深圳南山区中日商务陪同口译项目',
        interpretation_domain='软件',task_description='陪同客户参加商务会议',project_types=['business_escort'],
        time_ranges=[{'scheduled_start':datetime(2026,12,9,9),'scheduled_end':datetime(2026,12,9,18),
          'location_details':[{'country_province':'中国广东省','city':'深圳市','address':'南山区会议中心'}],
          'language_directions':[{'language_ids':ids,'required_count':2}]}])


def test_release_template_uses_fields_and_retains_fixed_submission_text():
    draft=payload();content=build_release(draft,['中文（简体） ↔ 日语'],'深圳')
    first=content.splitlines()[0]
    assert first=='深圳南山区中日商务陪同口译项目（信实深圳翻译公司）'
    assert content.splitlines()[1]==''
    for text in ['需求人数：2人','项目语言：中文（简体） ↔ 日语','项目时间：2026年12月09日 09:00—18:00','项目地点：深圳市',
                 '领域/行业/产品：软件','工作内容：陪同客户参加商务会议','居住在深圳市及周边地区','XXXXXXXXX优先考虑',
                 '🙏投递格式：','🌹咨询联系','👉hr4@xinshifanyi.com.cn','微信17324319719//Geeksbin',
                 '零误差','深耕口译领域十余载','+2026年12月9日深圳南山区中日商务陪同口译项目（信实深圳翻译公司招募）']:
        assert text in content
    assert '项目地点：中国' not in content and '南山区会议中心' not in content
    assert content.index('项目时间：') < content.index('项目地点：')
    assert '[玫瑰]' not in content and '[合十]' not in content


def test_project_name_only_uses_city_from_structured_locations():
    from interpretation_service import build_interpretation_project_name
    draft=payload()
    name=build_interpretation_project_name(draft,['中文 ↔ 日语'])
    assert '深圳市，中文 ↔ 日语' in name
    assert '中国' not in name and '广东省' not in name and '南山区会议中心' not in name


def test_multiple_cities_deduplicated_and_times_keep_each_period():
    from interpretation_service import build_interpretation_project_name
    draft=payload()
    second=draft.time_ranges[0].model_copy(deep=True)
    second.scheduled_start=datetime(2026,12,10,14)
    second.scheduled_end=datetime(2026,12,10,18)
    second.location_details[0].city='上海市'
    draft.time_ranges.extend([second,second.model_copy(deep=True)])
    name=build_interpretation_project_name(draft,['中文 ↔ 日语'])
    assert '深圳市、上海市' in name
    release=build_release(draft,['中文 ↔ 日语'],'上海')
    assert '项目地点：深圳市、上海市' in release
    assert '2026年12月10日 14:00—18:00' in release


def test_legacy_separated_location_only_keeps_city():
    from interpretation_location_summary import interpretation_cities
    from interpretation_schemas import InterpretationNamePreviewRequest
    assert interpretation_cities(InterpretationNamePreviewRequest(locations=['中国广东省 深圳市 南山区会议中心']))==['深圳市']
    assert interpretation_cities(InterpretationNamePreviewRequest(locations=['中国广东省深圳市']))==['深圳市']


def test_rotation_three_shanghai_then_shenzhen_and_same_draft_idempotent(environment):
    db,_=environment
    from tools.apply_interpretation_demand_release_migration import apply_migration
    before=set(inspect(db.connection()).get_table_names());apply_migration(db.connection());apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names())==before
    keys=[uuid4() for _ in range(8)]
    offices=[]
    for key in keys:
        offices.append(choose_office(db,key,['中国 北京市']))
        assert choose_office(db,key,['中国 北京市'])==offices[-1]
        db.commit()
    assert offices==['上海','上海','上海','深圳']*2
    assert choose_office(db,uuid4(),['中国广东省 深圳市'])=='深圳'
    assert choose_office(db,uuid4(),['上海浦东'])=='上海'
    assert db.query(InterpretationDemandReleaseOffice).count()==8


def test_rotation_rollback_does_not_consume_sequence(environment):
    db,_=environment
    assert choose_office(db,uuid4(),['广州'])=='上海'
    db.rollback()
    assert db.query(InterpretationDemandReleaseOffice).count()==0
    assert choose_office(db,uuid4(),['广州'])=='上海'
    assert db.query(InterpretationDemandReleaseOffice).one().sequence==1


def test_generator_uses_language_catalog_and_city_fields(environment):
    db,_=environment;draft=payload()
    for language,label in zip(draft.language_directions[0].language_ids,['中文（简体）','日语']):
        db.add(InterpretationLanguage(id=language,label=label,code=str(language)))
    db.commit()
    result=generate(draft,db)
    assert result['office']=='深圳'
    assert '中文（简体） ↔ 日语' in result['content']
    assert db.query(InterpretationDemandReleaseOffice).count()==0


def test_oral_resource_prefill_copies_release_instead_of_work_content(environment):
    db,_=environment
    from interpretation_models import InterpretationProject
    from resource_request_service import get_resource_request_source_prefill
    row=InterpretationProject(id=uuid4(),order_no='IP-RELEASE',project_name='发布测试',
        task_description='简短工作内容',social_post_request='完整需求发布文案',interpreter_special_requirements='客户要求')
    from interpretation_models import InterpretationProjectLanguageDirection
    row.language_directions=[InterpretationProjectLanguageDirection(id=uuid4(),sequence_no=1,source_language_id=uuid4(),target_language_id=uuid4(),required_count=1)]
    db.add(row);db.commit()
    result=get_resource_request_source_prefill(db,'interpretation',row.id)
    assert result['request_detail']=='完整需求发布文案'
    assert [item['content'] for item in result['request_content']['versions']]==['完整需求发布文案']*2
    assert not any(item['copied_from_task'] for item in result['request_content']['versions'])


def test_oral_circle_and_post_dispatch_use_same_history_and_oral_candidates(environment,monkeypatch):
    from test_resource_request_dispatch import setup_data
    from interpretation_models import InterpretationProject
    from department_models import Department,DepartmentMember
    from resource_request_dispatch_defaults import catalog
    db,sender,annotation_person,oral_person,request,_project,service,notices=setup_data(environment,monkeypatch)
    project=InterpretationProject(id=uuid4(),order_no='IP-DISPATCH',project_name='口译发布')
    department=Department(id=uuid4(),name='口译项目部')
    db.add_all([project,department]);db.flush()
    db.add(DepartmentMember(department_id=department.id,user_id=oral_person.id,position='项目专员'))
    request.source_type='interpretation';request.request_category='interpretation'
    request.annotation_project_id=None;request.interpretation_project_id=project.id
    request.request_content={'versions':[{'name':'发帖','content':'口译发布正文'}],'dispatch_notes':{'circle':'请发圈','post':'请发帖'}}
    db.commit()
    options=catalog(db,sender,'circle','interpretation')
    assert str(oral_person.id) in {person['id'] for person in options['users']}
    assert str(annotation_person.id) in {person['id'] for person in options['users']}
    import pytest
    from fastapi import HTTPException
    assert {str(p.id) for p in [sender,annotation_person,oral_person]}==set(options['user_ids'])
    result=service.send(db,sender,request.id,service.DispatchWrite(kind='circle',user_ids=[oral_person.id],idempotency_key=str(uuid4())))
    assert result['snapshot']['request_content']['dispatch_notes']['circle']=='请发圈'
    assert result['snapshot']['request_content']['versions'][0]['content']=='口译发布正文'
    second=service.send(db,sender,request.id,service.DispatchWrite(kind='post',user_ids=[oral_person.id],idempotency_key=str(uuid4())))
    assert second['id']!=result['id']
    assert len(notices)==2


def test_multiple_directions_pair_each_count_and_list_multiple_locations():
    raw=payload().model_dump()
    raw['time_ranges'][0]['language_directions'].append({'language_ids':[uuid4(),uuid4()],'required_count':3})
    raw['time_ranges'][0]['location_details'].append({'country_province':'中国','city':'上海市','address':'浦东会展中心'})
    draft=DemandReleaseRequest(**raw)
    content=build_release(draft,['中文 ↔ 日语','中文 ↔ 英语'],'上海')
    assert '语言与人数：中文 ↔ 日语方向，2人；中文 ↔ 英语方向，3人' in content
    assert '需求人数：' not in content and '项目语言：' not in content
    assert '项目地点：深圳市、上海市' in content
