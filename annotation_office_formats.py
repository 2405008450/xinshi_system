"""Office 文件类型与 OOXML 校验；不通过 HTML 转换文档。"""
import io
import posixpath
import zipfile

from defusedxml.ElementTree import fromstring
from fastapi import HTTPException

LIMIT = 20 * 1024 * 1024
FORMATS = {
    'docx': {'editor': 'word', 'part': 'word/document.xml', 'root': 'document',
             'namespace': 'wordprocessingml',
             'mime': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
             'main_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'},
    'xlsx': {'editor': 'cell', 'part': 'xl/workbook.xml', 'root': 'workbook',
             'namespace': 'spreadsheetml',
             'mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
             'main_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'},
}


def file_kind(name):
    kind = str(name or '').rsplit('.', 1)[-1].lower()
    if '.' not in str(name or '') or kind not in FORMATS:
        raise HTTPException(400, 'Office 在线编辑仅支持 .docx、.xlsx')
    return kind


def validate_office(data, kind):
    if not data or len(data) > LIMIT:
        raise HTTPException(413, 'Office 文件不能为空或超过20MB')
    fmt = FORMATS[kind]
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            names = [item.filename for item in entries]
            if len(entries) > 10000 or len(names) != len(set(names)) or sum(item.file_size for item in entries) > 200 * 1024 * 1024:
                raise ValueError('文档解压大小超限或存在重复文件')
            for item in entries:
                name = item.filename
                if item.flag_bits & 1 or name.startswith('/') or '\\' in name or '..' in name.split('/'):
                    raise ValueError('文档加密或路径无效')
                if name.lower().endswith('vbaproject.bin') or '/macrosheets/' in name.lower():
                    raise ValueError('不允许宏文档')
            def xml(name):
                item = archive.getinfo(name)
                if item.file_size > LIMIT:
                    raise ValueError('XML 大小超限')
                return fromstring(archive.read(name))
            types = xml('[Content_Types].xml')
            if types.tag != '{http://schemas.openxmlformats.org/package/2006/content-types}Types':
                raise ValueError('文档内容类型清单无效')
            main_type = next((node.get('ContentType') for node in types if node.get('PartName') == '/' + fmt['part']), None)
            if main_type != fmt['main_type'] or any('macroenabled' in node.get('ContentType', '').lower() for node in types):
                raise ValueError('文档类型不匹配或含宏')
            root = xml(fmt['part'])
            namespaces = (f'http://schemas.openxmlformats.org/{fmt["namespace"]}/2006/main',
                          f'http://purl.oclc.org/ooxml/{fmt["namespace"]}/main')
            if root.tag not in {f'{{{ns}}}{fmt["root"]}' for ns in namespaces}:
                raise ValueError('正文结构无效')
            if kind == 'xlsx':
                ns = root.tag[1:].split('}')[0]
                sheets = root.findall(f'{{{ns}}}sheets/{{{ns}}}sheet')
                relationships = {node.get('Id'): node for node in xml('xl/_rels/workbook.xml.rels')}
                if not sheets:
                    raise ValueError('工作簿没有工作表')
                for sheet in sheets:
                    rid = next((value for key, value in sheet.attrib.items() if key.endswith('}id')), None)
                    rel = relationships.get(rid)
                    if rel is None or rel.get('TargetMode') == 'External':
                        raise ValueError('工作表关联无效')
                    tag = rel.get('Type', '').rsplit('/', 1)[-1]
                    if tag not in ('worksheet', 'chartsheet'):
                        raise ValueError('不支持的工作表类型')
                    target = rel.get('Target', '')
                    part = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('xl', target))
                    if not part.startswith('xl/') or xml(part).tag != f'{{{ns}}}{tag}':
                        raise ValueError('工作表内容无效')
    except Exception as exc:
        raise HTTPException(400, f'文件不是有效的未加密 .{kind} 文档，或包含不支持的宏') from exc


def blank_xlsx():
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="工作表1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>')
    return output.getvalue()
