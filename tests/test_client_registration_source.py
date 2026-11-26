from uuid import uuid4
import pytest
from models import Client
from tests.test_chat_participant_access import environment
from tools.apply_client_registration_source_migration import apply_migration
from client_registration_source import attach, LABELS
import crud


@pytest.fixture(autouse=True)
def sqlite_client_uuid():
    from sqlalchemy import event
    def assign_id(mapper, connection, target):
        if target.id is None:
            target.id = uuid4()
    event.listen(Client, 'before_insert', assign_id)
    yield
    event.remove(Client, 'before_insert', assign_id)


@pytest.mark.parametrize('module', list(LABELS))
def test_registration_is_first_creation_and_reused_client_keeps_source(environment, module):
    db, _ = environment
    apply_migration(db.connection())
    apply_migration(db.connection())
    if module in {'translation','interpretation','annotation','recruitment'}:
        with pytest.raises(ValueError, match='请在 新咨询管理/客户管理 先输入客户名称'):
            crud._resolve_or_create_project_client(db, '来源测试', None, '来源测试全称', registration_source=module)
        assert db.query(Client).count()==0
        return
    client_id, _, created = crud._resolve_or_create_project_client(
        db, '来源测试', None, '来源测试全称', registration_source=module)
    db.commit()
    assert created
    reused_id, _, created = crud._resolve_or_create_project_client(
        db, '来源测试', None, '来源测试全称', registration_source='translation')
    assert not created and reused_id == client_id
    assert crud.get_client(db, client_id).registration_source == LABELS[module]
    assert crud.get_clients(db)[0].registration_source == LABELS[module]


def test_historical_source_is_not_inferred(environment):
    db, _ = environment
    client = Client(id=uuid4(), client_code='LEGACY-SOURCE', client_name='历史客户')
    db.add(client)
    db.commit()
    attach(db, [client])
    assert client.registration_source == '历史数据（未记录）'
