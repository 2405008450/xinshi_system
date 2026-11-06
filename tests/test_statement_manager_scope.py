from uuid import uuid4
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
from models import Client
from project_client_manager import ProjectClientManagerChange
from annotation_progress_time import business_now
from finance_manager_scope import manager_fields
import translation_customer_finance as finance
import statement_customer_groups as groups
import translation_document_requirements as documents


def test_statement_customers_share_main_manager_identity_and_scoped_moves(context):
    http,db,clients,granted,owner=context
    http.app.include_router(finance.router);granted.add('projects:write')
    from models import AppUser
    member=db.query(AppUser).filter(AppUser.id!=owner.id).first()
    owner.full_name='经理甲';member.full_name='经理乙'
    clients[0].client_manager='经理甲';clients[1].client_manager='经理乙'
    first=project(db,clients[0],'M1','2026-11');second=project(db,clients[0],'M2','2026-11');third=project(db,clients[1],'M3','2026-11')
    for row,person in [(first,owner),(second,member),(third,member)]:
        db.add(ProjectClientManagerChange(project_type='translation',project_id=row.id,revision=1,new_manager_id=person.id,new_manager_name=person.full_name,actor_user_id=owner.id,actor_name=owner.full_name,reason='隔离验证',changed_at=business_now()))
    db.commit()
    params=dict(billing_month='2026-11',only_mine=True)
    page=http.get('/translation-customer-finance/page',params=params).json()
    response=http.get('/translation-customer-finance/statement-customer-groups',params=params)
    assert response.status_code==200,response.text
    selected=response.json()['items']
    assert {row['id'] for row in page['items']}=={str(first.id)}
    assert len(selected)==1 and selected[0]['id']==str(clients[0].id) and selected[0]['project_count']==1
    assert selected[0]['client_managers']==['经理甲']
    named=http.get('/translation-customer-finance/statement-customer-groups',params={'billing_month':'2026-11','manager_ids':str(member.id)}).json()
    assert len(named['items'])==2 and all(row['project_count']==1 for row in named['items'])
    all_clients=http.get('/translation-customer-finance/statement-customer-groups',params={'billing_month':'2026-11'}).json()['items']
    assert sum(row['project_count'] for row in all_clients)==3
    # 修改客户当前经理筛选内项目的需求，不波及同客户另一位经理的项目。
    groups.move(db,owner,clients[0].id,groups.CustomerGroupMove(billing_month='2026-11',statement_required=False,expected_version=selected[0]['version'],only_mine=True))
    documents.attach(db,[first,second])
    assert not first.statement_required and second.statement_required
