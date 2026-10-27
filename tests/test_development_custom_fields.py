"""自定义开拓字段与动态账号列；仅使用隔离内存库。"""
from datetime import date
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment


def test_custom_values_roundtrip_privacy_filter_copy_compatibility_and_account_columns(environment, monkeypatch):
    db, users = environment
    import resource_development_service as service
    from resource_development_models import DevelopmentOption as Option, DevelopmentAudit
    from resource_development_schemas import RecordWrite, CustomFieldWrite
    from routers.resource_development import create_custom_field
    from resource_development_custom_fields import account_columns
    from tools.apply_development_custom_fields_migration import apply_migration
    from routers import resource_development as router
    monkeypatch.setattr(service,'lock_writes',lambda db:None)
    monkeypatch.setattr(router,'lock_writes',lambda db:None)
    monkeypatch.setattr(service,'refresh_draft',lambda *args:None)
    monkeypatch.setattr(service,'can_delegate',lambda *args:False)
    monkeypatch.setattr(service,'is_admin',lambda *args:False)
    apply_migration(db.connection()); apply_migration(db.connection())
    definition=create_custom_field(CustomFieldWrite(name='自定义领域'),db,users[0])
    repeated=create_custom_field(CustomFieldWrite(name='自定义领域'),db,users[0])
    assert definition['id']==repeated['id']
    platform=Option(id=uuid4(),kind='platform',category='national',name='字段测试平台',code='CUSTOMTEST')
    db.add(platform);db.commit()
    values=dict(id=uuid4(),platform_id=platform.id,owner_id=users[0].id,work_date=date(2026,10,26),full_name='自定义字段测试')
    row=service.save_record(db,users[0],RecordWrite(**values,custom_fields={definition['id']:'医疗_%/汉字'},custom_accounts=[{'name':'Telegram','value':'tg_%_ABC'}]))
    db.commit()
    data=service.serialize_record(db,users[0],row,True)
    assert data['custom_fields'][definition['id']]=='医疗_%/汉字'
    assert data['custom_field_items'][0]['name']=='自定义领域'
    assert service.serialize_record(db,users[2],row)['custom_fields'][definition['id']]=='受限内容'
    assert account_columns(db)==[{'key':'custom_account:telegram','name':'Telegram'}]
    field_key='custom_field:'+definition['id']
    query=lambda user,filters:service.filtered_records(db,user,None,None,column_filters=filters)
    from resource_development_models import DevelopmentCustomValue as Value, DevelopmentRecord as Record
    from search_matching import keyword_ilike
    assert db.query(Record).filter(Record.owner_id==users[0].id).count()==1
    assert db.query(Value).filter(keyword_ilike(Value.value,'%_%%')).count()==1
    assert query(users[0],{field_key:'_%'}).count()==1
    assert query(users[2],{field_key:'_%'}).count()==0
    assert query(users[0],{'custom_account:telegram':'_%_'}).count()==1
    assert query(users[0],{'custom_account:telegram':'not-found'}).count()==0
    assert query(users[2],{'custom_account:telegram':'ABC'}).count()==0
    service.save_record(db,users[0],RecordWrite(**values,revision=row.revision))
    db.commit()
    assert service.serialize_record(db,users[0],row)['custom_fields'][definition['id']]=='医疗_%/汉字'
    service.save_record(db,users[0],RecordWrite(**values,revision=row.revision,custom_fields={definition['id']:''}))
    db.commit()
    assert service.serialize_record(db,users[0],row)['custom_fields'][definition['id']]==''
    assert db.query(DevelopmentAudit).filter_by(entity_id=row.id,entity_type='record_custom_fields').count()==2
    with pytest.raises(HTTPException):
        service.save_record(db,users[0],RecordWrite(**values,revision=row.revision,custom_fields={str(uuid4()):'未知字段'}))


def test_custom_field_limits():
    from resource_development_schemas import RecordWrite,CustomFieldWrite
    with pytest.raises(ValueError):CustomFieldWrite(name=' ')
    with pytest.raises(ValueError):CustomFieldWrite(name='a'*101)
    with pytest.raises(ValueError):RecordWrite(id=uuid4(),platform_id=uuid4(),owner_id=uuid4(),work_date=date(2026,10,26),full_name='测试',custom_fields={uuid4():'a'*20001})
