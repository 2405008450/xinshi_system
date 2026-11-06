from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from models import Client,TranslationProject
import translation_document_requirements as documents
from statement_customer_groups import customers,move,CustomerGroupMove


def test_month_groups_search_move_and_stale_snapshot(environment):
    db,(actor,*_)=environment
    documents.TranslationProjectDocuments.__table__.create(db.connection(),checkfirst=True)
    client=Client(id=uuid4(),client_name='AA科技 BB',client_short_name='甲客户',client_manager='实际客户经理')
    other=Client(id=uuid4(),client_name='其他客户',client_short_name='乙客户')
    db.add_all([client,other]);db.flush()
    projects=[]
    for number,owner in [('TP-261001-001',client),('TP-261002-001',client),('TP-261101-001',client),('TP-261003-001',other)]:
        project=TranslationProject(id=uuid4(),order_no=number,project_name=number,client_id=owner.id,created_by=actor.id)
        db.add(project);projects.append(project)
    db.flush()
    for project,value in zip(projects,[True,False,True,False]):documents.save(db,project,statement_required=value,actor_id=actor.id)
    db.commit()
    required=customers(db,'2026-10',True,'BB AA',0,20)
    assert required['total']==1
    row=required['items'][0]
    assert row['project_count']==2 and row['required_count']==1
    assert row['client_managers']==['实际客户经理']
    assert customers(db,'2026-10',False,None,0,20)['total']==1
    result=move(db,actor,client.id,CustomerGroupMove(billing_month='2026-10',statement_required=False,expected_version=row['version']))
    assert result['affected_count']==1
    assert customers(db,'2026-10',True,None,0,20)['total']==0
    assert customers(db,'2026-10',False,None,0,20)['total']==2
    documents.attach(db,projects)
    assert not projects[0].statement_required and not projects[1].statement_required
    assert projects[2].statement_required
    with pytest.raises(HTTPException) as stale:move(db,actor,client.id,CustomerGroupMove(billing_month='2026-10',statement_required=True,expected_version=row['version']))
    assert stale.value.status_code==409
