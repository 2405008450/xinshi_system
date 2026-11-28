"""标注财务复用笔译付款表单的数据契约，兼容原账簿收款数据。"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from pydantic import Field
from interpretation_finance_schemas import StrictInput
from translation_payment_confirmation import PaymentConfirmationWrite
from translation_payment_service import ProjectPayment


class BusinessPayment(ProjectPayment):
    currency: str = Field(default='CNY', pattern=r'^[A-Z]{3}$')


class Registration(StrictInput):
    confirmation: PaymentConfirmationWrite = Field(default_factory=PaymentConfirmationWrite)
    payments: list[BusinessPayment] = Field(default_factory=list, max_length=100)
    full_payment_received_on: date | None = None


def registration(payload):
    if payload.get('payment_registration') is not None:
        return deepcopy(payload['payment_registration'])
    settlement = payload.get('settlement') or {}
    old = settlement.get('payments', [])
    full = settlement.get('payment_status') == 'full' and len(old) <= 1
    paid = settlement.get('payment_status', 'unrecorded') != 'unrecorded' or bool(old)
    currency = old[0]['currency'] if old else next((row['currency'] for row in payload.get('rates', [])), 'CNY')
    proofs = settlement.get('payment_note', '')
    if full and old and old[0].get('note'):
        proofs = '\n'.join(filter(None, [proofs, old[0]['note']]))
    confirmation = dict(is_paid=paid, payment_option='full' if full else 'deposit' if paid else None,
        full_payment_currency=currency, full_payment_amount=old[0]['amount'] if full and old else None,
        proofs=proofs, payment_account='')
    payments = [] if full else [dict(stage_type='deposit' if index == 0 else 'final' if row.get('stage_type') == 'tail' else 'mid',
        stage_no=index+1, actual_amount=row['amount'], currency=row['currency'],
        payment_time=row['received_on']+'T00:00:00+08:00' if row.get('received_on') else None,
        proofs=row.get('note', ''), payment_method='') for index, row in enumerate(old)]
    return dict(confirmation=confirmation, payments=payments,
                full_payment_received_on=old[0].get('received_on') if full and old else None)


def apply_registration(payload, billing):
    """将新表单同步为既有结算收款口径，账单与统计共用同一数据。"""
    from annotation_progress_time import business_datetime
    value = Registration.model_validate(payload['payment_registration'])
    confirmation = value.confirmation
    payments = value.payments
    if not confirmation.is_paid:
        payments = []
    elif confirmation.payment_option == 'full':
        if confirmation.full_payment_amount is None:
            raise HTTPException(422, '请填写已付全款金额')
        reference = billing.get(confirmation.full_payment_currency)
        if (reference is None or Decimal(str(reference)) != confirmation.full_payment_amount) and not confirmation.mismatch_reason.strip():
            raise HTTPException(422, '请说明全款金额不匹配的原因')
        payments = []
    elif confirmation.payment_option not in ('deposit', 'once'):
        raise HTTPException(422, '请选择已付定金或已付全款')
    if payments and payments[0].stage_type != 'deposit':
        raise HTTPException(422, '首笔付款阶段必须为定金')
    finals = [index for index, row in enumerate(payments) if row.stage_type == 'final']
    if len(finals) > 1 or finals and finals[0] != len(payments)-1:
        raise HTTPException(422, '尾款只能有一笔且必须为最后一期')
    if finals and any(row.actual_amount is None for row in payments):
        raise HTTPException(422, '登记尾款后请填写每次实际金额')
    if finals:
        received={}
        for row in payments:received[row.currency]=received.get(row.currency,Decimal(0))+row.actual_amount
        if any(received.get(code,Decimal(0))!=Decimal(str(billing.get(code,0))) for code in received.keys()|billing.keys()) and not confirmation.mismatch_reason.strip():
            raise HTTPException(422, '请说明尾款累计实付与项目总价不匹配的原因')
    settlement = payload['settlement']
    if confirmation.is_paid and confirmation.payment_option == 'full':
        settlement['payments'] = [dict(amount=str(confirmation.full_payment_amount), currency=confirmation.full_payment_currency,
            stage_type='full', received_on=value.full_payment_received_on.isoformat() if value.full_payment_received_on else None, note='')]
        settlement['payment_status'] = 'full'
    else:
        settlement['payments'] = [dict(amount=str(row.actual_amount), currency=row.currency,
            received_on=business_datetime(row.payment_time).date().isoformat() if row.payment_time else None,
            stage_type='tail' if row.stage_type=='final' else row.stage_type, note=row.proofs[:2000]) for row in payments if row.actual_amount is not None]
        settlement['payment_status'] = 'full' if finals else 'partial' if len(payments)>1 else 'deposit' if confirmation.is_paid else 'unrecorded'
    settlement['payment_note'] = confirmation.proofs[:5000]
    saved_confirmation=confirmation.model_dump(mode='json')
    if finals and len({row.currency for row in payments})==1:
        code=payments[0].currency
        saved_confirmation.update(full_payment_source='details',full_payment_currency=code,
            full_payment_amount=str(sum((row.actual_amount for row in payments),Decimal(0))))
    if confirmation.is_paid and (confirmation.payment_option=='full' or saved_confirmation.get('full_payment_source')=='details'):
        code=saved_confirmation['full_payment_currency']
        reference=billing.get(code)
        saved_confirmation.update(full_match_status='matched' if reference is not None and Decimal(str(reference))==Decimal(saved_confirmation['full_payment_amount']) else 'mismatch',
            full_reference_label='项目计费金额',full_reference_amount=str(reference) if reference is not None else None)
    payload['payment_registration'] = dict(confirmation=saved_confirmation, payments=[row.model_dump(mode='json') for row in payments],full_payment_received_on=value.full_payment_received_on.isoformat() if value.full_payment_received_on else None)


def history_snapshot(payload):
    result = registration(payload)
    return {**result['confirmation'], 'payment_details': result['payments']}


def promote_payment_proofs(db,registration):
    from editor_screenshot_service import references,valid_references,ready,api_time,now,promote_business_references
    from editor_screenshot_models import EditorScreenshot
    texts=[]
    def collect(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in {'proofs','receipt_proofs'} and isinstance(item,str):texts.append(item)
                else:collect(item)
        elif isinstance(value,list):
            for item in value:collect(item)
    collect(registration)
    text='\n'.join(texts);ids=references(text)
    if not ids:return
    if ids!=valid_references(text):raise HTTPException(422,'付款或收款截图引用无效，请重新上传')
    if not ready(db):raise HTTPException(503,'截图存储尚未初始化')
    images=db.query(EditorScreenshot).filter(EditorScreenshot.id.in_(ids)).all()
    if len(images)!=len(ids) or any(not row.blob_sha256 or row.expires_at and api_time(row.expires_at)<=now() for row in images):raise HTTPException(422,'付款或收款截图不存在或已过期，请重新上传')
    promote_business_references(db,ids)
