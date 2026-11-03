"""客户对账单设置与笔译对账单；只读取已保存的项目收费，金额按币种分别合计。"""
import base64
import hashlib
import json
import math
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

COMPANY = '广州信实翻译服务公司'
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


class SettingsWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)
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


def settings_value(row):
    return dict(bank_name=row.bank_name if row else '',account_name=row.account_name if row else '',
                account_number=row.account_number if row else '',stamp_image=row.stamp_image if row else None,
                default_stamp=default_stamp(),revision=row.revision if row else 0)


@router.get('/customer-statement-settings')
def read_company_settings(db=Depends(get_db),user=Depends(read_settings)):
    return settings_value(db.get(CustomerStatementSettings,'company'))


@router.put('/customer-statement-settings')
def save_company_settings(data:SettingsWrite,db=Depends(get_db),user=Depends(write_settings)):
    try:
        row=db.query(CustomerStatementSettings).filter_by(key='company').with_for_update().populate_existing().first()
        if data.revision!=(row.revision if row else 0):raise HTTPException(409,'对账单设置已更新，请重新打开后编辑')
        stamp=clean_stamp(data.stamp_image)
        if row is None:row=CustomerStatementSettings(key='company',revision=0);db.add(row)
        for key in ('bank_name','account_name','account_number'):setattr(row,key,getattr(data,key).strip())
        row.stamp_image=stamp;row.revision+=1;row.updated_at=business_now();row.updated_by=user.id
        db.commit();return settings_value(row)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'对账单设置已更新，请重新打开后编辑')
    except Exception:
        db.rollback();raise


def client_preference(db,client_id):
    if not db.get(Client,client_id):raise HTTPException(404,'客户不存在')
    row=db.get(CustomerStatementPreference,client_id)
    return dict(tax_included=bool(row.tax_included) if row else False,revision=row.revision if row else 0)


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
        db.commit();return client_preference(db,client_id)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'客户含税设置已更新，请重新加载后编辑')
    except Exception:
        db.rollback();raise


def money(value):
    return str(Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if value is not None else None


def build_statement(db,project_id,order_id,month,scope):
    project=crud.get_translation_project(db,project_id)
    if not project or project.annotation_migrated_at is not None:raise HTTPException(404,'笔译项目不存在')
    client=project.client or (project.sub_client.parent_client if project.sub_client else None)
    if not client:raise HTTPException(422,'请先为项目关联客户')
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
        def append(item,quantity,unit,amount,currency,remark='',basis='',issue=None):
            rows.append(dict(order_no=item['order_no'],received_date=business_datetime(root.customer_reception_time).strftime('%Y-%m-%d') if root.customer_reception_time else None,
                project_name=item['project_name'] or '-',language_pair=item['language_pair'] or '-',quantity=quantity,basis=basis,
                unit_price=str(unit) if unit is not None else None,unit_label=label,currency=currency,subtotal=money(amount),
                remarks=remark or getattr(owners.get(item['id']),'remarks',None) or ''))
            if issue:pending.append(f"{item['order_no']}：{issue}")
        def visit(item,inherited_month):
            current_month=item.get('billing_month') or inherited_month
            if item['pricing_mode']=='fixed':
                if current_month==month:
                    value=item.get('adjusted_total_incl_tax' if preference['tax_included'] else 'adjusted_total')
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
                    basis=f"{dimension} · {METRICS.get(price.get('quantity_metric'),price.get('quantity_metric') or '')}（每{Decimal(size):f}计价）"
                    line={**item,'language_pair':price.get('language_pair') or item['language_pair']}
                    append(line,str(quantity) if quantity is not None else None,unit,amount,price['currency'],item.get('explanation',''),basis,
                           f'未填写{label}单价或对应工作量' if unit is None or quantity is None or amount is None else None)
            override=item.get('adjusted_total_incl_tax' if preference['tax_included'] else 'adjusted_total')
            if override is not None and current_month==month and len(rows)>start:
                matching=[row for row in rows[start:] if row['currency']==item['currency']]
                if matching and all(row['subtotal'] is not None for row in matching):
                    difference=Decimal(override)-sum(Decimal(row['subtotal']) for row in matching)
                    if difference:append(item,None,None,difference,item['currency'],item.get('explanation',''),'总价调整')
        visit(*selected)
        if len(rows)>10000:raise HTTPException(422,'本次对账单超过10000条，请缩小项目范围')
    sums={}
    for row in rows:
        if row['subtotal'] is not None:sums[row['currency']]=sums.get(row['currency'],Decimal(0))+Decimal(row['subtotal'])
    settings=settings_value(db.get(CustomerStatementSettings,'company'))
    result=dict(company=COMPANY,title='对账单',client_name=client.client_name or client.client_short_name,client_code=client.client_code,
        month=month,scope=scope,tax_included=preference['tax_included'],rows=rows,totals={key:money(value) for key,value in sums.items()},pending=pending,
        settings={key:settings[key] for key in ('bank_name','account_name','account_number')},stamp_image=settings['stamp_image'] or settings['default_stamp'])
    result['statement_version']=hashlib.sha256(json.dumps(result,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    result['generated_at']=business_now().isoformat()
    return result


@router.get('/translation-statements/preview')
def preview(project_id:UUID,month:str=Query(pattern=MONTH),scope:Literal['project','customer']='project',order_id:UUID|None=None,db=Depends(get_db),user=Depends(read_projects)):
    return build_statement(db,project_id,order_id,month,scope)


def excel_bytes(data):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side
    from openpyxl.drawing.image import Image as ExcelImage
    from project_export_excel import _safe_text
    workbook=Workbook();sheet=workbook.active;sheet.title='对账单';sheet.sheet_view.showGridLines=False
    sheet.merge_cells('A1:G1');sheet['A1']=data['company'];sheet['A1'].font=Font(name='微软雅黑',size=18,bold=True)
    sheet.merge_cells('A2:G2');sheet['A2']='对账单';sheet['A2'].font=Font(name='微软雅黑',size=16,bold=True)
    sheet.merge_cells('A3:G3');sheet['A3']=_safe_text(f"客户：{data['client_name']}    账单月份：{data['month']}    金额口径：{'含税' if data['tax_included'] else '不含税'}")
    sheet.append([]);sheet.append(['来稿日期','项目名称','翻译方向','工作量（计价方式）','单价','小计','备注'])
    for row in data['rows']:
        workload=(str(row['quantity'])+'\n' if row['quantity'] is not None else '')+row['basis']
        unit=f"{row['currency']} {row['unit_price']}（{row['unit_label']}）" if row['unit_price'] is not None else '-'
        values=[row['received_date'],row['project_name'],row['language_pair'],workload,unit,
                f"{row['currency']} {row['subtotal']}" if row['subtotal'] is not None else '待补',row['remarks']]
        sheet.append([_safe_text(value) for value in values]);sheet.row_dimensions[sheet.max_row].height=46
    total_row=sheet.max_row+1;sheet.merge_cells(start_row=total_row,start_column=1,end_row=total_row,end_column=5)
    sheet.cell(total_row,1,'合计（已登记金额）' if data['pending'] else '合计')
    sheet.cell(total_row,6,'\n'.join(f'{key} {value}' for key,value in data['totals'].items()) or '-')
    sheet.row_dimensions[total_row].height=max(55,len(data['totals'])*20)
    border=Border(*( [Side(style='thin',color='777777')]*4 ))
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
            if cell.row>=5:cell.border=border;cell.font=Font(name='微软雅黑',size=10,bold=cell.row in (5,total_row))
    sheet.append([])
    for text in ['信实翻译公司 账户信息','开户行：'+data['settings']['bank_name'],'账户名：'+data['settings']['account_name'],'账号：'+data['settings']['account_number']]:
        sheet.append([_safe_text(text)]);sheet.merge_cells(start_row=sheet.max_row,start_column=1,end_row=sheet.max_row,end_column=7)
        sheet.cell(sheet.max_row,1).alignment=Alignment(horizontal='left',vertical='center');sheet.row_dimensions[sheet.max_row].height=24
    if data['pending']:
        sheet.append([_safe_text('待补资料：'+'；'.join(data['pending']))]);sheet.merge_cells(start_row=sheet.max_row,start_column=1,end_row=sheet.max_row,end_column=7);sheet.cell(sheet.max_row,1).alignment=Alignment(wrap_text=True);sheet.row_dimensions[sheet.max_row].height=50
    image=ExcelImage(BytesIO(base64.b64decode(data['stamp_image'].split(',',1)[1])));image.width=image.height=130
    sheet.add_image(image,f'D{max(5,total_row-1)}')
    for index,width in zip('ABCDEFG',[16,36,22,33,30,22,34]):sheet.column_dimensions[index].width=width
    sheet.sheet_properties.pageSetUpPr.fitToPage=True;sheet.page_setup.orientation='landscape';sheet.page_setup.paperSize=sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth=1;sheet.page_setup.fitToHeight=0;sheet.print_title_rows='1:5';sheet.print_options.horizontalCentered=True
    output=BytesIO();workbook.save(output);return output.getvalue()


@router.get('/translation-statements/excel')
def export_excel(project_id:UUID,month:str=Query(pattern=MONTH),scope:Literal['project','customer']='project',order_id:UUID|None=None,version:str|None=Query(None,pattern=r'^[a-f0-9]{64}$'),db=Depends(get_db),user=Depends(read_projects)):
    data=build_statement(db,project_id,order_id,month,scope)
    if version and version!=data['statement_version']:raise HTTPException(409,'对账单数据已变化，请重新生成后下载')
    if not data['rows']:raise HTTPException(422,'所选账单月份暂无可生成的项目')
    filename=quote(f"信实翻译对账单_{data['month']}_{data['client_code']}.xlsx")
    return Response(excel_bytes(data),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f"attachment; filename*=UTF-8''{filename}"})
