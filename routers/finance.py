from typing import List, Optional
from uuid import UUID
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import FinanceRecord, FinancePayment, TranslationProject, Client, AppUser, Consultation
from schemas import (
    FinanceRecordCreate, FinanceRecordUpdate, FinanceRecordResponse,
    FinancePaymentCreate, FinancePaymentResponse,
    FinanceRecordDisplayResponse,
    FinanceEntryPayload, FinanceEntryResponse
)
from routers.auth import require_module_access
from crud import generate_consultation_code

router = APIRouter(prefix="/finance", tags=["财务管理"], dependencies=[Depends(require_module_access("finance:read", "finance:write"))])


# ---------- 辅助函数 ---------- #

def _build_display_item(row, db: Session) -> dict:
    """把一条 FinanceRecord 组装成 FinanceRecordDisplayResponse 所需的 dict"""
    fr: FinanceRecord = row[0]
    order_no = row[1]
    client_short_name = row[2]
    project_name = row[3]
    project_status = row[4]
    customer_reception_time = row[5]

    # 获取人员名称
    sales_person_name = None
    follow_up_person_name = None
    if fr.sales_person_id:
        user = db.query(AppUser).filter(AppUser.id == fr.sales_person_id).first()
        if user:
            sales_person_name = user.full_name or user.username
    if fr.follow_up_person_id:
        user = db.query(AppUser).filter(AppUser.id == fr.follow_up_person_id).first()
        if user:
            follow_up_person_name = user.full_name or user.username

    return {
        "finance_id": fr.id,
        "project_id": fr.project_id,
        "order_no": order_no,
        "client_short_name": client_short_name,
        "project_name": project_name,
        "project_status": project_status,
        "customer_reception_time": customer_reception_time,
        "settlement_method": fr.settlement_method,
        "unit_price_excl_tax": float(fr.unit_price_excl_tax) if fr.unit_price_excl_tax is not None else None,
        "unit_price_incl_tax": float(fr.unit_price_incl_tax) if fr.unit_price_incl_tax is not None else None,
        "total_excl_tax": float(fr.total_excl_tax) if fr.total_excl_tax is not None else None,
        "total_incl_tax": float(fr.total_incl_tax) if fr.total_incl_tax is not None else None,
        "invoice_status": fr.invoice_status,
        "remarks": fr.remarks,
        "edited_by": fr.edited_by,
        "created_at": fr.created_at,
        "updated_at": fr.updated_at,
        "payments": fr.payments,
        "sales_person_id": fr.sales_person_id,
        "follow_up_person_id": fr.follow_up_person_id,
        "sales_person_name": sales_person_name,
        "follow_up_person_name": follow_up_person_name,
    }


def _base_display_query(db: Session):
    """构建展示查询（联表）"""
    return db.query(
        FinanceRecord,
        TranslationProject.order_no,
        Client.client_short_name,
        TranslationProject.project_name,
        TranslationProject.project_status,
        TranslationProject.customer_reception_time,
    ).join(
        TranslationProject, TranslationProject.id == FinanceRecord.project_id
    ).outerjoin(
        Client, Client.id == TranslationProject.client_id
    )


# ---------- 接口 ---------- #

@router.get("/", response_model=List[FinanceRecordDisplayResponse])
def list_finance_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    invoice_status: Optional[str] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取财务记录列表（带项目/客户信息）"""
    query = _base_display_query(db)
    if invoice_status:
        query = query.filter(FinanceRecord.invoice_status == invoice_status)
    if project_name:
        query = query.filter(TranslationProject.project_name.ilike(f"%{project_name}%"))
    if order_no:
        query = query.filter(TranslationProject.order_no.ilike(f"%{order_no}%"))

    rows = query.order_by(FinanceRecord.updated_at.desc()).offset(skip).limit(limit).all()
    return [_build_display_item(row, db) for row in rows]


@router.get("/count")
def count_finance_records(
    invoice_status: Optional[str] = None,
    project_name: Optional[str] = None,
    order_no: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取财务记录总数"""
    query = db.query(FinanceRecord.id).join(
        TranslationProject, TranslationProject.id == FinanceRecord.project_id
    )
    if invoice_status:
        query = query.filter(FinanceRecord.invoice_status == invoice_status)
    if project_name:
        query = query.filter(TranslationProject.project_name.ilike(f"%{project_name}%"))
    if order_no:
        query = query.filter(TranslationProject.order_no.ilike(f"%{order_no}%"))
    return {"total": query.count()}


@router.get("/by-project/{project_id}", response_model=FinanceRecordDisplayResponse)
def get_finance_by_project(project_id: UUID, db: Session = Depends(get_db)):
    """按项目 ID 获取财务记录"""
    row = _base_display_query(db).filter(FinanceRecord.project_id == project_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="该项目暂无财务记录")
    return _build_display_item(row, db)


@router.get("/{finance_id}", response_model=FinanceRecordDisplayResponse)
def get_finance_record(finance_id: UUID, db: Session = Depends(get_db)):
    """按 ID 获取单条财务记录"""
    row = _base_display_query(db).filter(FinanceRecord.id == finance_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="财务记录不存在")
    return _build_display_item(row, db)


@router.post("/entry", response_model=FinanceEntryResponse, status_code=201)
def finance_entry(payload: FinanceEntryPayload, db: Session = Depends(get_db)):
    """
    4步表单综合录入接口：
    1. 新建/复用咨询记录
    2. 新建/复用翻译项目（可携带原文路径）
    3. 新建财务记录（含款项明细）
    """
    consultation_id = payload.consultation_id
    project_id = payload.project_id
    finance_id = None

    # ---------- 第1步：咨询 ----------
    if consultation_id:
        # 校验存在
        if not db.query(Consultation).filter(Consultation.id == consultation_id).first():
            raise HTTPException(status_code=404, detail="咨询记录不存在")
    elif payload.consultation:
        c_data = payload.consultation.model_dump()
        if not c_data.get("consultation_code"):
            c_data["consultation_code"] = generate_consultation_code(db)
        db_c = Consultation(**c_data)
        db.add(db_c)
        db.flush()
        consultation_id = db_c.id

    # ---------- 第2步：项目 ----------
    if project_id:
        proj = db.query(TranslationProject).filter(TranslationProject.id == project_id).first()
        if not proj:
            raise HTTPException(status_code=404, detail="翻译项目不存在")
        # 若传了路径则更新
        if payload.source_file_path is not None:
            proj.client_feedback = payload.source_file_path
            db.flush()
    elif payload.project:
        p_data = payload.project.model_dump()
        if not p_data.get("order_no"):
            p_data["order_no"] = f"P{uuid_lib.uuid4().hex[:8].upper()}"
        if payload.source_file_path:
            p_data["client_feedback"] = payload.source_file_path
        db_p = TranslationProject(**p_data)
        db.add(db_p)
        db.flush()
        project_id = db_p.id

    # ---------- 第3步：财务 ----------
    if payload.finance and project_id:
        existing = db.query(FinanceRecord).filter(FinanceRecord.project_id == project_id).first()
        if existing:
            finance_data = payload.finance.model_dump(exclude={"payments", "project_id"})
            for k, v in finance_data.items():
                if v is not None:
                    setattr(existing, k, v)
            if payload.finance.payments is not None:
                db.query(FinancePayment).filter(FinancePayment.finance_id == existing.id).delete()
                for p in payload.finance.payments:
                    db.add(FinancePayment(finance_id=existing.id, **p.model_dump()))
            db.flush()
            finance_id = existing.id
        else:
            finance_data = payload.finance.model_dump(exclude={"payments"})
            finance_data["project_id"] = project_id
            db_fr = FinanceRecord(**finance_data)
            db.add(db_fr)
            db.flush()
            for p in (payload.finance.payments or []):
                db.add(FinancePayment(finance_id=db_fr.id, **p.model_dump()))
            finance_id = db_fr.id

    db.commit()
    return FinanceEntryResponse(
        consultation_id=consultation_id,
        project_id=project_id,
        finance_id=finance_id,
        detail="录入成功",
    )


@router.post("/", response_model=FinanceRecordResponse, status_code=201)
def create_finance_record(payload: FinanceRecordCreate, db: Session = Depends(get_db)):
    """创建财务记录（含款项明细）"""
    # 检查项目是否存在
    project = db.query(TranslationProject).filter(TranslationProject.id == payload.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="关联项目不存在")

    # 检查是否已有财务记录
    existing = db.query(FinanceRecord).filter(FinanceRecord.project_id == payload.project_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="该项目已有财务记录，请使用更新接口")

    record_data = payload.model_dump(exclude={"payments"})
    db_record = FinanceRecord(**record_data)
    db.add(db_record)
    db.flush()  # 获取 id

    # 批量写入款项
    for p in (payload.payments or []):
        db_payment = FinancePayment(finance_id=db_record.id, **p.model_dump())
        db.add(db_payment)

    db.commit()
    db.refresh(db_record)
    # 显式加载 payments，避免序列化时 lazy load 失败
    _ = db_record.payments
    return db_record


@router.put("/entry/{finance_id}", response_model=FinanceEntryResponse)
def finance_entry_update(finance_id: UUID, payload: FinanceEntryPayload, db: Session = Depends(get_db)):
    """4步表单综合更新接口（基于已有 finance_id）"""
    db_record = db.query(FinanceRecord).filter(FinanceRecord.id == finance_id).first()
    if not db_record:
        raise HTTPException(status_code=404, detail="财务记录不存在")

    project_id = db_record.project_id
    consultation_id = payload.consultation_id

    if payload.consultation and consultation_id:
        db_c = db.query(Consultation).filter(Consultation.id == consultation_id).first()
        if db_c:
            for k, v in payload.consultation.model_dump(exclude_unset=True).items():
                setattr(db_c, k, v)

    if payload.project:
        db_p = db.query(TranslationProject).filter(TranslationProject.id == project_id).first()
        if db_p:
            for k, v in payload.project.model_dump(exclude_unset=True, exclude={"order_no"}).items():
                setattr(db_p, k, v)
    if payload.source_file_path is not None:
        db_p = db.query(TranslationProject).filter(TranslationProject.id == project_id).first()
        if db_p:
            db_p.client_feedback = payload.source_file_path

    if payload.finance:
        finance_data = payload.finance.model_dump(exclude_unset=True, exclude={"payments", "project_id"})
        for k, v in finance_data.items():
            setattr(db_record, k, v)
        if payload.finance.payments is not None:
            db.query(FinancePayment).filter(FinancePayment.finance_id == finance_id).delete()
            for p in payload.finance.payments:
                db.add(FinancePayment(finance_id=finance_id, **p.model_dump()))

    db.commit()
    return FinanceEntryResponse(
        consultation_id=consultation_id,
        project_id=project_id,
        finance_id=finance_id,
        detail="更新成功",
    )


@router.put("/{finance_id}", response_model=FinanceRecordResponse)
def update_finance_record(finance_id: UUID, payload: FinanceRecordUpdate, db: Session = Depends(get_db)):
    """更新财务记录（含款项明细全量替换）"""
    db_record = db.query(FinanceRecord).filter(FinanceRecord.id == finance_id).first()
    if not db_record:
        raise HTTPException(status_code=404, detail="财务记录不存在")

    update_data = payload.model_dump(exclude_unset=True, exclude={"payments"})
    for field, value in update_data.items():
        setattr(db_record, field, value)

    # 如果传了 payments，则全量替换
    if payload.payments is not None:
        # 删旧
        db.query(FinancePayment).filter(FinancePayment.finance_id == finance_id).delete()
        # 写新
        for p in payload.payments:
            db_payment = FinancePayment(finance_id=finance_id, **p.model_dump())
            db.add(db_payment)

    db.commit()
    db.refresh(db_record)
    # 显式加载 payments，避免序列化时 lazy load 失败
    _ = db_record.payments
    return db_record


@router.delete("/{finance_id}")
def delete_finance_record(finance_id: UUID, db: Session = Depends(get_db)):
    """删除财务记录（级联删除款项）"""
    db_record = db.query(FinanceRecord).filter(FinanceRecord.id == finance_id).first()
    if not db_record:
        raise HTTPException(status_code=404, detail="财务记录不存在")
    db.delete(db_record)
    db.commit()
    return {"detail": "删除成功"}
