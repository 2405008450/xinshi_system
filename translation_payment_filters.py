"""付款状态筛选：四种阶段互斥，已付款汇总各已付阶段；实付尾款按全款处理。"""
from sqlalchemy import select,exists,and_,or_,false,func
from models import TranslationProject,FinanceRecord,FinancePayment


def payment_amount_mismatches(item, confirmation):
    """按已选核对口径或当前计费总价比较；币种不同、金额缺失也需核对。"""
    from decimal import Decimal
    amount = item.get('payment_actual_total')
    currency = item.get('payment_currency') or 'CNY'
    key = confirmation.get('full_payment_total_key')
    fields = {'billing': 'billing_totals', 'excl': 'totals_excl_tax',
              'incl': 'totals_incl_tax', 'adjusted': 'adjusted_totals'}
    if key:
        kind, _, selected_currency = key.partition(':')
        totals = item.get(fields.get(kind, ''), {})
        expected = totals.get(selected_currency) if selected_currency == currency else None
    else:
        totals = item.get('billing_totals', {})
        expected = totals.get(currency) if len(totals) == 1 else None
    return (amount is None or expected is None
            or Decimal(str(amount)).quantize(Decimal('.01')) != Decimal(str(expected)).quantize(Decimal('.01')))


def attach_payment_status(db,result):
    from decimal import Decimal
    from uuid import UUID
    from sqlalchemy import case
    from translation_payment_confirmation import TranslationPaymentConfirmation,ready,record_value
    items=result.get('items',[]);ids=[UUID(item['id']) for item in items]
    if not ids:return result
    state=case((payment_status_condition(db,'full'),'full'),(payment_status_condition(db,'mid'),'mid'),(payment_status_condition(db,'deposit'),'deposit'),else_='unpaid')
    states={str(uid):status for uid,status in db.query(TranslationProject.id,state).filter(TranslationProject.id.in_(ids))}
    amounts={str(uid):amount for uid,amount in db.query(FinanceRecord.project_id,func.sum(FinancePayment.actual_amount)).join(FinancePayment,FinancePayment.finance_id==FinanceRecord.id).filter(FinanceRecord.project_id.in_(ids)).group_by(FinanceRecord.project_id)}
    confirmations={str(row.project_id):record_value(row) for row in db.query(TranslationPaymentConfirmation).filter(TranslationPaymentConfirmation.project_id.in_(ids))} if ready(db) else {}
    for item in items:
        confirmation=confirmations.get(item['id'],{})
        amount=confirmation.get('full_payment_amount') if confirmation.get('is_paid') and confirmation.get('payment_option')=='full' else amounts.get(item['id'],0)
        item['payment_status']=states.get(item['id'],'unpaid');item['payment_actual_total']=format(Decimal(str(amount)),'.2f') if amount is not None else None
        item['payment_currency']=confirmation.get('full_payment_currency','CNY')
        reference_item = item
        reference_key = confirmation.get('full_payment_total_key') or ''
        if item['payment_status'] == 'full' and reference_key.startswith(('statement:', 'monthly:')):
            from translation_payment_confirmation import project_totals
            totals = project_totals(db, UUID(item['id']))['items']
            selected = next((total for total in totals if total['key'] == reference_key), None)
            reference_item = {**item, 'billing_totals': {selected['currency']: selected['amount']} if selected else {}}
            confirmation = {**confirmation, 'full_payment_total_key': f"billing:{reference_key.partition(':')[2]}"}
        item['payment_amount_mismatch']=payment_amount_mismatches(reference_item,confirmation)
        # 付款属于母订单，下级展示同一份付款状态。
        pending=list(item.get('children',[]))
        while pending:
            child=pending.pop();child['payment_status']=item['payment_status']
            child['payment_amount_mismatch']=item['payment_amount_mismatch']
            pending.extend(child.get('children',[]))
    return result

def payment_status_condition(db,status):
    from translation_payment_confirmation import TranslationPaymentConfirmation,ready
    def paid_stage(stage=None):
        conditions=[FinanceRecord.project_id==TranslationProject.id,FinancePayment.actual_amount.is_not(None)]
        if stage:conditions.append(FinancePayment.stage_type==stage)
        else:conditions.append(FinancePayment.actual_amount>0)
        return exists(select(1).select_from(FinancePayment).join(FinanceRecord,FinanceRecord.id==FinancePayment.finance_id).where(*conditions).correlate(TranslationProject))
    paid=false();manual_full=false()
    if ready(db):
        base=[TranslationPaymentConfirmation.project_id==TranslationProject.id,TranslationPaymentConfirmation.is_paid.is_(True)]
        paid=exists(select(1).where(*base).correlate(TranslationProject))
        option=func.replace(TranslationPaymentConfirmation.payment_option,' ','')
        manual_full=exists(select(1).where(*base,or_(option=='full',option.contains('"type":"full"'))).correlate(TranslationProject))
    full=or_(manual_full,paid_stage('final'))
    mid=paid_stage('mid')
    any_paid=or_(paid,paid_stage())
    return {'paid':or_(full,mid,any_paid),'full':full,'mid':and_(~full,mid),'deposit':and_(~full,~mid,any_paid),'unpaid':and_(~full,~mid,~any_paid)}[status]
