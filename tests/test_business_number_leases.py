import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from business_numbering import BusinessNumberLease, allocate, consume_explicit, live
from chat_time import now
from routers.business_numbers import Reserve, reserve, release, heartbeat, skip_number
import main  # 注册业务模型关系，不启动服务或执行迁移。

@pytest.fixture
def database(tmp_path, monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'isolated.sqlite'))
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE app_user (id CHAR(32) PRIMARY KEY)'))
        conn.execute(text('CREATE TABLE translation_project (id CHAR(32) PRIMARY KEY, order_no TEXT)'))
        conn.execute(text('CREATE TABLE consultation (id CHAR(32) PRIMARY KEY, consultation_code TEXT)'))
        conn.execute(text("INSERT INTO translation_project VALUES ('saved', 'TP-261107-999')"))
        BusinessNumberLease.__table__.create(conn)
    import routers.auth
    monkeypatch.setattr(routers.auth,'get_user_permission_codes',lambda *_:['*'])
    yield engine
    engine.dispose()

def opening(engine,owner=None,window=None):
    with Session(engine) as db:
        user=SimpleNamespace(id=owner or uuid4())
        payload=Reserve(kind='translation',window_id=window or uuid4(),business_date='2026-11-07')
        return user,reserve(payload,db,user),payload

def test_accounts_and_windows_claim_distinct_numbers_and_network_retry_is_idempotent(database):
    user,a,payload=opening(database)
    _,b,_=opening(database,user.id)
    _,c,_=opening(database)
    assert [a['number'],b['number'],c['number']]==['TP-261107-1000','TP-261107-1001','TP-261107-1002']
    with Session(database) as db:assert reserve(payload,db,user)==a

def test_close_returns_number_to_pool_and_reopen_gets_new_proof(database):
    user,a,_=opening(database)
    with Session(database) as db:release(__import__('uuid').UUID(a['token']),db,user)
    with Session(database) as db:assert db.get(BusinessNumberLease,__import__('uuid').UUID(a['token'])).state=='released'
    _,b,_=opening(database,user.id)
    assert b['number']==a['number']=='TP-261107-1000'
    assert b['token']!=a['token']
    with Session(database) as db:
        db.info.update(number_actor=user.id,number_tokens=json.dumps([a['token']]))
        with pytest.raises(HTTPException):consume_explicit(db,'translation',a['number'])
        with pytest.raises(HTTPException):allocate(db,'translation','TP-261107-',1)
        release(__import__('uuid').UUID(a['token']),db,user)
        assert live(db.get(BusinessNumberLease,__import__('uuid').UUID(b['token'])))

def test_save_claim_is_transactional_foreign_window_and_owner_rejected(database):
    user,a,_=opening(database)
    token=__import__('uuid').UUID(a['token'])
    with Session(database) as db:
        db.info.update(number_actor=user.id,number_tokens=json.dumps([a['token']]))
        assert allocate(db,'translation','TP-261107-',1)==a['number']
        db.rollback()
    with Session(database) as db:assert db.get(BusinessNumberLease,token).state=='active'
    with Session(database) as db:
        db.info.update(number_actor=uuid4(),number_tokens=json.dumps([a['token']]))
        with pytest.raises(HTTPException):allocate(db,'translation','TP-261107-',1)
    with Session(database) as db:
        with pytest.raises(HTTPException):consume_explicit(db,'translation',a['number'])
    with Session(database) as db:
        db.info.update(number_actor=user.id,number_tokens=json.dumps([a['token']]))
        assert allocate(db,'translation','TP-261107-',1)==a['number']
        db.commit()
    with Session(database) as db:
        release(token,db,user)
        assert db.get(BusinessNumberLease,token).state=='used'

def test_expiry_and_heartbeat_are_owner_scoped(database):
    user,a,_=opening(database)
    token=__import__('uuid').UUID(a['token'])
    with Session(database) as db:
        with pytest.raises(HTTPException):heartbeat(token,db,SimpleNamespace(id=uuid4()))
        assert heartbeat(token,db,user)['ok']
        db.get(BusinessNumberLease,token).expires_at=now()-timedelta(seconds=1);db.commit()
        assert not live(db.get(BusinessNumberLease,token))
        with pytest.raises(HTTPException):heartbeat(token,db,user)
        db.info.update(number_actor=user.id,number_tokens=json.dumps([a['token']]))
        with pytest.raises(HTTPException):allocate(db,'translation','TP-261107-',1)
    _,new,_=opening(database,user.id)
    assert new['number']=='TP-261107-1000'
    assert new['token']!=a['token']

def test_migration_only_creates_new_table_and_is_repeatable(tmp_path):
    from tools.apply_business_number_lease_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE app_user (id CHAR(32) PRIMARY KEY)'))
        apply_migration(conn);apply_migration(conn)
        assert set(inspect(conn).get_table_names())=={'app_user','business_number_lease'}

def test_background_creation_skips_open_windows_and_uses_integer_suffixes(database):
    _,a,_=opening(database)
    with Session(database) as db:
        # 后台导入不带窗口凭证，也不可取走1000。
        assert allocate(db,'translation','TP-261107-',1)=='TP-261107-1001'
        db.execute(text("INSERT INTO translation_project VALUES ('imported', 'TP-261107-1200')"));db.commit()
        assert allocate(db,'translation','TP-261107-',1)=='TP-261107-1201'

def test_reuse_skips_active_used_and_saved_numbers_even_below_saved_maximum(database):
    user,a,_=opening(database)
    _,b,_=opening(database)
    _,c,_=opening(database)
    with Session(database) as db:
        release(__import__('uuid').UUID(a['token']),db,user)
        # 已保存项目的编号不能因旧租约被释放而回收。
        db.execute(text("INSERT INTO translation_project VALUES ('persisted', :number)"),{'number':a['number']})
        db.commit()
        db.get(BusinessNumberLease,__import__('uuid').UUID(b['token'])).state='used';db.commit()
        release(__import__('uuid').UUID(c['token']),db,SimpleNamespace(id=db.get(BusinessNumberLease,__import__('uuid').UUID(c['token'])).owner_id))
    _,new,_=opening(database)
    assert new['number']==c['number']
    assert new['token']!=c['token']

def test_released_number_can_be_reassigned_to_another_account(database):
    user,a,_=opening(database)
    with Session(database) as db:release(__import__('uuid').UUID(a['token']),db,user)
    other,b,_=opening(database)
    assert other.id!=user.id and b['number']==a['number'] and b['token']!=a['token']
    with Session(database) as db:
        with pytest.raises(HTTPException):heartbeat(__import__('uuid').UUID(a['token']),db,user)
        db.info.update(number_actor=user.id,number_tokens=json.dumps([a['token']]))
        with pytest.raises(HTTPException):allocate(db,'translation','TP-261107-',1)
        assert heartbeat(__import__('uuid').UUID(b['token']),db,other)['ok']

def test_replace_consultation_number_releases_old_number_for_future_use(database):
    user=SimpleNamespace(id=uuid4())
    business_date=now().date()
    prefix=f'EQ-{business_date:%y%m%d}-'
    with Session(database) as db:
        first=reserve(Reserve(kind='consultation',window_id=uuid4(),business_date=business_date),db,user)
    with Session(database) as db:
        replacement=skip_number(__import__('uuid').UUID(first['token']),db,user)
        assert replacement['number']==f'{prefix}002'
        assert db.get(BusinessNumberLease,__import__('uuid').UUID(first['token'])).state=='released'
    with Session(database) as db:
        with pytest.raises(HTTPException) as error:
            skip_number(__import__('uuid').UUID(first['token']),db,user)
        assert error.value.status_code==409
    with Session(database) as db:
        release(__import__('uuid').UUID(replacement['token']),db,user)
    with Session(database) as db:
        next_number=reserve(Reserve(kind='consultation',window_id=uuid4(),business_date=business_date),db,user)
        assert next_number['number']==f'{prefix}001'

def test_skip_translation_number_preserves_business_date(database):
    user=SimpleNamespace(id=uuid4())
    with Session(database) as db:
        first=reserve(Reserve(kind='translation',window_id=uuid4(),business_date='2026-11-07'),db,user)
    with Session(database) as db:
        second=skip_number(__import__('uuid').UUID(first['token']),db,user)
    assert first['number']=='TP-261107-1000'
    assert second['number']=='TP-261107-1001'

def test_repeated_number_changes_reuse_released_numbers_instead_of_growing_sequence(database):
    user,current,_=opening(database)
    values={current['number']}
    for _ in range(10):
        with Session(database) as db:
            current=skip_number(__import__('uuid').UUID(current['token']),db,user)
            values.add(current['number'])
    assert values=={'TP-261107-1000','TP-261107-1001'}

@pytest.mark.parametrize('scope,prefix,width',[
    ('interpretation','IP-261107-',3),('annotation','AP-261107-',3),
    ('recruitment','HP-261107-',3),('client','CL-261107-',3),
    ('consultation','EQ-261107-',3),('resource_request','RR-261107-',3),
    ('hr_requirement','RT-261107-',3),('technical_task','DT-261107-',3),
    ('feedback','FB-261107-',3),('talent','RC',6),
    ('translation_suborder:'+str(uuid4()),'TP-261107-001.',3),
    ('annotation_suborder:'+str(uuid4()),'AP-261107-001.001.',3),
    ('subclient:'+str(uuid4()),'CL-261107-001.',3),
    ('technical_subtask:'+str(uuid4()),'DT-261107-001.',3),
    ('greeting:'+str(uuid4()),'TEST-261107-',3),
])
@pytest.mark.parametrize('released_state',['released','skipped'])
def test_all_automatic_number_scopes_recycle_released_leases(database,scope,prefix,width,released_state):
    with Session(database) as db:
        db.info.update(number_actor=uuid4(),number_reserve=uuid4())
        first=allocate(db,scope,prefix,1,width);row=db.info['number_reserved_row'];old=row.id
        row.state=released_state;db.commit()
    with Session(database) as db:
        db.info.update(number_actor=uuid4(),number_reserve=uuid4())
        assert allocate(db,scope,prefix,99,width)==first
        assert db.info['number_reserved_row'].id!=old
