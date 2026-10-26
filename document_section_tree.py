"""知识栏目统一支持三级，校验排序、父链和循环引用。"""
def section_depth(section_id, by_id):
    seen = set()
    depth = 0
    while section_id is not None:
        if section_id in seen:
            raise ValueError('栏目不能循环嵌套')
        seen.add(section_id)
        row = by_id.get(section_id)
        if row is None:
            raise ValueError('父级栏目不存在')
        depth += 1
        section_id = row.parent_id
    return depth


def validate_section_depths(by_id):
    for section_id in by_id:
        if section_depth(section_id, by_id) > 3:
            raise ValueError('最多支持三级栏目')


def ordered_sections(children):
    result = []
    def visit(parent_id):
        for row in children[parent_id]:
            result.append(row)
            visit(row.id)
    visit(None)
    return result


def section_breadcrumb(row, by_id):
    path = []
    while row is not None:
        path.append(row.title)
        row = by_id.get(row.parent_id)
    return ' / '.join(reversed(path))
