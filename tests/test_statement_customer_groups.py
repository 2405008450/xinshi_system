from uuid import UUID,uuid4
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from models import Client,TranslationProject
import translation_document_requirements as documents
from statement_customer_groups import customers,move,CustomerGroupMove


@pytest.mark.parametrize('child_task', [False, True])
def test_existing_statement_classification_matches_finance_list(environment, child_task):
    """已有对账单时，即使历史需求为否，分类与财务列表也必须一致。"""
    from models import TranslationSubOrder
    from customer_statement_workspace import StatementWorkspace
    import translation_customer_finance as finance
    db, (actor, *_) = environment
    client = Client(id=uuid4(), client_name='已生成对账单客户')
    db.add(client); db.flush()
    project = TranslationProject(id=uuid4(), order_no='TP-261101-001', project_name='测试项目',
                                 client_id=client.id, created_by=actor.id)
    db.add(project); db.flush()
    documents.save(db, project, statement_required=False, actor_id=actor.id)
    task_id = str(project.id)
    order_no = project.order_no
    if child_task:
        child = TranslationSubOrder(id=uuid4(), parent_project_id=project.id,
                                    sub_order_no=order_no+'.001', sub_project_name='测试子订单')
        db.add(child)
        task_id, order_no = str(child.id), child.sub_order_no
    db.add(StatementWorkspace(client_id=client.id, revision=1, updated_by=actor.id, payload={
        'roots': {str(project.id): {}},
        'boards': [{'id': 'board', 'name': '2026-11 对账单'}],
        'tasks': {task_id: {'id': task_id, 'board_id': 'board', 'month': '2026-11',
                            'pending': False, 'rows': [{'root_id': str(project.id), 'order_no': order_no}]}},
    }))
    db.commit()
    client_id, project_id = client.id, project.id
    assert finance.read(db, project_id)['item']['statement_required'] is True
    db.expunge_all()  # 新请求不能依赖财务页留在 Session 中的临时属性。
    required = customers(db, '2026-11', True, None, 0, 20)
    not_required = customers(db, '2026-11', False, None, 0, 20)
    assert {row['id'] for row in required['items']} == {str(client_id)}
    assert required['items'][0]['required_count'] == 1
    assert not_required['total'] == 0
    assert db.get(documents.TranslationProjectDocuments, project_id).statement_required is False


def test_customer_search_limits_finance_calculation_but_keeps_all_matching_customer_projects(environment, monkeypatch):
    from models import SubClient
    import translation_customer_finance as finance
    db, (actor, *_) = environment
    parent = Client(id=uuid4(), client_name='甲客户')
    other = Client(id=uuid4(), client_name='不匹配客户')
    db.add_all([parent, other]); db.flush()
    child = SubClient(id=uuid4(), parent_client_id=parent.id, sub_client_code='MATCH', client_name='子客户匹配词')
    db.add(child); db.flush()
    projects = []
    for index, (client, sub) in enumerate([(parent, child), (parent, None), (other, None)]):
        project = TranslationProject(id=uuid4(), order_no=f'TP-261101-{index:03}', project_name='测试',
            client_id=client.id, sub_client_id=sub.id if sub else None, created_by=actor.id)
        db.add(project); db.flush()
        documents.save(db, project, statement_required=False, actor_id=actor.id)
        projects.append(project)
    db.commit()
    original = finance.effective_statement_requirements
    seen = []
    def calculate(db, rows):
        seen.extend(row.id for row in rows)
        return original(db, rows)
    monkeypatch.setattr(finance, 'effective_statement_requirements', calculate)
    result = customers(db, '2026-11', False, '子客户匹配词', 0, 20)
    assert seen == [row.id for row in projects[:2]]
    assert result['total'] == 1
    assert result['items'][0]['project_count'] == 2
    assert result['items'][0]['sub_clients'][0]['id'] == str(child.id)


def test_explicit_normal_requirements_skip_finance_tree_calculation(environment, monkeypatch):
    import translation_customer_finance as finance
    from statement_customer_groups import project_query
    db, (actor, *_) = environment
    client = Client(id=uuid4(), client_name='明确需求客户')
    db.add(client); db.flush()
    expected = {}
    for index, value in enumerate([True, False]):
        project = TranslationProject(id=uuid4(), order_no=f'TP-261101-{index:03}', project_name='测试',
                                     client_id=client.id, created_by=actor.id)
        db.add(project); db.flush()
        documents.save(db, project, statement_required=value, actor_id=actor.id)
        expected[project.id] = value
    db.commit()
    monkeypatch.setattr(finance, 'tree', lambda *args, **kwargs: pytest.fail('明确需求不应再计算整棵财务树'))
    assert finance.effective_statement_requirements(db, project_query(db,'2026-11').all()) == expected


def test_customer_page_reuses_requirements_and_preserves_snapshot_versions(environment, monkeypatch):
    import statement_customer_groups as groups
    import translation_customer_finance as finance
    db,(actor,*_)=environment
    documents.TranslationProjectDocuments.__table__.create(db.connection(),checkfirst=True)
    clients=[Client(id=uuid4(),client_name=f'客户{index}') for index in range(3)]
    db.add_all(clients);db.flush()
    for index,client in enumerate(clients):
        project=TranslationProject(id=uuid4(),order_no=f'TP-261001-{index:03}',
            project_name='项目',client_id=client.id,created_by=actor.id)
        db.add(project);db.flush()
        documents.save(db,project,payment_method='special',statement_required=True,actor_id=actor.id)
    db.commit()
    calls=[]
    calculate=finance.effective_statement_requirements
    def counted(db,projects):
        calls.append(len(projects))
        return calculate(db,projects)
    monkeypatch.setattr(finance,'effective_statement_requirements',counted)
    result=customers(db,'2026-10',True,None,0,20,settlement_scope='special')
    assert result['total']==3
    assert calls==[3]
    for item in result['items']:
        _,version=groups.snapshot(db,UUID(item['id']),'2026-10',settlement_scope='special')
        assert item['version']==version


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
    assert not projects[2].statement_required  # 自动同步客户默认，同时更新其他账期。
    with pytest.raises(HTTPException) as stale:move(db,actor,client.id,CustomerGroupMove(billing_month='2026-10',statement_required=True,expected_version=row['version']))
    assert stale.value.status_code==409
