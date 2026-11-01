"""本人项目归集，仅使用隔离 SQLite。"""
from datetime import date
from uuid import uuid4
import pytest
from test_chat_participant_access import environment
from models import TranslationProject, Consultation
from interpretation_models import InterpretationProject
from annotation_models import AnnotationProject
from recruitment_models import RecruitmentProject
from workflow_models import ProjectWorkbenchResponsibility
from project_client_manager import ProjectClientManagerChange
from project_arrangement import ProjectArrangement
from my_project_tasks import search


def test_four_project_groups_follow_current_managers(environment):
    db, (owner, member, outsider) = environment
    for group, model in [('translation', TranslationProject), ('interpretation', InterpretationProject), ('annotation', AnnotationProject), ('recruitment', RecruitmentProject)]:
        project = model(id=uuid4(), order_no=group+'-01', project_name='BB-AA 项目')
        db.add(project)
        if group == 'translation':
            project.project_manager_id = member.id
        else:
            db.add(ProjectWorkbenchResponsibility(id=uuid4(), role_code='project_manager', assignee_id=member.id, **{group+'_project_id': project.id}))
        if group in ('annotation', 'recruitment'):
            project.client_manager_id = owner.id
        else:
            db.add(ProjectClientManagerChange(id=uuid4(), project_type=group, project_id=project.id, revision=1, new_manager_id=owner.id, reason='测试'))
        db.commit()
        assert search(db, owner, group)['total'] == 1
        assert search(db, member, group, 'aa bb')['total'] == 1
        assert search(db, outsider, group)['total'] == 0
        if group == 'translation':
            project.project_manager_id = outsider.id
        else:
            db.query(ProjectWorkbenchResponsibility).filter_by(assignee_id=member.id).update({'assignee_id': outsider.id})
        db.commit()
        assert search(db, member, group)['total'] == 0
        assert search(db, outsider, group)['total'] == 1


def test_consultation_customer_manager_and_latest_change(environment):
    db, (owner, member, outsider) = environment
    consultation = Consultation(id=uuid4(), consultation_code='C-01', customer_service_id=owner.id)
    project = TranslationProject(id=uuid4(), order_no='TP-01', consultation_id=consultation.id)
    db.add_all([consultation, project]); db.commit()
    assert search(db, owner, 'translation')['total'] == 1
    db.add(ProjectClientManagerChange(id=uuid4(), project_type='translation', project_id=project.id, revision=1, new_manager_id=member.id, reason='交接'))
    db.commit()
    assert search(db, owner, 'translation')['total'] == 0
    assert search(db, member, 'translation')['total'] == 1
    db.add(ProjectClientManagerChange(id=uuid4(), project_type='translation', project_id=project.id, revision=2, new_manager_id=None, reason='撤销'))
    db.commit()
    assert search(db, owner, 'translation')['total'] == 0
    assert search(db, member, 'translation')['total'] == 0


def test_assigned_translation_distinct_search_paging_and_isolation(environment):
    db, (owner, member, outsider) = environment
    for i in range(3):
        project = TranslationProject(id=uuid4(), order_no=f'TP-{i}', project_name='安排%项目')
        db.add(project)
        for n in range(2):
            db.add(ProjectArrangement(id=uuid4(), project_id=project.id, assignee_id=member.id, assigned_by=owner.id, content=f'任务{n}', work_date=date(2026, 11, 1)))
    db.commit()
    assert search(db, member, 'assigned_translation', '%', 1, 2)['total'] == 3
    assert len(search(db, member, 'assigned_translation', '%', 2, 2)['items']) == 1
    assert search(db, owner, 'assigned_translation')['total'] == 0
    assert search(db, outsider, 'assigned_translation')['total'] == 0
    assert search(db, member, 'translation')['total'] == 0
    with pytest.raises(Exception) as error:
        search(db, owner, 'invalid')
    assert error.value.status_code == 422
