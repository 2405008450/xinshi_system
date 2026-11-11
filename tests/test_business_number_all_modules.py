"""逐模块验证真实占号接口；只使用隔离 SQLite，不连接业务数据库。"""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert
from tests.test_chat_participant_access import environment
from business_numbering import Base, BusinessNumberLease, SPECS
from routers.business_numbers import Reserve, reserve, skip_number, release


@pytest.mark.parametrize('kind', [*SPECS, 'translation_suborder', 'annotation_suborder', 'subclient', 'technical_subtask', 'greeting'])
def test_each_module_recycles_after_repeated_changes_and_close(environment, monkeypatch, kind):
    db, users = environment
    db.autoflush = False
    import routers.auth
    import hr_access
    import technical_development
    monkeypatch.setattr(routers.auth, 'get_user_permission_codes', lambda *_: ['*'])
    access_calls=[]
    monkeypatch.setattr(hr_access, 'require_hr', lambda *_: access_calls.append('hr'))
    monkeypatch.setattr(technical_development, 'require_user', lambda *_: access_calls.append('technical'))
    parent=None
    parent_specs={
        'translation_suborder': ('translation_project', 'id', 'order_no', 'TP-261107-001'),
        'annotation_suborder': ('annotation_project', 'id', 'order_no', 'AP-261107-001'),
        'subclient': ('client', 'id', 'client_code', 'CL-261107-001'),
        'technical_subtask': ('technical_task_hierarchy_number', 'task_id', 'task_no', 'DT-261107-001'),
        'greeting': ('resource_development_option', 'id', 'code', 'QA'),
    }
    if kind in parent_specs:
        parent=uuid4()
        table,key,field,number=parent_specs[kind]
        db.execute(insert(Base.metadata.tables[table]).values(**{key:parent,field:number}))
        db.commit()
    payload=lambda: Reserve(kind=kind, window_id=uuid4(), parent_id=parent, business_date='2026-11-07')
    first=reserve(payload(),db,users[0])
    current=first
    seen={first['number']}
    for _ in range(10):
        current=skip_number(UUID(current['token']),db,users[0])
        seen.add(current['number'])
    assert len(seen)==2
    if kind=='hr_requirement':assert access_calls==['hr']*11
    if kind in ('technical_task','technical_subtask','feedback'):assert access_calls==['technical']*11
    # 另一账号可占用已释放号，连续换号不能抢走该窗口的编号。
    other=reserve(payload(),db,users[1])
    replacement=skip_number(UUID(current['token']),db,users[0])
    assert replacement['number']!=other['number']
    assert db.get(BusinessNumberLease,UUID(other['token'])).state=='active'
    release(UUID(replacement['token']),db,users[0])
    release(UUID(other['token']),db,users[1])
    reopened=reserve(payload(),db,users[0])
    assert reopened['number']==first['number']
    # 即使历史占号状态不准确，业务表中已保存的编号仍不可回收。
    sources={
        'translation_suborder':('translation_sub_order','sub_order_no'),
        'annotation_suborder':('annotation_project','order_no'),
        'subclient':('sub_client','sub_client_code'),
        'technical_subtask':('technical_task_hierarchy_number','task_no'),
        'greeting':('resource_development_record','greeting_no'),
    }
    table_name,field=SPECS[kind][:2] if kind in SPECS else sources[kind]
    table=Base.metadata.tables[table_name]
    key=next(iter(table.primary_key.columns)).name
    db.execute(insert(table).values(**{key:uuid4(),field:reopened['number']}))
    db.get(BusinessNumberLease,UUID(reopened['token'])).state='skipped'
    db.commit()
    assert reserve(payload(),db,users[0])['number']!=reopened['number']
