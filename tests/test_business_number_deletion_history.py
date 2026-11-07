from uuid import uuid4
from sqlalchemy import create_engine,inspect,text,event
from tests.test_chat_participant_access import environment
from tests.test_client_cooperation_auto import client,project
from business_numbering import BusinessNumberDeletionHistory,BusinessNumberLease,allocate
import crud
import pytest

def test_history_migration_only_creates_new_table_and_is_repeatable():
    from tools.apply_business_number_history_migration import apply_migration
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE app_user (id CHAR(32) PRIMARY KEY)'))
        apply_migration(connection);apply_migration(connection)
        assert set(inspect(connection).get_table_names())=={'app_user','business_number_deletion_history'}

def test_hard_delete_archives_before_reusing_number_and_never_overwrites_old_history(environment):
    db,(owner,_,_)=environment;customer=client(db)
    def generated_ids(session,*_):
        for item in session.new:
            if hasattr(item,'id') and item.id is None:item.id=uuid4()
    event.listen(db,'before_flush',generated_ids)
    db.info.update(number_actor=owner.id,number_actor_name=owner.full_name or owner.username)
    first=project(db,customer,'777',None)
    first_id=first.id;number=first.order_no
    assert crud.delete_translation_project(db,first.id,actor_user_id=owner.id)
    history=db.query(BusinessNumberDeletionHistory).filter_by(number=number).one()
    assert history.entity_id==str(first_id) and history.actor_id==owner.id
    assert history.snapshot['project_name']=='合作项目'
    db.info['number_reserve']=uuid4()
    assert allocate(db,'translation','TP-261001-',999)==number
    token=db.info['number_reserved_row'].id;db.commit()
    db.info.pop('number_reserve')
    import json
    db.info['number_tokens']=json.dumps([str(token)])
    assert allocate(db,'translation','TP-261001-',999)==number
    second=project(db,customer,'777',None)
    second_id=second.id
    assert first_id!=second_id
    db.info['number_tokens']='[]'
    assert crud.delete_translation_project(db,second.id,actor_user_id=owner.id)
    histories=db.query(BusinessNumberDeletionHistory).filter_by(number=number).all()
    assert {row.entity_id for row in histories}=={str(first_id),str(second_id)}

def test_failed_delete_rolls_back_history_and_keeps_number_used(environment):
    db,(owner,_,_)=environment;customer=client(db)
    db.info.update(number_actor=owner.id)
    row=project(db,customer,'888',None)
    lease=BusinessNumberLease(id=uuid4(),owner_id=owner.id,window_id=uuid4(),scope='translation',number=row.order_no,state='used',expires_at=__import__('chat_time').now())
    db.add(lease);db.commit();root_id=row.id;token=lease.id;number=row.order_no
    db.delete(row);db.flush()
    assert db.query(BusinessNumberDeletionHistory).filter_by(number=number).count()==1
    db.rollback()
    assert db.query(BusinessNumberDeletionHistory).filter_by(number=number).count()==0
    assert db.get(BusinessNumberLease,token).state=='used'
    from models import TranslationProject
    assert db.get(TranslationProject,root_id)

def test_annotation_delete_releases_unique_reservation_but_keeps_original_snapshot(environment):
    from annotation_models import AnnotationProject
    from project_order_no_models import ProjectOrderNoReservation
    from annotation_service import reserve_annotation_order_no
    db,(owner,_,_)=environment
    db.info.update(number_actor=owner.id,number_actor_name=owner.username)
    root=AnnotationProject(id=uuid4(),order_no='AP-261107-123',project_name='待删除标注项目')
    reservation=ProjectOrderNoReservation(id=uuid4(),project_type='annotation',project_id=root.id,order_no=root.order_no,order_no_key=root.order_no,assignment_source='test')
    db.add_all([root,reservation]);db.commit();old_id=root.id;number=root.order_no
    db.delete(root);db.commit()
    assert db.query(ProjectOrderNoReservation).filter_by(order_no=number).count()==0
    history=db.query(BusinessNumberDeletionHistory).filter_by(number=number).one()
    assert history.entity_id==str(old_id) and history.snapshot['project_name']=='待删除标注项目'
    db.info['number_reserve']=uuid4()
    assert allocate(db,'annotation','AP-261107-',999)==number

def test_history_query_is_permission_scoped_and_uses_all_keywords(environment,monkeypatch):
    from business_numbering import archive_number
    from routers.business_numbers import history
    from fastapi import HTTPException
    import routers.auth
    db,(owner,_,_)=environment;customer=client(db)
    root=project(db,customer,'SEARCH',None)
    archive_number(db,'translation',root.order_no,root,actor=owner);db.commit()
    monkeypatch.setattr(routers.auth,'get_user_permission_codes',lambda *_:['projects:read'])
    found=history('translation','SEARCH 合作',0,20,db,owner)
    assert found['total']==1 and found['items'][0]['snapshot']['project_name']=='合作项目'
    assert found['items'][0]['deleted_at'].utcoffset().total_seconds()==28800
    assert history('translation','SEARCH 不匹配',0,20,db,owner)['total']==0
    with pytest.raises(HTTPException) as error:history('talent','',0,20,db,owner)
    assert error.value.status_code==403

def test_legacy_translator_and_talent_share_one_number_pool(environment):
    from models import Translator
    from resource_models import ResourcePerson
    db,(owner,_,_)=environment;db.info['number_actor']=owner.id
    existing=Translator(id=uuid4(),translator_name='已有译员',translator_code='RC000001')
    db.add(existing);db.commit()
    new=Translator(id=uuid4(),translator_name='新译员')
    db.add(new);db.commit()
    assert new.translator_code=='RC000002'
    person=ResourcePerson(id=uuid4(),full_name='新人才')
    db.add(person);db.commit()
    assert person.resource_code=='RC000003'
