"""只使用隔离库验证局部修改、并发保护与修改记录。"""
from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_chat_participant_access import environment


def test_patch_preserves_other_fields_records_changes_and_masks_history(environment, monkeypatch):
    db, users = environment
    import resource_service
    from resource_models import ResourcePerson
    from talent_path_edit import TalentPathEdit, TalentPathChange, save_path_fields, path_history
    from tools.apply_talent_path_history_migration import apply_migration
    monkeypatch.setattr(resource_service, 'lock_account_writes', lambda db: None)
    person = ResourcePerson(id=uuid4(), resource_code='EDIT-001', full_name='原姓名', status='active', ancestral_home='原籍贯', native_place='原成长地', remarks='其他资料不能改变', wechat='old-wechat')
    db.add(person);db.commit()
    apply_migration(db.connection());apply_migration(db.connection())
    payload=TalentPathEdit(changes={'full_name':'新姓名','ancestral_home':'新籍贯','wechat':'new-wechat'},expected_values={'full_name':'原姓名','ancestral_home':'原籍贯','wechat':'old-wechat'})
    saved=save_path_fields(db,person.id,payload,users[0],contacts_visible=True);db.commit();db.expire_all()
    assert saved.full_name=='新姓名' and saved.ancestral_home=='新籍贯'
    assert saved.native_place=='原成长地' and saved.remarks=='其他资料不能改变'
    history=path_history(db,person.id,skip=0,limit=20,contacts_visible=True)
    assert history['total']==1
    assert history['items'][0]['changes']['full_name']=={'before':'原姓名','after':'新姓名'}
    assert history['items'][0]['actor_name']==users[0].full_name
    assert history['items'][0]['created_at'].endswith('+08:00')
    masked=path_history(db,person.id,skip=0,limit=20,contacts_visible=False)
    assert masked['items'][0]['changes']['wechat']=={'before':'******','after':'******'}
    with pytest.raises(HTTPException) as conflict:
        save_path_fields(db,person.id,payload,users[0],contacts_visible=True)
    assert conflict.value.status_code==409
    assert db.query(TalentPathChange).count()==1
    with pytest.raises(HTTPException) as denied:
        save_path_fields(db,person.id,TalentPathEdit(changes={'wechat':'forbidden'},expected_values={'wechat':'new-wechat'}),users[0],contacts_visible=False)
    assert denied.value.status_code==403
    # 不同字段的独立更新可以合并，不会覆盖先前修改。
    save_path_fields(db,person.id,TalentPathEdit(changes={'native_place':'新成长地'},expected_values={'native_place':'原成长地'}),users[0],contacts_visible=False)
    db.commit()
    assert db.query(TalentPathChange).count()==2
    assert db.get(ResourcePerson,person.id).full_name=='新姓名'
    assert path_history(db,person.id,skip=1,limit=1,contacts_visible=True)['total']==2


def test_allowed_fields_required_values_lengths_and_number_uniqueness(environment,monkeypatch):
    db,users=environment
    import resource_service
    from resource_models import ResourcePerson
    from talent_path_edit import TalentPathEdit, save_path_fields, TalentPathChange
    monkeypatch.setattr(resource_service,'lock_account_writes',lambda db:None)
    for changes,expected in [({'remarks':'unexpected'},{'remarks':''}),({'full_name':'  '},{'full_name':'a'}),({'resource_code':'x'*51},{'resource_code':'a'}),({'native_place':'a'},{}),({'primary_phone':'x'*51},{'primary_phone':None})]:
        with pytest.raises(ValueError):TalentPathEdit(changes=changes,expected_values=expected)
    a=ResourcePerson(id=uuid4(),resource_code='ONE',full_name='甲',status='active')
    b=ResourcePerson(id=uuid4(),resource_code='TWO',full_name='乙',status='active')
    db.add_all([a,b]);db.commit()
    with pytest.raises(HTTPException) as duplicate:
        save_path_fields(db,b.id,TalentPathEdit(changes={'resource_code':'ONE'},expected_values={'resource_code':'TWO'}),users[0],contacts_visible=True)
    assert duplicate.value.status_code==409
    assert db.query(TalentPathChange).count()==0
    save_path_fields(db,a.id,TalentPathEdit(changes={'full_name':'甲'},expected_values={'full_name':'甲'}),users[0],contacts_visible=True)
    db.commit()
    assert db.query(TalentPathChange).count()==0


def test_patch_endpoint_requires_write_access_and_history_keeps_contact_permissions(environment,monkeypatch):
    db,users=environment
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers import talents,auth
    from resource_models import ResourcePerson
    import resource_service
    monkeypatch.setattr(resource_service,'lock_account_writes',lambda db:None)
    person=ResourcePerson(id=uuid4(),resource_code='API-EDIT',full_name='接口测试',status='active',resume_path=None,wechat='private-old')
    db.add(person);db.commit()
    app=FastAPI();app.include_router(talents.router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[auth.get_current_user]=lambda:users[0]
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda *args:[])
    monkeypatch.setattr(talents,'can_view_talent_contacts',lambda *args:False)
    url=f'/talents/{person.id}/path-fields'
    payload={'changes':{'resume_path':'D:/new.pdf'},'expected_values':{'resume_path':None}}
    with TestClient(app) as client:
        assert client.patch(url,json=payload).status_code==403
        monkeypatch.setattr(auth,'get_user_permission_codes',lambda *args:['talents:write'])
        saved=client.patch(url,json=payload)
        assert saved.status_code==200,saved.text
        assert saved.json()['resume_path']=='D:/new.pdf'
        assert client.patch(url,json=payload).status_code==409
        assert client.patch(url,json={'changes':{'wechat':'hidden-change'},'expected_values':{'wechat':'private-old'}}).status_code==403
        logs=client.get(f'/talents/{person.id}/path-history').json()
        assert logs['total']==1
        assert logs['items'][0]['changes']['resume_path']=={'before':None,'after':'D:/new.pdf'}
