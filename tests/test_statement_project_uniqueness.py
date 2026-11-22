from copy import deepcopy
import pytest
from fastapi import HTTPException
from tests.test_customer_statement_workspace import setup,imported
from tests.test_customer_statements import context
from tests.test_chat_participant_access import environment
from statement_project_uniqueness import validate
import translation_document_requirements as documents


def test_ordinary_project_cannot_span_two_active_boards_but_special_can(setup):
    _,db,clients,_,user,first,_=setup
    state=imported(setup,['2026-10'])
    payload=deepcopy(state['payload'])
    original=payload['boards'][0]
    other={**deepcopy(original),'id':'other','name':'另一账期','billing_months':['2026-11']}
    payload['boards'].append(other)
    task=deepcopy(payload['tasks'][str(first.id)])
    task.update(id='other-task',board_id='other',month='2026-11')
    payload['tasks']['other-task']=task
    with pytest.raises(HTTPException) as rejected:validate(db,clients[0].id,payload)
    assert rejected.value.status_code==409
    assert rejected.value.detail['code']=='project_multiple_active_statements'
    assert '财务主表' in rejected.value.detail['message'] and '特殊结算' in rejected.value.detail['message']
    other['status']='void'
    validate(db,clients[0].id,payload)
    other['status']='active'
    documents.save(db,first,payment_method='special',actor_id=user.id);db.flush()
    validate(db,clients[0].id,payload)
