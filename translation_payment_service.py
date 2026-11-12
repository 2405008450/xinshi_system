"""复用既有财务收款记录，两处入口共享；不创建第二份付款数据。"""
from collections import Counter
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
    proofs: str = Field(default='',max_length=20000)


class ProjectPaymentRead(ProjectPayment):
    confirmed_by: UUID | None = None
    confirmed_by_name: str | None = None
    confirmed_at: datetime | None = None


class PaymentWrite(BaseModel):
    version: str
    payments: list[ProjectPayment] = Field(max_length=100)
    confirmation:PaymentConfirmationWrite|None=None

    @model_validator(mode='after')
    def distinct_rows(self):
        ids = [row.id for row in self.payments if row.id]
        if len(set(ids)) != len(ids):
            raise ValueError('付款记录不能重复')
        return self


class PaymentConfirm(BaseModel):
    version: str
    payment_id: UUID | None = None


def confirm(db, project, payload, actor):
    from hr_access import can_manage_hr
    if not can_manage_hr(db,actor):
        raise HTTPException(403,'仅行政部人员可确认付款')
    current=read(db,project)
    if payload.version!=current['version']:
        raise HTTPException(409,'付款情况已变化，请重新打开后确认')
    state=current['confirmation']
    if payload.payment_id is None:
        if not state['is_paid'] or state['payment_option']!='full' or state['full_payment_amount'] is None:
            raise HTTPException(422,'请先保存已付全款金额，再确认')
        confirmations.save(db,project.id,PaymentConfirmationWrite(**state),actor.id,confirm_full=True)
        return read(db,project)

    row=db.query(FinancePayment).join(FinanceRecord).filter(
        FinancePayment.id==payload.payment_id,FinanceRecord.project_id==project.id,
    ).first()
    if row is None:raise HTTPException(404,'当前项目没有该付款明细')
    if row.actual_amount is None:raise HTTPException(422,'请先保存实际付款金额，再确认')
    if not confirmations.ready(db):raise HTTPException(503,'付款确认存储尚未初始化')
    row.confirmed_by=actor.id
    row.confirmed_at=business_now().replace(tzinfo=None)
    db.flush()
    db.expire(row,['confirmer'])
    result=read(db,project)
    confirmations.append_history(db,project.id,state['revision'],actor,
        {**state,'payment_details':current['payments']},
        {**state,'payment_details':result['payments'],'action':'确认付款明细'})
    return result


def _date(value):
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
    return value


def confirmation_fields(row):
    return {
        'confirmed_by': row.confirmed_by,
        'confirmed_by_name': (row.confirmer.full_name or row.confirmer.username) if row.confirmer else None,
        'confirmed_at': business_datetime(row.confirmed_at),
    }


def read(db, project):
    finance = db.query(FinanceRecord).filter_by(project_id=project.id).first()
    rows = sorted(finance.payments, key=lambda row: row.stage_no) if finance else []
    if any(row.stage_no != index for index, row in enumerate(rows, 1)):
        # 旧记录按阶段分别编号，读取时合并为连续期次。
        stages = {'deposit': 0, 'mid': 1, 'final': 2}
        rows.sort(key=lambda row: (stages.get(row.stage_type, 3), row.stage_no, str(row.id)))
    confirmation=confirmations.read(db,project.id)
    positions={key:index for index,key in enumerate(confirmation.get('payment_detail_order',[]))}
    if positions:
        rows.sort(key=lambda row: positions.get(str(row.id),len(positions)))
    proof_map=confirmation.get('payment_details_proofs',{})
    values = [ProjectPaymentRead(id=row.id,stage_type=row.stage_type,stage_no=index+1,
        planned_amount=Decimal(row.planned_amount).quantize(Decimal('.01')) if row.planned_amount is not None else None,
        actual_amount=Decimal(row.actual_amount).quantize(Decimal('.01')) if row.actual_amount is not None else None,
        payment_time=business_datetime(row.payment_time) if row.payment_time else None,payment_method=row.payment_method,
        proofs=proof_map.get(str(row.id),confirmation.get('proofs','') if index==0 else ''),
        **confirmation_fields(row)).model_dump(mode='json') for index,row in enumerate(rows)]
    version = hashlib.sha256(json.dumps([str(finance.id) if finance else None,values,confirmation,
        [(str(row.confirmed_by),str(row.confirmed_at),str(row.updated_at)) for row in rows]],sort_keys=True).encode()).hexdigest()
    return dict(project_id=project.id,order_no=project.order_no,project_name=project.source_file_name or project.project_name,version=version,payments=values,confirmation=confirmation)


def _sync_confirmation(db,project,payments,actor_id,confirmation=None,cleared_payments=None,detail_proofs=None,payment_details_before=None,payment_details_after=None):
    current=confirmations.read(db,project.id)
    desired=confirmation or PaymentConfirmationWrite(**current)
    if not (desired.is_paid and desired.payment_option=='full'):
        actual=[row for row in payments if row.actual_amount is not None and row.actual_amount>0]
        if payments:
            methods=list(dict.fromkeys(row.payment_method.strip() for row in actual if row.payment_method and row.payment_method.strip()))
            desired=desired.model_copy(update={'is_paid':True,'payment_option':'deposit','payment_account':methods[0] if len(methods)==1 else '' if methods else desired.payment_account})
        elif confirmation is None:
            desired=desired.model_copy(update={'is_paid':False,'payment_option':None})
    if payments and desired.is_paid and desired.payment_option!='full':desired=desired.model_copy(update={'proofs':payments[0].proofs})
    return confirmations.save(db,project.id,desired,actor_id,cleared_payments=cleared_payments,detail_proofs=detail_proofs,
        payment_details_before=payment_details_before,payment_details_after=payment_details_after,
        detail_order=[row['id'] for row in payment_details_after] if payment_details_after is not None else None)


def save(db, project, payments, version, actor_id, confirmation=None):
    current = read(db, project)
    if version is not None and version != current['version']:
        # 清空为幂等操作：旧窗口再次提交已完成的清空，不误报外部修改。
        # 只有服务器确实无付款数据时才允许；新登记的付款仍受版本保护。
        if not current['payments'] and confirmations.already_cleared(confirmation,current['confirmation']):return current
        raise HTTPException(409, '付款情况已被修改，请重新打开后编辑')
    cleared_payments=None
    if confirmation is not None and confirmation.replace_details:
        cleared_payments=current['payments']
    if confirmation is not None and not confirmation.is_paid:
        cleared_payments=current['payments'];payments=[]
    if confirmation is not None and confirmation.is_paid and confirmation.payment_option=='full':
        # 只有明确确认切换的请求允许清除原分期明细，并由确认历史留存。
        confirmations.save(db,project.id,confirmation,actor_id)
        return read(db,project)
    ids=[row.id for row in payments if row.id]
    if len(set(ids))!=len(ids):
        raise HTTPException(422,'付款记录不能重复')
    stages=Counter(row.stage_type for row in payments)
    if stages['deposit']>1 or stages['final']>1:
        raise HTTPException(422,'定金和尾款各可登记一笔，其他分次付款请选择中期款')
    # 主项目调用方与独立接口均锁定同一项目；既有财务记录也加锁。
    finance = db.query(FinanceRecord).filter_by(project_id=project.id).with_for_update().first()
    if finance is not None and version is None:
        raise HTTPException(422, '请先加载当前付款情况，再保存修改')
    if finance is None and not payments:
        if confirmation is not None:_sync_confirmation(db,project,payments,actor_id,confirmation,cleared_payments)
        return read(db,project)
    now = business_now().replace(tzinfo=None)
    if finance is None:
        finance = FinanceRecord(id=uuid4(),project_id=project.id,invoice_status='unissued',created_at=now,updated_at=now)
        db.add(finance);db.flush()
    existing = {row.id:row for row in finance.payments}
    previous_details={row['id']:row for row in current['payments']}
    if any(row.id and row.id not in existing for row in payments):
        raise HTTPException(422, '付款记录不属于当前项目')
    # 全量明细同事务替换并保留记录 ID，支持交换阶段/期次而不触发中间唯一冲突。
    for row in existing.values():
        db.delete(row)
    db.flush()
    proof_map={};saved_details=[];normalized=[]
    stage_numbers=Counter()
    for index,item in enumerate(payments):
        # 未携带新字段的旧客户端保留原凭证；新版显式空字符串表示清除。
        if 'proofs' not in item.model_fields_set:
            proof=(confirmation.proofs if index==0 and confirmation is not None and 'proofs' in confirmation.model_fields_set else previous_details.get(str(item.id),{}).get('proofs',''))
            item=item.model_copy(update={'proofs':proof})
        normalized.append(item)
        previous = existing.get(item.id)
        data = item.model_dump(exclude={'id','proofs'})
        # 数据库按阶段编号，窗口期次按全部付款的顺序显示。
        stage_numbers[item.stage_type] += 1
        data['stage_no'] = stage_numbers[item.stage_type]
        data['payment_time'] = _date(item.payment_time)
        changed = previous is None or any(
            getattr(previous,key,None)!=value for key,value in data.items() if key != 'stage_no'
        ) or item.proofs!=previous_details.get(str(item.id),{}).get('proofs','')
        confirmed_by = previous.confirmed_by if previous else None
        confirmed_at = previous.confirmed_at if previous else None
        if item.actual_amount is None or changed:
            confirmed_by = confirmed_at = None
        row = FinancePayment(id=item.id or uuid4(),finance_id=finance.id,
            created_at=previous.created_at if previous else now,
            updated_at=now if changed else previous.updated_at,
            confirmed_by=confirmed_by,confirmed_at=confirmed_at,**data)
        db.add(row)
        proof_map[str(row.id)]=item.proofs
        snapshot={**data,'stage_no':index+1,'payment_time':business_datetime(row.payment_time) if row.payment_time else None}
        for key in ('planned_amount','actual_amount'):
            if snapshot[key] is not None:snapshot[key]=Decimal(snapshot[key]).quantize(Decimal('.01'))
        saved_details.append((row, snapshot, item.proofs))
    finance.edited_by=actor_id;finance.updated_at=now
    db.flush();db.expire(finance,['payments'])
    snapshots = [ProjectPaymentRead(id=row.id, **values, proofs=proofs, **confirmation_fields(row)).model_dump(mode='json')
                 for row, values, proofs in saved_details]
    _sync_confirmation(db,project,normalized,actor_id,confirmation,cleared_payments,detail_proofs=proof_map,
        payment_details_before=current['payments'],payment_details_after=snapshots)
    return read(db, project)
