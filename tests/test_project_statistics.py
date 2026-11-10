"""各项目新老客户统计：隔离 SQLite，不连接业务库。"""
from datetime import date, datetime, timezone
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from models import Client, SubClient
from tests.test_chat_participant_access import environment
from project_statistics import MODELS, report, project_day, router


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
