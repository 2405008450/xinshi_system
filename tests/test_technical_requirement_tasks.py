from uuid import uuid4
import pytest
from fastapi import HTTPException
from test_technical_development import environment, setup
import technical_development as tasks
import technical_requirement_tasks as source


@pytest.fixture
def context(setup):
    from annotation_models import AnnotationProject
    from technical_requirement_models import TechnicalRoom
    from chat_session_category_models import ChatSessionCategory
    from discussion_chat_models import DiscussionMember
    db, users = setup
    actor = users[0]
    project = AnnotationProject(id=uuid4(), order_no='AP-REQ-001', project_name='原始项目名称', created_by=actor.id)
    room_id = uuid4()
    db.add_all([project, ChatSessionCategory(id=room_id,name='技术需求',updated_by=actor.id)])
    db.flush()
    room = TechnicalRoom(project_id=project.id,room_id=room_id,requirements='原始技术需求汇总',revision=1,created_by=actor.id,updated_by=actor.id)
    db.add_all([room, DiscussionMember(room_id=room_id,user_id=actor.id)])
    db.commit()
    return db, users, room


def payload(actor, **extra):
    return source.SourceWrite(**(dict(source_revision=1,arranger_id=actor.id,executor_id=actor.id,content='复制的技术汇总',suffix='少量补充') | extra))


def test_context_does_not_create_and_saved_task_is_unique_and_name_protected(context):
    db, (actor, _, _), room = context
    value=source.context(db,actor,room.room_id)
    assert value['task_id'] is None and value['source_name']=='原始项目名称'
    assert value['requirements']=='原始技术需求汇总' and value['default_executor_id']==actor.id
    assert db.query(tasks.DevelopmentTask).count()==0
    saved=source.save(db,actor,room.room_id,payload(actor))
    assert saved['name']=='原始项目名称 · 少量补充' and saved['content']=='复制的技术汇总'
    assert saved['task_no'].startswith('DT-') and saved['source']['base_name']=='原始项目名称'
    assert source.context(db,actor,room.room_id)['task_id']==saved['id']
    with pytest.raises(HTTPException):source.save(db,actor,room.room_id,payload(actor))
    assert db.query(tasks.DevelopmentTask).count()==1
    edited=source.save(db,actor,room.room_id,payload(actor,task_revision=1,suffix='补充更新'))
    assert edited['id']==saved['id'] and edited['task_no']==saved['task_no'] and edited['revision']==2
    fields=dict(name='任意改名',content='编辑',arranger_id=actor.id,executor_id=actor.id,revision=2)
    with pytest.raises(HTTPException) as rejected:tasks.update_task(db,actor,saved['id'],tasks.TaskUpdate(**fields))
    assert rejected.value.status_code==422
    fields['name']='原始项目名称 · 表单补充'
    result=tasks.update_task(db,actor,saved['id'],tasks.TaskUpdate(**fields))
    assert result['source']['suffix']=='表单补充'


def test_room_membership_department_and_stale_summary_revision(context):
    db,(actor,nonmember,outsider),room=context
    with pytest.raises(HTTPException):source.context(db,nonmember,room.room_id)
    with pytest.raises(HTTPException):source.context(db,outsider,room.room_id)
    room.requirements='新汇总';room.revision=2;db.commit()
    with pytest.raises(HTTPException) as stale:source.save(db,actor,room.room_id,payload(actor))
    assert stale.value.status_code==409 and db.query(tasks.DevelopmentTask).count()==0
    saved=source.save(db,actor,room.room_id,payload(actor,source_revision=2,executor_id=nonmember.id))
    assert saved['executor_id']==nonmember.id


def test_source_migration_create_only(context):
    db,(actor,_,_),room=context
    from tools.apply_technical_requirement_task_migration import apply_migration
    source.RequirementTaskLink.__table__.drop(db.connection());db.commit()
    apply_migration(db.connection());apply_migration(db.connection());db.commit()
    assert source.context(db,actor,room.room_id)['task_id'] is None
    assert room.requirements=='原始技术需求汇总'


def test_requirement_handoff_supports_multiple_executors(context):
    db,(actor,other,_),room=context
    saved=source.save(db,actor,room.room_id,payload(actor,allocations=[dict(executor_id=actor.id,content='后端分工'),dict(executor_id=other.id,content='前端分工')]))
    assert saved['has_allocations'] and saved['executor_ids']==[actor.id,other.id]
    assert [item['content'] for item in saved['allocations']]==['后端分工','前端分工']
    assert source.context(db,actor,room.room_id)['task']['has_allocations']
