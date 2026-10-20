"""统一多关键词包含匹配：空白分词、词间 AND、忽略大小写，通配符按字面处理。"""
from sqlalchemy import and_, or_, true


def search_terms(value):
    """支持连续空格、全角空格、制表符；去重但不丢弃任何不同的关键词。"""
    return list(dict.fromkeys(str(value or '').lower().split()))


def matches_keywords(value, keyword):
    text = str(value or '').lower()
    return all(term in text for term in search_terms(keyword))


def escape_like(value, escape='\\'):
    return str(value).replace(escape, escape + escape).replace('%', escape + '%').replace('_', escape + '_')


def _is_contains(pattern):
    return isinstance(pattern, str) and len(pattern) >= 2 and pattern.startswith('%') and pattern.endswith('%')


def _literal_body(pattern, escape):
    body = pattern[1:-1]
    if not escape:
        return body
    result = []; index = 0
    while index < len(body):
        if body[index] == escape and index + 1 < len(body):
            index += 1
        result.append(body[index]); index += 1
    return ''.join(result)


def keyword_contains(column, keyword):
    terms = search_terms(keyword)
    return and_(*(column.ilike('%' + escape_like(term) + '%', escape='\\') for term in terms)) if terms else true()


def keyword_ilike(column, pattern, escape=None):
    # MIME 类型、前缀编号、精确别名等非包含规则沿用原语义。
    return keyword_contains(column, _literal_body(pattern, escape)) if _is_contains(pattern) else column.ilike(pattern, escape=escape)


def keyword_like(column, pattern, escape=None):
    return keyword_contains(column, _literal_body(pattern, escape)) if _is_contains(pattern) else column.like(pattern, escape=escape)


def keyword_or(builder, pattern):
    """在原 OR 查询的各字段/关联中寻找每个词，保留现有授权与范围条件。"""
    if not _is_contains(pattern):
        return builder(pattern)
    # 保留原转义形式，让原表达式中的 keyword_ilike 负责解码和字面匹配。
    words = list(dict.fromkeys(pattern[1:-1].split()))
    return and_(*(builder('%' + word + '%') for word in words)) if words else true()


def keyword_any(columns, keyword):
    terms = search_terms(keyword)
    return and_(*(or_(*(keyword_contains(column, term) for column in columns)) for term in terms)) if terms else true()
