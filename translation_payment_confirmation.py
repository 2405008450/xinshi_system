"""项目付款确认与永久支付凭证，收费窗口和付款明细共用。"""
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Boolean,Column,DateTime,ForeignKey,Integer,JSON,Text,Uuid,inspect
from fastapi import HTTPException
from models import Base,TranslationProject
from annotation_progress_time import business_now,business_datetime


class PaymentConfirmationWrite(BaseModel):
    model_config=ConfigDict(extra='ignore')
    revision:int=Field(default=0,ge=0)
    is_paid:bool=False
    payment_option:Literal['full','deposit','once']|None=None
    proofs:str=Field(default='',max_length=20000)

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
    return {'revision':row.revision if row else 0,'is_paid':bool(row.is_paid) if row else False,
            'payment_option':row.payment_option if row else None,'proofs':row.proofs or '' if row else ''}


def attach(db,projects):
    projects=projects or []
    values={row.project_id:row for row in db.query(TranslationPaymentConfirmation).filter(TranslationPaymentConfirmation.project_id.in_([project.id for project in projects])).all()} if projects and ready(db) else {}
    for project in projects:
        row=values.get(project.id)
        project.payment_confirmation={'revision':row.revision,'is_paid':bool(row.is_paid),'payment_option':row.payment_option,'proofs':row.proofs or ''} if row else PaymentConfirmationWrite().model_dump()


def save(db,project_id,payload,actor_id):
    if payload is None:return read(db,project_id)
    if not ready(db):raise HTTPException(503,'付款确认存储尚未初始化')
    # 所有入口锁同一母订单，状态与既有付款记录不会分别覆盖。
    project=db.query(TranslationProject).filter_by(id=project_id).with_for_update().first()
    if project is None:raise HTTPException(404,'笔译项目不存在')
    row=db.query(TranslationPaymentConfirmation).filter_by(project_id=project_id).with_for_update().populate_existing().first()
    before=read(db,project_id)
    if payload.revision!=before['revision']:raise HTTPException(409,'付款情况已被修改，请重新打开后编辑')
    values=payload.model_dump(exclude={'revision'})
    if values=={key:before[key] for key in values}:return before
    from editor_screenshot_service import references,valid_references,ready as screenshots_ready,api_time,now,promote_business_references
    from editor_screenshot_models import EditorScreenshot
    ids=references(payload.proofs)
    if ids:
        if ids!=valid_references(payload.proofs):raise HTTPException(422,'支付截图引用无效，请重新上传')
        if not screenshots_ready(db):raise HTTPException(503,'支付截图存储尚未初始化')
        images=db.query(EditorScreenshot).filter(EditorScreenshot.id.in_(ids)).all()
        if len(images)!=len(ids) or any(not image.blob_sha256 or (image.expires_at and api_time(image.expires_at)<=now()) for image in images):raise HTTPException(422,'支付截图不存在或已过期，请重新上传')
        promote_business_references(db,ids)
    if row is None:row=TranslationPaymentConfirmation(project_id=project_id,revision=0);db.add(row)
    for key,value in values.items():setattr(row,key,value)
    row.revision+=1;row.updated_by=actor_id;row.updated_at=business_now();db.flush()
    from models import AppUser
    actor=db.get(AppUser,actor_id) if actor_id else None
    after=read(db,project_id)
    db.add(TranslationPaymentConfirmationHistory(id=uuid4(),project_id=project_id,revision=row.revision,actor_id=actor_id,
        actor_name=(actor.full_name or actor.username) if actor else '用户',before=before,after=after,created_at=business_now()))
    return after


def history(db,project_id,page=1):
    if not ready(db):return {'items':[],'total':0}
    query=db.query(TranslationPaymentConfirmationHistory).filter_by(project_id=project_id)
    return {'total':query.count(),'items':[{'id':str(row.id),'revision':row.revision,'actor_name':row.actor_name,
        'created_at':business_datetime(row.created_at).isoformat(),'before':row.before,'after':row.after}
        for row in query.order_by(TranslationPaymentConfirmationHistory.revision.desc()).offset((page-1)*10).limit(10)]}
