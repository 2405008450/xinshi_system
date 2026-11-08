"""项目付款确认与永久支付凭证，收费窗口和付款明细共用。"""
from uuid import uuid4
from decimal import Decimal
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Boolean,Column,DateTime,ForeignKey,Integer,JSON,Text,Uuid,inspect
from fastapi import HTTPException
from models import Base,TranslationProject
from annotation_progress_time import business_now,business_datetime


class PaymentConfirmationWrite(BaseModel):
    model_config=ConfigDict(extra='ignore')
    revision:int=Field(default=0,ge=0)
    clear_details:bool=False
    is_paid:bool=False
    payment_option:Literal['full','deposit','once']|None=None
    payment_account:str=Field(default='',max_length=50)
    proofs:str=Field(default='',max_length=20000)
    full_payment_amount:Decimal|None=Field(default=None,ge=0,max_digits=14,decimal_places=2)
    full_payment_currency:str=Field(default='CNY',pattern=r'^[A-Z]{3}$')
    full_payment_total_key:str|None=Field(default=None,max_length=80)
    mismatch_reason:str=Field(default='',max_length=2000)

    @model_validator(mode='after')
    def paid_option(self):
        if self.is_paid and not self.payment_option:raise ValueError('请选择付款情况')
        from editor_screenshot_service import references
        if len(references(self.proofs))>9:raise ValueError('支付截图最多9张')
        return self


class TranslationPaymentConfirmation(Base):
    __tablename__='translation_payment_confirmation'
    project_id=Column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),primary_key=True)
    revision=Column(Integer,nullable=False,default=0)
    is_paid=Column(Boolean,nullable=False,default=False)
    payment_option=Column(Text)
    proofs=Column(Text,nullable=False,default='')
    updated_by=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    updated_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


class TranslationPaymentConfirmationHistory(Base):
    __tablename__='translation_payment_confirmation_history'
    id=Column(Uuid,primary_key=True,default=uuid4)
    project_id=Column(Uuid,ForeignKey('translation_project.id',ondelete='CASCADE'),nullable=False,index=True)
    revision=Column(Integer,nullable=False)
    actor_id=Column(Uuid,ForeignKey('app_user.id',ondelete='SET NULL'))
    actor_name=Column(Text,nullable=False)
    before=Column(JSON,nullable=False)
    after=Column(JSON,nullable=False)
    created_at=Column(DateTime(timezone=True),nullable=False,default=business_now)


def ready(db):
    key='translation_payment_confirmation_ready'
    if key not in db.info:
        schema=inspect(db.connection())
        db.info[key]=all(schema.has_table(model.__tablename__) for model in (TranslationPaymentConfirmation,TranslationPaymentConfirmationHistory))
    return db.info[key]


def read(db,project_id):
    row=db.get(TranslationPaymentConfirmation,project_id) if ready(db) else None
    return record_value(row)


def record_value(row):
    option=row.payment_option if row else None
    account=''
    full={}
    if option and option.startswith('{'):
        try:
            data=json.loads(option);option=data.get('type');account=data.get('account','');full=data.get('full_payment') or {}
        except (ValueError,AttributeError):option=None
    return {'revision':row.revision if row else 0,'is_paid':bool(row.is_paid) if row else False,
            'payment_option':option,'payment_account':account,'proofs':row.proofs or '' if row else '',
            'full_payment_source':full.get('source'),'full_payment_amount':full.get('amount'),'full_payment_currency':full.get('currency','CNY'),
            'full_payment_total_key':full.get('total_key'),'mismatch_reason':full.get('mismatch_reason',''),
            'full_match_status':full.get('match_status','unverified' if row and row.is_paid and option=='full' else 'none'),
            'full_reference_label':full.get('reference_label',''),'full_reference_amount':full.get('reference_amount')}


def project_totals(db,project_id):
    from translation_customer_finance import read as read_finance
    data=read_finance(db,project_id)
    node=data['item']
    items=[]
    for key,label,field in [('excl','不含税总价','totals_excl_tax'),('incl','含税总价','totals_incl_tax'),('adjusted','调整后总价','adjusted_totals')]:
        for currency,amount in node.get(field,{}).items():
            items.append({'key':f'{key}:{currency}','label':label,'currency':currency,'amount':format(Decimal(amount),'.2f')})
    return {'items':items,'version':data['version']}


def attach(db,projects):
    projects=projects or []
    values={row.project_id:row for row in db.query(TranslationPaymentConfirmation).filter(TranslationPaymentConfirmation.project_id.in_([project.id for project in projects])).all()} if projects and ready(db) else {}
    for project in projects:
        row=values.get(project.id)
        project.payment_confirmation=record_value(row)


def save(db,project_id,payload,actor_id,cleared_payments=None):
    if payload is None:return read(db,project_id)
    if not ready(db):raise HTTPException(503,'付款确认存储尚未初始化')
    # 所有入口锁同一母订单，状态与既有付款记录不会分别覆盖。
    project=db.query(TranslationProject).filter_by(id=project_id).with_for_update().first()
    if project is None:raise HTTPException(404,'笔译项目不存在')
    row=db.query(TranslationPaymentConfirmation).filter_by(project_id=project_id).with_for_update().populate_existing().first()
    before=read(db,project_id)
    if payload.revision!=before['revision']:raise HTTPException(409,'付款情况已被修改，请重新打开后编辑')
    clearing=not payload.is_paid
    if clearing:
        if cleared_payments is None:
            from translation_payment_service import read as read_payments
            cleared_payments=read_payments(db,project)['payments']
        if payload.clear_details:payload=payload.model_copy(update={'payment_option':None,'payment_account':'','proofs':'','full_payment_amount':None,'full_payment_total_key':None,'mismatch_reason':''})
    source='manual'
    if payload.is_paid and payload.payment_option=='deposit':
        from models import FinanceRecord,FinancePayment
        details=db.query(FinancePayment).join(FinanceRecord,FinancePayment.finance_id==FinanceRecord.id).filter(FinanceRecord.project_id==project_id).all()
        if any(item.stage_type=='final' for item in details):
            if any(item.actual_amount is None for item in details):raise HTTPException(422,'登记尾款后，请填写每次付款的实际金额再核对总价')
            source='details'
            payload=payload.model_copy(update={'full_payment_amount':sum((Decimal(item.actual_amount) for item in details),Decimal('0')).quantize(Decimal('.01'))})
    values=payload.model_dump(exclude={'revision','clear_details'})
    if values['full_payment_amount'] is not None:values['full_payment_amount']=format(values['full_payment_amount'],'.2f')
    full={}
    unchanged=values=={key:before[key] for key in values}
    if payload.is_paid and (payload.payment_option=='full' or source=='details'):
        if payload.full_payment_amount is None:
            if unchanged:return before  # 兼容未登记金额的历史全款确认，不把它冒认为已匹配。
            raise HTTPException(422,'请填写已付全款金额并核对项目总价')
        totals=project_totals(db,project_id)['items']
        selected=next((item for item in totals if item['key']==payload.full_payment_total_key),None)
        if selected is None and payload.full_payment_total_key:raise HTTPException(409,'选定的项目总价已变化，请重新选择')
        if selected is None:selected=next((item for item in totals if item['currency']==payload.full_payment_currency and Decimal(item['amount'])==payload.full_payment_amount),None)
        matched=bool(selected and selected['currency']==payload.full_payment_currency and Decimal(selected['amount'])==payload.full_payment_amount)
        if not matched and not payload.mismatch_reason.strip():raise HTTPException(422,'全款金额与项目总价不匹配，请填写原因')
        values['full_payment_total_key']=selected['key'] if selected else None
        values['mismatch_reason']='' if matched else payload.mismatch_reason.strip()
        full={'source':source,'amount':values['full_payment_amount'],'currency':payload.full_payment_currency,'total_key':values['full_payment_total_key'],
              'match_status':'matched' if matched else 'mismatch','mismatch_reason':values['mismatch_reason'],
              'reference_label':selected['label'] if selected else '项目暂无匹配总价','reference_amount':selected['amount'] if selected else None}
        if unchanged and before['full_match_status']==full['match_status'] and before['full_reference_amount']==full['reference_amount'] and before['full_payment_source']==source:return before
    elif unchanged and before['full_match_status']=='none' and not cleared_payments:return before
    from editor_screenshot_service import references,valid_references,ready as screenshots_ready,api_time,now,promote_business_references
    from editor_screenshot_models import EditorScreenshot
    ids=references(payload.proofs)
    if ids:
        if ids!=valid_references(payload.proofs):raise HTTPException(422,'支付截图引用无效，请重新上传')
        if not screenshots_ready(db):raise HTTPException(503,'支付截图存储尚未初始化')
        images=db.query(EditorScreenshot).filter(EditorScreenshot.id.in_(ids)).all()
        if len(images)!=len(ids) or any(not image.blob_sha256 or (image.expires_at and api_time(image.expires_at)<=now()) for image in images):raise HTTPException(422,'支付截图不存在或已过期，请重新上传')
        promote_business_references(db,ids)
    if clearing and cleared_payments:
        from models import FinanceRecord,FinancePayment
        ids=db.query(FinanceRecord.id).filter(FinanceRecord.project_id==project_id)
        db.query(FinancePayment).filter(FinancePayment.finance_id.in_(ids)).delete(synchronize_session=False)
        db.flush()
        for finance in db.query(FinanceRecord).filter(FinanceRecord.project_id==project_id):db.expire(finance,['payments'])
    if row is None:row=TranslationPaymentConfirmation(project_id=project_id,revision=0);db.add(row)
    row.is_paid=payload.is_paid;row.proofs=payload.proofs
    row.payment_option=payload.payment_option
    # 复用既有 Text 存储付款类型及账户，兼容历史纯类型值，无需改表结构。
    if payload.payment_account or full:row.payment_option=json.dumps({'type':payload.payment_option,'account':payload.payment_account,'full_payment':full},ensure_ascii=False)
    row.revision+=1;row.updated_by=actor_id;row.updated_at=business_now();db.flush()
    from models import AppUser
    actor=db.get(AppUser,actor_id) if actor_id else None
    after=read(db,project_id)
    history_before={**before,'payment_details':cleared_payments or []} if clearing else before
    history_after={**after,'payment_details':[],'action':'清除付款选择'} if clearing else after
    db.add(TranslationPaymentConfirmationHistory(id=uuid4(),project_id=project_id,revision=row.revision,actor_id=actor_id,
        actor_name=(actor.full_name or actor.username) if actor else '用户',before=history_before,after=history_after,created_at=business_now()))
    return after


def history(db,project_id,page=1):
    if not ready(db):return {'items':[],'total':0}
    query=db.query(TranslationPaymentConfirmationHistory).filter_by(project_id=project_id)
    return {'total':query.count(),'items':[{'id':str(row.id),'revision':row.revision,'actor_name':row.actor_name,
        'created_at':business_datetime(row.created_at).isoformat(),'before':row.before,'after':row.after}
        for row in query.order_by(TranslationPaymentConfirmationHistory.revision.desc()).offset((page-1)*10).limit(10)]}


def recheck_after_fee_change(db,project_id,actor_id):
    current=read(db,project_id)
    if not current['is_paid'] or (current['payment_option']!='full' and current['full_payment_source']!='details') or current['full_payment_amount'] is None:return current
    totals=project_totals(db,project_id)['items']
    selected=next((item for item in totals if item['key']==current['full_payment_total_key']),None)
    if selected is None:selected=next((item for item in totals if item['currency']==current['full_payment_currency'] and Decimal(item['amount'])==Decimal(current['full_payment_amount'])),None)
    matched=bool(selected and selected['currency']==current['full_payment_currency'] and Decimal(selected['amount'])==Decimal(current['full_payment_amount']))
    status='matched' if matched else 'mismatch'
    if current['full_match_status']==status and current['full_reference_amount']==(selected['amount'] if selected else None):return current
    payload=PaymentConfirmationWrite(**{**current,'full_payment_total_key':selected['key'] if selected else None,
        'mismatch_reason':'' if matched else current['mismatch_reason'] or '项目收费总价变更后不匹配，需重新核对全款金额'})
    return save(db,project_id,payload,actor_id)
