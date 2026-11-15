"""对账单编号，按账单 ID 保留拆分关系和已使用的流水号。"""
from sqlalchemy import Column, ForeignKey, Integer, String, Uuid, func, inspect, text

from annotation_progress_time import business_datetime, business_now
from models import Base


class TranslationStatementNumber(Base):
    __tablename__ = 'translation_statement_number'
    board_id = Column(String(36), primary_key=True)
    client_id = Column(Uuid, ForeignKey('client.id',ondelete='CASCADE'),nullable=False,index=True)
    number = Column(String(40),nullable=False,unique=True)
    date_code = Column(String(6),nullable=False,index=True)
    sequence = Column(Integer,nullable=False)
    child_sequence = Column(Integer,nullable=False,default=0)


def ready(db):
    if db is None:
        return False
    if 'translation_statement_number_ready' not in db.info:
        db.info['translation_statement_number_ready']=inspect(db.connection()).has_table(TranslationStatementNumber.__tablename__)
    return db.info['translation_statement_number_ready']


def numbers(db,client_id):
    if not ready(db):
        return {}
    return {row.board_id:row.number for row in db.query(TranslationStatementNumber).filter_by(client_id=client_id)}


def parent_id(board):
    # Each billing period is an independent statement, including legacy snapshots.
    return None if board.get('period_number') else board.get('number_parent_id')


def correct_period_numbers(db, client_id, boards, entries):
    model = TranslationStatementNumber
    periods = [entries[board['id']] for board in boards
               if board.get('period_number') and board['id'] in entries and entries[board['id']].child_sequence]
    if not periods:
        return 0
    historical, dates = historical_boards(db, client_id)
    parents = {key: parent_id(board) for key, board in historical.items()}
    parents.update({board['id']: parent_id(board) or parents.get(board['id'])
                    for board in boards if not board.get('period_number')})
    children = {}
    for key, parent in parents.items():
        if parent and key in entries:
            children.setdefault(parent, []).append(entries[key])
    for period in sorted(periods, key=lambda row: (row.date_code, row.sequence, row.child_sequence)):
        created_at = business_datetime(dates.get(period.board_id))
        date_code = created_at.strftime('%y%m%d') if created_at else period.date_code
        sequence = (db.query(func.max(model.sequence)).filter_by(date_code=date_code).scalar() or 0) + 1
        base = f'TB-{date_code}-{sequence:03d}'
        period.number, period.date_code, period.sequence, period.child_sequence = base, date_code, sequence, 0
        descendants = []
        pending = children.get(period.board_id, []).copy()
        while pending:
            row = pending.pop()
            descendants.append(row)
            pending.extend(children.get(row.board_id, []))
        for index, row in enumerate(sorted(descendants, key=lambda item: item.child_sequence), 1):
            row.number, row.date_code, row.sequence, row.child_sequence = f'{base}.{index:02d}', date_code, sequence, index
        db.flush()
    return len(periods)


def issue(db,client_id,boards,creation_dates=None):
    if not boards or not ready(db):
        return 0
    boards=list(boards)
    model=TranslationStatementNumber
    if db.get_bind().dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(17635, 2)'))
    entries={row.board_id:row for row in db.query(model).filter_by(client_id=client_id)}
    correct_period_numbers(db,client_id,boards,entries)
    pending={board['id']:board for board in boards if board['id'] not in entries}
    dates=creation_dates or {}
    sequences={}
    child_sequences={}
    count=len(pending)
    while pending:
        for board_id,board in list(pending.items()):
            source_id=parent_id(board)
            if source_id in pending:
                continue
            parent=entries.get(source_id)
            if parent:
                date_code,sequence=parent.date_code,parent.sequence
                group=(date_code,sequence)
                if group not in child_sequences:
                    child_sequences[group]=db.query(func.max(model.child_sequence)).filter_by(date_code=date_code,sequence=sequence).scalar() or 0
                child_sequences[group]+=1
                child=child_sequences[group]
            else:
                date_code=business_datetime(dates.get(board_id) or business_now()).strftime('%y%m%d')
                if date_code not in sequences:
                    sequences[date_code]=db.query(func.max(model.sequence)).filter_by(date_code=date_code).scalar() or 0
                sequences[date_code]+=1
                sequence=sequences[date_code]
                child=0
            number=f'TB-{date_code}-{sequence:03d}'+(f'.{child:02d}' if child else '')
            row=model(board_id=board_id,client_id=client_id,number=number,date_code=date_code,sequence=sequence,child_sequence=child)
            db.add(row)
            entries[board_id]=row
            del pending[board_id]
    db.flush()
    return count


def historical_boards(db,client_id):
    from customer_statement_workspace import StatementWorkspaceHistory

    boards={}
    dates={}
    events=db.query(StatementWorkspaceHistory).filter_by(client_id=client_id).order_by(StatementWorkspaceHistory.revision)
    for event in events:
        previous=event.before.get('boards',[])
        for board in event.after.get('boards',[]):
            key=board['id']
            if key in dates:
                continue
            dates[key]=event.created_at
            boards[key]=dict(board)
            if board.get('period_number'):
                boards[key].pop('number_parent_id', None)
                continue
            if board.get('number_parent_id'):
                continue
            changes=event.changes
            parents=set()
            if event.action=='分拆历史对账单':
                parents=set(changes.get('before',{}).values())
            elif event.action=='新增对账单' and previous:
                parents={changes.get('parent_board_id') or previous[0]['id']}
            if len(parents)==1:
                boards[key]['number_parent_id']=parents.pop()
    return boards,dates
