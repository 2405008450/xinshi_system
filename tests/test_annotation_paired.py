"""双人采标事务、订单隔离与历史归属；只连接临时 PostgreSQL。"""
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text

from test_annotation_child_orders import sessions, context, update_payload
from annotation_models import AnnotationProject
from annotation_paired_models import PairedWorkspace, PairedContact, PairedGroup, PairedTask, PairedRecord, PairedAudit
from annotation_paired_schemas import ContactWrite, GroupWrite, TaskWrite, TransferWrite, RecordWrite, WorkspaceWrite, RecordData
from models import AppUser
from resource_models import ResourcePerson
import annotation_paired_service as service


@pytest.fixture
def setup(context):
    db, project_id, language_id = context
    sql = (Path(__file__).resolve().parents[1] / 'data/migrations/20261024_annotation_paired_workspace.sql').read_text(encoding='utf-8')
    db.execute(text(sql))
    db.execute(text(sql))
    db.commit()
    project = db.get(AnnotationProject, project_id)
    project.project_types = ['paired_collection_annotation']
    actor = AppUser(username='paired-'+uuid4().hex,password_hash='not-a-login-hash',full_name='采标验收员')
    people = [ResourcePerson(full_name='采标测试'+str(index), resource_code='PAIR-'+uuid4().hex[:12]) for index in range(4)]
    db.add_all([actor,*people]);db.commit()
    service.workspace(db, project_id, write=True, initialize=True);db.commit()
    for person in people:
        service.save_contact(db,project_id,ContactWrite(person_id=person.id,data={'sources':['来源一']}),actor)
    db.commit()
    yield db,project_id,actor,people


def group(setup, pair=(0,1), **changes):
    db,pid,actor,people=setup
    values=dict(request_key=uuid4(),name='分组1',person1_id=people[pair[0]].id,person2_id=people[pair[1]].id)
    values.update(changes)
    row=service.save_group(db,pid,GroupWrite(**values),actor)
    db.commit()
    return row


def task(setup, group_id):
    db,pid,actor,_=setup
    return db.query(PairedTask).filter_by(group_id=group_id,stage='collection').one()


def test_contact_dedup_does_not_reset_willingness(setup):
    db,pid,actor,people=setup
    row=db.query(PairedContact).filter_by(project_id=pid,person_id=people[0].id).one()
    service.save_contact(db,pid,ContactWrite(person_id=people[0].id,expected_revision=row.revision,willingness='available',data={'sources':['来源一'],'quote':'整组200元/有效小时'}),actor,row.id)
    service.save_contact(db,pid,ContactWrite(person_id=people[0].id,data={'sources':['来源二','来源一']}),actor)
    db.commit()
    assert row.willingness=='available'
    assert row.data['sources']==['来源一','来源二']
    assert row.data['quote']=='整组200元/有效小时'
    assert db.query(PairedContact).filter_by(project_id=pid).count()==4


def test_group_idempotency_and_default_batch(setup):
    db,pid,actor,people=setup
    key=uuid4()
    first=group(setup,request_key=key)
    second=group(setup,request_key=key)
    assert first['id']==second['id']
    assert db.query(PairedTask).filter_by(group_id=UUID(first['id'])).count()==1


from uuid import UUID


def test_same_member_and_duplicate_groups(setup):
    with pytest.raises(ValidationError):
        group(setup,pair=(0,0))
    group(setup)
    with pytest.raises(HTTPException,match='其他有效分组'):
        group(setup,pair=(0,2))
    setup[0].rollback()


def test_enable_multiple_groups_and_cannot_disable_with_conflicts(setup):
    db,pid,actor,_=setup
    group(setup)
    ws=db.get(PairedWorkspace,pid)
    service.save_workspace(db,pid,WorkspaceWrite(expected_revision=ws.revision,allow_multiple_groups=True),actor)
    db.commit()
    group(setup,pair=(0,2))
    with pytest.raises(HTTPException,match='不能关闭'):
        service.save_workspace(db,pid,WorkspaceWrite(expected_revision=ws.revision),actor)
    db.rollback()


def test_member_change_keeps_prior_batch_identity(setup):
    db,pid,actor,people=setup
    first=group(setup)
    old_task=task(setup,UUID(first['id']))
    old_members=old_task.members_id
    changed=service.save_group(db,pid,GroupWrite(request_key=first['request_key'],name='分组1',person1_id=people[0].id,person2_id=people[2].id,reason='原搭档退出',expected_revision=first['revision']),actor,UUID(first['id']))
    assert old_task.members_id==old_members
    assert old_task.person_ids==[str(people[0].id),str(people[1].id)]
    assert changed['members']['version']==2
    row=service.save_task(db,pid,TaskWrite(request_key=uuid4(),group_id=first['id'],name='新搭档批次'),actor)
    assert row['members_id']==changed['members']['id']
    assert row['person_ids']==[str(people[0].id),str(people[2].id)]


def test_transfer_other_people_parallel_idempotent(setup):
    db,pid,actor,people=setup
    first=group(setup)
    source=task(setup,UUID(first['id']))
    payload=TransferWrite(task_ids=[source.id],person_ids=[people[2].id])
    target=service.transfer(db,pid,payload,actor)[0]
    second=service.transfer(db,pid,payload,actor)[0]
    db.commit()
    assert target['id']==second['id']
    assert target['person_ids']==[str(people[2].id)]
    assert source.status=='pending'
    assert not db.query(PairedRecord).filter_by(task_id=source.id).first()


def test_record_insert_and_history_and_stable_ids(setup):
    db,pid,actor,people=setup
    first=group(setup); source=task(setup,UUID(first['id']))
    records=[]
    for index in range(2):
        records.append(service.save_record(db,pid,source.id,RecordWrite(request_key=uuid4(),kind='progress',title=f'节点{index+1}'),actor))
    db.commit()
    inserted=service.save_record(db,pid,source.id,RecordWrite(request_key=uuid4(),kind='progress',title='补采',insert_after_id=records[0]['id']),actor)
    db.commit()
    assert inserted['position']==2 and inserted['data']['inserted']
    old=db.get(PairedRecord,UUID(records[1]['id']))
    assert old.position==3 and old.data['postponed']
    assert db.query(PairedAudit).filter_by(entity_id=old.id,action='postpone').count()==1


def test_stale_revision_rejected(setup):
    db,pid,actor,people=setup
    row=db.query(PairedContact).filter_by(project_id=pid,person_id=people[0].id).one()
    with pytest.raises(HTTPException) as exc:
        service.save_contact(db,pid,ContactWrite(person_id=row.person_id,expected_revision=row.revision+1),actor,row.id)
    assert exc.value.status_code==409


def test_history_prevents_group_delete(setup):
    db,pid,actor,_=setup
    first=group(setup); source=task(setup,UUID(first['id']))
    service.save_record(db,pid,source.id,RecordWrite(request_key=uuid4(),kind='trial',title='允许直接开工'),actor)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        service.delete_entity(db,pid,'groups',UUID(first['id']),actor)
    assert exc.value.status_code==409


def test_unused_group_delete(setup):
    db,pid,actor,_=setup
    first=group(setup)
    service.delete_entity(db,pid,'groups',UUID(first['id']),actor)
    db.commit()
    assert db.get(PairedGroup,UUID(first['id'])) is None


def test_free_text_and_no_automatic_overall_score(setup):
    db,pid,actor,people=setup
    first=group(setup);source=task(setup,UUID(first['id']))
    saved=service.save_task(db,pid,TaskWrite(request_key=source.request_key,group_id=source.group_id,name=source.name,expected_revision=source.revision,status='in_progress',data={'price':'待协商/含奖励','workload':'约两段，自由填写'}),actor,source.id)
    assert saved['data']['price']=='待协商/含奖励'
    record=service.save_record(db,pid,source.id,RecordWrite(request_key=uuid4(),kind='performance',title='人员表现',data={'result':'配合良好'}),actor)
    db.commit()
    assert people[0].collection_score is None
    assert service.talent_records(db,[people[0].id],pid)[0]['id']==record['id']


def test_cross_order_access_and_transfer_rollback(setup,context):
    db,pid,actor,people=setup
    first=group(setup);source=task(setup,UUID(first['id']))
    with pytest.raises(HTTPException):
        service.scoped(db,PairedTask,uuid4(),source.id)
    with pytest.raises(HTTPException):
        service.transfer(db,pid,TransferWrite(task_ids=[source.id,uuid4()],person_ids=[people[2].id]),actor)
    db.rollback()
    assert db.query(PairedTask).filter_by(source_task_id=source.id).count()==0


def test_list_count_uses_same_filters(setup):
    db,pid,actor,people=setup
    row=db.query(PairedContact).filter_by(person_id=people[0].id,project_id=pid).one()
    service.save_contact(db,pid,ContactWrite(person_id=row.person_id,expected_revision=row.revision,willingness='available'),actor,row.id)
    db.commit()
    page=service.list_entities(db,pid,'contacts',keyword='测试0',statuses=['available'])
    assert page['total']==len(page['items'])==1


def test_record_time_timezone_and_validation():
    values=RecordData(actual_start='2026-10-24T01:00:00Z',actual_end='2026-10-24T10:00:00+08:00')
    assert values.model_dump(mode='json')['actual_start']=='2026-10-24T09:00:00+08:00'
    with pytest.raises(ValidationError):
        RecordData(actual_start='2026-10-24T10:00:00',actual_end='2026-10-24T09:00:00')
    with pytest.raises(ValidationError):
        RecordData(duration_adjustment_minutes=20)


def test_archived_workspace_rejects_writes(setup):
    db,pid,actor,people=setup
    ws=db.get(PairedWorkspace,pid)
    service.save_workspace(db,pid,WorkspaceWrite(expected_revision=ws.revision,archived=True),actor)
    db.commit()
    with pytest.raises(HTTPException):
        service.save_contact(db,pid,ContactWrite(person_id=people[0].id),actor)


def test_cancel_type_requires_archive(setup):
    db,pid,actor,_=setup
    import annotation_service
    project=annotation_service.get_annotation_project(db,pid)
    with pytest.raises(ValueError,match='归档'):
        annotation_service.update_annotation_project(db,pid,update_payload(project,project_types=['text_annotation']),actor.id)
    db.rollback()


def test_idempotency_key_cannot_replay_different_payload(setup):
    key=uuid4()
    group(setup,request_key=key)
    with pytest.raises(HTTPException) as exc:
        group(setup,pair=(2,3),request_key=key,name='不同内容')
    assert exc.value.status_code==409


def test_api_read_only_permissions_and_contact_privacy(setup,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.annotation_paired import router
    import routers.auth as auth
    db,pid,actor,people=setup
    people[0].primary_phone='13800001234';db.commit()
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:actor
    allowed={'projects:read','talents:read'}
    monkeypatch.setattr(auth,'user_has_permission',lambda db,user_id,permission:permission in allowed)
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda db,user_id:list(allowed))
    with TestClient(app) as client:
        base=f'/annotation-ops/projects/{pid}/paired-workspace'
        assert client.get(base).status_code==200
        assert client.post(base+'/initialize').status_code==403
        response=client.get(base+'/candidates').json()
        candidate=next(item for item in response['items'] if item['id']==str(people[0].id))
        assert candidate['phone']=='******' and candidate['contact_restricted']
        allowed.clear()
        assert client.get(base).status_code==403


def test_api_followup_uses_server_actor_and_attachments_scoped(setup,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.annotation_paired import router
    import routers.auth as auth
    db,pid,actor,people=setup
    row=db.query(PairedContact).filter_by(project_id=pid,person_id=people[0].id).one()
    other=db.query(PairedContact).filter_by(project_id=pid,person_id=people[1].id).one()
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:actor
    monkeypatch.setattr(auth,'user_has_permission',lambda *args:True)
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda *args:['*'])
    with TestClient(app) as client:
        base=f'/annotation-ops/projects/{pid}/paired-workspace'
        response=client.post(base+f'/contacts/{row.id}/follow-ups',json={'expected_revision':row.revision,'channel':'message','contact_date':'2026-10-24','content':'第一次留言追问'})
        assert response.status_code==200,response.text
        follow=response.json()['data']['follow_ups'][0]
        assert follow['actor_id']==str(actor.id) and follow['created_at'].endswith('+08:00')
        response=client.post(base+f'/contacts/{row.id}/attachments',files={'file':('测试.txt','验收附件'.encode(),'text/plain')})
        assert response.status_code==200,response.text
        attachment=response.json()['id']
        assert client.get(base+f'/contacts/{other.id}/attachments/{attachment}').status_code==404
        assert client.get(base+f'/contacts/{row.id}/attachments/{attachment}').content=='验收附件'.encode()


def test_concurrent_groups_same_people_only_one_succeeds(setup,sessions):
    from concurrent.futures import ThreadPoolExecutor
    db,pid,actor,people=setup
    actor_id=actor.id;ids=[item.id for item in people];db.commit()
    def create(index):
        with sessions() as concurrent:
            try:
                current_actor=concurrent.get(AppUser,actor_id)
                service.save_group(concurrent,pid,GroupWrite(request_key=uuid4(),name=f'并发组{index}',person1_id=ids[0],person2_id=ids[index+1]),current_actor)
                concurrent.commit();return True
            except HTTPException:
                concurrent.rollback();return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(create,[0,1]))
    assert sorted(results)==[False,True]


def test_external_annotator_keeps_foreign_key_after_reassignment(setup):
    from annotation_paired_models import PairedParticipant
    from sqlalchemy.exc import IntegrityError
    db,pid,actor,people=setup
    first=group(setup);source=task(setup,UUID(first['id']))
    target=service.transfer(db,pid,TransferWrite(task_ids=[source.id],person_ids=[people[2].id]),actor)[0]
    target_id=UUID(target['id'])
    assert db.get(PairedParticipant,(target_id,people[2].id)) is not None
    service.save_task(db,pid,TaskWrite(request_key=target['request_key'],group_id=source.group_id,name='换人后标注',person_ids=[people[3].id],expected_revision=target['revision']),actor,target_id)
    db.commit()
    assert not db.get(PairedParticipant,(target_id,people[2].id)).active
    # 即使移除联系表、且不是任何采集组员，旧标注人员仍有真实外键保护。
    db.query(PairedContact).filter_by(project_id=pid,person_id=people[2].id).delete();db.commit()
    from routers.annotation_paired import people as read_people
    assert str(people[2].id) in {row['id'] for row in read_people(pid,db)}
    assert any(item[0] == people[2].id for item in service.talent_participations(db,[people[2].id]))
    with pytest.raises(IntegrityError):
        db.query(ResourcePerson).filter_by(id=people[2].id).delete();db.flush()
    db.rollback()


def test_new_resource_counts_use_success_action_date_and_dedupe_channels(setup):
    from datetime import date
    from resource_development_models import DevelopmentOption, DevelopmentRecord, DevelopmentAction
    from routers.annotation_paired import candidates
    db,pid,actor,people=setup
    ws=db.get(PairedWorkspace,pid);ws.created_at=datetime.fromisoformat('2026-10-20T00:00:00+08:00')
    option=DevelopmentOption(kind='platform',name='测试平台'+uuid4().hex);db.add(option);db.flush()
    for index in range(2):
        row=DevelopmentRecord(greeting_no=uuid4().hex,platform_id=option.id,work_date=date(2026,10,19),owner_id=actor.id,full_name=people[index].full_name,person_id=people[index].id,created_by=actor.id,updated_by=actor.id)
        db.add(row);db.flush()
        if index==0:
            for channel in ['wechat','enterprise']:
                db.add(DevelopmentAction(record_id=row.id,channel=channel,status='已添加',action_date=date(2026,10,21),operator_id=actor.id,created_by=actor.id,updated_by=actor.id))
        else:
            db.add(DevelopmentAction(record_id=row.id,channel='wechat',status='已添加',action_date=date(2026,10,19),operator_id=actor.id,created_by=actor.id,updated_by=actor.id))
    db.commit()
    result=candidates(project_id=pid,keyword='',language_id=None,channel='',company_account='',only_new=False,added_date=date(2026,10,21),skip=0,limit=100,db=db,actor=actor)
    assert result['total']==1
    assert result['daily_new']==[{'date':'2026-10-21','count':1}]
    assert len(result['items'][0]['added_sources'])==2 and result['items'][0]['joined']


def test_candidates_batch_load_language_and_accent(setup):
    from sqlalchemy import event
    from interpretation_models import InterpretationLanguage
    from resource_models import ResourceLanguageSkill
    from routers.annotation_paired import candidates
    db, pid, actor, people = setup
    language_id = db.query(InterpretationLanguage.id).first()[0]
    for talent in people:
        db.add(ResourceLanguageSkill(person_id=talent.id, language_id=language_id,
                                     role='native', accent='演示口音'))
    db.commit()
    db.expire_all()
    statements = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    bind = db.get_bind()
    event.listen(bind, 'before_cursor_execute', capture)
    try:
        result = candidates(project_id=pid, keyword='', language_id=None, channel='',
                            company_account='', only_new=False, added_date=None,
                            skip=0, limit=100, db=db, actor=actor)
    finally:
        event.remove(bind, 'before_cursor_execute', capture)
    assert len(result['items']) >= len(people)
    assert all(item['language_skills'][0]['accent'] == '演示口音'
               for item in result['items'] if item['id'] in {str(person.id) for person in people})
    # 人数增加时仍只有一次语言明细查询，口音与语言名称一并加载。
    assert sum('FROM resource_language_skill' in sql for sql in statements) == 1


def test_stage_account_permission_cannot_be_bypassed(setup,monkeypatch):
    from routers.annotation_paired import check_account_permission
    import permission_service
    db,pid,actor,_=setup
    monkeypatch.setattr(permission_service,'user_has_permission',lambda *args:False)
    with pytest.raises(HTTPException) as exc:
        check_account_permission(db,actor,RecordWrite(request_key=uuid4(),kind='account',title='账号引用'))
    assert exc.value.status_code==403


def test_workspace_isolated_on_three_order_levels_and_copy(setup):
    import annotation_service
    from annotation_models import AnnotationArea
    from test_annotation_child_orders import item
    db,pid,actor,people=setup
    parent=annotation_service.get_annotation_project(db,pid)
    language_id=parent.language_items[0].source_language_id
    child=annotation_service.create_annotation_children(db,pid,[item(language_id,project_types=['paired_collection_annotation'])],actor.id,uuid4().hex)[0]
    area=AnnotationArea(label='采标片区'+uuid4().hex[:5],name_key=uuid4().hex);db.add(area);db.commit()
    leaf=annotation_service.create_annotation_children(db,child.id,[item(language_id,area_id=area.id,project_types=['paired_collection_annotation'])],actor.id,uuid4().hex)[0]
    assert db.get(PairedWorkspace,child.id) is None and db.get(PairedWorkspace,leaf.id) is None
    for project_id in [child.id,leaf.id]:
        service.workspace(db,project_id,write=True,initialize=True)
        service.save_contact(db,project_id,ContactWrite(person_id=people[0].id,willingness='declined'),actor)
    db.commit()
    assert service.list_entities(db,pid,'contacts')['total']==4
    assert service.list_entities(db,child.id,'contacts')['total']==1
    assert service.list_entities(db,leaf.id,'contacts')['total']==1


def test_new_talent_duplicate_choice_and_atomic_rollback(setup,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from database import get_db
    from routers.auth import get_current_user
    from routers.annotation_paired import router
    import routers.auth as auth
    import talent_privacy
    db,pid,actor,people=setup
    app=FastAPI();app.include_router(router)
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:actor
    monkeypatch.setattr(auth,'user_has_permission',lambda *args:True)
    monkeypatch.setattr(auth,'get_user_permission_codes',lambda *args:['*'])
    monkeypatch.setattr(talent_privacy,'can_view_talent_contacts',lambda *args:True)
    base=f'/annotation-ops/projects/{pid}/paired-workspace'
    phone='PAIR-'+uuid4().hex[:10]
    payload={'request_key':str(uuid4()),'referral_person_id':str(people[0].id),'talent':{'full_name':'自行带来搭档','primary_phone':phone,'capabilities':[{'capability_type':'annotation'}]}}
    with TestClient(app) as client:
        response=client.post(base+'/talents',json=payload)
        assert response.status_code==200,response.text
        saved=response.json()
        assert saved['contact']['data']['sources']==[people[0].full_name+'搭档']
        assert client.post(base+'/talents',json=payload).json()['person']['id']==saved['person']['id']
        payload['request_key']=str(uuid4());payload['talent']['full_name']='姓名明显不同的人'
        response=client.post(base+'/talents',json=payload)
        assert response.status_code==409,response.text
        assert response.json()['detail']['code']=='duplicate_talent'
        payload['talent']['allow_duplicate']=True
        assert client.post(base+'/talents',json=payload).status_code==200
        name='必须回滚'+uuid4().hex
        payload={'request_key':str(uuid4()),'talent':{'full_name':name}}
        def fail(*args,**kwargs):raise HTTPException(400,'模拟联系保存失败')
        monkeypatch.setattr(service,'save_contact',fail)
        assert client.post(base+'/talents',json=payload).status_code==400
        assert db.query(ResourcePerson).filter_by(full_name=name).count()==0


def test_language_accent_preserves_legacy_omission_and_rejects_stale(setup):
    import resource_service
    from resource_models import ResourceLanguageSkill
    from resource_schemas import ResourcePersonUpdate
    db,pid,actor,people=setup
    language_id=db.get(AnnotationProject,pid).language_items[0].source_language_id
    skill=ResourceLanguageSkill(person_id=people[0].id,language_id=language_id,role='native',priority=1,accent='当前口音')
    db.add(skill);db.commit()
    base={'id':skill.id,'language_id':language_id,'role':'native','priority':1}
    legacy=ResourcePersonUpdate(full_name=people[0].full_name,language_skills=[base])
    resource_service._sync_owned_collections(db,people[0],legacy)
    assert skill.accent=='当前口音'
    stale=ResourcePersonUpdate(full_name=people[0].full_name,language_skills=[{**base,'accent':'用户修改','expected_accent':'过时口音'}])
    with pytest.raises(ValueError,match='口音已被其他人修改'):
        resource_service._sync_owned_collections(db,people[0],stale)
    db.rollback()
