"""对账单文件导出：中文字体嵌入、固定业务排版，不包含浏览器页眉页脚。"""
import base64
import re
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape


@lru_cache(maxsize=1)
def chinese_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    for path in ('C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simsun.ttc','/usr/share/fonts/truetype/arphic/uming.ttc'):
        if Path(path).is_file():
            pdfmetrics.registerFont(TTFont('StatementChinese',path))
            bold_path=Path('C:/Windows/Fonts/msyhbd.ttc')
            pdfmetrics.registerFont(TTFont('StatementChineseBold',str(bold_path) if bold_path.is_file() else path))
            pdfmetrics.registerFontFamily('StatementChinese',normal='StatementChinese',bold='StatementChineseBold')
            return 'StatementChinese'
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    return 'STSong-Light'


def pdf_bytes(statements):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, PageBreak, Flowable, KeepTogether
    from customer_statements import statement_title
    output=BytesIO();font=chinese_font()
    document=SimpleDocTemplate(output,pagesize=landscape(A4),leftMargin=14*mm,rightMargin=14*mm,topMargin=14*mm,bottomMargin=14*mm,title='客户对账单',author='信实翻译')
    styles={key:ParagraphStyle(key,fontName=font,fontSize=size,leading=size*1.45,alignment=alignment,wordWrap='CJK') for key,size,alignment in [('cell',9,TA_CENTER),('date',8,TA_CENTER),('company',15,TA_CENTER),('title',16.5,TA_CENTER),('text',10,TA_LEFT),('footer',8,TA_LEFT),('right',10,TA_RIGHT),('heading',9,TA_CENTER),('total',9,TA_CENTER),('total_label',9,TA_RIGHT),('account',11.25,TA_LEFT),('pending',9,TA_LEFT)]}
    for key in ('company','title','heading','total','total_label','account'):
        styles[key].fontName='StatementChineseBold' if font=='StatementChinese' else font
    styles['footer'].textColor=colors.HexColor('#64748b')
    styles['pending'].textColor=colors.HexColor('#a54a21')
    def paragraph(value,style='cell'):
        return Paragraph(escape(str(value if value is not None else '')).replace('\n','<br/>'),styles[style])
    class Stamp(Flowable):
        def __init__(self,image):Flowable.__init__(self);self.image=image;self.width=document.width;self.height=0
        def draw(self):
            self.canv.drawImage(ImageReader(self.image),document.width*.44,-8,width=34*mm,height=34*mm,mask='auto')
    story=[]
    for index,data in enumerate(statements):
        if index:story.append(PageBreak())
        story.extend([paragraph(data['company'],'company'),Spacer(1,4*mm),paragraph(statement_title(data),'title'),Spacer(1,6*mm)])
        meta=LongTable([[paragraph('客户：'+data['client_name'],'text'),paragraph('账单月份：'+data['month']+'　'+('含税' if data['tax_included'] else '不含税'),'right')]],colWidths=[document.width*.6,document.width*.4])
        meta.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]));story.extend([meta,Spacer(1,3*mm)])
        customer_order=any(str(row.get('customer_order_no') or '').strip() for row in data['rows'])
        origin=any(row.get('origin_client_id') or row.get('origin_client_name') for row in data['rows'])
        headings=(['原客户'] if origin else [])+(['客户单号'] if customer_order else [])+['来稿日期','项目名称','翻译方向','工作量（计价方式）','单价','小计','备注']
        weights=([24] if origin else [])+([24] if customer_order else [])+[24,35.7,17.6,29.7,30,22,34]
        cells=[[paragraph(label,'heading') for label in headings]]
        for row in data['rows']:
            basis=re.sub(r'[（(]每1(?:\.0+)?计价[）)]','',row.get('basis') or '')
            unit='-' if row.get('unit_price') is None else f"{row['currency']} {Decimal(str(row['unit_price'])).quantize(Decimal('.001'),rounding=ROUND_HALF_UP):.3f}"
            remark=('汇总参考，不重复计入合计。' if row.get('counted_in_total') is False else '')+(row.get('remarks') or '')
            values=([row.get('origin_client_name') or data['client_name']] if origin else [])+([row.get('customer_order_no') or ''] if customer_order else [])+[str(row.get('received_date') or '-'),row['project_name'],row['language_pair'],str(row['quantity'])+'\n'+basis if row.get('quantity') is not None else basis,unit,f"{row['currency']} {row['subtotal']}" if row.get('subtotal') is not None else '待补',remark]
            cells.append([paragraph(value,'date' if column==int(origin)+int(customer_order) else 'cell') for column,value in enumerate(values)])
        label_width=document.width*sum(weights[:-2])/sum(weights)-12
        summary=LongTable([[paragraph('账单日期：'+(data.get('issue_date') or '—'),'footer'),paragraph('合计（已登记金额）' if data['pending'] else '合计','total_label')]],colWidths=[label_width*.6,label_width*.4])
        summary.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        cells.append([summary]+['']*(len(headings)-3)+[paragraph('\n'.join(f'{key} {value}' for key,value in data['totals'].items()),'total'),''])
        table=LongTable(cells,colWidths=[document.width*weight/sum(weights) for weight in weights],repeatRows=1,splitInRow=1)
        date_column=int(origin)+int(customer_order)
        table.setStyle(TableStyle([('LEFTPADDING',(date_column,0),(date_column,-2),2),('RIGHTPADDING',(date_column,0),(date_column,-2),2),('GRID',(0,0),(-1,-1),.5,colors.HexColor('#888888')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('SPAN',(0,-1),(-3,-1)),('SPAN',(-2,-1),(-1,-1))]))
        story.append(table)
        if data.get('stamp_image'):
            story.append(Stamp(BytesIO(base64.b64decode(data['stamp_image'].split(',',1)[1]))))
        account=[Spacer(1,8*mm),paragraph('收款账户信息','account')]
        for label,key in [('开户行','bank_name'),('账户名','account_name'),('账号','account_number')]:account.extend([Spacer(1,2*mm),paragraph(label+'：'+(data['settings'].get(key) or ''),'text')])
        story.append(KeepTogether(account))
        if data['pending']:story.extend([Spacer(1,3*mm),paragraph('待补资料：'+'；'.join(data['pending']),'pending')])
    document.build(story)
    return output.getvalue()
