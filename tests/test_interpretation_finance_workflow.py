from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event

import interpretation_customer_finance as finance
import interpretation_service as projects
import interpretation_statements as statements
from interpretation_finance_schemas import FinanceWrite, InterpretationQuotationWrite
from interpretation_models import InterpretationLanguage, InterpretationProject
from interpretation_schemas import InterpretationProjectCreate
from models import Client
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context
from translation_revenue import other_entries, report


def test_project_form_saves_finance_and_quotation_in_one_transaction(environment, monkeypatch):
    db, (actor, *_) = environment
    monkeypatch.setattr(finance, 'user_has_permission', lambda *_: True)
    monkeypatch.setattr(projects, 'generate_interpretation_order_no', lambda _: 'IP-261101-001')
    def assign_test_ids(session, *_):
        for obj in session.new:
            if type(obj).__module__ in ('interpretation_models', 'workflow_models', 'project_audit_models') and getattr(obj, 'id', False) is None:
                obj.id = uuid4()

    event.listen(db, 'before_flush', assign_test_ids)
    client = Client(id=uuid4(), client_code='CL-ORAL', client_name='测试公司')
    first, second = [InterpretationLanguage(id=uuid4(), label=label) for label in ('中文', '英文')]
    db.add_all([client, first, second])
    db.commit()
    direction = dict(language_ids=[first.id, second.id], required_count=1)
    rate = dict(direction='中文 ↔ 英文', amount='100', unit='小时', quantity=3,
                tax_prices={'unit_price_excl_tax': '100', 'total_excl_tax': '300'})
    draft = dict(revision=0, rates=[rate], settlement={'tax_basis': 'excl_tax', 'billing_month': '2026-12'},
                 quotation_draft={'items': [{'unit': '小时', 'quantity': 3, 'unit_price': '100'}]})
    bad = InterpretationProjectCreate(client_id=client.id, project_name='口译测试', language_directions=[direction],
                                     finance_draft={**draft, 'revision': 1})
    with pytest.raises(HTTPException) as conflict:
        projects.create_interpretation_project(db, bad, actor.id)
    assert conflict.value.status_code == 409
    db.rollback()
    assert db.query(InterpretationProject).count() == 0

    valid = bad.model_copy(update={'finance_draft': bad.finance_draft.model_copy(update={'revision': 0})})
    project = projects.create_interpretation_project(db, valid, actor.id)
    current = finance.context(db, 'project', project.id)
    assert current['totals_excl_tax'] == {'CNY': '300.00'}
    assert current['quotation']['items'][0]['unit'] == '小时'
    assert finance.context(db, 'client', client.id)['payload']['rates'] == []

    finance.save(db, actor, 'project', project.id,
                 FinanceWrite(revision=1, rates=[rate], update_library=True, sync_confirmed=True, library_revision=0))
    reference = finance.context(db, 'client', client.id)['payload']['rates'][0]
    assert reference['quantity'] == '1'
    assert reference['tax_prices']['total_excl_tax'] is None
    assert finance.context(db, 'project', project.id)['quotation'] == current['quotation']
    with pytest.raises(HTTPException) as outdated:
        finance.put_quotation(project.id, InterpretationQuotationWrite(revision=1, document=current['quotation']), db, actor)
    assert outdated.value.status_code == 409
    db.rollback()

    assert not statements.build(db, project.id, '2026-11', 'project')['rows']
    statement = statements.build(db, project.id, '2026-12', 'customer')
    assert statement['rows'][0]['basis'] == '小时'
    assert statement['totals'] == {'CNY': '300.00'}
    assert statements.statements.excel_bytes(statement).startswith(b'PK')
    entries, _, _ = other_entries(db, 'interpretation', client.id, {}, date(2026, 11, 1), date(2026, 12, 1))
    assert report(entries, 'month', date(2026, 11, 1))['overall']['amount'] == '300.00'


def test_revenue_filters_four_project_types(context):
    from annotation_models import AnnotationProject, AnnotationProjectPriceItem
    from recruitment_models import RecruitmentProject
    from tests.test_customer_statements import project as translation_project
    from translation_revenue import router

    http, db, clients, _, _ = context
    http.app.include_router(router)
    client_id = clients[0].id
    translation_project(db, clients[0], fixed=True)
    oral = InterpretationProject(id=uuid4(), order_no='IP-261101-001', client_id=client_id)
    annotation = AnnotationProject(id=uuid4(), order_no='AP-261101-001', client_id=client_id)
    annotation.price_items = [AnnotationProjectPriceItem(id=uuid4(), amount=5, currency='CNY',
                                                         tax_prices={'total_excl_tax': 70})]
    recruitment = RecruitmentProject(id=uuid4(), order_no='HP-261101-001', client_id=client_id,
                                     service_fee_amount=80, service_fee_currency='CNY')
    db.add_all([oral, annotation, recruitment])
    db.flush()
    db.add(finance.InterpretationCustomerFinance(project_id=oral.id, revision=1,
                                                payload={'adjusted_totals': [{'currency': 'CNY', 'amount': '90'}]}))
    db.commit()
    for module, amount in [('translation', '500.00'), ('interpretation', '90.00'),
                           ('annotation', '70.00'), ('recruitment', '80.00'), ('all', '740.00')]:
        response = http.get('/translation-revenue', params={'anchor': '2026-11-10', 'project_type': module})
        assert response.status_code == 200, response.text
        assert response.json()['overall']['amount'] == amount
