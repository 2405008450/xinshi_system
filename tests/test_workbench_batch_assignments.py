"""隔离验证工作台列表批量查询，避免项目数量增长造成 N+1。"""
from uuid import uuid4
from sqlalchemy import event
from tests.test_chat_participant_access import environment
from interpretation_models import InterpretationProject
from workflow_models import ProjectWorkbenchResponsibility
import project_workbench_service as service


def test_management_and_task_roles_use_one_batch_and_preserve_scope(environment):
    db,(owner,member,outsider)=environment
    for i in range(25):
        project=InterpretationProject(id=uuid4(),order_no=f'IP-PERF-{i}',project_name='性能验证',project_status='in_progress')
        db.add(project);db.flush()
        for role,user in [('project_manager',owner),('project_specialist',member)]:
            db.add(ProjectWorkbenchResponsibility(id=uuid4(),interpretation_project_id=project.id,role_code=role,assignee_id=user.id))
    db.commit();queries=[]
    def count(connection,cursor,statement,*args):
        if statement.lstrip().upper().startswith('SELECT'):queries.append(statement)
    event.listen(db.bind,'before_cursor_execute',count)
    try:
        result=service.get_management_responsibilities(db,owner.id)
        assert len(result)==25
        assert len(queries)<12,len(queries)
        assert all(any(role['assignee_id']==member.id for role in row['role_assignments']) for row in result)
        queries.clear()
        tasks=service.get_responsibility_tasks(db,member.id,{'项目专员'})
        assert len(tasks)==25 and len(queries)<12
        assert service.get_management_responsibilities(db,outsider.id)==[]
    finally:event.remove(db.bind,'before_cursor_execute',count)
