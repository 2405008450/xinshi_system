"""性能回归验证查询次数及业务口径；只使用隔离数据库。"""
from uuid import uuid4
from types import SimpleNamespace

from sqlalchemy import event

from test_chat_participant_access import environment
from test_talent_duplicate_review import db as review_db, person


def test_scoped_contact_evidence_matches_full_pool_with_archived_sources(review_db):
    from resource_models import ResourcePerson
    from talent_duplicate_service import contact_usage_index, pair_evidence
    db = review_db
    left = person(db, name='范围甲', primary_phone='+86 138-0013-8000', wechat='shared_%_account')
    right = person(db, name='范围乙', primary_phone='8613800138000', wechat='shared_%_account')
    source = person(db, name='归档来源', primary_email='SOURCE@example.com', archived_into_id=left.id)
    external = person(db, name='组外共享', secondary_phone='86 (138) 0013 8000', wechat='shared_%_account')
    db.execute(ResourcePerson.__table__.insert(), [dict(id=uuid4(), full_name=f'无关人员{i}',
               resource_code=f'PERF{i}', status='standby') for i in range(30)])
    db.commit()
    baseline = contact_usage_index(db)
    row_counts = []
    def recorded(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith('SELECT resource_person.id') and 'resource_person.primary_phone' in statement:
            row_counts.append(cursor.rowcount)
    event.listen(db.get_bind(), 'after_cursor_execute', recorded)
    try:
        scoped = contact_usage_index(db, person_ids=[left.id, right.id])
    finally:
        event.remove(db.get_bind(), 'after_cursor_execute', recorded)
    assert pair_evidence(left, right, scoped) == pair_evidence(left, right, baseline)
    assert scoped.by_person[str(left.id)] == baseline.by_person[str(left.id)]
    assert sum(row_counts) == 4  # 本组、归档来源、组外共享者；不传回无关人员。
    assert len(scoped[('phone', '8613800138000')]) == 3


def test_scoped_non_ascii_phone_keeps_exact_fallback(review_db):
    from talent_duplicate_service import contact_usage_index, pair_evidence
    db = review_db
    left = person(db, name='数字甲', primary_phone='１３８００１３８０００')
    right = person(db, name='数字乙', primary_phone='１３８００１３８０００')
    person(db, name='数字丙', primary_phone='１３８００１３８０００')
    assert pair_evidence(left, right, contact_usage_index(db, person_ids=[left.id, right.id])) == pair_evidence(left, right, contact_usage_index(db))


def test_overview_reads_do_not_write_or_lock_when_already_synced(review_db):
    from interpretation_models import InterpretationLanguage
    from resource_models import ResourceLanguageSkill
    from talent_overview_models import TalentOverviewSnapshot
    from talent_overview_service import load_talent_overview_data
    from talent_pool_statistics import get_synced_talent_overview
    db = review_db
    db.add(TalentOverviewSnapshot(id=1, payload=load_talent_overview_data(), revision=1))
    owner = person(db, name='新增语种人才')
    language = InterpretationLanguage(id=uuid4(), label='性能验证新增语种')
    db.add(language)
    db.add(ResourceLanguageSkill(id=uuid4(), person_id=owner.id, language_id=language.id, role='native', priority=0, sort_order=0))
    db.commit()
    first = get_synced_talent_overview(db)
    assert any(row['language'] == language.label for row in first['rows'])
    assert db.get(InterpretationLanguage, language.id).talent_overview_key
    queries = []
    def recorded(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement.upper())
    event.listen(db.get_bind(), 'after_cursor_execute', recorded)
    try:
        second = get_synced_talent_overview(db)
        assert second == first
        assert not any('FOR UPDATE' in sql or sql.startswith(('INSERT', 'UPDATE', 'DELETE')) for sql in queries)
    finally:
        event.remove(db.get_bind(), 'after_cursor_execute', recorded)


def test_batched_project_families_do_not_grow_queries_per_row(environment, monkeypatch):
    from resource_models import ResourcePerson
    from resource_service import get_talent_project_histories
    db, _ = environment
    # 配对工作台使用 PostgreSQL JSON 函数；本例只统计归档关系的批量查询。
    monkeypatch.setattr('annotation_paired_service.talent_participations', lambda *args: [])
    rows = [ResourcePerson(id=uuid4(), full_name=f'性能人才{i}', status='standby') for i in range(20)]
    db.add_all(rows)
    db.commit()
    queries = []
    def recorded(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)
    event.listen(db.get_bind(), 'after_cursor_execute', recorded)
    try:
        get_talent_project_histories(db, [rows[0].id])
        single = len(queries)
        queries.clear()
        result = get_talent_project_histories(db, [row.id for row in rows])
        multiple = len(queries)
    finally:
        event.remove(db.get_bind(), 'after_cursor_execute', recorded)
    assert set(result) == {row.id for row in rows}
    assert all(not events for events in result.values())
    assert multiple <= single  # 结构检查只在首次调用发生。


def test_database_language_aggregation_matches_reference_and_excludes_archives(environment):
    from resource_models import ResourceLanguageSkill, ResourcePerson
    from talent_pool_statistics import aggregate_language_people, summarize_language_people
    db, _ = environment
    identifiers = [uuid4() for _ in range(4)]
    languages = [SimpleNamespace(id=identifier, label=label, talent_overview_key=key, aliases=[],
                   code=None, name_zh=None, name_en=None, short_name_zh=None, short_name_en=None)
                 for identifier, label, key in zip(identifiers, ['英语', '英语别名', '闽南语', '未映射'], ['en', 'en', 'min', None])]
    rows = [ResourcePerson(id=uuid4(), full_name=f'统计人才{i}', status='standby') for i in range(4)]
    rows[3].archived_into_id = rows[0].id
    db.add_all(rows)
    skills = [(rows[0].id, identifiers[0], 'native'), (rows[0].id, identifiers[1], 'foreign'),
              (rows[0].id, identifiers[2], 'native'), (rows[1].id, identifiers[0], 'foreign'),
              (rows[2].id, identifiers[3], 'native'), (rows[2].id, identifiers[3], 'foreign'),
              (rows[3].id, identifiers[2], 'foreign')]
    db.add_all([ResourceLanguageSkill(id=uuid4(), person_id=p, language_id=l, role=r, priority=0, sort_order=0)
                for p, l, r in skills])
    db.commit()
    data = {'rows': [{'overview_key': key, 'language': label} for key, label in
                    [('en', '英语'), ('native', '英语（母语者）'), ('min', '闽南语'), ('empty', '未登记行')]]}
    expected = summarize_language_people(data, languages, skills[:-1], 3)
    actual = aggregate_language_people(db, data, languages)
    assert actual == expected


def test_unreviewed_duplicate_names_do_not_load_full_groups(environment, monkeypatch):
    import talent_duplicate_service as service
    from resource_models import ResourcePerson
    db, _ = environment
    row = ResourcePerson(id=uuid4(), full_name='同名测试', name_duplicate=True, status='standby')
    db.add(row)
    db.commit()
    row.__dict__['name_review_state'] = 'different'
    def unexpected(*args, **kwargs):
        raise AssertionError('无人工核重结论时不应加载整组档案或全库联系方式')
    monkeypatch.setattr('resource_service._person_options', unexpected)
    monkeypatch.setattr(service, 'contact_usage_index', unexpected)
    service.annotate_review_states(db, [row])
    assert row.name_review_state == 'pending'


def test_auxiliary_batch_is_constant_and_does_not_survive_scope(environment):
    from talent_duplicate_profiles import batch_auxiliary_rows, auxiliary_rows
    from resource_models import ResourcePerson
    from talent_resume_profile import TalentResumeProfile
    from business_time import business_now
    db, _ = environment
    rows = [ResourcePerson(id=uuid4(), full_name=f'批量资料{i}', status='standby') for i in range(10)]
    db.add_all(rows)
    db.add(TalentResumeProfile(person_id=rows[0].id, revision=1, data={'self_assessment': '旧值'}, updated_at=business_now()))
    db.commit()
    queries = []
    def recorded(*args):
        queries.append(args[2])
    event.listen(db.get_bind(), 'after_cursor_execute', recorded)
    try:
        with batch_auxiliary_rows(db, rows):
            for row in rows:
                auxiliary_rows(row)
                auxiliary_rows(row)
        assert len(queries) == 2
        assert 'talent_review_auxiliary_batch' not in db.info
        db.get(TalentResumeProfile, rows[0].id).data = {'self_assessment': '新值'}
        db.flush()
        assert auxiliary_rows(rows[0])['resume_profile'].data['self_assessment'] == '新值'
    finally:
        event.remove(db.get_bind(), 'after_cursor_execute', recorded)
