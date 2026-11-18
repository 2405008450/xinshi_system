"""客户对账单设置与笔译对账单；只读取已保存的项目收费，金额按币种分别合计。"""
import base64
import hashlib
import json
import math
import os
import re
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Literal
from uuid import UUID
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Uuid, func, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from models import Base, Client, SubClient, TranslationProject, TranslationSubOrder
from customer_translation_rates import CustomerTranslationRateHistory
from database import get_db
from routers.auth import require_permission, require_any_permission
from annotation_progress_time import business_now, business_datetime
import crud
import translation_customer_finance as finance
from customer_statement_defaults import CustomerStatementDefault, CustomerTranslationFinanceDefault, finance_defaults_ready, write_finance_defaults
from invoice_parties import SUBJECTS, SubjectKey

COMPANIES = tuple(name for _, name in SUBJECTS.values())
COMPANY = COMPANIES[0]
COMPANY_KEYS = {name: key for key, (_, name) in SUBJECTS.items()}
PAYMENT_ACCOUNT_FIELDS = ('bank_name', 'account_name', 'account_number')
PRIVATE_STATEMENT_FIELDS = frozenset((*PAYMENT_ACCOUNT_FIELDS, 'stamp_image'))
MONTH = r'^\d{4}-(0[1-9]|1[0-2])$'
METRICS = {'words':'字数','characters_no_spaces':'字符数（不计空格）','foreign_words':'外文字数',
           'cjk_chars_korean_words':'中朝字数','documents':'份数','pages':'页数'}
WORKLOAD_METRICS = {**METRICS, 'minutes': '分钟', 'hours': '小时'}
read_settings = require_any_permission('clients:read', 'projects:read')
write_settings = require_permission('clients:write')
read_projects = require_permission('projects:read')
router = APIRouter(tags=['客户对账单'])


class CustomerStatementPreference(Base):
    __tablename__ = 'customer_statement_preference'
    client_id = Column(Uuid, ForeignKey('client.id', ondelete='CASCADE'), primary_key=True)
    tax_included = Column(Boolean, nullable=False, default=False)
    revision = Column(Integer, nullable=False, default=1)
    updated_by = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


def load_customer_tax_preferences(db, client_ids):
    cache = db.info.setdefault('customer_statement_tax_preferences', {})
    missing = {client_id for client_id in client_ids if client_id and client_id not in cache}
    if missing:
        cache.update(dict.fromkeys(missing, False))
        cache.update(dict(db.query(CustomerStatementPreference.client_id, CustomerStatementPreference.tax_included)
                          .filter(CustomerStatementPreference.client_id.in_(missing)).all()))
    return cache


class CustomerStatementSettings(Base):
    __tablename__ = 'customer_statement_settings'
    key = Column(String(30), primary_key=True)
    bank_name = Column(String(255), nullable=False, default='')
    account_name = Column(String(255), nullable=False, default='')
    account_number = Column(String(100), nullable=False, default='')
    stamp_image = Column(Text, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    updated_by = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


class CollectionAccountMaterials(Base):
    __tablename__ = 'finance_collection_account_materials'
    key = Column(String(30), ForeignKey('customer_statement_settings.key', ondelete='CASCADE'), primary_key=True)
    notes = Column(Text, nullable=False, default='')
    attachments = Column(JSON, nullable=False, default=list)


class PreferenceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)
    tax_included: bool
    statement_default: Literal['required','not_required','unknown'] | None = None
    payment_method: Literal['individual', 'monthly'] | None = None
    quotation_required: bool | None = None
    invoice_required: bool | None = None


class CustomerStatementCompany(Base):
    __tablename__ = 'customer_statement_company'
    key = Column(String(30), primary_key=True)
    company = Column(String(255), nullable=False)
    updated_by = Column(Uuid, ForeignKey('app_user.id', ondelete='SET NULL'))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=business_now)


class SettingsWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)
    company: Literal['广州信实翻译服务有限公司','广州信实翻译服务有限公司深圳分公司','广州信实翻译服务有限公司上海分公司'] = COMPANY
    bank_name: str = Field(default='', max_length=255)
    account_name: str = Field(default='', max_length=255)
    account_number: str = Field(default='', max_length=100)
    stamp_image: str | None = Field(default=None, max_length=3_000_000)


def png_url(image):
    output = BytesIO(); image.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()


@lru_cache(maxsize=4)
def default_stamp(company=COMPANY):
    """透明底示例章；独立图层覆盖表格线，可由上传的正式章替换。"""
    size=480; image=Image.new('RGBA',(size,size)); draw=ImageDraw.Draw(image); red=(192,24,32,210)
    draw.ellipse((25,25,455,455),outline=red,width=9)
    fonts=[Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
    font_path=next((str(path) for path in fonts if path.exists()),None)
    font=ImageFont.truetype(font_path,32) if font_path else ImageFont.load_default(size=30)
    for index,char in enumerate(company):
        angle=-160+index*140/(len(company)-1)
        radians=math.radians(angle)
        tile=Image.new('RGBA',(70,70));ImageDraw.Draw(tile).text((35,35),char,font=font,fill=red,anchor='mm')
        tile=tile.rotate(-angle-90,resample=Image.Resampling.BICUBIC,expand=True)
        x,y=240+170*math.cos(radians),240+170*math.sin(radians)
        image.alpha_composite(tile,(round(x-tile.width/2),round(y-tile.height/2)))
    points=[(240+(80 if i%2==0 else 32)*math.cos(-math.pi/2+i*math.pi/5),
             247+(80 if i%2==0 else 32)*math.sin(-math.pi/2+i*math.pi/5)) for i in range(10)]
    draw.polygon(points,fill=red);draw.text((240,355),'示例章',font=font,fill=red,anchor='mm')
    return png_url(image.rotate(-9,resample=Image.Resampling.BICUBIC))


def clean_stamp(value):
    if not value:return None
    try:
        prefix,encoded=value.split(',',1)
        if prefix not in ('data:image/png;base64','data:image/jpeg;base64','data:image/webp;base64'):
            raise ValueError()
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>2_000_000:raise ValueError()
        with Image.open(BytesIO(raw)) as image:
            if image.format not in ('PNG','JPEG','WEBP'):raise ValueError()
            if image.width*image.height>16_000_000:raise ValueError()
            image.load();image=image.convert('RGBA');image.thumbnail((1024,1024))
            return png_url(image)
    except (ValueError,UnidentifiedImageError,OSError,Image.DecompressionBombError):
        raise HTTPException(422,'印章请上传不超过2MB的PNG、JPG或WebP图片，建议使用透明底PNG')


def settings_value(row, company=COMPANY):
    return dict(bank_name=row.bank_name if row else '',account_name=row.account_name if row else '',
                account_number=row.account_number if row else '',stamp_image=row.stamp_image if row else None,
                company=company,company_options=list(COMPANIES),default_stamp=default_stamp(company),revision=row.revision if row else 0)


def statement_company_settings(db, subject_key=None):
    legacy = db.get(CustomerStatementCompany, 'company')
    default_company = legacy.company if legacy and legacy.company in COMPANY_KEYS else COMPANY
    company = SUBJECTS[subject_key][1] if subject_key else default_company
    row = db.get(CustomerStatementSettings, 'company' if company == default_company else COMPANY_KEYS[company])
    return row, company


def private_statement_settings_available():
    return os.getenv('APP_ENV', '').strip().lower() == 'production'


def require_private_statement_settings():
    if not private_statement_settings_available():
        raise HTTPException(403, '对账单印章和收款账户仅在 OA 管理')


COLLECTION_ACCOUNT_LIMIT = 8_000_000
COLLECTION_ATTACHMENT_COUNT = 9


class CollectionAccountAttachment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=4, max_length=10_666_668)


class CollectionAccountWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)
    bank_name: str = Field(default='', max_length=255)
    account_name: str = Field(default='', max_length=255)
    account_number: str = Field(default='', max_length=100)
    notes: str = Field(default='', max_length=5000)
    attachments: list[CollectionAccountAttachment] = Field(default_factory=list, max_length=COLLECTION_ATTACHMENT_COUNT)


def require_collection_account(db):
    require_private_statement_settings()
    if not inspect(db.connection()).has_table(CollectionAccountMaterials.__tablename__):
        raise HTTPException(503, '收款账户资料表尚未初始化')


def collection_account_value(account, materials):
    return {
        **{key: getattr(account, key) if account else '' for key in PAYMENT_ACCOUNT_FIELDS},
        'revision': account.revision if account else 0,
        'notes': materials.notes if materials else '',
        'attachments': materials.attachments if materials else [],
    }


@router.get('/finance/collection-account')
def read_collection_account(response: Response, db=Depends(get_db), user=Depends(write_settings)):
    require_collection_account(db)
    response.headers['Cache-Control'] = 'no-store'
    row = (
        db.query(CustomerStatementSettings.revision, CustomerStatementSettings.bank_name,
                 CustomerStatementSettings.account_name, CustomerStatementSettings.account_number,
                 CollectionAccountMaterials)
        .outerjoin(CollectionAccountMaterials, CustomerStatementSettings.key == CollectionAccountMaterials.key)
        .filter(CustomerStatementSettings.key == 'company').first()
    )
    return collection_account_value(row, row.CollectionAccountMaterials if row else None)


@router.put('/finance/collection-account')
def save_collection_account(data: CollectionAccountWrite, response: Response, db=Depends(get_db), user=Depends(write_settings)):
    require_collection_account(db)
    attachments = []
    total_size = 0
    for item in data.attachments:
        name = item.name.replace('\\', '/').rsplit('/', 1)[-1].strip()
        try:
            raw = base64.b64decode(item.content, validate=True)
        except ValueError as exc:
            raise HTTPException(422, '附件数据无效') from exc
        if not name or not raw or any(ord(char) < 32 for char in name):
            raise HTTPException(422, '附件名称或内容无效')
        total_size += len(raw)
        if total_size > COLLECTION_ACCOUNT_LIMIT:
            raise HTTPException(422, '附件合计不得超过 8 MB')
        attachments.append({'name': name, 'content': item.content})

    account = db.query(CustomerStatementSettings).filter_by(key='company').with_for_update().populate_existing().first()
    if data.revision != (account.revision if account else 0):
        raise HTTPException(409, '收款账户已更新，请重新打开后编辑')
    if account is None:
        account = CustomerStatementSettings(key='company', revision=0)
        db.add(account)
    for key in PAYMENT_ACCOUNT_FIELDS:
        setattr(account, key, getattr(data, key).strip())
    account.revision += 1
    account.updated_by = user.id
    account.updated_at = business_now()
    try:
        db.flush()
        materials = db.get(CollectionAccountMaterials, 'company')
        if materials is None:
            materials = CollectionAccountMaterials(key='company')
            db.add(materials)
        materials.notes = data.notes.strip()
        materials.attachments = attachments
        result = collection_account_value(account, materials)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, '收款账户已更新，请重新打开后编辑') from exc
    response.headers['Cache-Control'] = 'no-store'
    return result


@router.get('/customer-statement-settings')
def read_company_settings(db=Depends(get_db),user=Depends(read_settings),subject_key:SubjectKey|None=None):
    require_private_statement_settings()
    return settings_value(*statement_company_settings(db,subject_key))


@router.put('/customer-statement-settings')
def save_company_settings(data:SettingsWrite,db=Depends(get_db),user=Depends(write_settings),subject_key:SubjectKey|None=None):
    require_private_statement_settings()
    _, default_company = statement_company_settings(db)
    company = SUBJECTS[subject_key][1] if subject_key else data.company
    if subject_key and data.company != company:
        raise HTTPException(422,'公司名称与所选主体不一致')
    setting_key = subject_key if subject_key and company != default_company else 'company'
    try:
        row=db.query(CustomerStatementSettings).filter_by(key=setting_key).with_for_update().populate_existing().first()
        if data.revision!=(row.revision if row else 0):raise HTTPException(409,'对账单设置已更新，请重新打开后编辑')
        stamp=clean_stamp(data.stamp_image)
        if row is None:row=CustomerStatementSettings(key=setting_key,revision=0);db.add(row)
        for key in ('bank_name','account_name','account_number'):setattr(row,key,getattr(data,key).strip())
        row.stamp_image=stamp;row.revision+=1;row.updated_at=business_now();row.updated_by=user.id
        if not subject_key and company != default_company:
            if db.get(CustomerStatementSettings,COMPANY_KEYS[company]):
                raise HTTPException(409,'该主体已单独维护，请按主体保存设置')
            subject=db.get(CustomerStatementCompany,'company')
            if subject is None:subject=CustomerStatementCompany(key='company');db.add(subject)
            subject.company=company;subject.updated_by=user.id;subject.updated_at=business_now()
        db.commit();return settings_value(row,company)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'对账单设置已更新，请重新打开后编辑')
    except Exception:
        db.rollback();raise


def client_preference(db,client_id):
    if not db.get(Client,client_id):raise HTTPException(404,'客户不存在')
    row=db.get(CustomerStatementPreference,client_id)
    default=db.get(CustomerStatementDefault,client_id)
    finance_default=db.get(CustomerTranslationFinanceDefault,client_id) if finance_defaults_ready(db) else None
    return dict(tax_included=bool(row.tax_included) if row else False,statement_default=default.choice if default else 'unknown',revision=row.revision if row else 0,
                **{field:getattr(finance_default,field,None) for field in ('payment_method','quotation_required','invoice_required')})


def set_customer_statement_default(db, client_id, choice, actor_id):
    default = db.get(CustomerStatementDefault, client_id)
    if default is None:
        default = CustomerStatementDefault(client_id=client_id)
        db.add(default)
    default.choice = choice
    default.updated_by = actor_id
    default.updated_at = business_now()


DOCUMENT_DEFAULT_FIELDS = ('statement_default', 'quotation_required', 'invoice_required', 'payment_method')
DOCUMENT_HISTORY_ORIGINS = ('document_defaults_client', 'document_defaults_project', 'order_documents')


def record_order_documents(db, user, project, client_id, *, initial=False, **submitted):
    from customer_translation_rates import record_order_finance
    from translation_document_requirements import payment_method

    if not client_id or not any(value is not None for value in submitted.values()):
        return
    previous = {
        'statement_default': 'required' if project.statement_required else 'not_required',
        'quotation_required': project.effective_quotation_required,
        'invoice_required': project.effective_invoice_required,
        'payment_method': payment_method(project),
    }
    after = {
        field: ('required' if value else 'not_required') if field == 'statement_default' else value
        for field,value in submitted.items() if value is not None
    }
    before = {field:previous[field] for field in after}
    customer = client_preference(db, client_id)
    if customer['payment_method']=='statement':
        customer['payment_method']='monthly'
    record_order_finance(db,user,client_id,project.id,project.order_no,'order_documents',
                         {field:customer[field] for field in after} if initial else before,after,
                         matches_customer=all(customer[field]==value for field,value in after.items()),initial=initial)


def record_document_defaults(db, client_id, user, before, origin):
    after = client_preference(db, client_id)
    changed = {field for field in DOCUMENT_DEFAULT_FIELDS if before[field] != after[field]}
    if not changed:
        return
    if not inspect(db.connection()).has_table(CustomerTranslationRateHistory.__tablename__):
        raise HTTPException(503, '客户财务修改记录尚未初始化')
    db.add(CustomerTranslationRateHistory(
        client_id=client_id, actor_id=user.id, actor_name=user.full_name or user.username,
        origin=origin, before_snapshot={field:before[field] for field in DOCUMENT_DEFAULT_FIELDS if field in changed},
        after_snapshot={field:after[field] for field in DOCUMENT_DEFAULT_FIELDS if field in changed},
        created_at=business_now(),
    ))


def sync_project_statement_default(db, client_id, revision, required, user, payment_method=None, finance_values=None):
    from permission_service import user_has_permission

    if not user_has_permission(db, user.id, 'clients:write'):
        raise HTTPException(403, '缺少客户管理编辑权限')
    row = db.query(CustomerStatementPreference).filter_by(client_id=client_id).with_for_update().populate_existing().first()
    if revision != (row.revision if row else 0):
        raise HTTPException(409, '客户对账单默认设置已变化，请重新确认')
    before = client_preference(db, client_id)
    if row is None:
        row = CustomerStatementPreference(client_id=client_id, revision=0, tax_included=False)
        db.add(row)
    row.revision += 1
    row.updated_at = business_now()
    row.updated_by = user.id
    if required is not None:
        set_customer_statement_default(db, client_id, 'required' if required else 'not_required', user.id)
    finance_values = dict(finance_values or {})
    if payment_method:
        finance_values['payment_method'] = payment_method
    if finance_values:
        write_finance_defaults(db, client_id, finance_values)
    db.flush()
    record_document_defaults(db, client_id, user, before, 'document_defaults_project')


@router.get('/clients/{client_id}/statement-preference')
def read_preference(client_id:UUID,db=Depends(get_db),user=Depends(read_settings)):
    return client_preference(db,client_id)


@router.get('/clients/{client_id}/statement-preference/history')
def preference_history(client_id:UUID,page:int=Query(1,ge=1),db=Depends(get_db),user=Depends(read_settings)):
    if not inspect(db.connection()).has_table(CustomerTranslationRateHistory.__tablename__):
        return {'items': [], 'total': 0}
    model = CustomerTranslationRateHistory
    query = db.query(model).filter(model.client_id == client_id, model.origin.in_(DOCUMENT_HISTORY_ORIGINS))
    rows = query.order_by(model.created_at.desc(),model.id.desc()).offset((page-1)*10).limit(10).all()
    from customer_translation_rates import history_entry
    return {'total':query.count(),'items':[history_entry(row) for row in rows]}


@router.put('/clients/{client_id}/statement-preference')
def save_preference(client_id:UUID,data:PreferenceWrite,db=Depends(get_db),user=Depends(write_settings)):
    try:
        if not db.query(Client.id).filter_by(id=client_id).with_for_update().first():
            raise HTTPException(404,'客户不存在')
        row=db.query(CustomerStatementPreference).filter_by(client_id=client_id).with_for_update().populate_existing().first()
        if data.revision!=(row.revision if row else 0):raise HTTPException(409,'客户含税设置已更新，请重新加载后编辑')
        before = client_preference(db, client_id)
        if row is None:row=CustomerStatementPreference(client_id=client_id,revision=0);db.add(row)
        row.tax_included=data.tax_included;row.revision+=1;row.updated_at=business_now();row.updated_by=user.id
        db.info.get('customer_statement_tax_preferences', {}).pop(client_id, None)
        defaults = data.model_dump(include=data.model_fields_set & {'payment_method','quotation_required','invoice_required'})
        choice = data.statement_default
        if choice is not None:
            set_customer_statement_default(db, client_id, choice, user.id)
        if defaults:
            write_finance_defaults(db, client_id, defaults)
        db.flush()
        record_document_defaults(db, client_id, user, before, 'document_defaults_client')
        after = client_preference(db, client_id)
        changed = {field:after[field] for field in DOCUMENT_DEFAULT_FIELDS if before[field]!=after[field]}
        if changed:
            from translation_document_requirements import apply_customer_documents
            apply_customer_documents(db,client_id,changed,user.id)
        db.commit();return client_preference(db,client_id)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'客户含税设置已更新，请重新加载后编辑')
    except Exception:
        db.rollback();raise


def money(value):
    return str(Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if value is not None else None


def tax_label(data):
    if data.get('module') == 'interpretation':
        labels = {row['unit_label'] for row in data['rows'] if row.get('unit_label')}
        return next(iter(labels)) if len(labels) == 1 else '税口径按项目' if labels else ''
    labels={row.get('unit_label') for row in data.get('rows',[]) if row.get('unit_label') in ('含税','不含税')}
    return '含税／不含税（按项目）' if len(labels)>1 else '含税' if data.get('tax_included') else '不含税'


def is_fixed_statement_row(row):
    # 旧对账单快照只有计价方式，没有独立的计价模式。
    return row.get('pricing_mode') == 'fixed' or (
        not row.get('pricing_mode') and (row.get('basis') or '').split('\n', 1)[0] == '固定收费'
    )


def fixed_workload(matrix):
    customer = matrix.get('customer') or {}
    company = matrix.get('company') or {}
    values = {}
    for metric in WORKLOAD_METRICS:
        if customer.get(metric) is not None:
            values.setdefault('客户统计', {})[metric] = str(customer[metric])
        elif company.get(metric) is not None:
            values.setdefault('我司统计', {})[metric] = str(company[metric])
    return values


def workload_lines(values):
    lines = []
    for source, counts in values.items():
        amounts = [
            f'{label} {format(Decimal(counts[metric]).normalize(), ",f")}'
            for metric, label in WORKLOAD_METRICS.items() if metric in counts
        ]
        if amounts:
            lines.append(f'{source}：' + '、'.join(amounts))
    return lines


def summarize_workloads(rows):
    totals = {}
    for row in rows:
        for source, counts in row.get('fixed_workload', {}).items():
            group = totals.setdefault(source, {})
            for metric, count in counts.items():
                group[metric] = group.get(metric, Decimal(0)) + Decimal(count)
    return totals


def statement_display_rows(node, rows, mode):
    """显示层汇总不改变收费明细；同时展示父子时，汇总行不参与合计。"""
    if mode=='children' or not node['children'] or node.get('direct_pricing') or not rows:return rows

    def descendants(item):
        number=item['order_no']
        return [row for row in rows if row['order_no']==number or row['order_no'].startswith(number+'.')]

    def summaries(item, details, counted):
        groups={}
        for row in details:groups.setdefault(row['currency'],[]).append(row)
        result = []
        for currency, group in groups.items():
            fixed = all(is_fixed_statement_row(row) for row in group)
            basis = '订单汇总' + ('（部分待补）' if any(row['subtotal'] is None for row in group) else '')
            if fixed:
                basis = '\n'.join([basis, '固定收费', *workload_lines(summarize_workloads(group))])
            amounts = [Decimal(row['subtotal']) for row in group if row['subtotal'] is not None]
            result.append({**group[0], 'order_no':item['order_no'], 'project_name':item['project_name'] or '-',
                           'language_pair':item['language_pair'] or '-', 'quantity':None, 'unit_price':None,
                           'pricing_mode':'fixed' if fixed else 'aggregate', 'basis':basis, 'currency':currency,
                           'subtotal':money(sum(amounts)) if amounts else None,
                           'task_ids':list(dict.fromkeys(row['task_id'] for row in group)),
                           'remarks':item.get('customer_explanation') or '', 'counted_in_total':counted})
        return result

    if mode=='parents':return summaries(node,rows,True)
    def render(item):
        details=descendants(item)
        if not details:return []
        exact=[row for row in details if row['order_no']==item['order_no']]
        # 固定收费订单已是独立结算行，不再额外添加相同金额的汇总。
        result=summaries(item,details,False) if item.get('price_aggregate') else []
        for child in item['children']:result.extend(render(child))
        result.extend(exact)
        return result
    return render(node)


def direction_statement_rows(rows, *, include_members=False):
    """Consolidate direction rows after task selection, without changing ledger identities."""
    rendered = []
    groups = {}
    workloads = {}

    def collect_workload(family, label, source, quantity):
        values = workloads.setdefault(family,{}).setdefault(label,(set(),set()))
        if quantity is not None and quantity!='':
            values[source].add(Decimal(str(quantity)))

    for row in rows:
        parent = row.get('direction_parent_no')
        if not parent or (row.get('basis') or '').startswith(('订单汇总','总价调整')):
            rendered.append(row)
            continue
        basis = (row.get('basis') or '').split('（每', 1)[0]
        family = (row['root_id'],parent)
        if not basis or is_fixed_statement_row(row):
            for source,counts in enumerate((row.get('direction_parent_workload'),row.get('fixed_workload'))):
                for dimension,metrics in (counts or {}).items():
                    for metric,quantity in metrics.items():
                        collect_workload(family,f'{dimension} · {WORKLOAD_METRICS[metric]}',source,quantity)
        else:
            collect_workload(family,basis,0,row.get('direction_parent_quantity'))
            collect_workload(family,basis,1,row.get('quantity'))
        detail = {**row, 'project_name':'', 'quantity':None, 'basis':'', 'direction_detail':True}
        if row['unit_price'] is None or row['subtotal'] is None:
            rendered.append(detail)
            continue
        unit = basis.split(' · ', 1)[-1]
        key = (row['root_id'], parent, row.get('origin_client_id'), row.get('billing_month'),
               row['currency'], row['unit_label'], Decimal(str(row['unit_price'])), Decimal(str(row.get('unit_size') or 1)), unit)
        groups.setdefault(key, []).append((len(rendered), detail))
        rendered.append(detail)
    for positions in groups.values():
        members = [row for _, row in positions]
        directions = list(dict.fromkeys(row['language_pair'] for row in members))
        if len(directions) < 2:
            continue
        task_ids = list(dict.fromkeys(task for row in members for task in row.get('task_ids', [row['task_id']])))
        identities = sorted(row['line_id'] for row in members)
        group_id = 'directions:' + hashlib.sha256('|'.join(identities).encode()).hexdigest()
        group = {**members[0], 'line_id':group_id, '_row_id':group_id, 'task_ids':task_ids,
                 'language_pair':'；'.join(directions), 'direction_count':len(directions),
                 'subtotal':money(sum(Decimal(str(row['subtotal'])) for row in members)),
                 'remarks':'\n'.join(dict.fromkeys(row['remarks'] for row in members if row.get('remarks')))}
        if include_members:
            group['direction_members'] = members
        rendered[positions[0][0]] = group
        for index, _ in positions[1:]:
            rendered[index] = None
    return direction_parent_subtotals([row for row in rendered if row is not None],workloads)


def direction_parent_subtotals(rows,workloads):
    def key(row, order_no):
        return row['root_id'], order_no, row['currency']

    def workload(row, order_no):
        lines = []
        for basis,(parent_values,child_values) in workloads.get((row['root_id'],order_no),{}).items():
            values = parent_values or child_values
            quantity = format(next(iter(values)).normalize(),'f') if len(values)==1 else None
            if basis or quantity is not None:
                lines.append((quantity,basis))
        if len(lines)==1:
            quantity,basis=lines[0]
            return {'quantity':quantity,'basis':basis if quantity is not None else '待补'+(f' · {basis}' if basis else '')}
        basis='\n'.join(' · '.join(filter(None,(quantity or '待补',label))) for quantity,label in lines)
        return {'quantity':None,'basis':basis or '待补'}

    details = {}
    for row in rows:
        if row.get('direction_detail'):
            details.setdefault(key(row,row['direction_parent_no']), []).append(row)
    existing = {key(row,row['order_no']) for row in rows if row.get('counted_in_total') is False}
    result = []
    for row in rows:
        if row.get('counted_in_total') is False and key(row,row['order_no']) in details:
            result.append({**row,**workload(row,row['order_no']),'direction_parent_summary':True})
            continue
        if row.get('direction_detail'):
            parent = row['direction_parent_no']
            group = key(row,parent)
            if group not in existing:
                existing.add(group)
                members = details[group]
                amounts = [Decimal(str(item['subtotal'])) for item in members if item['subtotal'] is not None]
                task_ids = list(dict.fromkeys(uid for item in members for uid in item.get('task_ids',[item['task_id']])))
                row_id = f"direction-parent:{row['root_id']}:{parent}:{row['currency']}"
                result.append({**row,**workload(row,parent),'line_id':row_id,'_row_id':row_id,'order_no':parent,'task_ids':task_ids,
                               'project_name':row.get('direction_parent_name') or parent,
                               'language_pair':'','unit_price':None,'unit_label':'','remarks':'',
                               'subtotal':money(sum(amounts)) if amounts else None,'counted_in_total':False,
                               'direction_detail':False,'direction_count':None,'direction_members':None,
                               'direction_parent_summary':True})
        result.append(row)
    families = {}
    ordered = []
    for row in result:
        if row.get('direction_parent_summary') or row.get('direction_detail'):
            family = (row['root_id'], row['order_no'] if row.get('direction_parent_summary') else row['direction_parent_no'])
            if family not in families:
                families[family] = []
                ordered.append(families[family])
            families[family].append(row)
        else:
            ordered.append([row])
    return [row for family in ordered for row in family]


def statement_shared_cell_spans(rows):
    start = None
    family = None
    for index, row in enumerate(rows):
        order_no = row['order_no'] if row.get('direction_parent_summary') else (
            row.get('direction_parent_no') if row.get('direction_detail') else None
        )
        current = (row.get('root_id'),order_no) if order_no else None
        if current == family:
            continue
        if start is not None and index-start>1:
            yield start,index-1
        family,start = current,index if row.get('direction_parent_summary') else None
    if start is not None and len(rows)-start>1:
        yield start,len(rows)-1


def build_statement(db,project_id,order_id,month,scope,order_display='children',*,special=False,group_directions=True):
    if order_display not in ('parents','all','children'):raise HTTPException(422,'请选择有效的订单显示方式')
    project=crud.get_translation_project(db,project_id)
    if not project or project.annotation_migrated_at is not None:raise HTTPException(404,'笔译项目不存在')
    client=project.client or (project.sub_client.parent_client if project.sub_client else None)
    if not client:raise HTTPException(422,'请先为项目关联客户')
    import translation_billing_tax_mode as billing_tax
    preference=client_preference(db,client.id);kind='incl_tax' if preference['tax_included'] else 'excl_tax'
    label='含税' if preference['tax_included'] else '不含税'
    if scope=='customer':
        projects=db.query(TranslationProject).outerjoin(SubClient,TranslationProject.sub_client_id==SubClient.id).filter(
            func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)==client.id,
            TranslationProject.annotation_migrated_at.is_(None)).options(
                selectinload(TranslationProject.customer_charge_items),selectinload(TranslationProject.sub_orders).selectinload(TranslationSubOrder.customer_charge_items)).order_by(TranslationProject.order_no).all()
    else:projects=[project]
    crud._attach_word_count_matrices(db,projects=projects)
    from translation_document_requirements import attach as attach_documents
    attach_documents(db,projects)
    from translation_special_settlement import apply_settings, settings_by_project
    from translation_document_requirements import payment_method
    if special:
        projects=[root for root in projects if payment_method(root)=='special']
    special_settings=settings_by_project(db,[root.id for root in projects]) if special else {}
    finance.attach_monthly_payment_peers(db,projects)
    rows=[];pending=[]
    for root in projects:
        crud._attach_project_client_fields(root)
        owners={str(owner.id):owner for owner in [root,*root.sub_orders]}
        owners_by_number={root.order_no: root, **{child.sub_order_no:child for child in root.sub_orders}}
        node=finance.tree(root)['item']
        if special:
            apply_settings(node,special_settings.get(root.id,{}))
        effective_default=finance.order_billing_month(root.order_no) or (business_datetime(root.customer_reception_time).strftime('%Y-%m') if root.customer_reception_time else None)
        def find(item,wanted,inherited_month):
            current_month=item.get('billing_month') or inherited_month
            if item['id']==str(wanted):return item,current_month
            return next((found for child in item['children'] if (found:=find(child,wanted,current_month))),None)
        selected=find(node,order_id or root.id,effective_default) if scope=='project' else (node,effective_default)
        if selected is None:raise HTTPException(422,'所选订单不属于当前项目')
        line_counts={}
        def append(item,quantity,unit,amount,currency,remark='',basis='',issue=None,unit_size='1',quantity_basis=None):
            line_index=line_counts.get(item['id'],0);line_counts[item['id']]=line_index+1
            direction_parent=getattr(owners[item['id']], 'word_count_parent_order_no', None)
            parent=owners_by_number.get(direction_parent)
            parent_name=(root.source_file_name or root.project_name) if parent is root else getattr(parent,'sub_project_name',None)
            parent_quantity=None
            if parent is not None and quantity_basis is not None:
                dimension,metric=quantity_basis
                parent_quantity=(parent.word_count_matrix or {}).get(dimension,{}).get(metric)
            rows.append(dict(order_no=item['order_no'],customer_order_no=(root.customer_order_no or '').strip(),received_date=business_datetime(root.customer_reception_time).strftime('%Y-%m-%d') if root.customer_reception_time else None,
                task_id=item['id'],root_id=str(root.id),line_id=f"{item['id']}:{line_index}",unit_size=format(Decimal(str(unit_size)),'f'),
                project_name=item['project_name'] or '-',language_pair=item['language_pair'] or '-',quantity=quantity,basis=basis,
                direction_parent_no=direction_parent,direction_parent_name=parent_name,
                direction_parent_quantity=str(parent_quantity) if parent_quantity is not None else None,
                direction_parent_workload=fixed_workload(parent.word_count_matrix or {}) if parent is not None and quantity_basis is None else None,
                statement_required=item['statement_required'],
                sub_client_id=item.get('document_sub_client_id'),
                sub_client_name=root.sub_client.client_name if item.get('document_sub_client_id') else None,
                sub_client_code=item.get('sub_client_code') if item.get('document_sub_client_id') else None,
                settlement_period_number=item.get('settlement_period_number'),
                unit_price=str(unit) if unit is not None else None,unit_label='含税' if item.get('special_tax_mode',item.get('effective_billing_tax_mode'))=='incl_tax' else '不含税' if item.get('special_tax_mode',item.get('effective_billing_tax_mode'))=='excl_tax' else label,currency=currency,subtotal=money(amount),
                remarks=item.get('customer_explanation') or ''))
            if issue:pending.append(f"{item['order_no']}：{issue}")
        def visit(item,inherited_month):
            current_month=item.get('billing_month') or inherited_month
            kind=item.get('special_tax_mode',item.get('effective_billing_tax_mode'))
            if kind not in ('incl_tax','excl_tax'):kind=billing_tax.effective(item,item.get('billing_tax_mode')) or ('incl_tax' if preference['tax_included'] else 'excl_tax')
            label='含税' if kind=='incl_tax' else '不含税'
            if item['pricing_mode']=='fixed':
                if current_month==month:
                    workload = fixed_workload(item.get('word_count_matrix') or {})
                    basis = '\n'.join(['固定收费', *workload_lines(workload)])
                    amounts=item.get('totals_'+kind) or {item['currency']:None}
                    for currency,value in amounts.items():
                        append(item,None,None,value,currency,item.get('explanation',''),basis,None if value is not None else f'未填写{label}固定收费')
                        rows[-1].update(pricing_mode='fixed', fixed_workload=workload)
                return
            children=[] if item.get('direct_pricing') else item['children'];start=len(rows)
            if children:
                for child in children:visit(child,current_month)
            elif current_month==month:
                prices=item['prices']
                if not prices:append(item,None,None,None,item['currency'],item.get('explanation',''),issue='未登记客户单价')
                for price in prices:
                    tax=price.get('tax_prices') or {};unit=tax.get('unit_price_'+kind)
                    if unit is None and not any(tax.get('unit_price_'+side) is not None for side in ('excl_tax','incl_tax')):
                        if kind=='excl_tax' or not special and not item.get('unified_billing_tax_mode'):
                            unit=price['amount']
                    quantity=price.get('quantity');size=price.get('unit_size') or '1';amount=tax.get('total_'+kind)
                    if amount is None and unit is not None and quantity is not None:amount=Decimal(str(unit))*Decimal(str(quantity))/Decimal(size)
                    dimension='我司统计' if price.get('quantity_dimension')=='company' else '客户统计'
                    basis=f"{dimension} · {METRICS.get(price.get('quantity_metric'),price.get('quantity_metric') or '')}"+(f"（每{Decimal(size):f}计价）" if Decimal(size)!=1 else '')
                    line={**item,'language_pair':price.get('language_pair') or item['language_pair']}
                    append(line,str(quantity) if quantity is not None else None,unit,amount,price['currency'],item.get('explanation',''),basis,
                           f'未填写{label}单价或对应工作量' if unit is None or quantity is None or amount is None else None,
                           unit_size=size,quantity_basis=(price.get('quantity_dimension'),price.get('quantity_metric')))
            manual=item.get('effective_total_adjustment') or {}
            if kind in manual and current_month==month:
                currency=manual['currency']
                matching=[row for row in rows[start:] if row['currency']==currency and row.get('counted_in_total',True)]
                for row in matching:
                    if row['subtotal'] is None:
                        row['counted_in_total']=False
                difference=Decimal(manual[kind])-sum(Decimal(row['subtotal']) for row in matching if row['subtotal'] is not None)
                if difference or not any(row['subtotal'] is not None for row in matching):
                    side=kind.replace('_tax','_discount')
                    adjustment=item.get('total_adjustment') or {}
                    reason='总价调整'
                    if kind not in adjustment and adjustment.get(side) is not None and item.get('adjusted_total_incl_tax' if kind=='incl_tax' else 'adjusted_total') is None:
                        reason=f"总价调整（{adjustment[side]:02d}折）"
                    append(item,None,None,difference,currency,item.get('explanation',''),reason)
            override=item.get('adjusted_total_incl_tax' if kind=='incl_tax' else 'adjusted_total')
            if kind not in manual and override is not None and current_month==month and len(rows)>start:
                matching=[row for row in rows[start:] if row['currency']==item['currency']]
                if matching and all(row['subtotal'] is not None for row in matching):
                    difference=Decimal(override)-sum(Decimal(row['subtotal']) for row in matching)
                    if difference:append(item,None,None,difference,item['currency'],item.get('explanation',''),'总价调整')
        start=len(rows)
        visit(*selected)
        rows[start:]=statement_display_rows(selected[0],rows[start:],order_display)
        if len(rows)>10000:raise HTTPException(422,'本次对账单超过10000条，请缩小项目范围')
    if group_directions:
        rows=direction_statement_rows(rows)
    sums={}
    for row in rows:
        if row.get('counted_in_total',True) and row['subtotal'] is not None:sums[row['currency']]=sums.get(row['currency'],Decimal(0))+Decimal(row['subtotal'])
    subject=db.get(CustomerStatementCompany,'company')
    private_settings=private_statement_settings_available()
    result=dict(company=subject.company if subject else COMPANY,title='对账单',client_name=client.client_name or client.client_short_name,client_code=client.client_code,
        month=month,issue_date=business_now().date().isoformat(),scope=scope,order_display=order_display,tax_included=preference['tax_included'],rows=rows,totals={key:money(value) for key,value in sums.items()},pending=pending,
        private_settings_available=private_settings,settings={},stamp_image=None)
    if scope=='project' and project.sub_client and project.settlement_party=='sub_client':
        result.update(sub_client_name=project.sub_client.client_name,sub_client_code=project.sub_client.sub_client_code)
    if private_settings:
        settings=settings_value(*statement_company_settings(db))
        result.update(settings={key:settings[key] for key in PAYMENT_ACCOUNT_FIELDS},stamp_image=settings['stamp_image'] or settings['default_stamp'])
    labels={row['unit_label'] for row in rows if row.get('unit_label')}
    if len(labels)==1:result['tax_included']=next(iter(labels))=='含税'
    result['statement_version']=hashlib.sha256(json.dumps(result,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    result['generated_at']=business_now().isoformat()
    return result


@router.get('/translation-statements/preview')
def preview(project_id:UUID,month:str=Query(pattern=MONTH),scope:Literal['project','customer']='project',order_id:UUID|None=None,order_display:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_projects)):
    return build_statement(db,project_id,order_id,month,scope,order_display)


def statement_customer_label(data):
    customer = f"客户：{data['client_name']}"
    if child := data.get('sub_client_name'):
        return f'{customer}\n子客户：{child}'
    return customer


def statement_title(data):
    title=data.get('title') or '对账单';month=data.get('month') or ''
    prefix=f'{month} ' if month else ''
    return title[len(prefix):] if prefix and title.startswith(prefix) else title


def statement_has_unit_column(rows):
    return not rows or any(not is_fixed_statement_row(row) for row in rows)


def statement_amount(row, mixed_tax=False):
    if row.get('subtotal') is None:
        return '待补（不计入合计）' if row.get('direction_parent_summary') else '待补'
    amount = f"{row['currency']} {row['subtotal']}"
    if mixed_tax and is_fixed_statement_row(row) and row.get('unit_label'):
        amount += f"（{row['unit_label']}）"
    if row.get('direction_count'):
        amount += f"（{row['direction_count']} 个方向合计）"
    if row.get('direction_parent_summary'):
        amount += '（不计入合计）'
    return amount


def statement_unit_amount(row, mixed_tax=False):
    unit_price = row.get('unit_price')
    unit = '-' if unit_price is None else f"{row['currency']} {Decimal(str(unit_price)).quantize(Decimal('.001'),rounding=ROUND_HALF_UP):.3f}"
    if row.get('direction_detail') and unit_price is not None:
        size = Decimal(str(row.get('unit_size') or 1))
        if size != 1:
            unit += f'（每{size.normalize():f}计价）'
    if mixed_tax and row.get('unit_label') and not is_fixed_statement_row(row):
        unit += f"（{row['unit_label']}）"
    return unit


def write_excel_sheet(sheet,data):
    from openpyxl.styles import Font, Alignment, Border, Side
    from openpyxl.drawing.image import Image as ExcelImage
    from openpyxl.utils import get_column_letter
    from project_export_excel import _safe_text
    has_customer_order=any(str(row.get('customer_order_no') or '').strip() for row in data['rows'])
    has_origin=any(row.get('origin_client_id') or row.get('origin_client_name') for row in data['rows'])
    show_unit = statement_has_unit_column(data['rows'])
    mixed_tax = '按项目' in tax_label(data)
    offset = int(has_customer_order) + int(has_origin)
    column_count = 6 + int(show_unit) + offset
    last_col = get_column_letter(column_count)
    amount_column = column_count - 1
    sheet.sheet_view.showGridLines=False
    sheet.merge_cells(f'A1:{last_col}1');sheet['A1']=_safe_text(data['company']);sheet['A1'].font=Font(name='微软雅黑',size=15,bold=True)
    sheet.merge_cells(f'A2:{last_col}2');sheet['A2']=_safe_text(statement_title(data));sheet['A2'].font=Font(name='微软雅黑',size=16.5,bold=True)
    sheet.merge_cells(start_row=3,start_column=1,end_row=3,end_column=4+offset);sheet['A3']=_safe_text(statement_customer_label(data))
    if data.get('sub_client_name'):
        sheet.row_dimensions[3].height = 36
    sheet.merge_cells(start_row=3,start_column=5+offset,end_row=3,end_column=column_count);sheet.cell(3,5+offset,_safe_text(f"账单月份：{data['month']}　{tax_label(data)}"))
    headings = ['来稿日期','项目名称','翻译方向','工作量（计价方式）']
    if data.get('module') == 'interpretation':
        headings[:3] = ['订单日期', '项目名称', '口译方向']
    headings.extend(['单价','小计'] if show_unit else ['固定价格'])
    if data.get('statement_number'):
        sheet.merge_cells(f'A4:{last_col}4')
        sheet['A4']=_safe_text(f"对账单编号：{data['statement_number']}")
    else:
        sheet.append([])
    sheet.append((['原客户'] if has_origin else [])+(['客户单号'] if has_customer_order else [])+headings+['备注'])
    for row in data['rows']:
        workload=(str(row['quantity'])+'\n' if row['quantity'] is not None else '')+re.sub(r'[（(]每1(?:\.0+)?计价[）)]','',row['basis'])
        unit=statement_unit_amount(row,mixed_tax)
        fixed = is_fixed_statement_row(row)
        values=([row.get('origin_client_name') or data['client_name']] if has_origin else [])+([row.get('customer_order_no','')] if has_customer_order else [])+[row['received_date'],row['project_name'],row['language_pair'],workload]
        if show_unit:
            values.append(None if fixed or row.get('direction_parent_summary') else unit)
        values.extend([statement_amount(row, mixed_tax), ('汇总参考，不重复计入合计。' if row.get('counted_in_total') is False and not row.get('direction_parent_summary') else '')+(row['remarks'] or '')])
        sheet.append(['-' if value=='-' else _safe_text(value) for value in values])
        sheet.row_dimensions[sheet.max_row].height = max(46, 16*(workload.count('\n')+1+len(workload)//24)) if fixed else 46
        if row.get('direction_count'):
            sheet.row_dimensions[sheet.max_row].height = max(46,16*(1+len(row['language_pair'])//14))
    total_row=sheet.max_row+1;sheet.merge_cells(start_row=total_row,start_column=1,end_row=total_row,end_column=3)
    if amount_column>5:sheet.merge_cells(start_row=total_row,start_column=4,end_row=total_row,end_column=amount_column-1)
    sheet.cell(total_row,1,'账单日期：'+(data.get('issue_date') or '-'))
    sheet.cell(total_row,4,'合计（已登记金额）' if data['pending'] else '合计')
    sheet.cell(total_row,amount_column,'\n'.join(f'{key} {value}' for key,value in data['totals'].items()) or '-')
    sheet.row_dimensions[total_row].height=max(55,len(data['totals'])*20)
    border=Border(*( [Side(style='thin',color='777777')]*4 ))
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
            if cell.row==3:cell.font=Font(name='微软雅黑',size=10)
            if cell.row>=5:cell.border=border;cell.font=Font(name='微软雅黑',size=10,bold=cell.row in (5,total_row))
    for start,end in statement_shared_cell_spans(data['rows']):
        for column in (1+offset,2+offset,4+offset):
            sheet.merge_cells(start_row=start+6,start_column=column,end_row=end+6,end_column=column)
    sheet['A3'].alignment=Alignment(horizontal='left',vertical='center',wrap_text=True)
    sheet.cell(3,5+offset).alignment=Alignment(horizontal='right',vertical='center',wrap_text=True)
    sheet.cell(total_row,1).alignment=Alignment(horizontal='left',vertical='center')
    sheet.cell(total_row,1).font=Font(name='微软雅黑',size=9,color='64748B')
    sheet.cell(total_row,4).alignment=Alignment(horizontal='right',vertical='center',wrap_text=True,indent=1)
    if data.get('private_settings_available',True):
        sheet.append([])
        for text in ['收款账户信息','开户行：'+data['settings']['bank_name'],'账户名：'+data['settings']['account_name'],'账号：'+data['settings']['account_number']]:
            sheet.append([_safe_text(text)]);sheet.merge_cells(start_row=sheet.max_row,start_column=1,end_row=sheet.max_row,end_column=column_count)
            sheet.cell(sheet.max_row,1).alignment=Alignment(horizontal='left',vertical='center');sheet.row_dimensions[sheet.max_row].height=24
            sheet.cell(sheet.max_row,1).font=Font(name='微软雅黑',size=11.25 if text=='收款账户信息' else 10,bold=text=='收款账户信息')
    if data['pending']:
        sheet.append([_safe_text('待补资料：'+'；'.join(data['pending']))]);sheet.merge_cells(start_row=sheet.max_row,start_column=1,end_row=sheet.max_row,end_column=column_count);sheet.cell(sheet.max_row,1).alignment=Alignment(wrap_text=True);sheet.row_dimensions[sheet.max_row].height=50
        sheet.cell(sheet.max_row,1).font=Font(name='微软雅黑',size=9,color='A54A21')
    if data.get('stamp_image'):
        image=ExcelImage(BytesIO(base64.b64decode(data['stamp_image'].split(',',1)[1])));image.width=image.height=130
        sheet.add_image(image,f'D{max(5,total_row-1)}')
    widths = [24,35.7,17.6,29.7] + ([30] if show_unit else []) + [22,34]
    for index,width in enumerate(([24] if has_origin else [])+([24] if has_customer_order else [])+widths,1):sheet.column_dimensions[get_column_letter(index)].width=width
    sheet.sheet_properties.pageSetUpPr.fitToPage=True;sheet.page_setup.orientation='landscape';sheet.page_setup.paperSize=sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth=1;sheet.page_setup.fitToHeight=0;sheet.print_title_rows='1:5';sheet.print_options.horizontalCentered=True


def excel_bytes(data):
    from openpyxl import Workbook
    workbook=Workbook();sheet=workbook.active;sheet.title='对账单'
    write_excel_sheet(sheet,data)
    output=BytesIO();workbook.save(output);return output.getvalue()


@router.get('/translation-statements/excel')
def export_excel(project_id:UUID,month:str=Query(pattern=MONTH),scope:Literal['project','customer']='project',order_id:UUID|None=None,version:str|None=Query(None,pattern=r'^[a-f0-9]{64}$'),order_display:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_projects)):
    data=build_statement(db,project_id,order_id,month,scope,order_display)
    if version and version!=data['statement_version']:raise HTTPException(409,'对账单数据已变化，请重新生成后下载')
    if not data['rows']:raise HTTPException(422,'所选账单月份暂无可生成的项目')
    filename=quote(f"信实翻译对账单_{data['month']}.xlsx")
    return Response(excel_bytes(data),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f"attachment; filename*=UTF-8''{filename}"})
