from io import BytesIO
from uuid import uuid4
import pytest
from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from talent_region_matching import RegionMatchWrite, RegionIndex, normalize, prepare_source, import_table
from test_chat_participant_access import environment  # noqa: F401


def payload(rows, mappings=None, **kwargs):
    return RegionMatchWrite(rows=rows, mappings=mappings or [{'source_column': 0, 'target_fields': ['ancestral_home']}], **kwargs)


def test_source_is_a_contiguous_whole_not_scattered_or_partial():
    index = RegionIndex([
        dict(id='whole', ancestral_home='前ABC后', native_place='', residence_address=''),
        dict(id='spaced', ancestral_home='A B C', native_place='', residence_address=''),
        dict(id='scattered', ancestral_home='AxByC', native_place='', residence_address=''),
        dict(id='partial', ancestral_home='AB', native_place='C', residence_address=''),
    ])
    for threshold in (50, 60, 70, 80, 90, 100):
        request = payload([['ABC']], threshold=threshold)
        assert index.row_scores(request.rows[0], request) == {'whole':100}
    assert normalize(' ＡＢＣ ') == 'abc'
    assert normalize('A B-C') == 'a b-c'


def test_suffix_only_once_longest_first_short_names_and_empty_safety():
    rules = payload([['深圳市']], match_mode='trim_suffix', suffixes=['省','市','区','县','镇','乡','自治州','自治县','自治区'])
    for source, expected in [('深圳市','深圳'),('广东省','广东'),('自治州',''),('广西自治区','广西'),('延边自治州','延边'),('大理自治县','大理'),('市中区','市中'),('深圳市区','深圳市'),('省市深圳','省市深圳'),('深圳市中心','深圳市中心'),('房县','房县'),('中山市','中山')]:
        assert prepare_source(source, rules) == expected
    assert prepare_source('房县', rules.model_copy(update={'preserve_short':False})) == '房'
    assert prepare_source('广西自治区', rules.model_copy(update={'suffixes':['区']})) == '广西自治'
    assert prepare_source('深圳市', rules.model_copy(update={'match_mode':'full'})) == '深圳市'
    assert prepare_source('深圳市', rules.model_copy(update={'suffixes':[]})) == '深圳市'
    index = RegionIndex([dict(id='one',ancestral_home='广东深圳',native_place='上海',residence_address='')])
    request=payload([['市','上海']], mappings=[{'source_column':0,'target_fields':['ancestral_home']},{'source_column':1,'target_fields':['native_place']}],match_mode='trim_suffix',suffixes=['市'],preserve_short=False)
    assert index.row(request.rows[0], request) == set()


def test_mapping_cardinalities_combine_and_blank_rows():
    index = RegionIndex([
        dict(id='one', ancestral_home='广东深圳市', native_place='四川成都', residence_address='广东广州'),
        dict(id='two', ancestral_home='广西桂林', native_place='广东深圳', residence_address='四川成都'),
        dict(id='three', ancestral_home='广东深市', native_place=None, residence_address=None),
    ])
    one = payload([['广东深圳']])
    assert index.row(one.rows[0], one) == {'one'}
    one_many = payload([['广东深圳']], [{'source_column':0,'target_fields':['ancestral_home','native_place']}])
    assert index.row(one_many.rows[0], one_many) == {'one','two'}
    many_one = payload([['广东','深圳']], [{'source_column':0,'target_fields':['ancestral_home']},{'source_column':1,'target_fields':['ancestral_home']}])
    assert index.row(many_one.rows[0], many_one) == {'one'}
    many_many = payload([['广东深圳','四川成都']], [{'source_column':0,'target_fields':['ancestral_home','native_place']},{'source_column':1,'target_fields':['native_place','residence_address']}])
    assert index.row(many_many.rows[0], many_many) == {'one','two'}
    assert index.row(one_many.rows[0], one_many.model_copy(update={'target_combine':'all'})) == set()
    assert index.row([''], one) == set()
    assert index.row(['   '], one) == set()
    assert index.row(['广东','桂林'], many_one.model_copy(update={'combine':'any'})) == {'one','two','three'}


def test_contract_rejects_invalid_mapping_precision_or_shape():
    assert payload([['深圳']], threshold=50).threshold == 50
    for arguments in [dict(threshold=49),dict(threshold=55),dict(threshold=79),dict(threshold=101),dict(threshold=99.5),dict(threshold=True)]:
        with pytest.raises(ValidationError): payload([['深圳']], **arguments)
    for mappings in [[{'source_column':1,'target_fields':['ancestral_home']}], [{'source_column':0,'target_fields':['primary_phone']}], [{'source_column':0,'target_fields':[]}], [{'source_column':0,'target_fields':['ancestral_home']}]*2]:
        with pytest.raises(ValidationError): payload([['深圳']], mappings)
    with pytest.raises(ValidationError):payload([['深'*256]])
    with pytest.raises(ValidationError):payload([['深圳']]*1001)
    with pytest.raises(ValidationError):payload([['深圳']], match_mode='fuzzy')
    with pytest.raises(ValidationError):payload([['深圳']], suffixes=['街道'])


def test_excel_and_csv_import_sheet_headers_source_rows_and_limits():
    from openpyxl import Workbook
    workbook=Workbook(); workbook.active.title='区域一'
    workbook.active.append(['籍贯','成长地']);workbook.active.append(['广东深圳','四川成都']);workbook.active.append([None,None]);workbook.active.append(['广东广州',None])
    workbook.create_sheet('区域二').append(['上海','北京'])
    stream=BytesIO();workbook.save(stream);workbook.close()
    imported=import_table(stream.getvalue(),'地区.xlsx')
    assert imported['sheets']==['区域一','区域二']
    assert [row['source_row'] for row in imported['rows']]==[2,4]
    assert imported['rows'][1]['values']==['广东广州','']
    assert imported['columns'][0]['label']=='A列 · 籍贯'
    assert import_table(stream.getvalue(),'地区.xlsx','区域二',False)['rows'][0]['values']==['上海','北京']
    assert import_table('籍贯,成长地\n广东深圳,四川成都'.encode(),'区域.csv')['rows'][0]['values']==['广东深圳','四川成都']
    for content,name in [(b'bad','bad.xlsx'),(b'bad','bad.xls'),(b'','empty.csv'),(('省\n'+'广东\n'*1001).encode(),'large.csv')]:
        with pytest.raises(HTTPException):import_table(content,name)


def test_summary_and_expanded_pages_use_real_pool_mask_contacts_and_deduplicate(environment, monkeypatch):
    db,users=environment
    from resource_models import ResourcePerson
    from business_time import business_now
    from routers import talents
    from routers.auth import get_current_user
    from database import get_db
    for index in range(3):
        db.add(ResourcePerson(id=uuid4(),resource_code=f'MATCH-{index}',full_name=f'匹配人才{index}',status='active',name_duplicate=False,duplicate_review_required=False,ancestral_home='广东深圳' if index<2 else '四川成都',primary_phone='private-phone',created_at=business_now(),updated_at=business_now()))
    db.commit()
    app=FastAPI();app.include_router(talents.router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:users[0]
    monkeypatch.setattr(talents,'can_view_talent_contacts',lambda *_:False)
    # 区域匹配测试不涉及配对任务历史；隔离 PostgreSQL 专用 JSONB 查询。
    import annotation_paired_service
    monkeypatch.setattr(annotation_paired_service, 'talent_participations', lambda *_: [])
    client=TestClient(app)
    request=payload([['广东深圳'],['广东深圳'],['']]).model_dump()
    summary=client.post('/talents/region-match',json=request)
    assert summary.status_code==200,summary.text
    assert [item['total'] for item in summary.json()['items']]==[2,2,0]
    assert summary.json()['unique_total']==2
    assert summary.json()['items'][0]['average_rate']==100
    assert summary.json()['items'][2]['average_rate'] is None
    request['rows']=[['广东深圳']]
    first=client.post('/talents/region-match/page?limit=1',json=request)
    assert first.status_code==200,first.text
    assert first.json()['total']==2
    assert first.json()['items'][0]['primary_phone']=='******'
    assert first.json()['items'][0]['contact_restricted'] is True
    assert first.json()['items'][0]['match_rate']==100 and first.json()['average_rate']==100
    second=client.post('/talents/region-match/page?skip=1&limit=1',json=request).json()
    assert second['total']==2 and second['items'][0]['id']!=first.json()['items'][0]['id']
    request['rows']=[['']]
    assert client.post('/talents/region-match/page',json=request).json()=={'items':[],'total':0,'average_rate':None}
    fuzzy_request = {**request, 'rows':[['广东深圳北京']], 'threshold':50}
    fuzzy_page = client.post('/talents/region-match/page?limit=1',json=fuzzy_request).json()
    assert fuzzy_page == {'items':[], 'total':0, 'average_rate':None}
    # 单行去字重匹配后，重新汇总全部来源行，跨行去重总数必须同步。
    adjusted={**request,'rows':[['广东深圳市'],['四川成都市']],'match_mode':'trim_suffix','suffixes':['市']}
    rematched=client.post('/talents/region-match',json=adjusted).json()
    assert rematched['unique_total']==3 and [row['total'] for row in rematched['items']]==[2,1]
    adjusted['rows'][0]=['广东不存在']
    rematched=client.post('/talents/region-match',json=adjusted).json()
    assert rematched['unique_total']==1 and [row['total'] for row in rematched['items']]==[0,1]
    request['rows']=[['广东深圳'],['四川']]
    assert client.post('/talents/region-match/page',json=request).status_code==422
    app.dependency_overrides.pop(get_current_user)
    assert client.post('/talents/region-match',json=request).status_code==401
