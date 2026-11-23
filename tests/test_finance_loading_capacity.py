"""公网往返较慢时的财务批量读取回归，仅使用内存 SQLite。"""
from uuid import uuid4
from sqlalchemy import event
from tests.test_chat_participant_access import environment
from models import Client, TranslationProject, TranslationSubOrder
import translation_customer_finance as finance


def orders(db, owner):
    client = Client(id=uuid4(), client_code='BATCH', client_name='批量查询测试')
    db.add(client)
    roots = []
    for index in range(12):
        root = TranslationProject(id=uuid4(), order_no=f'TP-261101-{index:03}',
                                  project_name='测试项目', client_id=client.id, created_by=owner.id)
        db.add(root)
        roots.append(root)
        for child in range(3):
            db.add(TranslationSubOrder(id=uuid4(), parent_project_id=root.id,
                                      sub_order_no=f'{root.order_no}.{child:03}', sub_project_name='测试文件'))
    db.commit()
    root_id = roots[0].id
    db.expunge_all()
    return db.get(TranslationProject, root_id)


def test_monthly_peer_charge_reads_are_batched(environment):
    db, (owner, *_) = environment
    root = orders(db, owner)
    finance.attach_monthly_payment_peers(db, [root])
    statements = []
    def track(_conn, _cursor, statement, *_args): statements.append(statement)
    event.listen(db.bind, 'before_cursor_execute', track)
    try:
        peers = finance.monthly_tax_projects(db, root)
        assert len(peers) == 12
        assert sum(len(peer.sub_orders) for peer in peers) == 36
        for peer in peers:
            list(peer.customer_charge_items)
            for child in peer.sub_orders: list(child.customer_charge_items)
    finally:
        event.remove(db.bind, 'before_cursor_execute', track)
    charge_reads = [sql for sql in statements if 'FROM translation_sub_order_charge_item' in sql]
    assert 0 < len(charge_reads) <= 2


def test_client_subtotals_batch_pricing_documents(environment):
    db, (owner, *_) = environment
    orders(db, owner)
    statements = []
    def track(_conn, _cursor, statement, *_args): statements.append(statement)
    event.listen(db.bind, 'before_cursor_execute', track)
    try:
        result = finance.client_subtotals(db, {})
    finally:
        event.remove(db.bind, 'before_cursor_execute', track)
    assert result[0]['project_count'] == 12
    document_reads = [sql for sql in statements if 'FROM translation_project_documents' in sql]
    assert len(document_reads) == 1


def test_list_preloads_peer_groups_without_followup_queries(environment):
    db, (owner, *_) = environment
    root = orders(db, owner)
    roots = db.query(TranslationProject).all()
    from translation_document_requirements import attach
    attach(db, roots)
    finance.attach_monthly_payment_peers(db, roots)
    finance.preload_monthly_tax_projects(db, roots)
    statements = []
    def track(_conn, _cursor, statement, *_args): statements.append(statement)
    event.listen(db.bind, 'before_cursor_execute', track)
    try:
        for project in roots:
            assert {peer.id for peer in finance.monthly_tax_projects(db, project)} == {row.id for row in roots}
            assert all(hasattr(peer, 'word_count_matrix') for peer in finance.monthly_tax_projects(db, project))
    finally:
        event.remove(db.bind, 'before_cursor_execute', track)
    assert not statements


def test_finance_page_skips_operational_details(environment):
    import inspect
    from fastapi.params import Param
    db, (owner, *_) = environment
    orders(db, owner)
    params = {key: (value.default.default if isinstance(value.default, Param) else value.default)
              for key, value in inspect.signature(finance.page).parameters.items()}
    params.update(db=db, user=owner, skip=0, limit=10, paginate_children=True,
                  include_payment_status=True, count_parent_orders=True)
    statements = []
    def track(_conn, _cursor, statement, *_args): statements.append(statement)
    event.listen(db.bind, 'before_cursor_execute', track)
    try:
        result = finance.page(**params)
    finally:
        event.remove(db.bind, 'before_cursor_execute', track)
    assert result['total'] == 48
    assert result['items']
    assert all(row['payment_status'] == 'unpaid' for row in result['items'])
    assert not any('FROM manuscript_arrangement' in sql or 'FROM project_role_assignment' in sql
                   for sql in statements)
