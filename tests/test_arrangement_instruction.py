from uuid import uuid4
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from test_chat_participant_access import environment
from test_project_arrangement import create
import project_arrangement as service
import project_arrangement_history as history
import project_arrangement_instruction as instructions

def test_instruction_shared_by_all_assignees_updated_and_audited(environment):
    db,(owner,member,other)=environment
    project,first=create(db,owner,member)
    second=service.create_assignments(db,owner,project.id,service.AssignmentBatch(items=[{'assignee_id':other.id,'content':'检查版式','work_date':'2026-10-25'}],common_instruction='统一使用客户术语表\n回稿前检查文件',instruction_revision=0))[0]
    assert second['common_instruction']=='统一使用客户术语表\n回稿前检查文件'
    assert service.serialize(db,db.get(service.ProjectArrangement,first['id']))['common_instruction']==second['common_instruction']
    result=history.detail(db,project.id)
    assert result['instruction_revision']==1
    assert result['history'][0]['before_snapshot']['common_instruction']==''
    assert result['history'][0]['after_snapshot']['common_instruction']==second['common_instruction']
    saved=instructions.save(db,owner,project.id,instructions.InstructionWrite(content='改用最新术语表',revision=1))
    assert saved['instruction_revision']==2 and saved['history'][0]['operation']=='instruction'
    assert saved['history'][0]['before_snapshot']['common_instruction']==second['common_instruction']
    assert all(row['common_instruction']=='改用最新术语表' for row in saved['tasks'])
    assert [row['content'] for row in saved['tasks']]==['核对稿件','检查版式']
    with pytest.raises(HTTPException) as error:instructions.save(db,owner,project.id,instructions.InstructionWrite(content='旧窗口覆盖',revision=1))
    assert error.value.status_code==409
    db.rollback()
    assert instructions.read(db,project.id)['common_instruction']=='改用最新术语表'

def test_batch_conflict_rolls_back_personal_tasks_and_missing_table_is_readable(environment):
    db,(owner,member,_)=environment
    project,first=create(db,owner,member)
    instructions.save(db,owner,project.id,instructions.InstructionWrite(content='说明一',revision=0))
    count=db.query(service.ProjectArrangement).count()
    with pytest.raises(HTTPException):service.create_assignments(db,owner,project.id,service.AssignmentBatch(items=[{'assignee_id':member.id,'content':'新增任务','work_date':'2026-10-25'}],common_instruction='旧说明',instruction_revision=0))
    db.rollback()
    assert db.query(service.ProjectArrangement).count()==count
    assert instructions.read(db,project.id)['common_instruction']=='说明一'
    instructions.ArrangementInstruction.__table__.drop(db.connection());db.commit()
    assert service.serialize(db,db.get(service.ProjectArrangement,first['id']))['common_instruction']==''
    from tools.apply_arrangement_instruction_migration import apply_migration
    apply_migration(db.connection());apply_migration(db.connection())
    assert instructions.ready(db)

def test_assignee_can_read_common_instruction_but_cannot_write_it(environment):
    from routers.project_arrangements import router
    from routers.auth import get_current_user
    from database import get_db
    db,(owner,member,_)=environment
    project,_=create(db,owner,member)
    instructions.save(db,owner,project.id,instructions.InstructionWrite(content='仅限任务说明，不含他人任务细节',revision=0))
    app=FastAPI();app.include_router(router);app.dependency_overrides[get_db]=lambda:db;app.dependency_overrides[get_current_user]=lambda:member
    with TestClient(app) as client:
        response=client.get('/project-arrangements?day=2026-10-25').json()
        assert response['items'][0]['common_instruction']=='仅限任务说明，不含他人任务细节'
        assert client.put(f'/project-arrangements/project/{project.id}/instruction',json={'content':'非法修改','revision':1}).status_code==403
