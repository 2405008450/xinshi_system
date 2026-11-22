"""账单打开只读取历史日期元数据；全部使用内存数据库。"""
from uuid import uuid4
from datetime import timedelta
from sqlalchemy import event
from tests.test_chat_participant_access import environment
from models import Client
from annotation_progress_time import business_now, business_datetime
from customer_statement_workspace import StatementWorkspace, StatementWorkspaceHistory, board_issue_dates


def test_issue_dates_read_board_metadata_instead_of_order_snapshots(environment):
    db, (actor, *_) = environment
    client = Client(id=uuid4(), client_name='日期查询测试')
    db.add(client); db.flush()
    first = {'id': 'first', 'fields': {}}
    second = {'id': 'second', 'fields': {}}
    row = StatementWorkspace(client_id=client.id, revision=2, payload={'boards': [first, second]})
    db.add(row); db.flush()
    created = business_now()
    for revision, boards in [(1, [first]), (2, [first, second])]:
        db.add(StatementWorkspaceHistory(id=uuid4(), client_id=client.id, revision=revision,
            actor_name='测试', action='新增对账单', changes={}, before={},
            after={'boards': boards, 'roots': {'large': 'x' * 100_000}},
            created_at=created + timedelta(days=revision)))
    db.commit()
    queries = []
    def track(_conn, _cursor, statement, *_args): queries.append(statement)
    event.listen(db.bind, 'before_cursor_execute', track)
    try:
        dates = board_issue_dates(db, row)
    finally:
        event.remove(db.bind, 'before_cursor_execute', track)
    assert dates == {key: business_datetime(created + timedelta(days=index)).date().isoformat()
                     for index, key in [(1, 'first'), (2, 'second')]}
    reads = [sql for sql in queries if 'FROM customer_statement_workspace_history' in sql]
    assert len(reads) == 1
    assert 'JSON_EXTRACT' in reads[0]  # SQLite 中同样由数据库裁剪 JSON，不传输 roots/tasks。


def test_client_workspace_does_not_load_unrelated_customer_records(environment):
    from customer_statement_workspace import read_client_workspace
    db, (actor, *_) = environment
    client = Client(id=uuid4(), client_name='客户项目读取测试')
    db.add(client); db.commit()
    client_id = client.id
    db.expunge_all()
    queries = []
    def track(_conn, _cursor, statement, *_args): queries.append(statement)
    event.listen(db.bind, 'before_cursor_execute', track)
    try:
        result = read_client_workspace(client_id, db=db, user=actor)
    finally:
        event.remove(db.bind, 'before_cursor_execute', track)
    assert result['client_name'] == '客户项目读取测试'
    assert result['documents'] == []
    assert not any('FROM client_address' in sql or 'FROM client_cooperation' in sql for sql in queries)


def test_pending_customer_reads_project_only_tasks_and_respect_customer_scope(environment):
    from statement_customer_groups import pending_clients
    from models import SubClient
    db, (actor, *_) = environment
    first = Client(id=uuid4(), client_name='匹配客户')
    second = Client(id=uuid4(), client_name='其他客户')
    db.add_all([first, second]); db.flush()
    child = SubClient(id=uuid4(), parent_client_id=first.id, sub_client_code='CHILD', client_name='子客户别名')
    db.add(child)
    task = {'id': 'pending', 'pending': True, 'month': '2026-11'}
    for client in [first, second]:
        db.add(StatementWorkspace(client_id=client.id, revision=1, payload={
            'roots': {'large': 'x' * 100_000}, 'boards': [], 'tasks': {
                'pending': task, 'other-month': {**task, 'month': '2026-10'},
                'finished': {**task, 'pending': False},
            }}))
    db.commit()
    queries = []
    def track(_conn, _cursor, statement, *_args): queries.append(statement)
    event.listen(db.bind, 'before_cursor_execute', track)
    try:
        assert pending_clients(db, '2026-11', keyword='子客户别名') == {first.id: [task]}
        assert pending_clients(db, '2026-11', client_ids={second.id}) == {second.id: [task]}
        assert pending_clients(db, '2026-11', client_ids=set()) == {}
    finally:
        event.remove(db.bind, 'before_cursor_execute', track)
    workspace_reads = [sql for sql in queries if 'FROM customer_statement_workspace' in sql]
    assert workspace_reads and all('JSON_EXTRACT' in sql for sql in workspace_reads)


def test_statement_membership_does_not_download_saved_order_roots(environment):
    from models import TranslationProject
    from translation_statement_status import attach, customer_boards
    db, (actor, *_) = environment
    client = Client(id=uuid4(), client_name='归属读取测试')
    db.add(client); db.flush()
    project = TranslationProject(id=uuid4(), order_no='TP-261101-999', project_name='测试', client_id=client.id)
    db.add(project); db.flush()
    db.add(StatementWorkspace(client_id=client.id, revision=1, payload={
        'roots': {str(project.id): {'large': 'x' * 100_000}},
        'boards': [{'id': 'board', 'name': '测试账单'}],
        'tasks': {'task': {'id': 'task', 'month': '2026-11', 'board_id': 'board',
                           'rows': [{'root_id': str(project.id), 'order_no': project.order_no}]}},
    }))
    db.commit()
    queries = []
    def track(_conn, _cursor, statement, *_args): queries.append(statement)
    event.listen(db.bind, 'before_cursor_execute', track)
    try:
        attach(db, [project])
        boards = customer_boards(db, {client.id})
    finally:
        event.remove(db.bind, 'before_cursor_execute', track)
    assert project.statement_status[0]['board_id'] == 'board'
    assert boards[str(client.id)][0]['months'] == ['2026-11']
    reads = [sql for sql in queries if 'FROM customer_statement_workspace' in sql]
    assert len(reads) == 2 and all('JSON_EXTRACT' in sql for sql in reads)
