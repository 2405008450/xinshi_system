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
    no_orders = SubClient(id=uuid4(), parent_client_id=first.id, sub_client_code='A-42-2',
                          client_name='Unused Office', client_short_name='Unused')
    other_child = SubClient(id=uuid4(), parent_client_id=other.id, sub_client_code='B-12-1',
                            client_name='Other Office', client_short_name='Other')
    db.add_all([child, no_orders, other_child])
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
    expanded = dict(**filters, client=first.id, presence='all')
    matching = customer_projects(db, **expanded, project_keyword='legacy OFFICE', sub_client_id=child.id,
                                 skip=0, limit=1)
    assert matching['total'] == 1
    assert matching['items'][0]['project_name'] == 'legacy parent'
    assert [option['id'] for option in matching['sub_clients']] == [child.id, no_orders.id]
    assert customer_projects(db, **expanded, sub_client_id=no_orders.id, skip=0, limit=10)['total'] == 0
    assert customer_projects(db, **expanded, sub_client_id=other_child.id, skip=0, limit=10)['total'] == 0
    assert customer_projects(db, **expanded, project_keyword='legacy %', skip=0, limit=10)['total'] == 0
    ordered = customer_projects(db, **expanded, sort_by='project_name', sort_direction='asc', skip=1, limit=1)
    assert ordered['total'] == 3
    assert ordered['items'][0]['project_name'] == 'legacy parent'
    by_child = customer_projects(db, **expanded, sort_by='sub_client', sort_direction='desc', skip=2, limit=1)
    assert by_child['items'][0]['sub_client_id'] is None
    without_client = customer_projects(db, **filters, client=first.id, presence='without', skip=0, limit=10)
    assert [row['project_name'] for row in without_client['items']] == ['march']
    unlinked = customer_projects(db, months=filters['months'], keyword='', client='unlinked',
                                 presence='all', skip=0, limit=10)
    assert [row['project_name'] for row in unlinked['items']] == ['unlinked']
    assert customer_groups(db, months=filters['months'], keyword='', skip=1, limit=1)['total'] == 3

    linked_groups = customer_groups(db, months=filters['months'], keyword='', presence='with', skip=0, limit=1)
    assert linked_groups['total'] == 1
    assert linked_groups['items'][0]['client_id'] == first.id
    assert linked_groups['items'][0]['order_count'] == linked_groups['items'][0]['with_sub_client'] == 2
    assert linked_groups['items'][0]['without_sub_client'] == 0
    assert customer_groups(db, **filters, presence='with', skip=1, limit=1) == {'items': [], 'total': 1}

    unlinked_groups = customer_groups(db, **filters, presence='without', skip=0, limit=1)
    assert unlinked_groups['total'] == 1
    assert unlinked_groups['items'][0]['order_count'] == unlinked_groups['items'][0]['without_sub_client'] == 1
    assert unlinked_groups['items'][0]['with_sub_client'] == 0


def test_month_selection_deduplicates_and_rejects_invalid_month():
    assert month_bounds('2026-12,2026-12') == [(datetime(2026, 12, 1), datetime(2027, 1, 1))]
    with pytest.raises(ValueError, match='YYYY-MM'):
        month_bounds('2026-13')
