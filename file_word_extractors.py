"""本地 Office 文本提取：迁移自 fastapi-llm-demo 已验收的 text-content-v4-hidden-scope。
独立运行，不导入原项目、不调用跨项目服务。原始计数与提取规则保持一致。
"""
from __future__ import annotations
import os, re
from pathlib import Path
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time
from typing import Any, Iterable, Optional
from zipfile import ZipFile
from lxml import etree
from openpyxl import load_workbook
from file_word_counter import count_text as _count_text, TextMetrics, SCRIPT_COUNT_FIELDS, QUOTE_COUNT_FIELDS, _is_hangul

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "v": "urn:schemas-microsoft-com:vml",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

@dataclass(frozen=True)
class TextItem:
    source_type: str
    source_label: str
    text: str
    is_extra: bool = False
    paragraph_count: int = 1
    line_count: int = 1
    image_count: int = 0
    is_hidden: bool = False
    parsed_word_count: Optional[int] = None

@dataclass(frozen=True)
class ExtractedContent:
    items: list[TextItem]
    page_count: int = 0
    paragraph_count: int = 0
    line_count: int = 0
    line_count_method: str = "estimated"
    image_count: int = 0
    stat_method: str = ""
    portable_word_count: Optional[int] = None
    file_type: str = ""
    warning: str = ""
    excel_cells: tuple[dict[str, Any], ...] = ()

def _extract_txt_content(path: Path) -> ExtractedContent:
    items = _extract_txt_text_items(path)
    text = "\n".join(item.text for item in items)
    return ExtractedContent(
        items=items,
        page_count=1 if text.strip() else 0,
        paragraph_count=_count_text_paragraphs(text),
        line_count=_count_text_lines(text),
        image_count=0,
        stat_method="TXT文本解析+Word近似计数",
        file_type="TXT",
    )

def _extract_txt_text_items(path: Path) -> list[TextItem]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "big5"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        try:
            import chardet

            detected = chardet.detect(raw).get("encoding") or "utf-8"
            text = raw.decode(detected, errors="replace")
        except Exception:
            text = raw.decode("utf-8", errors="replace")
    return [
        TextItem(
            "txt",
            "文本文件",
            text,
            is_extra=False,
            paragraph_count=_count_text_paragraphs(text),
            line_count=_count_text_lines(text),
        )
    ] if text else []

def _excel_value_to_text(value: Any) -> str:
    """与参考项目保持一致，使用缓存值而非公式或显示格式。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d" if value.time() == datetime_time(0) else "%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, datetime_time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()

def _xlsx_hidden_dimensions(package: ZipFile, worksheet_path: str) -> tuple[set[int], list[tuple[int, int]]]:
    """流式读取隐藏标记，保留大工作簿的只读解析方式。"""
    hidden_rows: set[int] = set()
    hidden_columns: list[tuple[int, int]] = []
    with package.open(worksheet_path.lstrip("/")) as stream:
        for _, element in etree.iterparse(stream, events=("end",)):
            tag = etree.QName(element).localname
            if element.get("hidden") in {"1", "true"}:
                if tag == "row":
                    hidden_rows.add(int(element.get("r")))
                elif tag == "col":
                    hidden_columns.append((int(element.get("min")), int(element.get("max"))))
            element.clear()
            while element.getprevious() is not None:
                del element.getparent()[0]
    return hidden_rows, hidden_columns

def _extract_xlsx_content(path: Path) -> ExtractedContent:
    workbook = load_workbook(path, read_only=True, data_only=True)
    items: list[TextItem] = []
    cells: list[dict[str, Any]] = []
    sheet_count = 0
    total_non_empty_rows = 0
    total_non_empty_cells = 0
    try:
        with ZipFile(path) as package:
            for sheet in workbook.worksheets:
                sheet_hidden = sheet.sheet_state != "visible"
                if not sheet_hidden:
                    sheet_count += 1
                hidden_rows, hidden_columns = _xlsx_hidden_dimensions(package, sheet._worksheet_path)
                values: dict[bool, list[str]] = {False: [], True: []}
                row_numbers: dict[bool, set[int]] = {False: set(), True: set()}
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value is None:
                            continue
                        text = _excel_value_to_text(cell.value)
                        if not text:
                            continue
                        reasons = []
                        if sheet_hidden:
                            reasons.append("隐藏工作表")
                        if cell.row in hidden_rows:
                            reasons.append("隐藏行")
                        if any(first <= cell.column <= last for first, last in hidden_columns):
                            reasons.append("隐藏列")
                        is_hidden = bool(reasons)
                        values[is_hidden].append(text)
                        row_numbers[is_hidden].add(cell.row)
                        cells.append({
                            "sheet": sheet.title,
                            "cell": cell.coordinate,
                            "is_hidden": is_hidden,
                            "hidden_reason": "、".join(reasons),
                            "text": text,
                        })
                for is_hidden in (False, True):
                    if values[is_hidden]:
                        items.append(TextItem(
                            "excel_hidden_cell" if is_hidden else "excel_cell",
                            f"工作表: {sheet.title}" + ("（隐藏内容）" if is_hidden else ""),
                            "\n".join(values[is_hidden]),
                            is_hidden=is_hidden,
                            paragraph_count=len(values[is_hidden]),
                            line_count=len(row_numbers[is_hidden]),
                        ))
                total_non_empty_rows += len(row_numbers[False])
                total_non_empty_cells += len(values[False])
    finally:
        workbook.close()
    return ExtractedContent(
        items=items,
        excel_cells=tuple(cells),
        page_count=sheet_count,
        paragraph_count=total_non_empty_cells,
        line_count=total_non_empty_rows,
        image_count=_count_ooxml_image_references(path, ("xl/drawings/",)),
        stat_method="XLSX单元格解析+Word近似计数（隐藏内容单列，页数按可见工作表数近似）",
        file_type="Excel",
    )

def _extract_pptx_content(path: Path) -> ExtractedContent:
    from pptx import Presentation

    prs = Presentation(str(path))
    items: list[TextItem] = []
    has_merged_cells = False
    for slide_index, slide in enumerate(prs.slides, start=1):
        texts: list[str] = []
        paragraph_count = 0
        line_count = 0
        for shape in _iter_ppt_shapes(slide.shapes):
            if getattr(shape, "has_table", False):
                has_merged_cells = has_merged_cells or any(cell.is_merge_origin for row in shape.table.rows for cell in row.cells)
            shape_texts, shape_paragraphs, shape_lines = _extract_ppt_shape_texts(shape)
            texts.extend(shape_texts)
            paragraph_count += shape_paragraphs
            line_count += shape_lines
        additional = _extract_ppt_smartart_texts(slide)
        for shape in _iter_ppt_shapes(slide.shapes):
            if getattr(shape, "has_chart", False):
                additional.append(_extract_ppt_chart_text(shape))
        for text in additional:
            if text.strip():
                items.append(TextItem("ppt_diagram", f"第 {slide_index} 张图表/SmartArt", text, is_extra=True))
        if texts:
            items.append(
                TextItem(
                    "ppt_slide",
                    f"第 {slide_index} 张幻灯片",
                    "\n".join(texts),
                    is_extra=False,
                    paragraph_count=paragraph_count or _count_text_paragraphs("\n".join(texts)),
                    line_count=line_count or _count_text_lines("\n".join(texts)),
                )
            )
        notes_text = _extract_ppt_notes_text(slide)
        if notes_text:
            items.append(
                TextItem(
                    "ppt_notes",
                    f"第 {slide_index} 张幻灯片备注",
                    notes_text,
                    is_extra=True,
                    paragraph_count=_count_text_paragraphs(notes_text),
                    line_count=_count_text_lines(notes_text),
                )
            )
    return ExtractedContent(
        items=items,
        page_count=len(prs.slides),
        paragraph_count=sum(item.paragraph_count for item in items),
        line_count=sum(item.line_count for item in items),
        image_count=_count_ooxml_image_references(path, ("ppt/slides/",)),
        stat_method="PPTX形状与表格解析+Word近似计数（备注、图表和SmartArt单列）",
        warning=("PPT 合并单元格按参考项目 COM 网格读取口径计数，合并文本可能重复计入" if has_merged_cells else ""),
        file_type="PPT",
    )

def _extract_ppt_smartart_texts(slide) -> list[str]:
    texts: list[str] = []
    for relation in slide.part.rels.values():
        if not relation.reltype.endswith("/diagramData"):
            continue
        try:
            root = etree.fromstring(relation.target_part.blob)
            texts.extend(
                (node.text or "").strip()
                for node in root.iter(_qn("a:t"))
                if (node.text or "").strip()
            )
        except Exception:
            continue
    return texts

def _iter_ppt_shapes(shapes) -> Iterable[Any]:
    for shape in shapes:
        yield shape
        nested = getattr(shape, "shapes", None)
        if nested is not None:
            yield from _iter_ppt_shapes(nested)

def _extract_ppt_shape_texts(shape) -> tuple[list[str], int, int]:
    texts: list[str] = []
    paragraph_count = 0
    line_count = 0
    if getattr(shape, "has_text_frame", False):
        text, paragraphs, lines = _extract_text_frame_text(shape.text_frame)
        if text:
            texts.append(text)
            paragraph_count += paragraphs
            line_count += lines
    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            for cell in row.cells:
                if cell.is_spanned:
                    continue
                text, paragraphs, lines = _extract_text_frame_text(cell.text_frame)
                if text:
                    # 参考项目逐网格调用 COM Cell，合并范围内会重复返回锚点文本。
                    repeat = max(1, cell.span_width * cell.span_height)
                    texts.extend([text] * repeat)
                    paragraph_count += paragraphs * repeat
                    line_count += lines * repeat
    return texts, paragraph_count, line_count

def _extract_text_frame_text(text_frame) -> tuple[str, int, int]:
    texts: list[str] = []
    paragraph_count = 0
    line_count = 0
    for paragraph in getattr(text_frame, "paragraphs", []) or []:
        text = (paragraph.text or "").strip()
        if not text:
            continue
        texts.append(text)
        paragraph_count += 1
        line_count += _count_text_lines(text)
    if not texts:
        text = (getattr(text_frame, "text", "") or "").strip()
        if text:
            texts.append(text)
            paragraph_count = _count_text_paragraphs(text)
            line_count = _count_text_lines(text)
    return "\n".join(texts), paragraph_count, line_count

def _extract_ppt_chart_text(shape) -> str:
    try:
        chart_space = getattr(shape.chart, "_chartSpace", None)
        if chart_space is None:
            return ""
        return "\n".join(_extract_chart_texts(etree.tostring(chart_space)))
    except Exception:
        return ""

def _extract_ppt_notes_text(slide) -> str:
    try:
        if not getattr(slide, "has_notes_slide", False):
            return ""
        notes_frame = getattr(slide.notes_slide, "notes_text_frame", None)
        if notes_frame is None:
            return ""
        text, _, _ = _extract_text_frame_text(notes_frame)
        return text
    except Exception:
        return ""

def _qn(tag: str) -> str:
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"

def _extract_docx_content(
    path: Path,
    *,
    use_word_native_line_count: bool = False,
) -> ExtractedContent:
    items = _extract_docx_text_items(path)
    semantic_items = _extract_docx_text_items(path, word_semantics=True)
    semantic_main = "\n".join(i.text for i in semantic_items if not i.is_extra)
    language_adjusted = semantic_main != "\n".join(i.text for i in items if not i.is_extra)
    numbering_words = _docx_numbering_words(path)
    app_props = _read_ooxml_app_properties(path)
    page_count = _to_positive_int(app_props.get("Pages"))
    app_line_count = _to_positive_int(app_props.get("Lines"))
    fallback_line_count = sum(item.line_count for item in items)
    native_line_count = 0
    if not app_line_count and use_word_native_line_count:
        native_line_count = _read_word_native_line_count(path)
    if native_line_count:
        line_count = native_line_count
        line_count_method = "word_native_repagination"
    elif app_line_count:
        line_count = app_line_count
        line_count_method = "document_property"
    else:
        line_count = fallback_line_count
        line_count_method = "explicit_line_breaks"
    return ExtractedContent(
        items=items,
        portable_word_count=(_count_text(semantic_main).word_count + numbering_words if language_adjusted or numbering_words else None),
        warning=("按文档语言标记处理韩文词边界；中文不因字体改变计数" if language_adjusted else ""),
        page_count=page_count,
        paragraph_count=sum(item.paragraph_count for item in items),
        line_count=line_count,
        line_count_method=line_count_method,
        image_count=_count_ooxml_image_references(path, ("word/",)),
        stat_method=(
            "DOCX实际文本统计+Word实时重新分页"
            if native_line_count
            else "DOCX实际文本统计（中文逐字、字体无关）"
        ),
        file_type="Word",
    )

def _docx_numbering_words(path: Path) -> int:
    """Document.ComputeStatistics 将有效自动列表编号计为一个词。"""
    with ZipFile(path) as archive:
        if "word/numbering.xml" not in archive.namelist():
            return 0
        numbering = etree.fromstring(archive.read("word/numbering.xml"))
        valid = {n.get(_qn("w:numId")) for n in numbering.findall("w:num", NS)}
        styles = {}
        if "word/styles.xml" in archive.namelist():
            styles = {n.get(_qn("w:styleId")): n for n in etree.fromstring(archive.read("word/styles.xml")).findall("w:style", NS)}

        def style_number(style_id, visited=None):
            visited = set() if visited is None else visited
            if style_id in visited or style_id not in styles:
                return None
            visited.add(style_id)
            style = styles[style_id]
            number = style.find("w:pPr/w:numPr/w:numId", NS)
            if number is not None:
                return number.get(_qn("w:val"))
            parent = style.find("w:basedOn", NS)
            return style_number(parent.get(_qn("w:val")), visited) if parent is not None else None

        total = 0
        for name in ["word/document.xml", "word/footnotes.xml", "word/endnotes.xml"]:
            if name not in archive.namelist():
                continue
            for paragraph in etree.fromstring(archive.read(name)).iter(_qn("w:p")):
                number = paragraph.find("w:pPr/w:numPr/w:numId", NS)
                style = paragraph.find("w:pPr/w:pStyle", NS)
                number_id = number.get(_qn("w:val")) if number is not None else style_number(style.get(_qn("w:val"))) if style is not None else None
                if number_id and number_id != "0" and number_id in valid and _extract_text_from_element(paragraph, skip_textboxes=True).strip():
                    total += 1
        return total

def _docx_word_semantic_xml(data: bytes) -> bytes:
    """为计数生成临时语义文本，原始提取文本及文件保持原样。"""
    root = etree.fromstring(data)
    changed = False
    for run in root.iter(_qn("w:r")):
        lang = run.find("w:rPr/w:lang", NS)
        korean = lang is not None and (lang.get(_qn("w:eastAsia")) == "ko-KR" or lang.get(_qn("w:val")) == "ko-KR")
        if not korean:
            continue
        for node in run.iter(_qn("w:t")):
            text = node.text or ""
            # 只处理明确的韩文词边界，绝不将中文按西文字体折叠成词。
            semantic = "".join("x" if _is_hangul(c) else c for c in text)
            if semantic != text:
                node.text = semantic
                changed = True
    return etree.tostring(root) if changed else data

def _iter_docx_blocks(element) -> Iterable[Any]:
    """展开内容控件，表格仍作为整体处理，避免重复遍历单元格。"""
    for child in element:
        if child.tag in {_qn("w:p"), _qn("w:tbl"), _qn("w:altChunk")}:
            yield child
        elif child.tag in {_qn("w:sdt"), _qn("w:sdtContent"), _qn("w:customXml")}:
            yield from _iter_docx_blocks(child)

def _extract_docx_text_items(path: Path, *, word_semantics: bool = False) -> list[TextItem]:
    items: list[TextItem] = []
    with ZipFile(path) as zf:
        def read_xml(name):
            data = zf.read(name)
            return _docx_word_semantic_xml(data) if word_semantics else data

        names = set(zf.namelist())
        if "word/document.xml" not in names:
            raise ValueError("DOCX 结构异常，缺少 word/document.xml")

        document_root = etree.fromstring(read_xml("word/document.xml"))
        body = document_root.find(_qn("w:body"))
        if body is not None:
            for child in _iter_docx_blocks(body):
                if child.tag == _qn("w:p"):
                    _append_docx_paragraph_items(items, child, "body", "正文")
                elif child.tag == _qn("w:tbl"):
                    _append_docx_table_items(items, child)
                elif child.tag == _qn("w:altChunk"):
                    text = _extract_docx_alt_chunk(zf, child.get(_qn("r:id"), ""))
                    if text.strip():
                        items.append(TextItem("alt_chunk", "嵌入内容", text, paragraph_count=_count_text_paragraphs(text), line_count=_count_text_lines(text)))

        for xml_name in sorted(name for name in names if name.startswith("word/header") and name.endswith(".xml")):
            text = _extract_xml_text(read_xml(xml_name))
            if text.strip():
                items.append(
                    TextItem(
                        "header",
                        "页眉",
                        text,
                        is_extra=True,
                        paragraph_count=_count_text_paragraphs(text),
                        line_count=_count_text_lines(text),
                    )
                )

        for xml_name in sorted(name for name in names if name.startswith("word/footer") and name.endswith(".xml")):
            text = _extract_xml_text(read_xml(xml_name))
            if text.strip():
                items.append(
                    TextItem(
                        "footer",
                        "页脚",
                        text,
                        is_extra=True,
                        paragraph_count=_count_text_paragraphs(text),
                        line_count=_count_text_lines(text),
                    )
                )

        for xml_name, source_type, label in (
            ("word/footnotes.xml", "footnote", "脚注"),
            ("word/endnotes.xml", "endnote", "尾注"),
            ("word/comments.xml", "comment", "批注"),
        ):
            if xml_name in names:
                for text in _extract_note_like_texts(read_xml(xml_name), source_type):
                    items.append(
                        TextItem(
                            source_type,
                            label,
                            text,
                            is_extra=source_type not in {"footnote", "endnote"},
                            paragraph_count=_count_text_paragraphs(text),
                            line_count=_count_text_lines(text),
                        )
                    )

        for xml_name in sorted(name for name in names if name.startswith("word/charts/") and name.endswith(".xml")):
            chart_text = "\n".join(_extract_chart_texts(read_xml(xml_name)))
            if chart_text.strip():
                items.append(
                    TextItem(
                        "chart",
                        "图表",
                        chart_text,
                        is_extra=True,
                        paragraph_count=_count_text_paragraphs(chart_text),
                        line_count=_count_text_lines(chart_text),
                    )
                )

    return items

def _extract_docx_alt_chunk(archive: ZipFile, relation_id: str) -> str:
    """读取 Word 延迟导入的 HTML/MHTML/文本，不访问外部链接。"""
    import posixpath
    from urllib.parse import unquote
    from bs4 import BeautifulSoup
    from email import message_from_bytes

    relations = etree.fromstring(archive.read("word/_rels/document.xml.rels"))
    relation = next((n for n in relations if n.get("Id") == relation_id), None)
    if relation is None or relation.get("TargetMode") == "External":
        raise ValueError("嵌入内容关系缺失或为外部链接，需人工复核")
    target = unquote(relation.get("Target", ""))
    name = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "word/" + target)
    data = archive.read(name)
    suffix = Path(name).suffix.lower()
    charset = None
    if suffix in {".mht", ".mhtml"}:
        message = message_from_bytes(data)
        parts = [p for p in message.walk() if p.get_content_type() in {"text/html", "text/plain"}]
        part = next((p for p in parts if p.get_content_type() == "text/html"), parts[0] if parts else None)
        if part is None:
            return ""
        data = part.get_payload(decode=True) or b""
        charset = part.get_content_charset()
        suffix = ".html" if part.get_content_type() == "text/html" else ".txt"
    if suffix == ".txt":
        return data.decode(charset or "utf-8-sig", errors="replace")
    if suffix not in {".html", ".htm", ".xhtml"}:
        raise ValueError(f"暂不支持的嵌入内容类型 {suffix}，需人工复核")
    soup = BeautifulSoup(data, "html.parser", from_encoding=charset)
    for tag in soup.find_all(["script", "style", "head"]):
        tag.decompose()
    for tag in soup.find_all(style=True):
        if not tag.attrs:
            continue
        style = tag.get("style", "").replace(" ", "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            tag.decompose()
    for tag in soup.find_all("br"):
        tag.replace_with("\n")
    for tag in soup.find_all(["p", "div", "tr", "li", "h1", "h2", "h3"]):
        tag.append("\n")
    for tag in soup.find_all(["td", "th"]):
        tag.append("\t")
    return soup.get_text().strip()

def _append_docx_paragraph_items(items: list[TextItem], paragraph, source_type: str, label: str) -> None:
    normal_text = _extract_text_from_element(paragraph, skip_textboxes=True)
    if normal_text.strip():
        items.append(
            TextItem(
                source_type,
                label,
                normal_text,
                is_extra=False,
                paragraph_count=1,
                line_count=_count_text_lines(normal_text),
            )
        )
    for textbox_text in _extract_textbox_texts(paragraph):
        if textbox_text.strip():
            items.append(
                TextItem(
                    "textbox",
                    "正文文本框",
                    textbox_text,
                    is_extra=False,
                    paragraph_count=_count_text_paragraphs(textbox_text),
                    line_count=_count_text_lines(textbox_text),
                )
            )

def _append_docx_table_items(items: list[TextItem], table) -> None:
    for row in table.findall("w:tr", NS):
        row_texts: list[str] = []
        textbox_texts: list[str] = []
        for cell in row.findall("w:tc", NS):
            text = _extract_text_from_element(cell, skip_textboxes=True)
            if text.strip():
                row_texts.append(text)
            textbox_texts.extend(_extract_textbox_texts(cell))
        if row_texts:
            row_text = "\t".join(row_texts)
            items.append(
                TextItem(
                    "table",
                    "正文表格",
                    row_text,
                    is_extra=False,
                    paragraph_count=len(row_texts),
                    line_count=max(1, len(row_texts)),
                )
            )
        for textbox_text in textbox_texts:
            if textbox_text.strip():
                items.append(
                    TextItem(
                        "textbox",
                        "正文文本框",
                        textbox_text,
                        is_extra=False,
                        paragraph_count=_count_text_paragraphs(textbox_text),
                        line_count=_count_text_lines(textbox_text),
                    )
                )

def _extract_xml_text(xml_bytes: bytes) -> str:
    root = etree.fromstring(xml_bytes)
    return _extract_text_from_element(root, skip_textboxes=False)

def _extract_note_like_texts(xml_bytes: bytes, source_type: str) -> list[str]:
    root = etree.fromstring(xml_bytes)
    if source_type == "footnote":
        item_tag = _qn("w:footnote")
    elif source_type == "endnote":
        item_tag = _qn("w:endnote")
    else:
        item_tag = _qn("w:comment")

    texts: list[str] = []
    for elem in root.iter(item_tag):
        note_type = elem.get(_qn("w:type"), "")
        if source_type in {"footnote", "endnote"} and note_type in {
            "separator",
            "continuationSeparator",
            "continuationNotice",
        }:
            continue
        text = _extract_text_from_element(elem, skip_textboxes=False)
        if text.strip():
            texts.append(text)
    return texts

def _extract_text_from_element(element, *, skip_textboxes: bool) -> str:
    deleted_tag = _qn("w:del")
    moved_from_tag = _qn("w:moveFrom")
    instr_tag = _qn("w:instrText")
    text_tag = _qn("w:t")
    textbox_tags = {_qn("wps:txbx"), _qn("w:txbxContent"), _qn("v:textbox")}
    parts: list[str] = []
    fields: list[dict[str, Any]] = []

    def walk(node, *, deleted: bool = False, hidden: bool = False) -> None:
        if node.tag == _qn("mc:AlternateContent"):
            preferred_branch = _select_preferred_alternate_content_branch(node)
            if preferred_branch is not None:
                walk(preferred_branch, deleted=deleted, hidden=hidden)
            return
        if skip_textboxes and node.tag in textbox_tags:
            return

        next_deleted = deleted or node.tag in {deleted_tag, moved_from_tag}
        next_hidden = hidden or _is_hidden_word_run(node)
        if next_deleted or next_hidden:
            return
        if node.tag == _qn("w:fldChar"):
            kind = node.get(_qn("w:fldCharType"))
            if kind == "begin":
                fields.append({"code": "", "result": False})
            elif kind == "separate" and fields:
                fields[-1]["result"] = True
            elif kind == "end" and fields:
                field = fields.pop()
                # MACROBUTTON 的显示文字位于域指令中，没有普通域结果。
                if not field["result"]:
                    match = re.match(r"\s*MACROBUTTON\s+\S+\s+(.*)", field["code"], re.IGNORECASE | re.DOTALL)
                    if match:
                        parts.append(match[1])
            return
        if node.tag == instr_tag:
            if fields:
                fields[-1]["code"] += node.text or ""
            return
        if node.tag in {_qn("w:tab"), _qn("w:br"), _qn("w:cr")}:
            parts.append("\t" if node.tag == _qn("w:tab") else "\n")
            return
        if node.tag == text_tag:
            if node.text:
                parts.append(node.text)
            return
        for child in node:
            walk(child, deleted=next_deleted, hidden=next_hidden)
        if node.tag == _qn("w:p"):
            parts.append("\n")

    walk(element)
    return "".join(parts).rstrip("\n")

def _iter_textbox_elements(element) -> Iterable[Any]:
    canonical_tag = _qn("w:txbxContent")
    wrapper_tags = {_qn("wps:txbx"), _qn("v:textbox")}

    def walk(node) -> Iterable[Any]:
        if node.tag == _qn("mc:AlternateContent"):
            preferred_branch = _select_preferred_alternate_content_branch(node)
            if preferred_branch is not None:
                yield from walk(preferred_branch)
            return
        if node.tag == canonical_tag:
            yield node
            return
        if node.tag in wrapper_tags:
            canonical_descendants = list(node.iter(canonical_tag))
            if canonical_descendants:
                for descendant in canonical_descendants:
                    yield descendant
            else:
                yield node
            return
        for child in node:
            yield from walk(child)

    yield from walk(element)

def _extract_textbox_texts(element) -> list[str]:
    texts: list[str] = []
    for textbox in _iter_textbox_elements(element):
        text = _extract_text_from_element(textbox, skip_textboxes=False)
        if text.strip():
            texts.append(text)
    return texts

def _select_preferred_alternate_content_branch(element):
    for child in element:
        if child.tag == _qn("mc:Choice"):
            return child
    for child in element:
        if child.tag == _qn("mc:Fallback"):
            return child
    return None

def _is_hidden_word_run(element) -> bool:
    if element.tag != _qn("w:r"):
        return False
    run_properties = element.find("w:rPr", NS)
    if run_properties is None:
        return False
    for property_name in ("w:vanish", "w:webHidden"):
        hidden_property = run_properties.find(property_name, NS)
        if hidden_property is None:
            continue
        value = str(hidden_property.get(_qn("w:val"), "")).strip().lower()
        if value not in {"0", "false", "off"}:
            return True
    return False

def _extract_chart_texts(xml_bytes: bytes) -> list[str]:
    root = etree.fromstring(xml_bytes)
    seen: set[str] = set()
    texts: list[str] = []

    def add(value: Optional[str]) -> None:
        text = (value or "").strip()
        if text and text not in seen:
            seen.add(text)
            texts.append(text)

    for node in root.iter(_qn("a:t")):
        add(node.text)
    for node in root.iter(_qn("c:v")):
        value = (node.text or "").strip()
        if not value:
            continue
        try:
            float(value)
            continue
        except ValueError:
            add(value)
    return texts

def _read_ooxml_app_properties(path: Path) -> dict[str, str]:
    try:
        with ZipFile(path) as zf:
            if "docProps/app.xml" not in zf.namelist():
                return {}
            root = etree.fromstring(zf.read("docProps/app.xml"))
    except Exception:
        return {}
    props: dict[str, str] = {}
    for child in root:
        tag = etree.QName(child).localname
        props[tag] = (child.text or "").strip()
    return props

def _read_word_native_line_count(path: Path) -> int:
    """在 Windows 单文件任务中调用 Word 重新分页，获得接近界面“行数”的统计值。"""
    if os.name != "nt":
        return 0

    word = None
    document = None
    initialized = False
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        initialized = True
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(
            FileName=str(path.resolve(strict=True)),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            Revert=False,
            Visible=False,
            OpenAndRepair=False,
            NoEncodingDialog=True,
        )
        document.Repaginate()
        return _to_positive_int(document.ComputeStatistics(1))
    except Exception:
        return 0
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        if initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

def _count_ooxml_image_references(path: Path, prefixes: tuple[str, ...]) -> int:
    count = 0
    try:
        with ZipFile(path) as zf:
            for name in zf.namelist():
                if not name.endswith(".xml") or "/_rels/" in name:
                    continue
                if prefixes and not any(name.startswith(prefix) for prefix in prefixes):
                    continue
                try:
                    root = etree.fromstring(zf.read(name))
                except Exception:
                    continue
                for node in root.iter():
                    local_name = etree.QName(node).localname
                    if local_name in {"blip", "imagedata"}:
                        count += 1
    except Exception:
        return 0
    return count

def _count_text_lines(text: str) -> int:
    return sum(1 for line in re.split(r"\r\n|\r|\n", text or "") if line.strip())

def _count_text_paragraphs(text: str) -> int:
    content = (text or "").strip()
    if not content:
        return 0
    blocks = [block for block in re.split(r"(?:\r?\n\s*){2,}", content) if block.strip()]
    return len(blocks) if blocks else _count_text_lines(content)

def _to_positive_int(value: Any) -> int:
    try:
        number = int(str(value or "").strip())
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0
