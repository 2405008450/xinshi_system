"""笔译付款编号。付款主键、编号和首次登记时间独立于可修改的付款明细。"""
from decimal import Decimal, InvalidOperation

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Uuid, func, inspect, or_, text

from annotation_progress_time import business_datetime
from models import Base, FinancePayment, FinanceRecord


class TranslationSettlementNumber(Base):
    __tablename__ = 'translation_settlement_number'
    project_id = Column(Uuid, ForeignKey('translation_project.id', ondelete='CASCADE'), primary_key=True)
    payment_key = Column(String(36), primary_key=True)
    number = Column(String(40), nullable=False, unique=True)
    date_code = Column(String(6), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    installment = Column(Integer)
    issued_at = Column(DateTime(timezone=True), nullable=False)


def ready(db):
    if 'translation_settlement_number_ready' not in db.info:
        db.info['translation_settlement_number_ready'] = inspect(db.connection()).has_table(TranslationSettlementNumber.__tablename__)
    return db.info['translation_settlement_number_ready']


def records(db, project_id):
    if not ready(db):
        return {}
    return {row.payment_key: row for row in db.query(TranslationSettlementNumber).filter_by(project_id=project_id)}


def history(db, project_id, entry):
    from translation_finance_audit import TranslationFinanceEvent, TranslationFinanceEventItem, ready as audit_ready
    from translation_payment_confirmation import TranslationPaymentConfirmationHistory

    payments = db.query(TranslationPaymentConfirmationHistory).filter_by(project_id=project_id).filter(
        TranslationPaymentConfirmationHistory.created_at>=entry.issued_at,
    ).order_by(TranslationPaymentConfirmationHistory.created_at.desc(),TranslationPaymentConfirmationHistory.revision.desc())
    def state(snapshot):
        if entry.payment_key=='full':
            if snapshot.get('is_paid') and snapshot.get('payment_option')=='full':
                return {key:snapshot.get(key) for key in ('full_payment_amount','full_payment_currency','payment_account',
                                                         'proofs','matched_order_ids','mismatch_reason','full_payment_confirmed_at')}
            return None
        return next((item for item in snapshot.get('payment_details',[]) if item.get('id')==entry.payment_key),None)

    entries = []
    for event in payments:
        before,after=state(event.before),state(event.after)
        # Full-payment changes carry the complete state. Detail changes supply
        # both snapshots, including an empty side when adding or clearing rows.
        if entry.payment_key!='full' and 'payment_details' not in event.after:
            continue
        if before!=after:
            entries.append(dict(id=str(event.id),created_at=business_datetime(event.created_at).isoformat(),
                                actor_name=event.actor_name,action=event.after.get('action','修改付款情况'),
                                before=before,after=after))
    finance = []
    if audit_ready(db):
        audit = db.query(TranslationFinanceEvent,TranslationFinanceEventItem).join(TranslationFinanceEventItem).filter(
            TranslationFinanceEvent.project_id==project_id,
            TranslationFinanceEvent.created_at>=entry.issued_at,
        ).order_by(TranslationFinanceEvent.created_at.desc(),TranslationFinanceEventItem.order_no)
        fields = {'prices':'单价','word_count_cells':'工作量','pricing_mode':'计价方式','fixed_pricing_from':'固定收费归属',
                  'price_aggregate':'子订单汇总','recorded_adjusted_total':'不含税固定或调整金额',
                  'recorded_adjusted_total_incl_tax':'含税固定或调整金额','billing_totals':'计费总价',
                  'billing_tax_mode':'计费口径','document_notes':'单据说明','explanation':'内部说明',
                  'customer_explanation':'客户说明','payment_method':'结算模式'}
        for event,item in audit:
            before,after=item.before_snapshot,item.after_snapshot
            changed=[label for key,label in fields.items() if before.get(key)!=after.get(key)]
            if changed:
                finance.append({'id':f'{event.id}:{item.order_id}','actor_name':event.actor_name,'order_no':item.order_no,
                                'created_at':business_datetime(event.created_at).isoformat(),'changes':changed,
                                'before_totals':before.get('billing_totals',{}),'after_totals':after.get('billing_totals',{})})
    return {'payments':entries,'finance':finance}


def candidate_project_ids(db):
    from translation_payment_confirmation import TranslationPaymentConfirmation
    from models import TranslationProject
    actual = db.query(FinanceRecord.project_id).join(FinancePayment).filter(FinancePayment.actual_amount.is_not(None))
    full = db.query(TranslationPaymentConfirmation.project_id).filter(TranslationPaymentConfirmation.is_paid.is_(True))
    return db.query(TranslationProject.id).filter(TranslationProject.annotation_migrated_at.is_(None),
              or_(TranslationProject.id.in_(actual.statement),TranslationProject.id.in_(full.statement)))

def has_amount(value):
    try:
        return Decimal(str(value)).is_finite()
    except (InvalidOperation, ValueError):
        return False


def apply(db, project_id, current_time=None, *, only_full=False):
    """Caller locks the project. With no current time, recover first saved amounts from history."""
    if not ready(db):
        return 0
    from translation_payment_confirmation import TranslationPaymentConfirmation, TranslationPaymentConfirmationHistory, record_value

    existing = records(db, project_id)
    confirmation = db.get(TranslationPaymentConfirmation, project_id)
    value = record_value(confirmation)
    details = [] if only_full else db.query(FinancePayment).join(FinanceRecord).filter(FinanceRecord.project_id==project_id).all()
    stages = {'deposit': 0, 'mid': 1, 'final': 2}
    positions = {key: index for index, key in enumerate(value.get('payment_detail_order', []))}
    details.sort(key=lambda row: (positions.get(str(row.id), len(positions)),
                                 stages.get(row.stage_type, 3), row.stage_no, str(row.id)))
    active_details = [(row,index) for index,row in enumerate(details,1)
                      if row.actual_amount is not None and str(row.id) not in existing]
    new_full = confirmation and value['is_paid'] and value['payment_option']=='full' and has_amount(value['full_payment_amount']) and 'full' not in existing
    if not active_details and not new_full:
        return 0
    first_saved = {}
    if current_time is None:
        events = db.query(TranslationPaymentConfirmationHistory).filter_by(project_id=project_id).order_by(
            TranslationPaymentConfirmationHistory.created_at, TranslationPaymentConfirmationHistory.revision,
        )
        for event in events:
            snapshot = event.after
            if snapshot.get('is_paid') and snapshot.get('payment_option') == 'full' and has_amount(snapshot.get('full_payment_amount')):
                first_saved.setdefault('full', business_datetime(event.created_at))
            for item in snapshot.get('payment_details', []):
                if item.get('id') and has_amount(item.get('actual_amount')):
                    first_saved.setdefault(str(item['id']), business_datetime(event.created_at))
    pending = [(str(row.id), first_saved.get(str(row.id)) or current_time or business_datetime(row.created_at), index)
               for row,index in active_details]
    if new_full:
        pending.append(('full', first_saved.get('full') or current_time or business_datetime(confirmation.updated_at), None))
    pending = [(key, issued, position) for key, issued, position in pending if issued is not None]
    if not pending:
        return 0
    if db.bind.dialect.name == 'postgresql':
        # Serialize daily sequence allocation across projects until this transaction commits.
        db.execute(text('SELECT pg_advisory_xact_lock(17635, 261115)'))
    table = TranslationSettlementNumber
    sequences = {row.date_code: row.sequence for row in existing.values()}
    used = {row.installment for row in existing.values() if row.installment is not None}
    for key, issued, position in pending:
        date_code = issued.strftime('%y%m%d')
        if date_code not in sequences:
            maximum = db.query(func.max(table.sequence)).filter_by(date_code=date_code).scalar()
            sequences[date_code] = (maximum or 0) + 1
        sequence = sequences[date_code]
        if position in used:
            position = max(used) + 1
        if position is not None:
            used.add(position)
        number = f'TS-{date_code}-{sequence:03d}'
        if position is not None:
            number += f'.{position:02d}'
        db.add(table(project_id=project_id, payment_key=key, number=number, date_code=date_code,
                     sequence=sequence, installment=position, issued_at=issued))
    db.flush()
    return len(pending)
