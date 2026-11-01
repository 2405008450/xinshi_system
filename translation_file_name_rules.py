"""笔译各级订单：单个真实文件名、完整后缀，前后端共用格式清单。"""
import json
from pathlib import Path
import re

EXTENSION_CATEGORIES = json.loads((Path(__file__).parent / 'frontend/src/config/translationFileExtensions.json').read_text(encoding='utf-8'))
EXTENSIONS = frozenset(item for values in EXTENSION_CATEGORIES.values() for item in values)
SPLIT_ARCHIVE = re.compile(r'^(?:[rz]\d{2}|\d{3})$')
SUFFIX_TOKEN = re.compile(r'\.([a-zA-Z0-9][a-zA-Z0-9_-]{0,19})(?=$|[\s,，;；、|+&])')
MULTIPLE_MESSAGE = '一个订单号只能对应一个文件名，请将多个文件拆分为独立订单'
EXTENSION_MESSAGE = '文件名称必须保留完整扩展名（如 .docx、.pdf、.mp4、.jpg、.zip）；未知格式请先核对后缀'


def known_extension(value):
    value = value.lower()
    return value in EXTENSIONS or bool(SPLIT_ARCHIVE.fullmatch(value))


def normalize_single_file_name(value):
    name = str(value or '').lstrip('\ufeff').strip()
    if not name:
        raise ValueError('请输入项目名称（真实文件名）')
    if len(name) > 255:
        raise ValueError('项目名称不能超过255个字符')
    # 只数已知后缀形成的文件名边界；不按普通逗号或空格直接切开。
    tokens = [match for match in SUFFIX_TOKEN.finditer(name) if known_extension(match.group(1))]
    if len(tokens) > 1:
        raise ValueError(MULTIPLE_MESSAGE)
    if re.search(r'[<>:"/\\?*\x00-\x1f]', name) or name.endswith('.'):
        raise ValueError('请输入单个真实文件名，不要填写路径、引号或文件名禁用字符')
    if '.' not in name:
        raise ValueError(EXTENSION_MESSAGE)
    if not name.rpartition('.')[0].strip() or not re.search(r'[^.\s]', name.rpartition('.')[0]):
        raise ValueError('扩展名前必须有文件名称，不能只填写 .pdf 等后缀')
    if not tokens or tokens[-1].end() != len(name):
        raise ValueError(EXTENSION_MESSAGE)
    return name
