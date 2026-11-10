"""新咨询多联系人同步：仅内存 SQLite，不连接业务数据库。"""
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import event

from test_chat_participant_access import environment


@pytest.fixture
def contact_data(environment, monkeypatch):
    import crud
    from models import Client, SubClient
    db, _ = environment
    def ids(session, *_):
        for row in session.new:
            if hasattr(row, 'id') and row.id is None: row.id = uuid4()
    event.listen(db, 'before_flush', ids)
    monkeypatch.setattr(crud, 'generate_consultation_code', lambda db: 'ZX-' + uuid4().hex[:10])
    client = Client(id=uuid4(), client_code='CONTACT-QA', client_name='联系人客户', client_short_name='联系人', updated_at=datetime(2026, 11, 7, 12))
    other = Client(id=uuid4(), client_code='OTHER-QA', client_name='另一个客户', client_short_name='其他')
    sub = SubClient(id=uuid4(), parent_client_id=client.id, sub_client_code='SUB-QA', client_name='子客户', client_short_name='子客户')
    db.add_all([client, other, sub]); db.commit()
    return db, client, other, sub


def person(name, method, description=''):
    from schemas import ClientContactPersonInput
    return ClientContactPersonInput(name=name, contact_method=method, description=description)


@pytest.mark.parametrize('contacts_visible', [True, False])
def test_new_contact_with_production_autoflush_disabled(contact_data, contacts_visible):
    import crud
    from schemas import ConsultationCreate
    from client_contact_people import ClientContactPersonDetail, owner_rows
    db, client, _, _ = contact_data
    db.autoflush = False
    db.info['client_contacts_visible'] = contacts_visible
    client.manager_contact = '原有联系方式'
    db.flush()
    row = crud.create_consultation(db, ConsultationCreate(
        client_id=client.id, contact_people=[person('新增联系人', '新联系方式', '采购')],
    ))
    assert row.id is not None
    contact = owner_rows(db, client)[0]
    detail = db.get(ClientContactPersonDetail, contact.id)
    assert detail.description == '采购'
    assert detail.contact_method == ('新联系方式' if contacts_visible else '')
    assert client.manager_contact == ('新联系方式' if contacts_visible else '原有联系方式')


def test_create_and_edit_sync_contacts_without_deleting_other_people(contact_data):
    import crud
    from schemas import ConsultationCreate, ConsultationUpdate
    db, client, other, _ = contact_data
    row = crud.create_consultation(db, ConsultationCreate(client_id=client.id, contact_people=[person('张先生', '13800000000'), person('李女士', 'li@example.test', '采购')]))
    assert row.contact_name is None  # 业务项目联系人由表单单独传入，不强行覆盖旧字段。
    assert [item['name'] for item in row.contact_people] == ['张先生', '李女士']
    assert crud.get_client(db, client.id).contact_people[1]['description'] == '采购'
    assert crud.get_client(db, other.id).contact_people == []
    version = row.contact_people_updated_at
    changed = crud.update_consultation(db, row.id, ConsultationUpdate(contact_people=[person('李女士', 'new@example.test', '业务联系人'), person('王先生', '13900000000')], contact_people_updated_at=version))
    assert [item['name'] for item in changed.contact_people] == ['张先生', '李女士', '王先生']
    assert changed.contact_people[1]['contact_method'] == 'new@example.test'
    assert crud.get_client(db, client.id).manager_contact == '13800000000'
    crud.update_consultation(db, row.id, ConsultationUpdate(status='emphasis'))
    assert len(crud.get_client(db, client.id).contact_people) == 3


def test_subcustomer_isolation_conflict_and_duplicate_rejection(contact_data):
    import crud
    from schemas import ConsultationCreate, ConsultationUpdate
    from client_contact_people import replace_details
    from concurrency import StaleUpdateError
    db, client, other, sub = contact_data
    row = crud.create_consultation(db, ConsultationCreate(client_id=client.id, sub_client_id=sub.id, contact_people=[person('子客户联系人', '子客户电话')]))
    version = row.contact_people_updated_at
    assert crud.get_client(db, client.id).contact_people == []
    assert row.contact_people[0]['contact_method'] == '子客户电话'
    replace_details(db, sub, [person('子客户联系人', '客户管理更新的电话')]); db.commit()
    with pytest.raises(StaleUpdateError):
        crud.update_consultation(db, row.id, ConsultationUpdate(contact_people=[person('子客户联系人', '旧表单的新电话')], contact_people_updated_at=version))
    db.rollback()
    with pytest.raises(ValueError):
        crud.create_consultation(db, ConsultationCreate(client_id=other.id, sub_client_id=sub.id, contact_people=[person('姓名', '电话')]))
    db.rollback()
    with pytest.raises(ValueError):
        crud.create_consultation(db, ConsultationCreate(client_id=client.id, contact_people=[person('Alice', 'A'), person('alice', 'B')]))
    db.rollback()
    assert crud.get_sub_client(db, sub.id).contact_people[0]['contact_method'] == '客户管理更新的电话'


def test_new_client_created_by_consultation_keeps_all_contacts(contact_data, monkeypatch):
    import crud
    from models import Client
    from schemas import ConsultationCreate
    db, _, _, _ = contact_data
    def resolve(db, short_name, code, full_name, *, is_consultation=False):
        assert is_consultation is True
        client = Client(id=uuid4(), client_code='AUTO-QA', client_short_name=short_name, client_name=full_name)
        db.add(client); db.flush()
        return client.id, None, True
    monkeypatch.setattr(crud, '_resolve_or_create_project_client', resolve)
    row = crud.create_consultation(db, ConsultationCreate(client_short_name='新客户', client_name='新客户全称', contact_people=[person('第一位', '电话1'), person('第二位', '电话2'), person('第三位', '电话3')]))
    assert len(crud.get_client(db, row.client_id).contact_people) == 3
    assert row.manager_contact == '电话1'
