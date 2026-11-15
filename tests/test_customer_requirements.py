from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect

from models import Client, TranslationProject
from tests.test_chat_participant_access import environment


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
