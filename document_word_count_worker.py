"""单文件隔离统计进程，防止损坏的 Office 文件阻塞服务。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile
from file_word_counter import count_text
from file_word_extractors import _extract_docx_content, _extract_xlsx_content, _extract_pptx_content, _extract_txt_content

EXTENSIONS = {'.docx', '.xlsx', '.pptx', '.doc', '.xls', '.ppt', '.pdf', '.txt'}
POLICY = 'file-text-v4-local-1'

def count_file(path, include_hidden=False, include_extra=False):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in EXTENSIONS:
        raise ValueError('不支持的文件类型')
    if suffix in {'.doc', '.xls', '.ppt'}:
        executable = os.getenv('LIBREOFFICE_PATH') or shutil.which('soffice') or shutil.which('libreoffice')
        if not executable:
            candidate = Path('C:/Program Files/LibreOffice/program/soffice.exe')
            executable = str(candidate) if candidate.is_file() else None
        if not executable:
            raise ValueError('旧版 Office 文件需要 LibreOffice，请安装或先另存为 DOCX/XLSX/PPTX')
        with tempfile.TemporaryDirectory(prefix='xinshi-count-convert-') as temporary:
            directory = Path(temporary)
            target_suffix = {'.doc':'.docx', '.xls':'.xlsx', '.ppt':'.pptx'}[suffix]
            target = directory / (path.stem + target_suffix)
            conversion = subprocess.run([executable, '-env:UserInstallation='+ (directory/'profile').as_uri(),
                '--headless', '--convert-to', target_suffix[1:], '--outdir', str(directory), str(path)],
                capture_output=True, timeout=60, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if conversion.returncode or not target.exists():
                raise ValueError('旧格式转换失败，请检查文件是否损坏或被加密')
            return count_file(target, include_hidden, include_extra)
    if suffix in {'.docx','.xlsx','.pptx'}:
        with ZipFile(path) as archive:
            if sum(info.file_size for info in archive.infolist()) > 512*1024*1024:
                raise ValueError('Office 解压内容超过 512 MB 限制')
    if suffix == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('加密 PDF 无法读取，请先解除密码')
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        if not text.strip():
            return dict(status='needs_ocr', message='未提取到文字，需要 OCR 后统计', words=None, pages=len(reader.pages))
        metrics = count_text(text)
        return dict(status='counted',words=metrics.word_count,characters_no_spaces=metrics.non_space_chars,
                    pages=len(reader.pages),hidden_words=0,extra_words=0,policy=POLICY)
    extractor = {'.docx':_extract_docx_content,'.xlsx':_extract_xlsx_content,'.pptx':_extract_pptx_content,'.txt':_extract_txt_content}[suffix]
    content = extractor(path)
    items = [item for item in content.items if include_hidden or not item.is_hidden]
    main = '\n'.join(item.text for item in items if not item.is_extra)
    extra = '\n'.join(item.text for item in items if item.is_extra)
    hidden = '\n'.join(item.text for item in content.items if item.is_hidden and not item.is_extra)
    if not (main+extra).strip():
        return dict(status='needs_ocr',message='未提取到可编辑文字，空白或扫描文件需人工核验',words=None)
    main_words = count_text(main).word_count
    if suffix == '.docx' and content.portable_word_count is not None:
        main_words = content.portable_word_count
    return dict(status='counted',words=main_words+(count_text(extra).word_count if include_extra else 0),
        characters_no_spaces=count_text(main+(extra if include_extra else '')).non_space_chars,
        pages=content.page_count or None,hidden_words=count_text(hidden).word_count,
        extra_words=count_text(extra).word_count,policy=POLICY)

if __name__ == '__main__':
    try:
        result = count_file(sys.argv[1],sys.argv[2]=='1',sys.argv[3]=='1')
    except Exception as exc:
        result = dict(status='failed',message=str(exc),words=None)
    print(json.dumps(result,ensure_ascii=False))
