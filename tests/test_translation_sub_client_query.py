from datetime import datetime
from uuid import uuid4

import pytest

from models import Client, SubClient, TranslationProject
from tests.test_chat_participant_access import environment
from tests.test_translation_direction_children import case
from translation_sub_client_query import customer_groups, customer_projects, month_bounds


def test_monthly_customer_groups_and_project_filters(case):
    db, user, _ = case
    first = Client(id=uuid4(), client_code='A-42', client_short_name='Alpha', client_name='Alpha Company')
    other = Client(id=uuid4(), client_code='B-12', client_short_name='Other', client_name='Other Company')
    db.add_all([first, other])
    db.flush()
    child = SubClient(id=uuid4(), parent_client_id=first.id, sub_client_code='A-42-1',
                      client_name='Subsidiary Office', client_short_name='Subsidiary')
    db.add(child)
    db.flush()
    records = [
        ('january', first.id, child.id, datetime(2026, 1, 31, 23, 59, 59, 999999), datetime(2025, 12, 10)),
        ('february', first.id, None, datetime(2026, 2, 1), datetime(2026, 1, 1)),
        ('march', first.id, None, None, datetime(2026, 3, 1)),
        ('legacy parent', None, child.id, datetime(2026, 3, 2), None),
        ('unlinked', None, None, datetime(2026, 3, 3), None),
        ('other', other.id, None, datetime(2026, 3, 4), None),
    ]
    for index, (name, client_id, sub_client_id, reception, created) in enumerate(records, 1):
        db.add(TranslationProject(id=uuid4(), order_no=f'TP-260301-{index:03d}', project_name=name,
                                  client_id=client_id, sub_client_id=sub_client_id, customer_reception_time=reception,
                                  created_at=created, created_by=user.id))
    db.commit()

    filters = {'months': '2026-03,2026-01', 'keyword': 'a-42 ALPHA'}
    groups = customer_groups(db, **filters, skip=0, limit=1)
    assert groups['total'] == 1
    assert groups['items'][0] == {
        'client_id': first.id, 'client_name': 'Alpha Company', 'client_short_name': 'Alpha', 'client_code': 'A-42',
        'order_count': 3, 'with_sub_client': 2, 'without_sub_client': 1,
    }
    with_client = customer_projects(db, **filters, client=first.id, presence='with', skip=1, limit=1)
    assert with_client['total'] == 2
    assert with_client['items'][0]['project_name'] == 'january'
    assert with_client['items'][0]['sub_client_short_name'] == 'Subsidiary'
    assert with_client['items'][0]['received_at'] == '2026-01-31T23:59:59.999999+08:00'
    without_client = customer_projects(db, **filters, client=first.id, presence='without', skip=0, limit=10)
    assert [row['project_name'] for row in without_client['items']] == ['march']
    unlinked = customer_projects(db, months=filters['months'], keyword='', client='unlinked',
                                 presence='all', skip=0, limit=10)
    assert [row['project_name'] for row in unlinked['items']] == ['unlinked']
    assert customer_groups(db, months=filters['months'], keyword='', skip=1, limit=1)['total'] == 3


def test_month_selection_deduplicates_and_rejects_invalid_month():
    assert month_bounds('2026-12,2026-12') == [(datetime(2026, 12, 1), datetime(2027, 1, 1))]
    with pytest.raises(ValueError, match='YYYY-MM'):
        month_bounds('2026-13')
