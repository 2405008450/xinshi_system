"""子订单命名边界；不连接业务数据库。"""
import pytest

from annotation_child_copy_service import child_project_name


@pytest.mark.parametrize(('name', 'source', 'target', 'expected'), [
    ('A', '英语', None, '英语-A'),
    ('A', '中文', '英语', '中文→英语-A'),
    ('A', '英语', '中文', '英语→中文-A'),
    (' A ', ' 英语 ', '', '英语-A'),
    ('', '英语', None, None),
    (None, '英语', None, None),
    ('A', '', None, 'A'),
])
def test_child_name(name, source, target, expected):
    assert child_project_name(name, source, target) == expected


def test_child_name_length_is_validated_without_truncation():
    assert len(child_project_name('A' * 497, '英语')) == 500
    with pytest.raises(ValueError, match='500'):
        child_project_name('A' * 498, '英语')
