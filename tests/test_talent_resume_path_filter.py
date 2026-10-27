"""路径是否登记的筛选只检查字段内容，不访问 UNC 或业务数据库。"""
import json
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import Session
from fastapi import HTTPException


def test_path_presence_filter_uses_same_query_for_list_and_count():
    import main  # 注册所有 ORM 关系，不执行启动钩子。
    from resource_models import ResourcePerson
    from resource_service import _talent_query
    from routers.talents import _field_filters
    from sqlalchemy.dialects.sqlite import dialect
    from sqlalchemy.exc import CompileError
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        # _talent_query 会选择完整人员列，隔离表只需要类型，不继承生产约束。
        columns = []
        for column in ResourcePerson.__table__.columns:
            try: kind = column.type.compile(dialect=dialect())
            except CompileError: kind = 'TEXT'
            columns.append(f'"{column.name}" {kind}' + (' PRIMARY KEY' if column.primary_key else ''))
        connection.execute(text('CREATE TABLE resource_person (' + ','.join(columns) + ')'))
        for index, path in enumerate([None, '', ' \t\r\n\u3000', r'\\server\人才\简历.pdf', ' D:/人才/简历.pdf ']):
            connection.execute(text('INSERT INTO resource_person (id, full_name, status, resume_path) VALUES (:id,:name,:status,:path)'), {'id': uuid4().hex, 'name': f'test{index}', 'status': 'available', 'path': path})
    with Session(engine) as db:
        for exists, expected in [(True, {'test3', 'test4'}), (False, {'test0', 'test1', 'test2'})]:
            filters = _field_filters(json.dumps({'resume_path_registered': {'op': 'eq', 'value': exists}}))
            query = _talent_query(db, field_filters=filters)
            # 路径条件位于统一查询，分页结果与总数使用完全相同的谓词。
            names = {row[0] for row in query.with_entities(ResourcePerson.full_name).all()}
            assert names == expected
            assert query.count() == len(expected)
        assert _talent_query(db).count() == 5
        with pytest.raises(HTTPException):
            _field_filters(json.dumps({'resume_path_registered': {'op': 'contains', 'value': 'pdf'}}))
    engine.dispose()
