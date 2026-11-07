"""含母订单、四级子订单、完整路径和统计的分层 Excel。"""
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Alignment,Font,PatternFill
from annotation_progress_time import business_now
from word_count_service import ENTITY_DIMENSIONS,METRIC_TYPES

LABELS={'company':'我司统计','customer':'客户统计','preliminary':'预统计（不用以计算费用）','translator_estimate':'译员预定','words':'字数','characters_no_spaces':'字符数（不计空格）','cjk_chars_korean_words':'中文字符和朝鲜语单词','foreign_words':'外文字数','documents':'份数','pages':'页数','minutes':'分钟','hours':'小时'}

def build_workbook(root,records=()):
    book=Workbook();sheet=book.active;sheet.title='订单层级与统计'
    sheet.append(['笔译订单层级与统计',root.order_no]);sheet.append(['导出时间',business_now().isoformat(timespec='seconds')])
    sheet.append(['层级','上级订单号','订单号','项目名称','类型','完整路径']+[LABELS[d]+' / '+LABELS[m] for d in ENTITY_DIMENSIONS for m in METRIC_TYPES])
    rows=[root,*sorted(root.sub_orders,key=lambda row:tuple(int(v) for v in row.sub_order_no.split('.')[1:]))]
    parents={row.sub_order_no.rsplit('.',1)[0] for row in root.sub_orders}
    for owner in rows:
        number=getattr(owner,'sub_order_no',None) or root.order_no
        depth=number.count('.')
        values=[depth,number.rsplit('.',1)[0] if depth else '',number,getattr(owner,'sub_project_name',None) or owner.project_name,'母订单' if not depth else '文件夹' if getattr(owner,'folder_info',None) else '汇总订单' if number in parents else '文件',owner.network_file_path or '']
        values += [(getattr(owner,'word_count_matrix',{}) or {}).get(d,{}).get(m) for d in ENTITY_DIMENSIONS for m in METRIC_TYPES]
        sheet.append(values);index=sheet.max_row
        sheet.cell(index,4).alignment=Alignment(indent=depth,vertical='top',wrap_text=True)
        sheet.row_dimensions[index].outlineLevel=depth
        for cell in sheet[index]:
            if isinstance(cell.value,str):cell.data_type='s'
        if number in parents:
            for cell in sheet[index]:cell.fill=PatternFill('solid',fgColor='F1F5F9');cell.font=Font(bold=True,color='334155')
    for cell in sheet[3]:cell.fill=PatternFill('solid',fgColor='334155');cell.font=Font(color='FFFFFF',bold=True);cell.alignment=Alignment(wrap_text=True)
    from openpyxl.utils import get_column_letter
    for i,width in enumerate([10,28,32,48,14,100]+[22]*32,1):sheet.column_dimensions[get_column_letter(i)].width=width
    sheet.freeze_panes='E4';sheet.auto_filter.ref=f'A3:{get_column_letter(sheet.max_column)}{sheet.max_row}'
    sheet.sheet_properties.outlinePr.summaryRight=False;sheet.sheet_properties.outlinePr.summaryBelow=False
    audit=book.create_sheet('目录导入与空文件夹记录')
    audit.append(['操作时间（UTC+8）','操作人','根路径','空文件夹相对路径','空文件夹完整路径','处理结果','本次新增订单数'])
    import ntpath
    for record in records:
        for relative in record['empty_folders'] or ['']:
            audit.append([record['created_at'],record['actor_name'],record['root_path'],relative,ntpath.join(record['root_path'],*relative.split('/')[1:]) if relative else '', '空文件夹，不生成子订单' if relative else '未发现空文件夹' if record.get('empty_detection_complete',True) else '兼容模式，无法检测空目录',record['created_count']])
    for row in audit:
        for cell in row:
            if isinstance(cell.value,str):cell.data_type='s'
    for column,width in zip('ABCDEFG',[30,20,80,60,100,30,20]):audit.column_dimensions[column].width=width
    audit.freeze_panes='D2';audit.auto_filter.ref=audit.dimensions
    output=BytesIO();book.save(output);return output.getvalue()
