from types import SimpleNamespace
import os

import pytest

from talent_pool_statistics import append_pool_language_rows, summarize_language_people
from talent_overview_service import _prepare_saved_payload
from talent_overview_schemas import TalentOverviewWrite


def language(identifier, label, key=None):
    return SimpleNamespace(id=identifier, label=label, talent_overview_key=key,
                           code=None, name_zh=None, name_en=None, short_name_zh=None,
                           short_name_en=None, aliases=[])


def test_multilingual_people_deduplicate_per_overview_and_keep_snapshot_separate():
    data = {'rows': [
        {'overview_key': 'en', 'language': '英语', 'row_total': 9506},
        {'overview_key': 'native', 'language': '英语（母语者）'},
        {'overview_key': 'min', 'language': '闽南语'},
        {'overview_key': 'fr', 'language': '法语'},
    ]}
    languages = [language(1, '英语', 'en'), language(2, '英语旧名称', 'en'),
                 language(3, '闽南语', 'min'), language(4, '未映射语种')]
    skills = [(10, 1, 'native'), (10, 1, 'foreign'), (10, 2, 'foreign'),
              (10, 3, 'native'), (11, 1, 'foreign'),
              (12, 4, 'native'), (12, 4, 'foreign')]
    result = summarize_language_people(data, languages, skills, 4)
    assert {row['overview_key']: row['people_count'] for row in result['rows']} == {
        'en': 2, 'native': 1, 'min': 1, 'fr': 0,
    }
    assert result['total_people'] == 4
    assert result['with_language_people'] == 3
    assert result['without_language_people'] == 1
    assert result['unmatched'] == [{'language': '未映射语种', 'people_count': 1}]
    assert data['rows'][0]['row_total'] == 9506


def test_empty_pool_and_language_edit_recalculate_without_persisted_counts():
    data = {'rows': [{'overview_key': 'min', 'language': '闽南语'}]}
    languages = [language(1, '闽南语', 'min')]
    assert summarize_language_people(data, languages, [], 0)['rows'][0]['people_count'] == 0
    assert summarize_language_people(data, languages, [(1, 1, 'native')], 1)['rows'][0]['people_count'] == 1
    result = summarize_language_people(data, languages, [], 1)
    assert result['rows'][0]['people_count'] == 0
    assert result['without_language_people'] == 1


def test_auto_rows_are_stable_blank_and_editable_without_changing_existing_totals():
    data = {'columns': [{'key': 'sheet', 'label': '人才资料表', 'group': 'sheet', 'width': 120}],
            'rows': [{'overview_key': 'en', 'language': '英语', 'aliases': ['英文'],
                      'counts': {'sheet': 9506}}]}
    languages = [language(1, '英文'), language(2, '新增方言')]
    result, bindings = append_pool_language_rows(data, languages)
    assert len(result['rows']) == 2
    assert len(data['rows']) == 1
    assert bindings[1] == 'en'
    assert result['rows'][-1]['counts'] == {'sheet': None}
    assert result['rows'][-1]['updated_at'] is None
    assert result['grand_total'] == 9506
    again, repeated_bindings = append_pool_language_rows(result, list(reversed(languages)))
    assert again == result
    assert repeated_bindings == bindings
    rows = [dict(row) for row in result['rows']]
    rows[-1]['counts'] = {'sheet': 8}
    saved = _prepare_saved_payload(result, TalentOverviewWrite(
        expected_revision=1, columns=result['columns'], rows=rows,
    ))
    assert saved['grand_total'] == 9514
    # 总库登记减少后仍保留该行及人工维护的来源数据。
    retained, _ = append_pool_language_rows(saved, [])
    assert retained['rows'][-1]['counts'] == {'sheet': 8}


def test_auto_rows_do_not_guess_ambiguous_aliases_or_promote_placeholders():
    data = {'columns': [], 'rows': [
        {'overview_key': 'a', 'language': '语种甲'},
        {'overview_key': 'b', 'language': '语种乙'},
    ]}
    conflict = language(1, '冲突语种')
    conflict.aliases = [SimpleNamespace(alias=value, is_active=True) for value in ['语种甲', '语种乙']]
    result, bindings = append_pool_language_rows(data, [conflict, language(2, '无')])
    assert len(result['rows']) == 2
    assert bindings == {}


@pytest.mark.skipif(os.environ.get('XINSHI_POOL_DB_TEST') != '1', reason='仅在局域网显式启用事务回滚验证')
def test_database_auto_sync_is_idempotent_and_rejects_stale_edits():
    # 所有提交均限制在外层事务内，验证完成后回滚，不改动真实业务数据。
    import main  # noqa: F401
    from sqlalchemy.orm import Session
    from database import engine
    from concurrency import StaleUpdateError
    from talent_overview_models import TalentOverviewSnapshot
    from talent_overview_service import get_talent_overview, save_talent_overview
    from talent_pool_statistics import get_synced_talent_overview

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode='create_savepoint') as db:
                before = get_talent_overview(db)
                first = get_synced_talent_overview(db)
                second = get_synced_talent_overview(db)
                assert first == second
                assert first['grand_total'] == before['grand_total']
                assert first['rows'][:len(before['rows'])] == before['rows']
                for row in first['rows'][len(before['rows']):]:
                    assert all(value is None for value in row['counts'].values())
                payload = TalentOverviewWrite(expected_revision=first['revision'],
                                              columns=first['columns'], rows=first['rows'])
                # 模拟另一位用户或自动补行更新修订号后，旧草稿必须被拒绝。
                snapshot = db.get(TalentOverviewSnapshot, 1)
                snapshot.revision += 1
                db.commit()
                with pytest.raises(StaleUpdateError):
                    save_talent_overview(db, payload, None)
        finally:
            transaction.rollback()
