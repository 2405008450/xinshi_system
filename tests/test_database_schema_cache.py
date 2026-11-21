from sqlalchemy import create_engine, event, inspect, text

from database_schema_cache import install_schema_introspection_cache


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_engine():
    engine = create_engine('sqlite://')
    calls = []
    for name in ('has_table', 'get_columns'):
        original = getattr(engine.dialect, name)

        def counted(*args, _name=name, _original=original, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)

        setattr(engine.dialect, name, counted)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)'))
    return engine, calls


def probe(engine, table='sample'):
    with engine.connect() as connection:
        inspector = inspect(connection)
        return inspector.has_table(table), [c['name'] for c in inspector.get_columns(table)] if inspector.has_table(table) else []


def test_existing_table_probe_is_cached_between_inspectors():
    engine, calls = make_engine()
    install_schema_introspection_cache(engine, tables_ttl=600, columns_ttl=120, clock=Clock())
    first = probe(engine)
    second = probe(engine)
    assert first == second == (True, ['id', 'name'])
    assert calls.count('has_table') == 1 and calls.count('get_columns') == 1


def test_missing_table_is_never_cached_and_becomes_visible_after_migration():
    engine, calls = make_engine()
    install_schema_introspection_cache(engine, tables_ttl=600, columns_ttl=120, clock=Clock())
    assert probe(engine, 'later') == (False, [])
    assert probe(engine, 'later') == (False, [])
    assert calls.count('has_table') == 4  # probe 每次探测两遍，缺表结果都不得被缓存
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE later (id INTEGER)'))
    assert probe(engine, 'later') == (True, ['id'])


def test_entries_expire_and_ddl_in_process_clears_cache():
    engine, calls = make_engine()
    clock = Clock()
    install_schema_introspection_cache(engine, tables_ttl=600, columns_ttl=120, clock=clock)
    probe(engine)
    clock.now += 121
    probe(engine)
    assert calls.count('get_columns') == 2 and calls.count('has_table') == 1
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE sample ADD COLUMN extra TEXT'))
    assert probe(engine) == (True, ['id', 'name', 'extra'])


def test_returned_columns_are_copies_and_zero_ttl_disables_cache():
    engine, calls = make_engine()
    install_schema_introspection_cache(engine, tables_ttl=600, columns_ttl=120, clock=Clock())
    with engine.connect() as connection:
        first = inspect(connection).get_columns('sample')
        first[0]['name'] = 'mutated'
    assert probe(engine)[1] == ['id', 'name']
    disabled, disabled_calls = make_engine()
    assert install_schema_introspection_cache(disabled, tables_ttl=0) is None
    probe(disabled); probe(disabled)
    assert disabled_calls.count('has_table') >= 2
