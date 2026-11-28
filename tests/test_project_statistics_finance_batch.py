"""统计财务预加载不得随母订单数量产生逐条设置查询。"""
from uuid import uuid4

from sqlalchemy import event

from models import Client, SubClient, TranslationProject
from project_statistics_finance import attach_finance
from tests.test_chat_participant_access import environment


def test_translation_statistics_batch_loads_pricing_and_subclient_settings(environment):
    db, _ = environment
    customer = Client(id=uuid4(), client_code='BATCH-STATS', client_name='统计客户')
    db.add(customer)
    selected = []
    for index in range(8):
        child = SubClient(id=uuid4(), parent_client_id=customer.id,
                         sub_client_code=f'BATCH-{index}', client_name=f'子客户{index}')
        db.add(child)
        project = TranslationProject(id=uuid4(), order_no=f'TP-261128-{index:03}',
                                     project_name='批量统计', client_id=customer.id,
                                     sub_client_id=child.id)
        db.add(project)
        selected.append(dict(id=str(project.id), client_name='统计客户', client_short_name='统计客户'))
    db.commit()
    db.expire_all()
    statements = []
    connection = db.connection()

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lower())

    event.listen(connection, 'before_cursor_execute', capture)
    try:
        attach_finance(db, 'translation', selected)
    finally:
        event.remove(connection, 'before_cursor_execute', capture)
    for table in ('translation_project_documents', 'sub_client_finance_preference'):
        assert sum(f'from {table}' in sql for sql in statements) == 1
    assert all('finance' in row for row in selected)
