"""本人标注项目自动进入今日任务；只使用隔离 SQLite。"""
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_chat_participant_access import environment
from annotation_models import AnnotationProject
from annotation_today_tasks import EXCLUDED_STATUSES, managed_projects
from workflow_models import ProjectWorkbenchResponsibility


def project(db, creator, manager, status='trial_preparation', role='project_manager'):
    row = AnnotationProject(id=uuid4(), order_no=f'AP-{uuid4().hex[:12]}',
                            project_name='标注项目', task_description='收集和检查样本',
                            created_by=creator.id, client_manager_id=creator.id,
                            project_status=status)
    db.add(row)
    db.add(ProjectWorkbenchResponsibility(id=uuid4(), annotation_project_id=row.id,
                                          role_code=role, assignee_id=manager.id))
    db.commit()
    return row


@pytest.mark.parametrize('status', sorted(EXCLUDED_STATUSES))
def test_excluded_statuses(environment, status):
    db, (owner, member, _) = environment
    project(db, owner, member, status)
    assert managed_projects(db, member) == {'items': [], 'total': 0}


@pytest.mark.parametrize('status', ['initial_consultation', 'resource_sourcing',
    'trial_preparation', 'trial_in_progress', 'trial_submitted', 'trial_passed',
    'trial_failed', 'trial_partially_passed', 'project_in_progress',
    'client_feedback', 'partially_cancelled'])
def test_remaining_statuses_are_included(environment, status):
    db, (owner, member, _) = environment
    row = project(db, owner, member, status)
    data = managed_projects(db, member)
    assert data['total'] == 1
    assert data['items'][0]['id'] == str(row.id)
    assert data['items'][0]['projectStatus'] == status


def test_only_project_manager_and_live_changes(environment):
    db, (owner, member, outsider) = environment
    row = project(db, owner, member)
    project(db, owner, member, role='project_assistant')
    project(db, owner, outsider)
    # 客户经理、创建人并不自动获得任务。
    assert managed_projects(db, owner)['total'] == 0
    assert managed_projects(db, member)['total'] == 1
    row.project_status = 'paused'
    db.commit()
    assert managed_projects(db, member)['total'] == 0
    row.project_status = 'project_in_progress'
    manager = db.query(ProjectWorkbenchResponsibility).filter_by(annotation_project_id=row.id).one()
    manager.assignee_id = outsider.id
    db.commit()
    assert managed_projects(db, member)['total'] == 0
    assert managed_projects(db, outsider)['total'] == 2


def test_multiple_managers_duplicates_and_pagination(environment):
    db, (owner, member, outsider) = environment
    row = project(db, owner, member)
    for person in (member, outsider):
        db.add(ProjectWorkbenchResponsibility(id=uuid4(), annotation_project_id=row.id,
                                              role_code='project_manager', assignee_id=person.id))
    project(db, owner, member)
    assert managed_projects(db, member)['total'] == 2
    first = managed_projects(db, member, 1, 1)
    second = managed_projects(db, member, 2, 1)
    assert len(first['items']) == len(second['items']) == 1
    assert first['items'][0]['id'] != second['items'][0]['id']
    assert managed_projects(db, outsider)['total'] == 1


def test_endpoint_uses_authenticated_user_and_validates_page(environment):
    from database import get_db
    from routers.auth import get_current_user
    from routers.project_arrangements import router
    db, (owner, member, outsider) = environment
    own = project(db, owner, member)
    project(db, owner, outsider)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: member
    with TestClient(app) as client:
        response = client.get('/project-arrangements/annotation-managed', params={'person_id': str(outsider.id)})
        assert response.status_code == 200
        assert [item['id'] for item in response.json()['items']] == [str(own.id)]
        assert client.get('/project-arrangements/annotation-managed?page=0').status_code == 422
        assert client.get('/project-arrangements/annotation-managed?page_size=101').status_code == 422
