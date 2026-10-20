"""全部测试使用内存 SQLite；不连接业务库。"""
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, select, or_
from search_matching import keyword_any, keyword_contains, keyword_ilike, keyword_like, keyword_or, matches_keywords, search_terms


def test_terms_and_local_matching():
    assert search_terms(' AA\tBB　AA  ') == ['aa', 'bb']
    for text in ('AABB', 'AAA BBB', 'BB--AA'):
        assert matches_keywords(text, 'AA BB')
    assert not matches_keywords('only AA', 'AA BB')
    assert matches_keywords(None, '　 ')
    assert matches_keywords('100%_x', '% _')
    assert not matches_keywords('100abc', '% _')


def test_sql_like_groups_literals_and_count_list_consistency():
    engine = create_engine('sqlite:///:memory:')
    table = Table('search_rows', MetaData(), Column('id', Integer, primary_key=True), Column('name', String), Column('note', String))
    table.create(engine)
    with engine.begin() as db:
        db.execute(table.insert(), [
            {'id': 1, 'name': 'AABB', 'note': ''}, {'id': 2, 'name': 'AAA BBB', 'note': ''},
            {'id': 3, 'name': 'AA', 'note': 'BB'}, {'id': 4, 'name': 'AA', 'note': ''},
            {'id': 5, 'name': '100%_\\path', 'note': ''}, {'id': 6, 'name': None, 'note': None},
        ])
        ids = lambda clause: list(db.execute(select(table.c.id).where(clause).order_by(table.c.id)).scalars())
        assert ids(keyword_contains(table.c.name, 'AA BB')) == [1, 2]
        predicate = keyword_or(lambda pattern: or_(keyword_ilike(table.c.name, pattern), keyword_ilike(table.c.note, pattern)), '%AA BB%')
        assert ids(predicate) == [1, 2, 3]
        assert ids(keyword_any([table.c.name, table.c.note], 'AA BB')) == [1, 2, 3]
        assert ids(keyword_ilike(table.c.name, '%100%_%')) == [5]
        assert ids(keyword_ilike(table.c.name, r'%100\%\_\\path%', escape='\\')) == [5]
        assert ids(keyword_like(table.c.name, '%aa bb%')) == [1, 2]
        assert ids(keyword_ilike(table.c.name, 'AA%')) == [1, 2, 3, 4]
        assert ids(keyword_contains(table.c.name, '  ')) == [1, 2, 3, 4, 5, 6]
    engine.dispose()
