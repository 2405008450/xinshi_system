"""标注、招聘客户财务：复用项目报价，单独记录修改前后快照。"""
import hashlib
import json
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Uuid, or_, func
from sqlalchemy.orm import selectinload

from annotation_models import AnnotationProject, AnnotationProjectPriceItem
from annotation_schemas import AnnotationPriceItemInput
from annotation_progress_time import business_now, business_datetime
from database import get_db
from models import Base, Client, SubClient
from recruitment_models import RecruitmentProject
from routers.auth import require_module_access
from search_matching import keyword_any
from tax_prices import TaxPrices

Module = Literal['annotation', 'recruitment']
MODELS = {'annotation': AnnotationProject, 'recruitment': RecruitmentProject}


class ProjectCustomerFinanceHistory(Base):
    __tablename__ = 'project_customer_finance_history'
    id = Column(Uuid, primary_key=True, default=uuid4)
    module = Column(String(20), nullable=False, index=True)
    project_id = Column(Uuid, nullable=False, index=True)
    order_no = Column(String(50), nullable=False)
    actor_id = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    actor_name = Column(String(255), nullable=False)
    before = Column(JSON, nullable=False)
    after = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


class FinanceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: str
    prices: list[AnnotationPriceItemInput] | None = Field(default=None, max_length=100)
    tax_prices: TaxPrices | None = None
    currency: str = Field(default='CNY', pattern=r'^[A-Z]{3}$')


access = require_module_access('projects:read', 'projects:write')
router = APIRouter(prefix='/project-customer-finance', tags=['项目客户财务'])


def project_query(db, module):
    model = MODELS[module]
    query = db.query(model).options(selectinload(model.client), selectinload(model.sub_client))
    if module == 'annotation':
        query = query.options(*[selectinload(model.price_items).selectinload(relation) for relation in (
            AnnotationProjectPriceItem.tax_record, AnnotationProjectPriceItem.source_language, AnnotationProjectPriceItem.target_language)])
    return query


def owner(db, module, project_id, lock=False):
    model = MODELS[module]
    query = project_query(db, module).filter(model.id == project_id)
    if lock:
        query = query.with_for_update(of=model).populate_existing()
    project = query.first()
    if not project:
        raise HTTPException(404, '项目不存在')
    return project


def prices(project):
    return [dict(id=str(row.id), project_type=row.project_type, amount=format(Decimal(row.amount), '.6f'), currency=row.currency or 'CNY',
                 unit=row.unit, source_language_id=str(row.source_language_id) if row.source_language_id else None,
                 target_language_id=str(row.target_language_id) if row.target_language_id else None,
                 remarks=row.remarks, language_display=row.language_display, tax_prices=tax_snapshot(row.tax_prices))
            for row in project.price_items]


def tax_snapshot(value):
    return None if value is None else {key: format(Decimal(amount), '.6f' if key.startswith('unit_') else '.2f')
                                      if amount is not None else None for key, amount in value.items()}


def snapshot(module, project):
    if module == 'annotation':
        return {'prices': prices(project)}
    return {'tax_prices': tax_snapshot(project.tax_prices), 'currency': project.service_fee_currency or 'CNY',
            'legacy_amount': format(Decimal(project.service_fee_amount), '.6f') if project.service_fee_amount is not None else None,
            'service_fee_type': project.service_fee_type}


def version(module, project):
    def canonical(value):
        if isinstance(value, list):
            return [canonical(item) for item in value]
        if isinstance(value, dict):
            return {key: format(Decimal(item).normalize(), 'f') if item is not None and key in
                    {'amount', 'legacy_amount', *TaxPrices.model_fields} else canonical(item) for key, item in value.items()}
        return value
    value = [str(project.id), str(project.client_id), str(project.sub_client_id), str(project.updated_at), canonical(snapshot(module, project))]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def serialize(module, project):
    client = project.client or (project.sub_client.parent_client if project.sub_client else None)
    return dict(id=str(project.id), module=module, order_no=project.order_no, project_name=project.project_name,
                client_id=str(client.id) if client else None, client_name=(client.client_short_name or client.client_name) if client else None,
                project_status=project.project_status, project_types=list(project.project_types or []) if module == 'annotation' else [],
                version=version(module, project), **snapshot(module, project), **totals(module, [project]))


def totals(module, projects):
    result = {'excl_tax': {}, 'incl_tax': {}}
    missing = {'excl_tax': 0, 'incl_tax': 0}
    for project in projects:
        entries = [(row.currency or 'CNY', row.tax_prices) for row in project.price_items] if module == 'annotation' else [(project.service_fee_currency or 'CNY', project.tax_prices)]
        for currency, values in entries:
            for kind, amounts in result.items():
                value = (values or {}).get('total_' + kind)
                if value is None:
                    missing[kind] += 1
                else:
                    amounts[currency] = amounts.get(currency, Decimal(0)) + Decimal(value)
    return {'totals_' + kind: {currency: str(value) for currency, value in amounts.items()} for kind, amounts in result.items()} | {'missing_totals': missing}


@router.get('/{module}/page')
def read_page(module: Module, client_id: UUID | None = None, keyword: str = '', skip: int = Query(0, ge=0),
              limit: int = Query(10, ge=1, le=100), db=Depends(get_db), user=Depends(access)):
    model = MODELS[module]
    query = project_query(db, module).outerjoin(SubClient, model.sub_client_id == SubClient.id).outerjoin(Client, func.coalesce(model.client_id, SubClient.parent_client_id) == Client.id)
    if client_id:
        query = query.filter(or_(model.client_id == client_id, SubClient.parent_client_id == client_id))
    query = query.filter(keyword_any([model.order_no, model.project_name, Client.client_name, Client.client_short_name,
                                      SubClient.client_name, SubClient.client_short_name], keyword))
    # 金额小计和列表使用同一筛选；分别按币种和税口径汇总，不重复统计其他客户。
    projects = query.order_by(model.order_no.desc(), model.id.desc()).all()
    return dict(items=[serialize(module, row) for row in projects[skip:skip+limit]], total=len(projects), **totals(module, projects))


@router.get('/{module}/project/{project_id}')
def read_project(module: Module, project_id: UUID, db=Depends(get_db), user=Depends(access)):
    return serialize(module, owner(db, module, project_id))


def update_annotation(db, project, values):
    if values is None:
        raise HTTPException(422, '请提交客户报价明细')
    ids = [row.id for row in values if row.id]
    current = {row.id: row for row in project.price_items}
    if len(ids) != len(set(ids)) or set(ids) - set(current):
        raise HTTPException(422, '报价明细包含重复或不属于当前项目的记录')
    for value in values:
        if value.project_type and value.project_type not in (project.project_types or []):
            raise HTTPException(422, '标注类型必须来自当前项目已选择的项目类型')
        previous = current.get(value.id)
        if previous and (value.source_language_id, value.target_language_id) != (previous.source_language_id, previous.target_language_id):
            raise HTTPException(422, '请在项目管理中修改报价的语言范围')
        if not previous and (value.source_language_id or value.target_language_id):
            raise HTTPException(422, '请在项目管理中维护语言范围报价')
    for index, row in enumerate(project.price_items):
        row.sequence_no = 1_000_000 + index
    db.flush()
    retained = set(ids)
    for row in list(project.price_items):
        if row.id not in retained:
            project.price_items.remove(row)
    for index, value in enumerate(values, 1):
        row = current.get(value.id)
        if row is None:
            row = AnnotationProjectPriceItem(id=uuid4(), project_id=project.id)
            project.price_items.append(row)
        row.sequence_no = index
        for key, amount in value.model_dump(exclude={'id'}).items():
            setattr(row, key, amount)


@router.put('/{module}/project/{project_id}')
def save_project(module: Module, project_id: UUID, data: FinanceWrite, db=Depends(get_db), user=Depends(access)):
    try:
        if module == 'annotation':
            from annotation_service import _lock_annotation_order_numbers
            _lock_annotation_order_numbers(db)
        project = owner(db, module, project_id, lock=True)
        if data.version != version(module, project):
            raise HTTPException(409, '项目财务已更新，请重新打开后编辑')
        before = snapshot(module, project)
        if module == 'annotation':
            from annotation_inheritance_service import snapshot as inheritance_snapshot, finish_inline_change
            inheritance_before = inheritance_snapshot(project)
            update_annotation(db, project, data.prices)
            db.flush()
            finish_inline_change(db, project, inheritance_before, user.id)
        else:
            if data.tax_prices is None or data.prices is not None:
                raise HTTPException(422, '请提交招聘项目的税口径金额')
            project.tax_prices = data.tax_prices
            project.service_fee_currency = data.currency
        project.updated_at = business_now().replace(tzinfo=None)
        db.flush()
        after = snapshot(module, project)
        if before != after:
            db.add(ProjectCustomerFinanceHistory(module=module, project_id=project.id, order_no=project.order_no,
                       actor_id=user.id, actor_name=user.full_name or user.username, before=before, after=after))
        db.commit()
        return serialize(module, project)
    except Exception:
        db.rollback()
        raise


@router.get('/{module}/project/{project_id}/history')
def read_history(module: Module, project_id: UUID, page: int = Query(1, ge=1), db=Depends(get_db), user=Depends(access)):
    owner(db, module, project_id)
    query = db.query(ProjectCustomerFinanceHistory).filter_by(module=module, project_id=project_id)
    total = query.count()
    rows = query.order_by(ProjectCustomerFinanceHistory.created_at.desc(), ProjectCustomerFinanceHistory.id.desc()).offset((page-1)*10).limit(10).all()
    return dict(total=total, items=[dict(id=str(row.id), actor_name=row.actor_name,
                created_at=business_datetime(row.created_at).isoformat(), before=row.before, after=row.after) for row in rows])
