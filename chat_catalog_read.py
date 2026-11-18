"""只在一次目录只读计算中复用结果，不跨请求保留权限或业务数据。"""
from contextlib import contextmanager
from functools import wraps


_KEY = '_chat_catalog_read_cache'


@contextmanager
def catalog_read_scope(db):
    info = getattr(db, 'info', None)
    if info is None or _KEY in info:
        yield
        return
    info[_KEY] = {}
    try:
        yield
    finally:
        info.pop(_KEY, None)


def catalog_read(function):
    @wraps(function)
    def read(db, *args, **kwargs):
        with catalog_read_scope(db):
            return function(db, *args, **kwargs)
    return read


def catalog_cached(function):
    @wraps(function)
    def cached(db, *args, **kwargs):
        cache = getattr(db, 'info', {}).get(_KEY)
        if cache is None:
            return function(db, *args, **kwargs)
        key = (function, args, tuple(sorted(kwargs.items())))
        try:
            hash(key)
        except TypeError:
            return function(db, *args, **kwargs)
        if key not in cache:
            cache[key] = function(db, *args, **kwargs)
        return cache[key]
    return cached
