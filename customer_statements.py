"""客户对账单设置与笔译对账单；只读取已保存的项目收费，金额按币种分别合计。"""
import base64
import hashlib
import json
import math
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
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from models import Base, Client, SubClient, TranslationProject, TranslationSubOrder
from database import get_db
from routers.auth import require_permission, require_any_permission
from annotation_progress_time import business_now, business_datetime
import crud
import translation_customer_finance as finance
from customer_statement_defaults import CustomerStatementDefault

COMPANIES = ('广州信实翻译服务有限公司','广州信实翻译服务有限公司深圳分公司','广州信实翻译服务有限公司上海分公司')
COMPANY = COMPANIES[0]
MONTH = r'^\d{4}-(0[1-9]|1[0-2])$'
METRICS = {'words':'字数','characters_no_spaces':'字符数（不计空格）','foreign_words':'外文字数',
           'cjk_chars_korean_words':'中朝字数','documents':'份数','pages':'页数'}
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


class PreferenceWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)
    tax_included: bool
    statement_default: Literal['required','not_required','unknown'] | None = None


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


@lru_cache(maxsize=1)
def default_stamp():
    """透明底示例章；独立图层覆盖表格线，可由上传的正式章替换。"""
    size=480; image=Image.new('RGBA',(size,size)); draw=ImageDraw.Draw(image); red=(192,24,32,210)
    draw.ellipse((25,25,455,455),outline=red,width=9)
    fonts=[Path('C:/Windows/Fonts/msyh.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
    font_path=next((str(path) for path in fonts if path.exists()),None)
    font=ImageFont.truetype(font_path,32) if font_path else ImageFont.load_default(size=30)
    for index,char in enumerate(COMPANY):
        angle=-160+index*140/(len(COMPANY)-1)
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


def settings_value(row, company=None):
    return dict(bank_name=row.bank_name if row else '',account_name=row.account_name if row else '',
                account_number=row.account_number if row else '',stamp_image=row.stamp_image if row else None,
                company=company.company if company else COMPANY,company_options=list(COMPANIES),default_stamp=default_stamp(),revision=row.revision if row else 0)


@router.get('/customer-statement-settings')
def read_company_settings(db=Depends(get_db),user=Depends(read_settings)):
    return settings_value(db.get(CustomerStatementSettings,'company'),db.get(CustomerStatementCompany,'company'))


@router.put('/customer-statement-settings')
def save_company_settings(data:SettingsWrite,db=Depends(get_db),user=Depends(write_settings)):
    try:
        row=db.query(CustomerStatementSettings).filter_by(key='company').with_for_update().populate_existing().first()
        if data.revision!=(row.revision if row else 0):raise HTTPException(409,'对账单设置已更新，请重新打开后编辑')
        stamp=clean_stamp(data.stamp_image)
        if row is None:row=CustomerStatementSettings(key='company',revision=0);db.add(row)
        for key in ('bank_name','account_name','account_number'):setattr(row,key,getattr(data,key).strip())
        row.stamp_image=stamp;row.revision+=1;row.updated_at=business_now();row.updated_by=user.id
        subject=db.get(CustomerStatementCompany,'company')
        if subject is None:subject=CustomerStatementCompany(key='company');db.add(subject)
        subject.company=data.company;subject.updated_by=user.id;subject.updated_at=business_now()
        db.commit();return settings_value(row,subject)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'对账单设置已更新，请重新打开后编辑')
    except Exception:
        db.rollback();raise


def client_preference(db,client_id):
    if not db.get(Client,client_id):raise HTTPException(404,'客户不存在')
    row=db.get(CustomerStatementPreference,client_id)
    default=db.get(CustomerStatementDefault,client_id)
    return dict(tax_included=bool(row.tax_included) if row else False,statement_default=default.choice if default else 'unknown',revision=row.revision if row else 0)


@router.get('/clients/{client_id}/statement-preference')
def read_preference(client_id:UUID,db=Depends(get_db),user=Depends(read_settings)):
    return client_preference(db,client_id)


@router.put('/clients/{client_id}/statement-preference')
def save_preference(client_id:UUID,data:PreferenceWrite,db=Depends(get_db),user=Depends(write_settings)):
    try:
        if not db.get(Client,client_id):raise HTTPException(404,'客户不存在')
        row=db.query(CustomerStatementPreference).filter_by(client_id=client_id).with_for_update().populate_existing().first()
        if data.revision!=(row.revision if row else 0):raise HTTPException(409,'客户含税设置已更新，请重新加载后编辑')
        if row is None:row=CustomerStatementPreference(client_id=client_id,revision=0);db.add(row)
        row.tax_included=data.tax_included;row.revision+=1;row.updated_at=business_now();row.updated_by=user.id
        if data.statement_default is not None:
            default=db.get(CustomerStatementDefault,client_id)
            if default is None:default=CustomerStatementDefault(client_id=client_id);db.add(default)
            default.choice=data.statement_default;default.updated_by=user.id;default.updated_at=business_now()
        db.commit();return client_preference(db,client_id)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'客户含税设置已更新，请重新加载后编辑')
    except Exception:
        db.rollback();raise


def money(value):
    return str(Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if value is not None else None


def tax_label(data):
    labels={row.get('unit_label') for row in data.get('rows',[]) if row.get('unit_label') in ('含税','不含税')}
    return '含税／不含税（按项目）' if len(labels)>1 else '含税' if data.get('tax_included') else '不含税'


def statement_display_rows(node, rows, mode):
    """显示层汇总不改变收费明细；同时展示父子时，汇总行不参与合计。"""
    if mode=='children' or not node['children'] or not rows:return rows

    def descendants(item):
        number=item['order_no']
        return [row for row in rows if row['order_no']==number or row['order_no'].startswith(number+'.')]

    def summaries(item, details, counted):
        groups={}
        for row in details:groups.setdefault(row['currency'],[]).append(row)
        return [{**details[0], 'order_no':item['order_no'],'project_name':item['project_name'] or '-',
                 'language_pair':item['language_pair'] or '-', 'quantity':None,'unit_price':None,
                 'basis':'订单汇总'+('（部分待补）' if any(row['subtotal'] is None for row in group) else ''),
                 'currency':currency,'subtotal':money(sum((Decimal(row['subtotal']) for row in group if row['subtotal'] is not None),Decimal(0))) if any(row['subtotal'] is not None for row in group) else None,
                 'remarks':item.get('customer_explanation') or '', 'counted_in_total':counted}
                for currency,group in groups.items()]

    if mode=='parents':return summaries(node,rows,True)
    def render(item):
        details=descendants(item)
        if not details:return []
        exact=[row for row in details if row['order_no']==item['order_no']]
        # 固定收费订单已是独立结算行，不再额外添加相同金额的汇总。
        result=summaries(item,details,False) if item['children'] and item['pricing_mode']!='fixed' else []
        for child in item['children']:result.extend(render(child))
        result.extend(exact)
        return result
    return render(node)


def build_statement(db,project_id,order_id,month,scope,order_display='children'):
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
    rows=[];pending=[]
    for root in projects:
        crud._attach_project_client_fields(root)
        owners={str(owner.id):owner for owner in [root,*root.sub_orders]}
        node=finance.tree(root)['item']
        effective_default=finance.order_billing_month(root.order_no) or (business_datetime(root.customer_reception_time).strftime('%Y-%m') if root.customer_reception_time else None)
        def find(item,wanted,inherited_month):
            current_month=item.get('billing_month') or inherited_month
            if item['id']==str(wanted):return item,current_month
            return next((found for child in item['children'] if (found:=find(child,wanted,current_month))),None)
        selected=find(node,order_id or root.id,effective_default) if scope=='project' else (node,effective_default)
        if selected is None:raise HTTPException(422,'所选订单不属于当前项目')
        line_counts={}
        def append(item,quantity,unit,amount,currency,remark='',basis='',issue=None,unit_size='1'):
            line_index=line_counts.get(item['id'],0);line_counts[item['id']]=line_index+1
            rows.append(dict(order_no=item['order_no'],customer_order_no=(root.customer_order_no or '').strip(),received_date=business_datetime(root.customer_reception_time).strftime('%Y-%m-%d') if root.customer_reception_time else None,
                task_id=item['id'],root_id=str(root.id),line_id=f"{item['id']}:{line_index}",unit_size=format(Decimal(str(unit_size)),'f'),
                project_name=item['project_name'] or '-',language_pair=item['language_pair'] or '-',quantity=quantity,basis=basis,
                unit_price=str(unit) if unit is not None else None,unit_label='含税' if item.get('effective_billing_tax_mode')=='incl_tax' else '不含税' if item.get('effective_billing_tax_mode')=='excl_tax' else label,currency=currency,subtotal=money(amount),
                remarks=item.get('customer_explanation') or ''))
            if issue:pending.append(f"{item['order_no']}：{issue}")
        def visit(item,inherited_month):
            current_month=item.get('billing_month') or inherited_month
            kind=item.get('effective_billing_tax_mode')
            if kind not in ('incl_tax','excl_tax'):kind=billing_tax.effective(item,item.get('billing_tax_mode')) or ('incl_tax' if preference['tax_included'] else 'excl_tax')
            label='含税' if kind=='incl_tax' else '不含税'
            if item['pricing_mode']=='fixed':
                if current_month==month:
                    value=item.get('adjusted_total_incl_tax' if kind=='incl_tax' else 'adjusted_total')
                    append(item,None,None,value,item['currency'],item.get('explanation',''),'固定收费',None if value is not None else f'未填写{label}固定收费')
                return
            children=item['children'];start=len(rows)
            if children:
                for child in children:visit(child,current_month)
            elif current_month==month:
                prices=item['prices']
                if not prices:append(item,None,None,None,item['currency'],item.get('explanation',''),issue='未登记客户单价')
                for price in prices:
                    tax=price.get('tax_prices') or {};unit=tax.get('unit_price_'+kind)
                    if unit is None and not any(tax.get('unit_price_'+side) is not None for side in ('excl_tax','incl_tax')):unit=price['amount']
                    quantity=price.get('quantity');size=price.get('unit_size') or '1';amount=tax.get('total_'+kind)
                    if amount is None and unit is not None and quantity is not None:amount=Decimal(str(unit))*Decimal(str(quantity))/Decimal(size)
                    dimension='我司统计' if price.get('quantity_dimension')=='company' else '客户统计'
                    basis=f"{dimension} · {METRICS.get(price.get('quantity_metric'),price.get('quantity_metric') or '')}"+(f"（每{Decimal(size):f}计价）" if Decimal(size)!=1 else '')
                    line={**item,'language_pair':price.get('language_pair') or item['language_pair']}
                    append(line,str(quantity) if quantity is not None else None,unit,amount,price['currency'],item.get('explanation',''),basis,
                           f'未填写{label}单价或对应工作量' if unit is None or quantity is None or amount is None else None,unit_size=size)
            override=item.get('adjusted_total_incl_tax' if kind=='incl_tax' else 'adjusted_total')
            if override is not None and current_month==month and len(rows)>start:
                matching=[row for row in rows[start:] if row['currency']==item['currency']]
                if matching and all(row['subtotal'] is not None for row in matching):
                    difference=Decimal(override)-sum(Decimal(row['subtotal']) for row in matching)
                    if difference:append(item,None,None,difference,item['currency'],item.get('explanation',''),'总价调整')
        start=len(rows)
        visit(*selected)
        rows[start:]=statement_display_rows(selected[0],rows[start:],order_display)
        if len(rows)>10000:raise HTTPException(422,'本次对账单超过10000条，请缩小项目范围')
    sums={}
    for row in rows:
        if row.get('counted_in_total',True) and row['subtotal'] is not None:sums[row['currency']]=sums.get(row['currency'],Decimal(0))+Decimal(row['subtotal'])
    settings=settings_value(db.get(CustomerStatementSettings,'company'),db.get(CustomerStatementCompany,'company'))
    result=dict(company=settings['company'],title='对账单',client_name=client.client_name or client.client_short_name,client_code=client.client_code,
        month=month,issue_date=business_now().date().isoformat(),scope=scope,order_display=order_display,tax_included=preference['tax_included'],rows=rows,totals={key:money(value) for key,value in sums.items()},pending=pending,
        settings={key:settings[key] for key in ('bank_name','account_name','account_number')},stamp_image=settings['stamp_image'] or settings['default_stamp'])
    labels={row['unit_label'] for row in rows if row.get('unit_label')}
    if len(labels)==1:result['tax_included']=next(iter(labels))=='含税'
    result['statement_version']=hashlib.sha256(json.dumps(result,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    result['generated_at']=business_now().isoformat()
    return result


@router.get('/translation-statements/preview')
def preview(project_id:UUID,month:str=Query(pattern=MONTH),scope:Literal['project','customer']='project',order_id:UUID|None=None,order_display:Literal['parents','all','children']='children',db=Depends(get_db),user=Depends(read_projects)):
    return build_statement(db,project_id,order_id,month,scope,order_display)


def statement_title(data):
    title=data.get('title') or '对账单';month=data.get('month') or ''
    prefix=f'{month} ' if month else ''
    return title[len(prefix):] if prefix and title.startswith(prefix) else title


def write_excel_sheet(sheet,data):
    from openpyxl.styles import Font, Alignment, Border, Side
    from openpyxl.drawing.image import Image as ExcelImage
    from openpyxl.utils import get_column_letter
    from project_export_excel import _safe_text
    has_customer_order=any(str(row.get('customer_order_no') or '').strip() for row in data['rows'])
    has_origin=any(row.get('origin_client_id') or row.get('origin_client_name') for row in data['rows'])
    offset=int(has_customer_order)+int(has_origin);last_col=get_column_letter(7+offset)
    sheet.sheet_view.showGridLines=False
    sheet.merge_cells(f'A1:{last_col}1');sheet['A1']=_safe_text(data['company']);sheet['A1'].font=Font(name='微软雅黑',size=15,bold=True)
    sheet.merge_cells(f'A2:{last_col}2');sheet['A2']=_safe_text(statement_title(data));sheet['A2'].font=Font(name='微软雅黑',size=16.5,bold=True)
    sheet.merge_cells(start_row=3,start_column=1,end_row=3,end_column=4+offset);sheet['A3']=_safe_text(f"客户：{data['client_name']}")
    sheet.merge_cells(start_row=3,start_column=5+offset,end_row=3,end_column=7+offset);sheet.cell(3,5+offset,_safe_text(f"账单月份：{data['month']}　{tax_label(data)}"))
    sheet.append([]);sheet.append((['原客户'] if has_origin else [])+(['客户单号'] if has_customer_order else [])+['来稿日期','项目名称','翻译方向','工作量（计价方式）','单价','小计','备注'])
    for row in data['rows']:
        workload=(str(row['quantity'])+'\n' if row['quantity'] is not None else '')+re.sub(r'[（(]每1(?:\.0+)?计价[）)]','',row['basis'])
        unit=f"{row['currency']} {Decimal(str(row['unit_price'])).quantize(Decimal('0.001'),rounding=ROUND_HALF_UP):.3f}" if row['unit_price'] is not None else '-'
        if '按项目' in tax_label(data) and row.get('unit_label'):unit+='（'+row['unit_label']+'）'
        values=([row.get('origin_client_name') or data['client_name']] if has_origin else [])+([row.get('customer_order_no','')] if has_customer_order else [])+[row['received_date'],row['project_name'],row['language_pair'],workload,unit,
                f"{row['currency']} {row['subtotal']}" if row['subtotal'] is not None else '待补',
                ('汇总参考，不重复计入合计。' if row.get('counted_in_total') is False else '')+(row['remarks'] or '')]
        sheet.append(['-' if value=='-' else _safe_text(value) for value in values]);sheet.row_dimensions[sheet.max_row].height=46
    total_row=sheet.max_row+1;sheet.merge_cells(start_row=total_row,start_column=1,end_row=total_row,end_column=3);sheet.merge_cells(start_row=total_row,start_column=4,end_row=total_row,end_column=5+offset)
    sheet.cell(total_row,1,'账单日期：'+(data.get('issue_date') or '-'))
    sheet.cell(total_row,4,'合计（已登记金额）' if data['pending'] else '合计')
    sheet.cell(total_row,6+offset,'\n'.join(f'{key} {value}' for key,value in data['totals'].items()) or '-')
    sheet.row_dimensions[total_row].height=max(55,len(data['totals'])*20)
    border=Border(*( [Side(style='thin',color='777777')]*4 ))
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
            if cell.row==3:cell.font=Font(name='微软雅黑',size=10)
            if cell.row>=5:cell.border=border;cell.font=Font(name='微软雅黑',size=10,bold=cell.row in (5,total_row))
    sheet['A3'].alignment=Alignment(horizontal='left',vertical='center',wrap_text=True)
    sheet.cell(3,5+offset).alignment=Alignment(horizontal='right',vertical='center',wrap_text=True)
    sheet.cell(total_row,1).alignment=Alignment(horizontal='left',vertical='center')
    sheet.cell(total_row,1).font=Font(name='微软雅黑',size=9,color='64748B')
    sheet.cell(total_row,4).alignment=Alignment(horizontal='right',vertical='center',wrap_text=True,indent=1)
    sheet.append([])
    for text in ['收款账户信息','开户行：'+data['settings']['bank_name'],'账户名：'+data['settings']['account_name'],'账号：'+data['settings']['account_number']]:
        sheet.append([_safe_text(text)]);sheet.merge_cells(start_row=sheet.max_row,start_column=1,end_row=sheet.max_row,end_column=7+offset)
        sheet.cell(sheet.max_row,1).alignment=Alignment(horizontal='left',vertical='center');sheet.row_dimensions[sheet.max_row].height=24
        sheet.cell(sheet.max_row,1).font=Font(name='微软雅黑',size=11.25 if text=='收款账户信息' else 10,bold=text=='收款账户信息')
    if data['pending']:
        sheet.append([_safe_text('待补资料：'+'；'.join(data['pending']))]);sheet.merge_cells(start_row=sheet.max_row,start_column=1,end_row=sheet.max_row,end_column=7+offset);sheet.cell(sheet.max_row,1).alignment=Alignment(wrap_text=True);sheet.row_dimensions[sheet.max_row].height=50
        sheet.cell(sheet.max_row,1).font=Font(name='微软雅黑',size=9,color='A54A21')
    image=ExcelImage(BytesIO(base64.b64decode(data['stamp_image'].split(',',1)[1])));image.width=image.height=130
    sheet.add_image(image,f'D{max(5,total_row-1)}')
    for index,width in enumerate(([24] if has_origin else [])+([24] if has_customer_order else [])+[24,35.7,17.6,29.7,30,22,34],1):sheet.column_dimensions[get_column_letter(index)].width=width
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
