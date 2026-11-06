from tests.test_statement_reorganization import register
from tests.test_customer_statement_workspace import setup
from tests.test_customer_statements import context
from tests.test_chat_participant_access import environment
import statement_access as access


def test_batch_cartesian_grants_are_atomic_audited_and_manager_only(setup):
    http,db,clients,_,actor=register(setup)
    people=db.query(access.AppUser).filter(access.AppUser.id!=actor.id).all()
    expected=[dict(user_id=str(user.id),client_id=str(client.id),revision=0) for user in people for client in clients]
    payload=dict(user_ids=[str(user.id) for user in people],client_ids=[str(client.id) for client in clients],expected=expected,edit_content=True,cross_client=True)
    assert http.put('/statement-access/grants/batch',json=payload).status_code==403
    actor.username='williamzhao';db.commit()
    response=http.put('/statement-access/grants/batch',json=payload)
    assert response.status_code==200,response.text
    assert response.json()['affected_count']==4
    rows=db.query(access.StatementGrant).filter(access.StatementGrant.user_id.in_([user.id for user in people])).all()
    assert len(rows)==4 and all(row.edit_content and row.cross_client and row.revision==1 for row in rows)
    events=db.query(access.StatementGrantEvent).all()
    assert len(events)==4 and all(row.actor_id==actor.id and not row.before['edit_content'] and row.after['edit_content'] for row in events)
    # 仅一个组合版本过期，也必须全批拒绝。
    payload['expected']=[{**item,'revision':1} for item in expected];payload['expected'][0]['revision']=0
    payload['edit_content']=False
    assert http.put('/statement-access/grants/batch',json=payload).status_code==409
    assert all(row.edit_content and row.revision==1 for row in rows)
    assert db.query(access.StatementGrantEvent).count()==4
    payload['expected']=payload['expected'][:-1]
    assert http.put('/statement-access/grants/batch',json=payload).status_code==422


def test_batch_mixed_permission_can_preserve_each_existing_value(setup):
    http,db,clients,_,actor=register(setup)
    actor.username='williamzhao';db.commit()
    person=db.query(access.AppUser).filter(access.AppUser.id!=actor.id).first()
    db.add(access.StatementGrant(user_id=person.id,client_id=clients[0].id,edit_content=True,cross_client=False,revision=1));db.commit()
    payload=dict(user_ids=[str(person.id)],client_ids=[str(client.id) for client in clients],expected=[dict(user_id=str(person.id),client_id=str(client.id),revision=1 if index==0 else 0) for index,client in enumerate(clients)],edit_content=None,cross_client=True)
    response=http.put('/statement-access/grants/batch',json=payload)
    assert response.status_code==200,response.text
    assert access.flags(db,person,clients[0].id)==dict(edit_content=True,cross_client=True)
    assert access.flags(db,person,clients[1].id)==dict(edit_content=False,cross_client=True)
