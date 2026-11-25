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
