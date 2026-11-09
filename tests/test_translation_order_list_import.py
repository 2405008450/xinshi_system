from io import BytesIO
from zipfile import ZipFile
import pytest
from openpyxl import Workbook
from translation_order_list_import import parse_document, analyze, ListPreview
from tests.test_chat_participant_access import environment
from tests.test_translation_direction_children import case


def preview(rows, **kwargs):
    return analyze(ListPreview(rows=rows, **kwargs))


@pytest.mark.parametrize('encoding', ['utf-8-sig', 'utf-16', 'gb18030'])
def test_text_encodings(encoding):
    assert parse_document('清单.txt', '合同.docx\n附件.pdf'.encode(encoding))['text']=='合同.docx\n附件.pdf'


def test_word_and_excel_parsing():
    output=BytesIO()
    with ZipFile(output,'w') as archive:
        archive.writestr('word/document.xml','''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>合同.docx</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>路径</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>文件名</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>''')
    assert parse_document('清单.docx',output.getvalue())['text']=='合同.docx\n路径\t文件名'
    book=Workbook();book.active.append(['路径','文件名']);book.active.append([r'D:\项目\资料','合同.docx'])
    output=BytesIO();book.save(output)
    result=parse_document('清单.xlsx',output.getvalue())
    assert result['sheets'][0]['rows'][1]==[r'D:\项目\资料','合同.docx']


def test_flat_names_and_duplicates():
    result=preview([['合同.docx'],['附件.pdf'],['合同.docx']])
    assert result['file_names']==['合同.docx','附件.pdf'] and len(result['warnings'])==1


def test_editable_pdf_and_scanned_pdf():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer=PdfWriter();page=writer.add_blank_page(600,800)
    output=BytesIO();writer.write(output)
    with pytest.raises(ValueError,match='未提取到可编辑文字'):parse_document('扫描.pdf',output.getvalue())
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 10 700 Td (contract.docx) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    output=BytesIO();writer.write(output)
    assert 'contract.docx' in parse_document('清单.pdf',output.getvalue())['text']


def test_path_columns_build_four_levels_and_log_empty_directories():
    result=preview([
        ['路径','文件名'],[r'D:\项目','根.pdf'],
        [r'D:\项目\一级\二级\三级','末级.docx'],
        [r'D:\项目\空目录',''],
    ],path_column=0,filename_column=1,start_row=2)
    assert result['root_path']==r'D:\项目'
    entries={row['relative_path']:row['files'] for row in result['entries']}
    assert entries['项目/一级/二级/三级']==['末级.docx']
    assert result['empty_folders']==['项目/空目录'] and result['order_count']==5


def test_relative_paths_root_and_case_deduplication():
    result=preview([[r'项目\资料\a.pdf'],[r'项目\资料\A.pdf']],root_path=r'D:\项目')
    assert result['order_count']==2 and len(result['warnings'])==1


@pytest.mark.parametrize('rows,kwargs,message',[
    ([[r'D:\项目\a.pdf'],[r'E:\资料\b.pdf']],{},'同一根目录'),
    ([[r'E:\其他\a.pdf']],{'root_path':r'D:\项目'},'不在所选根路径'),
    ([[r'D:\项目\..\a.pdf']],{},'相对跳转'),
    ([[r'D:\项目\1\2\3\4\a.pdf']],{'root_path':r'D:\项目'},'超过四级'),
    ([['https://example.com/a.pdf']],{},'不支持网址'),
])
def test_invalid_paths(rows,kwargs,message):
    with pytest.raises(ValueError,match=message):preview(rows,**kwargs)


def test_manifest_persistence_uses_list_without_opening_network(case,monkeypatch):
    monkeypatch.setenv('OPENPATH_ALLOWED_ROOTS',r'\\test-server\share')
    from tests.test_translation_folder_orders import root_project
    from translation_folder_orders import FolderImport, import_folders
    db,user,crud=case;root=root_project(case)
    plan=preview([[r'\\test-server\share\项目\资料\a.pdf']],root_path=r'\\test-server\share\项目')
    result=import_folders(db,FolderImport(parent_project_id=root.id,source_kind='manifest',root_path=plan['root_path'],entries=plan['entries']),user.id)
    assert result['created_count']==2
    saved=crud.get_translation_project(db,root.id)
    assert next(row for row in saved.sub_orders if row.sub_project_name=='a.pdf').network_file_path==r'\\test-server\share\项目\资料\a.pdf'
