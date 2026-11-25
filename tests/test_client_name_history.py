from uuid import uuid4
import pytest
from models import Client, SubClient
from schemas import ClientUpdate
from tests.test_chat_participant_access import environment
from client_name_history import ClientNameHistory, read_history
from tools.apply_client_name_history_migration import apply_migration
import crud


def test_name_change_noop_delete_and_actor_snapshot(environment):
    db, users = environment
    apply_migration(db.connection())
    apply_migration(db.connection())
    client = Client(id=uuid4(), client_code='HISTORY', client_name='旧全称', client_short_name='旧简称')
    db.add(client)
    db.commit()
    from chat_time import api_time
    updated = crud.update_client(db, client.id, ClientUpdate(
        client_name='新全称', expected_updated_at=api_time(client.updated_at)), actor_id=users[0].id)
    crud.update_client(db, client.id, ClientUpdate(
        client_name='新全称', expected_updated_at=api_time(updated.updated_at)), actor_id=users[0].id)
    assert db.query(ClientNameHistory).count() == 1
    crud.delete_client(db, client.id, actor_id=users[0].id)
    result = read_history(client_id=client.id, keyword='', page=1, page_size=10, db=db, user=users[0])
    assert result['total'] == 2
    delete, rename = result['items']
    assert delete['operation'] == 'delete' and delete['before']['client_name'] == '新全称'
    assert rename['before']['client_name'] == '旧全称' and rename['after']['client_name'] == '新全称'
    assert rename['actor_name'] == (users[0].full_name or users[0].username)
    assert rename['occurred_at'].endswith('+08:00')
    assert read_history(keyword='旧全称 HISTORY', page=1, page_size=10, db=db, user=users[0])['total'] == 1


def test_delete_parent_keeps_child_names(environment):
    db, users = environment
    apply_migration(db.connection())
    client = Client(id=uuid4(), client_code='PARENT', client_name='母客户')
    db.add(client)
    db.flush()
    child = SubClient(id=uuid4(), parent_client_id=client.id, sub_client_code='CHILD', client_name='子客户')
    db.add(child)
    db.commit()
    crud.delete_client(db, client.id, actor_id=users[0].id)
    result = read_history(client_id=client.id, keyword='', page=1, page_size=10, db=db, user=users[0])
    assert result['total'] == 2
    assert {row['client_code'] for row in result['items']} == {'PARENT', 'CHILD'}
