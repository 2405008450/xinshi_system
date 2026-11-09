"""只解析用户提交的清单内容；不打开清单中列出的本地或网络文件。"""
from io import BytesIO
import ntpath
from zipfile import ZipFile
from xml.etree import ElementTree
from pydantic import BaseModel, Field
from translation_file_name_rules import normalize_single_file_name
from translation_folder_orders import FolderEntry, normalized_entries, folder_name
from path_security import validate_managed_path

MAX_BYTES=20*1024*1024
MAX_ROWS=5000
MAX_COLUMNS=64
MAX_TEXT=1000000


def zip_check(content):
    with ZipFile(BytesIO(content)) as archive:
        entries=archive.infolist()
        if len(entries)>5000 or sum(row.file_size for row in entries)>100*1024*1024:
            raise ValueError('文件解压后过大，请精简清单')


def text_lines(content):
    if len(content)>MAX_TEXT:raise ValueError('清单文字过多，请分批导入')
    return content.replace('\r\n','\n').replace('\r','\n')


def decode_text(content):
    for encoding in (['utf-16'] if content.startswith((b'\xff\xfe',b'\xfe\xff')) else ['utf-8-sig','gb18030']):
        try:return text_lines(content.decode(encoding))
        except UnicodeDecodeError:continue
    raise ValueError('TXT 编码无法识别，请另存为 UTF-8')


def parse_document(filename,content):
    if not content:raise ValueError('文件为空')
    if len(content)>MAX_BYTES:raise ValueError('文件不得超过20MB')
    suffix=ntpath.splitext(filename)[1].lower()
    try:
        if suffix=='.txt':return {'kind':'text','text':decode_text(content)}
        if suffix=='.docx':
            zip_check(content)
            with ZipFile(BytesIO(content)) as archive:xml=archive.read('word/document.xml')
            if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:raise ValueError('Word 文档包含不支持的 XML 声明')
            root=ElementTree.fromstring(xml);ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            def paragraph(node):
                parts=[]
                for child in node.iter():
                    name=child.tag.rsplit('}',1)[-1]
                    if name=='t':parts.append(child.text or '')
                    elif name=='tab':parts.append('\t')
                    elif name in ('br','cr'):parts.append('\n')
                return ''.join(parts)
            lines=[]
            for node in root.find('w:body',ns):
                if node.tag.endswith('}p'):lines.append(paragraph(node))
                elif node.tag.endswith('}tbl'):
                    for row in node.findall('w:tr',ns):lines.append('\t'.join(' '.join(paragraph(p) for p in cell.findall('w:p',ns)) for cell in row.findall('w:tc',ns)))
            return {'kind':'text','text':text_lines('\n'.join(lines))}
        if suffix=='.pdf':
            from pypdf import PdfReader
            reader=PdfReader(BytesIO(content))
            if reader.is_encrypted:raise ValueError('请先解除 PDF 密码保护')
            if len(reader.pages)>500:raise ValueError('PDF 超过500页，请分批导入')
            text=text_lines('\n'.join(page.extract_text() or '' for page in reader.pages))
            if not text.strip():raise ValueError('PDF 未提取到可编辑文字；扫描图片 PDF 请先识别文字，再复制导入')
            return {'kind':'text','text':text}
        if suffix in ('.xlsx','.xls'):
            sheets=[]
            if suffix=='.xlsx':
                zip_check(content)
                from openpyxl import load_workbook
                book=load_workbook(BytesIO(content),read_only=True,data_only=True,keep_links=False)
                try:
                    if len(book.worksheets)>30:raise ValueError('工作表过多，请保留需要导入的工作表')
                    for sheet in book.worksheets:
                        if sheet.max_row>MAX_ROWS or sheet.max_column>MAX_COLUMNS:raise ValueError('每张工作表最多5000行、64列，请删除无关行列后导入')
                        sheets.append({'name':sheet.title,'rows':[[str(value)[:4000] if value is not None else '' for value in row] for row in sheet.iter_rows(values_only=True)]})
                finally:book.close()
            else:
                import xlrd
                book=xlrd.open_workbook(file_contents=content,on_demand=True)
                try:
                    if book.nsheets>30:raise ValueError('工作表过多，请保留需要导入的工作表')
                    for sheet in book.sheets():
                        if sheet.nrows>MAX_ROWS or sheet.ncols>MAX_COLUMNS:raise ValueError('每张工作表最多5000行、64列')
                        sheets.append({'name':sheet.name,'rows':[[str(value) if value!='' else '' for value in sheet.row_values(index)] for index in range(sheet.nrows)]})
                finally:book.release_resources()
            return {'kind':'workbook','sheets':sheets}
        raise ValueError('支持 TXT、Word（.docx）、可编辑 PDF、Excel（.xlsx/.xls）；旧版 .doc 请另存为 .docx 或复制文字')
    except ValueError:raise
    except Exception as exc:raise ValueError('文件解析失败，请检查格式，或复制内容到编辑框中导入') from exc


class ListPreview(BaseModel):
    rows:list[list[str]]=Field(min_length=1,max_length=MAX_ROWS)
    filename_column:int=Field(default=0,ge=-1,lt=MAX_COLUMNS)
    path_column:int=Field(default=-1,ge=-1,lt=MAX_COLUMNS)
    start_row:int=Field(default=1,ge=1,le=MAX_ROWS)
    root_path:str=Field(default='',max_length=2000)


def path_value(value):
    value=str(value or '').strip().strip('"')
    if '://' in value:raise ValueError('此处只支持文件路径，不支持网址')
    value=value.replace('/','\\')
    if len(value)>2000 or '\x00' in value or any(part in ('.','..') for part in value.split('\\')):
        raise ValueError('路径过长或包含相对跳转，请填写规范路径')
    return ntpath.normpath(value) if value else ''


def analyze(payload):
    if payload.filename_column<0 and payload.path_column<0:raise ValueError('请选择文件名列或路径列')
    supplied=[];warnings=[];flat=[];seen=set()
    for index,cells in enumerate(payload.rows[payload.start_row-1:],payload.start_row):
        if len(cells)>MAX_COLUMNS:raise ValueError('清单列数不能超过64列')
        cell=lambda col:cells[col].strip() if 0<=col<len(cells) else ''
        name=cell(payload.filename_column);path=cell(payload.path_column)
        if not name and not path:continue
        if len(name)>2000 or len(path)>2000:raise ValueError(f'第{index}行路径或名称过长')
        directory=bool(path.endswith(('\\','/')) and not name)
        if not path and ('\\' in name or '/' in name):path,name=name,''
        if path:
            path=path_value(path)
            if name:
                folder_name(name)
                full=path.rstrip('\\') if ntpath.basename(path.rstrip('\\')).casefold()==name.casefold() else ntpath.join(path,name)
            else:full=path.rstrip('\\');name=ntpath.basename(full)
            supplied.append({'line':index,'path':full,'name':name,'directory':directory})
        else:
            name=normalize_single_file_name(name)
            if name.casefold() in seen:warnings.append(f'第{index}行重复文件名已跳过：{name}');continue
            seen.add(name.casefold());flat.append(name)
    if not supplied:
        if not flat:raise ValueError('没有可导入的文件名')
        if len(flat)>500:raise ValueError('不含路径的文件名清单每次最多500条')
        return {'kind':'flat','file_names':flat,'root_path':'','entries':[],'warnings':warnings,'order_count':len(flat)}
    root=path_value(payload.root_path).rstrip('\\')
    absolute=[row for row in supplied if ntpath.isabs(row['path'])]
    for row in supplied:
        has_children=any(other['path'].casefold().startswith(row['path'].casefold()+'\\') for other in supplied)
        row['directory']=row['directory'] or has_children or not ntpath.splitext(row['name'])[1]
        if not row['directory']:normalize_single_file_name(row['name'])
    if not root:
        if len(absolute)!=len(supplied):raise ValueError('清单含相对路径，请填写根路径后重新分析')
        try:root=ntpath.commonpath([row['path'] if row['directory'] else ntpath.dirname(row['path']) for row in supplied])
        except ValueError:raise ValueError('路径不属于同一根目录，请分批导入')
    if not ntpath.isabs(root) or not ntpath.basename(root):raise ValueError('请指定具体根文件夹，不能只使用盘符或不同共享目录')
    root=validate_managed_path(root)
    root_name=folder_name(ntpath.basename(root));entries={root_name:[]};dedupe=set();case_dirs={root_name.casefold():root_name}
    def add_directory(parts):
        parent=''
        for depth in range(1,len(parts)+1):
            relative=parent+'/'+parts[depth-1] if parent else parts[depth-1]
            canonical=case_dirs.setdefault(relative.casefold(),relative)
            entries.setdefault(canonical,[])
            parent=canonical
        return parent
    for row in supplied:
        full=row['path']
        if not ntpath.isabs(full):
            relative=full
            if relative.casefold().startswith(root_name.casefold()+'\\'):relative=relative[len(root_name)+1:]
            full=ntpath.join(root,relative)
        try:inside=ntpath.commonpath([root,full]).casefold()==root.casefold()
        except ValueError:inside=False
        if not inside:raise ValueError(f"第{row['line']}行不在所选根路径下")
        full=validate_managed_path(full)
        relative=ntpath.relpath(full,root)
        parts=[root_name]+([] if relative=='.' else relative.split('\\'))
        for part in parts:folder_name(part)
        if len(parts)>(4 if row['directory'] else 5):raise ValueError(f"第{row['line']}行超过四级子订单，无法导入：{full}")
        if full.casefold() in dedupe:warnings.append(f"第{row['line']}行重复路径已跳过：{full}");continue
        dedupe.add(full.casefold())
        if row['directory']:add_directory(parts)
        else:
            directory=add_directory(parts[:-1]);entries[directory].append(normalize_single_file_name(parts[-1]))
    for name in flat:
        if any(name.casefold()==existing.casefold() for existing in entries[root_name]):continue
        entries[root_name].append(name)
    if flat:warnings.append('未填写路径的文件已放在根目录下')
    normalized=normalized_entries([FolderEntry(relative_path=relative,files=files) for relative,files in entries.items()])
    empty=[relative for relative in normalized if not any(files for child,files in normalized.items() if child==relative or child.startswith(relative+'/'))]
    order_count=sum(len(files) for files in normalized.values())+len(normalized)-1-len([relative for relative in empty if relative!=root_name])
    return {'kind':'tree','root_path':root,'entries':[{'relative_path':relative,'files':files} for relative,files in normalized.items()],
            'warnings':warnings,'empty_folders':empty,'order_count':order_count}
