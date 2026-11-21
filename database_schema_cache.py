"""进程内缓存只读的结构探测（has_table / get_columns），减少每个请求里的公网往返。

业务代码大量使用 ``inspect(db.connection()).has_table(...)`` 判断迁移是否已就绪，Inspector 每次都是新实例，
同一请求乃至同一页面会重复发出数十条 pg_catalog 查询。后端经公网访问云端数据库时每条约 16ms，
这些探测在局域网版本里占了每个请求的相当比例。

缓存规则：
- 只缓存“表存在”的结果：运行中的业务表不会被删除；“表不存在”不缓存，迁移完成后立即可见。
- 列定义缓存时间较短，进程内执行 CREATE/DROP/ALTER 时立即清空，外部迁移最多延迟一个 TTL。
- ``DB_SCHEMA_CACHE_TTL_SECONDS=0`` 可完全关闭，回到逐次探测。
"""
import os
import threading
import time

from sqlalchemy import event

_DDL_PREFIXES = ('CREATE', 'DROP', 'ALTER', 'TRUNCATE', 'COMMENT', 'RENAME')


def _ttl(name, default):
    try:
        return max(0.0, float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return float(default)


def install_schema_introspection_cache(engine, *, tables_ttl=None, columns_ttl=None, clock=time.monotonic):
    tables_ttl = _ttl('DB_SCHEMA_CACHE_TTL_SECONDS', 600) if tables_ttl is None else tables_ttl
    columns_ttl = min(tables_ttl, _ttl('DB_SCHEMA_COLUMNS_CACHE_TTL_SECONDS', 120)) if columns_ttl is None else columns_ttl
    dialect = engine.dialect
    if not tables_ttl or getattr(dialect, '_xinshi_schema_cache', None) is not None:
        return getattr(dialect, '_xinshi_schema_cache', None)

    lock = threading.Lock()
    tables, columns = {}, {}
    original_has_table, original_get_columns = dialect.has_table, dialect.get_columns

    def clear():
        with lock:
            tables.clear(); columns.clear()

    def has_table(connection, table_name, schema=None, **kw):
        key = (table_name, schema)
        with lock:
            expires = tables.get(key)
        if expires is not None and expires > clock():
            return True
        result = original_has_table(connection, table_name, schema, **kw)
        if result:
            with lock:
                tables[key] = clock() + tables_ttl
        return result

    def get_columns(connection, table_name, schema=None, **kw):
        key = (table_name, schema, tuple(sorted((k, repr(v)) for k, v in kw.items() if k != 'info_cache')))
        with lock:
            hit = columns.get(key)
        if hit is not None and hit[0] > clock():
            return [dict(column) for column in hit[1]]
        result = original_get_columns(connection, table_name, schema, **kw)
        with lock:
            columns[key] = (clock() + columns_ttl, [dict(column) for column in result])
        return result

    dialect.has_table, dialect.get_columns = has_table, get_columns

    @event.listens_for(engine, 'after_cursor_execute')
    def invalidate_after_ddl(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip()[:8].upper().startswith(_DDL_PREFIXES):
            clear()

    dialect._xinshi_schema_cache = clear
    return clear
