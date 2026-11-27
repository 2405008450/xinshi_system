"""各项目新老客户统计：隔离 SQLite，不连接业务库。"""
from datetime import date, datetime, timezone
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from models import Client, SubClient
from tests.test_chat_participant_access import environment
from project_statistics import MODELS, report, project_day, project_period_bounds, router, INTERPRETATION_STATUSES


def client(db, name):
    row=Client(id=uuid4(),client_name=name+'有限公司',client_short_name=name,client_code='C-'+name)
    db.add(row)
    return row


def add(db, module, c, day, *, suffix='001', **values):
    model,prefix=MODELS[module]
    row=model(id=uuid4(),order_no=f'{prefix}-{day:%y%m%d}-{suffix}',project_name='统计测试',client_id=c.id if c else None,
              created_at=datetime(2026,11,9), **values)
    db.add(row)
    return row


@pytest.mark.parametrize('module',MODELS)
def test_history_independent_customer_filter_and_unlinked_orders(environment,module):
    db,_=environment
    old,new=client(db,'旧客'),client(db,'新客')
    add(db,module,old,date(2026,10,1))
    add(db,module,old,date(2026,11,1))
    add(db,module,new,date(2026,11,2))
    add(db,module,new,date(2026,11,3))
    add(db,module,None,date(2026,11,4))
    # 其他业务的老客户，不影响本模块的新客户判断。
    other=next(key for key in MODELS if key!=module)
    add(db,other,new,date(2025,1,1))
    db.commit()
    result=report(db,module,start=date(2026,11,1),end=date(2026,11,30))
    row=result['periods'][0]
    assert (row['order_count'],row['customer_count'],row['new_customer_count'],row['old_customer_count'])==(4,2,1,1)
    assert row['new_customer_share']==50 and row['new_order_share']==50 and row['old_order_share']==25 and row['unknown_order_share']==25
    assert result['generated_at'].endswith('+08:00')
    filtered=report(db,module,start=date(2026,11,1),end=date(2026,11,30),client_keyword='有限公司 旧客')
    assert filtered['order_count']==1 and filtered['customers'][0]['cohort']=='old'


@pytest.mark.parametrize('module',MODELS)
def test_week_day_timezone_subclient_and_date_fallback(environment,module):
    db,_=environment
    c=client(db,'日期')
    sub=SubClient(id=uuid4(),parent_client_id=c.id,client_name='分部',client_short_name='分部')
    db.add(sub)
    add(db,module,None,date(2026,10,31),sub_client_id=sub.id)
    add(db,module,c,date(2026,11,1),customer_consultation_time=datetime(2026,11,1,9))
    fallback=add(db,module,c,date(2026,11,9));fallback.order_no='legacy'
    db.commit()
    weekly=report(db,module,start=date(2026,11,1),end=date(2026,11,2),granularity='week')
    assert weekly['periods'][0]['period_start']=='2026-10-26' and weekly['periods'][0]['new_customer_count']==1
    daily=report(db,module,start=date(2026,11,1),end=date(2026,11,1),granularity='day')
    assert daily['periods'][0]['old_customer_count']==1
    fallback_result=report(db,module,start=date(2026,11,9),end=date(2026,11,9))
    assert fallback_result['fallback_date_orders']==1
    consulted=report(db,module,start=date(2026,11,1),end=date(2026,11,1),date_basis='reception')
    assert consulted['order_count']==1
    from annotation_progress_time import business_datetime
    assert business_datetime(datetime(2026,10,31,17,tzinfo=timezone.utc)).date()==date(2026,11,1)


def test_annotation_children_not_counted_twice(environment):
    db,_=environment;c=client(db,'层级')
    root=add(db,'annotation',c,date(2026,11,1))
    child=add(db,'annotation',c,date(2026,11,2),parent_project_id=root.id,child_sequence_no=1)
    add(db,'annotation',c,date(2026,11,3),parent_project_id=child.id,child_sequence_no=1)
    db.commit()
    result=report(db,'annotation',start=date(2026,11,1),end=date(2026,11,30))
    assert result['order_count']==1
    assert result['customers'][0]['first_order_date']=='2026-11-01'


def test_invalid_range_and_prefix(environment):
    db,_=environment
    assert project_day('HP-261109-001','HP')==date(2026,11,9)
    assert project_day('IP-261132-001','IP') is None
    for args in [dict(start=date(2026,11,2),end=date(2026,11,1)),dict(start=date(2020,1,1),end=date(2026,1,1))]:
        with pytest.raises(HTTPException):report(db,'interpretation',**args)


def test_routes_require_project_access(environment):
    app=FastAPI();app.include_router(router)
    response=TestClient(app).get('/project-statistics/recruitment?start=2026-11-01&end=2026-11-30')
    assert response.status_code in (401,403)


@pytest.mark.parametrize('granularity', ['week', 'month', 'quarter', 'all'])
def test_interpretation_status_counts_shares_and_merge(environment, granularity):
    db, _ = environment
    c = client(db, '状态客户')
    for index, status in enumerate(INTERPRETATION_STATUSES):
        add(db, 'interpretation', c, date(2026,11,2), suffix=f'{index:03}', project_status=status)
    add(db, 'interpretation', c, date(2026,9,30), project_status='in_progress')
    db.commit()
    args = dict(start=date(2026,11,2), end=date(2026,11,8), granularity=granularity)
    result = report(db, 'interpretation', **args)
    row = result['periods'][0]
    assert result['order_count'] == 11
    assert row['order_count'] == sum(item['count'] for item in row['status_counts'].values()) == 11
    assert all(item == {'count':1, 'share':9.09} for item in row['status_counts'].values())
    for key in ['candidates_provided','client_selected','client_changed']:assert row['status_counts'][key]['count']==1
    merged = report(db, 'interpretation', merge_deal_statuses=True, **args)
    values = merged['periods'][0]['status_counts']
    assert values['deal_merged'] == {'count':4, 'share':36.36}
    assert 'in_progress' not in values and 'ended' not in values
    assert sum(item['count'] for item in values.values()) == 11
    assert sum(item['share'] for item in values.values()) == pytest.approx(100,abs=.1)


def test_all_dates_ignores_range_keeps_client_filter_and_unknown_status(environment):
    db, _ = environment
    c, other = client(db, '历史客户'), client(db, '其他客户')
    add(db, 'interpretation', c, date(2019,12,31), project_status='legacy-status')
    add(db, 'interpretation', c, date(2026,11,2), project_status='settled')
    add(db, 'interpretation', other, date(2026,11,2), project_status='settled',suffix='002')
    db.commit()
    result = report(db, 'interpretation', start=date(2026,11,1), end=date(2026,11,3),
        granularity='all', all_dates=True, client_keyword='历史 客户')
    assert result['start'] == '2019-12-31' and result['end'] == '2026-11-02'
    assert len(result['periods']) == 1 and result['order_count'] == 2
    assert result['periods'][0]['status_counts']['legacy-status'] == {'count':1,'share':50}
    empty = report(db, 'interpretation', start=date(2026,11,1), end=date(2026,11,3),
        granularity='all', all_dates=True, client_keyword='不存在')
    assert empty['order_count'] == 0
    assert all(item == {'count':0,'share':0} for item in empty['periods'][0]['status_counts'].values())


def test_quarter_bounds_and_week_year_boundary():
    start, end = date(2026,1,1), date(2026,12,31)
    assert project_period_bounds(date(2026,12,31), 'quarter', start, end) == (date(2026,10,1), date(2026,12,31))
    assert project_period_bounds(date(2026,4,1), 'quarter', start, end) == (date(2026,4,1), date(2026,6,30))
    assert project_period_bounds(date(2026,1,1), 'week', start, end) == (date(2025,12,29), date(2026,1,4))
