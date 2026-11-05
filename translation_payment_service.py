"""复用既有财务收款记录，两处入口共享；不创建第二份付款数据。"""
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid4
import hashlib
import json
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from models import FinanceRecord, FinancePayment
from annotation_progress_time import business_now, business_datetime
from translation_payment_confirmation import PaymentConfirmationWrite
import translation_payment_confirmation as confirmations


class ProjectPayment(BaseModel):
    id: UUID | None = None
    stage_type: Literal['deposit', 'mid', 'final'] = 'deposit'
    stage_no: int = Field(default=1, ge=1, le=999)
    planned_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    actual_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    payment_time: datetime | None = None
    payment_method: str | None = Field(default=None, max_length=50)


class PaymentWrite(BaseModel):
    version: str
    payments: list[ProjectPayment] = Field(max_length=100)
    confirmation:PaymentConfirmationWrite|None=None

    @model_validator(mode='after')
    def distinct_rows(self):
        stages = [(row.stage_type,row.stage_no) for row in self.payments]
        ids = [row.id for row in self.payments if row.id]
        if len(set(stages)) != len(stages) or len(set(ids)) != len(ids):
            raise ValueError('付款阶段及期次、付款记录不能重复')
        return self


def _date(value):
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
    return value


def read(db, project):
    finance = db.query(FinanceRecord).filter_by(project_id=project.id).first()
    rows = sorted(finance.payments, key=lambda row:(row.stage_type,row.stage_no,str(row.id))) if finance else []
    values = [ProjectPayment(id=row.id,stage_type=row.stage_type,stage_no=row.stage_no,
        planned_amount=Decimal(row.planned_amount).quantize(Decimal('.01')) if row.planned_amount is not None else None,
        actual_amount=Decimal(row.actual_amount).quantize(Decimal('.01')) if row.actual_amount is not None else None,
        payment_time=business_datetime(row.payment_time) if row.payment_time else None,payment_method=row.payment_method).model_dump(mode='json') for row in rows]
    confirmation=confirmations.read(db,project.id)
    version = hashlib.sha256(json.dumps([str(finance.id) if finance else None,values,confirmation,
        [(str(row.confirmed_by),str(row.confirmed_at),str(row.updated_at)) for row in rows]],sort_keys=True).encode()).hexdigest()
    return dict(project_id=project.id,order_no=project.order_no,project_name=project.source_file_name or project.project_name,version=version,payments=values,confirmation=confirmation)


def _sync_confirmation(db,project,payments,actor_id,confirmation=None):
    current=confirmations.read(db,project.id)
    desired=confirmation or PaymentConfirmationWrite(**current)
    if not (desired.is_paid and desired.payment_option=='full'):
        actual=[row for row in payments if row.actual_amount is not None and row.actual_amount>0]
        if actual or any(row.stage_type=='final' for row in payments):
            methods=list(dict.fromkeys(row.payment_method.strip() for row in actual if row.payment_method and row.payment_method.strip()))
            desired=desired.model_copy(update={'is_paid':True,'payment_option':'deposit','payment_account':methods[0] if len(methods)==1 else '' if methods else desired.payment_account})
        elif confirmation is None:
            desired=desired.model_copy(update={'is_paid':False,'payment_option':None})
    return confirmations.save(db,project.id,desired,actor_id)


def save(db, project, payments, version, actor_id, confirmation=None):
    current = read(db, project)
    if version is not None and version != current['version']:
        raise HTTPException(409, '付款情况已被修改，请重新打开后编辑')
    if confirmation is not None and confirmation.is_paid and confirmation.payment_option=='full':
        # 全款确认不要求分期明细，也绝不能清除已有明细。
        confirmations.save(db,project.id,confirmation,actor_id)
        return read(db,project)
    stages=[(row.stage_type,row.stage_no) for row in payments]
    ids=[row.id for row in payments if row.id]
    if len(set(stages))!=len(stages) or len(set(ids))!=len(ids):
        raise HTTPException(422,'付款阶段及期次、付款记录不能重复')
    # 主项目调用方与独立接口均锁定同一项目；既有财务记录也加锁。
    finance = db.query(FinanceRecord).filter_by(project_id=project.id).with_for_update().first()
    if finance is not None and version is None:
        raise HTTPException(422, '请先加载当前付款情况，再保存修改')
    if finance is None and not payments:
        if confirmation is not None:_sync_confirmation(db,project,payments,actor_id,confirmation)
        return read(db,project)
    now = business_now().replace(tzinfo=None)
    if finance is None:
        finance = FinanceRecord(id=uuid4(),project_id=project.id,invoice_status='unissued',created_at=now,updated_at=now)
        db.add(finance);db.flush()
    existing = {row.id:row for row in finance.payments}
    if any(row.id and row.id not in existing for row in payments):
        raise HTTPException(422, '付款记录不属于当前项目')
    # 全量明细同事务替换并保留记录 ID，支持交换阶段/期次而不触发中间唯一冲突。
    for row in existing.values():
        db.delete(row)
    db.flush()
    for item in payments:
        previous = existing.get(item.id)
        data = item.model_dump(exclude={'id'})
        data['payment_time'] = _date(item.payment_time)
        changed = previous is None or any(getattr(previous,key,None)!=value for key,value in data.items())
        row = FinancePayment(id=item.id or uuid4(),finance_id=finance.id,
            created_at=previous.created_at if previous else now,
            updated_at=now if changed else previous.updated_at,
            confirmed_by=None if changed else previous.confirmed_by,
            confirmed_at=None if changed else previous.confirmed_at,**data)
        db.add(row)
    finance.edited_by=actor_id;finance.updated_at=now
    db.flush();db.expire(finance,['payments'])
    _sync_confirmation(db,project,payments,actor_id,confirmation)
    return read(db, project)
