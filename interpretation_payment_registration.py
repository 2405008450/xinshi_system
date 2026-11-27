"""口译付款沿用笔译表单契约；付款确认元数据仅由行政确认接口生成。"""
from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from fastapi import HTTPException
from annotation_progress_time import business_datetime, business_now
from business_finance_payment import apply_registration, registration, history_snapshot


class PaymentConfirm(BaseModel):
    revision: int = Field(ge=0)
    payment_id: UUID | None = None


def prepare(payload, before, billing):
    apply_registration(payload, billing)
    current = payload['payment_registration']
    previous = registration(before)
    known = {str(row.get('id')): row for row in previous['payments'] if row.get('id')}
    ids = set()
    for row in current['payments']:
        row['id'] = str(row.get('id') or uuid4())
        if row['id'] in ids:
            raise HTTPException(422, '付款记录不能重复')
        ids.add(row['id'])
        if row.get('payment_time'):
            row['payment_time'] = business_datetime(datetime.fromisoformat(row['payment_time'])).isoformat()
        old = known.get(row['id'])
        if old and all(old.get(key) == value for key,value in row.items()):
            for key in ('confirmed_by_name','confirmed_at'):
                if key in old:row[key]=old[key]
    value, old = current['confirmation'], previous['confirmation']
    if all(old.get(key) == value.get(key) for key in (
        'is_paid','payment_option','payment_account','proofs','full_payment_amount',
        'full_payment_currency','full_reference_amount','full_match_status','mismatch_reason')):
        for key in ('full_payment_confirmed_by_name','full_payment_confirmed_at'):
            if key in old:value[key]=old[key]


def payment_history(db, project_id, page):
    import interpretation_customer_finance as finance
    row=finance.record(db,'project',project_id)
    if not row:return dict(items=[],total=0)
    events=db.query(finance.InterpretationCustomerFinanceHistory).filter_by(finance_id=row.id).order_by(
        finance.InterpretationCustomerFinanceHistory.revision.desc()).all()
    items=[]
    for event in events:
        before,after=history_snapshot(event.before),history_snapshot(event.after)
        if before!=after:items.append(dict(id=event.id,actor_name=event.actor_name,
            created_at=business_datetime(event.created_at).isoformat(),before=before,after=after))
    return dict(items=items[(page-1)*10:page*10],total=len(items))


def mark_confirmed(state,actor,payment_id):
    value=state['confirmation']
    if payment_id:
        payment=next((r for r in state['payments'] if str(r.get('id'))==str(payment_id)),None)
        if payment is None:raise HTTPException(404,'没有该付款明细')
        if payment.get('actual_amount') is None:raise HTTPException(422,'请先保存实际付款金额，再确认')
        payment.update(confirmed_by_name=actor.full_name or actor.username,confirmed_at=business_now().isoformat())
    else:
        if not value.get('is_paid') or value.get('payment_option')!='full' or value.get('full_payment_amount') is None:
            raise HTTPException(422,'请先保存已付全款金额，再确认')
        value.update(full_payment_confirmed_by_name=actor.full_name or actor.username,full_payment_confirmed_at=business_now().isoformat())


def confirm(db, actor, project_id, data):
    from hr_access import can_manage_hr
    if not can_manage_hr(db,actor):raise HTTPException(403,'仅行政部人员可确认付款')
    import interpretation_customer_finance as finance
    project=finance.owner(db,'project',project_id)
    row=db.query(finance.InterpretationCustomerFinance).filter_by(project_id=project_id).with_for_update().populate_existing().first()
    if not row or row.revision!=data.revision:raise HTTPException(409,'付款情况已变化，请重新打开后确认')
    before=deepcopy(row.payload);payload=deepcopy(before)
    state=registration(payload)
    mark_confirmed(state,actor,data.payment_id)
    payload['payment_registration']=state
    row.payload=payload;row.revision+=1
    db.add(finance.InterpretationCustomerFinanceHistory(finance_id=row.id,revision=row.revision,
        actor_id=actor.id,actor_name=actor.full_name or actor.username,before=before,after=payload))
    db.commit()
    return finance.context(db,'project',project.id)
