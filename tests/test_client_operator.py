"""客户操作人及历史回溯隔离回归，不连接业务数据库。"""
from uuid import uuid4

from sqlalchemy import event
from tests.test_chat_participant_access import environment
from client_operator import ClientOperator
from models import Client, Consultation
from schemas import ClientCreate, ClientUpdate, ClientResponse, ConsultationCreate
from tools.backfill_client_operators import classify


def test_backfill_rejects_ambiguity_conflict_missing_user_and_existing():
    uid = uuid4()
    def row(**kwargs):
        return dict(client_id=uuid4(), editor_id=uid, username='user', full_name='用户', capture_owner_id=None, **kwargs)
    good = row()
    conflict = row(); conflict['capture_owner_id'] = str(uuid4())
    missing = row(); missing['username'] = None
    duplicate = row()
    existing = row()
    captured = row(); captured['capture_owner_id'] = str(uid)
    accepted, skipped = classify([good, conflict, missing, duplicate, duplicate, existing, captured], [existing['client_id']])
    assert [r['source'] for r in accepted] == ['consultation_editor_backfill', 'consultation_capture_backfill']
    assert len(skipped) == 4


def test_customer_create_cannot_spoof_and_edit_preserves_operator(environment):
    import crud
    db, users = environment
    def ids(session, *_):
        for row in session.new:
            if isinstance(row, Client) and row.id is None:
                row.id = uuid4()
    event.listen(db, 'before_flush', ids)
    payload = ClientCreate(client_code='CL-OP', client_name='客户', client_short_name='客户', operator_name='伪造人')
    row = crud.create_client(db, payload, actor=users[0])
    assert ClientResponse.model_validate(row).operator_name == users[0].full_name
    updated = crud.update_client(db, row.id, ClientUpdate(remarks='修改资料', operator_name='伪造人'))
    assert updated.operator_name == users[0].full_name
    assert updated.operator_source == 'client_create'
    assert next(item for item in crud.get_clients(db) if item.id == row.id).operator_name == users[0].full_name
    db.delete(db.get(ClientOperator, row.id)); db.flush()
    assert crud.get_client(db, row.id).operator_name is None


def test_consultation_new_client_uses_login_actor_not_selectable_editor(environment):
    import crud
    db, users = environment
    def ids(session, *_):
        for row in session.new:
            if isinstance(row, (Client, Consultation)) and row.id is None:
                row.id = uuid4()
    event.listen(db, 'before_flush', ids)
    row = crud.create_consultation(db, ConsultationCreate(
        client_short_name='咨询新客户', consultation_type='笔译项目', editor_id=users[1].id,
    ), actor=users[0])
    entry = db.get(ClientOperator, row.client_id)
    assert entry.operator_user_id == users[0].id
    assert entry.consultation_id == row.id
    assert entry.consultation_code == row.consultation_code
    crud.create_consultation(db, ConsultationCreate(
        client_id=row.client_id, consultation_type='笔译项目', editor_id=users[1].id,
    ), actor=users[1])
    assert db.get(ClientOperator, row.client_id).operator_user_id == users[0].id
