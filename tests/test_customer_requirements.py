from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect

from models import Client, TranslationProject
from tests.test_chat_participant_access import environment


@pytest.mark.parametrize('module', ['translation', 'interpretation', 'annotation', 'recruitment'])
def test_project_requirements_read_live_linked_content_only(environment, module):
    import customer_requirements as requirements
    from models import SubClient
    db, _ = environment
    client = Client(id=uuid4(), client_code='PROJECT-REQ', client_name='要求客户')
    db.add(client)
    db.flush()
    sub = SubClient(id=uuid4(), parent_client_id=client.id, sub_client_code='REQ-SUB')
    db.add(sub)
    db.flush()
    model = requirements.MODELS[module]
    field, column = next(iter(requirements.PROJECT_FIELDS[module].items()))
    project = model(id=uuid4(), sub_client_id=sub.id, order_no='REQ-02', project_name='已填要求',
                    **{column: ' 项目原要求 '})
    empty = model(id=uuid4(), client_id=client.id, order_no='REQ-01', project_name='空白项目',
                  **{column: ' \n\t '})
    foreign = model(id=uuid4(), order_no='REQ-03', project_name='其他客户', **{column: '无关要求'})
    db.add_all([project, empty, foreign])
    db.commit()
    result = requirements.read_project_requirements(client.id, module, page=1, page_size=10, db=db)
    assert result['total'] == 1
    assert result['items'][0]['values'] == {field: '项目原要求'}
    setattr(project, column, '项目更新要求')
    db.commit()
    result = requirements.read_project_requirements(client.id, module, page=1, page_size=10, db=db)
    assert result['items'][0]['values'][field] == '项目更新要求'
    assert requirements.read_project_requirements(client.id, module, page=2, page_size=1, db=db)['items'] == []


def test_history_ignores_unchanged_appends_edits_and_returns_latest(environment, monkeypatch):
    import customer_requirements as requirements
    from tools.apply_customer_requirement_history_migration import apply_migration

    db, users = environment
    client = Client(id=uuid4(), client_code='CL-REQ', client_name='要求测试', client_short_name='要求测试')
    project = TranslationProject(id=uuid4(), client_id=client.id, order_no='TP-REQ', project_name='要求测试')
    db.add_all([client, project])
    db.commit()
    initial_tables = set(inspect(db.connection()).get_table_names())
    requirements.CustomerRequirement.__table__.drop(db.connection())
    apply_migration(db.connection())
    apply_migration(db.connection())
    assert set(inspect(db.connection()).get_table_names()) == initial_tables
    monkeypatch.setattr(requirements, 'user_has_permission', lambda *args: True)

    field = 'customerRequirementProfessional'

    def append(text, project_id=None):
        draft = requirements.RequirementUpdate(values={field: text}, project_id=project_id)
        return requirements.append_requirements(client.id, 'translation', draft, db, users[0])['added']

    assert append('使用客户术语表') == 1
    assert append(' 使用客户术语表 ', project.id) == 0
    assert append('使用新版术语表', project.id) == 1
    assert append(' ') == 0
    with pytest.raises(HTTPException) as error:
        append('其他项目', uuid4())
    assert error.value.status_code == 422

    latest = requirements.read_requirements(client.id, 'translation', True, db, users[0])
    assert latest == {'values': {field: '使用新版术语表'}}
    entries = requirements.read_requirements(client.id, 'translation', False, db, users[0])['items']
    assert [entry['content'] for entry in entries] == ['使用新版术语表', '使用客户术语表']
    assert entries[0]['source_order_no'] == 'TP-REQ'
    assert entries[0]['added_at'].endswith('+08:00')
    assert requirements.read_requirements(client.id, 'annotation', True, db, users[0]) == {'values': {}}


def test_interpretation_import_and_project_sync_exclude_task_description(environment, monkeypatch):
    import customer_requirements as requirements
    from interpretation_models import InterpretationProject
    db, users = environment
    client = Client(id=uuid4(), client_code='ORAL-REQ', client_name='口译要求客户')
    project = InterpretationProject(id=uuid4(), client_id=client.id, order_no='IP-REQ',
        project_name='口译项目', task_description='项目自己的具体任务',
        interpreter_special_requirements='项目要求', remarks='项目补充')
    task_only = InterpretationProject(id=uuid4(), client_id=client.id, order_no='IP-TASK', task_description='只有任务')
    db.add_all([client, project, task_only]); db.commit()
    monkeypatch.setattr(requirements, 'user_has_permission', lambda *args: True)
    # 客户档案的既有记录继续保留，但最新带入结果不返回具体任务。
    requirements.append_requirements(client.id, 'interpretation', requirements.RequirementUpdate(values={
        'taskDescription':'客户历史任务', 'interpreterSpecialRequirements':'客户要求', 'remarks':'客户补充',
    }), db, users[0])
    latest = requirements.read_requirements(client.id, 'interpretation', True, db, users[0])
    assert latest['values'] == {'interpreterSpecialRequirements':'客户要求', 'remarks':'客户补充'}
    result = requirements.append_requirements(client.id, 'interpretation', requirements.RequirementUpdate(
        project_id=project.id, values={'taskDescription':'旧窗口尝试回传的任务',
            'interpreterSpecialRequirements':'新的客户要求', 'remarks':'新的补充说明'}), db, users[0])
    assert result['added'] == 2
    tasks = requirements.entries_query(db, client.id, 'interpretation').filter_by(field='taskDescription').all()
    assert [row.content for row in tasks] == ['客户历史任务']
    assert project.task_description == '项目自己的具体任务'
    linked = requirements.read_project_requirements(client.id, 'interpretation', page=1, page_size=10, db=db)
    assert linked['total'] == 1
    assert linked['items'][0]['values'] == {'interpreterSpecialRequirements':'项目要求', 'remarks':'项目补充'}


@pytest.mark.parametrize('module', ['translation', 'interpretation', 'annotation', 'recruitment'])
def test_project_sync_and_import_use_same_module_general_requirements(environment, monkeypatch, module):
    import customer_requirements as requirements
    db, users = environment
    client = Client(id=uuid4(), client_code='GENERAL-' + module, client_name='通用要求客户')
    model = requirements.MODELS[module]
    project = model(id=uuid4(), client_id=client.id, order_no='REQ-' + module)
    db.add_all([client, project]); db.commit()
    monkeypatch.setattr(requirements, 'user_has_permission', lambda *args: True)
    field = next(iter(requirements.PROJECT_FIELDS[module]))
    requirements.append_requirements(client.id, module, requirements.RequirementUpdate(
        values={field: '客户通用内容'}), db, users[0])
    assert requirements.read_requirements(client.id, module, True, db, users[0])['values'] == {field: '客户通用内容'}
    values = {field: '项目同步内容'}
    excluded = {'interpretation':'taskDescription', 'annotation':'taskDescription', 'recruitment':'jobDescription'}.get(module)
    if excluded:
        values[excluded] = '不可同步的任务'
    assert requirements.append_requirements(client.id, module, requirements.RequirementUpdate(
        project_id=project.id, values=values), db, users[0])['added'] == 1
    assert requirements.read_requirements(client.id, module, True, db, users[0])['values'] == {field: '项目同步内容'}
    history = requirements.read_requirements(client.id, module, False, db, users[0])['items']
    assert len(history) == 2
    assert history[0]['source_order_no'] == project.order_no
    for other in requirements.MODELS.keys() - {module}:
        assert requirements.read_requirements(client.id, other, True, db, users[0]) == {'values': {}}
