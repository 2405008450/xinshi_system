"""隔离 SQLite 验证组合计费、调整记录、乐观锁与重复建表。"""
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from test_chat_participant_access import environment
import interpretation_customer_finance as finance
from interpretation_models import InterpretationProject


def test_combined_units_overtime_and_currency_adjustments():
    data = finance.FinanceWrite(revision=0, rates=[
        dict(direction='中 ↔ 英', amount='100.1250', unit='天', quantity=2),
        dict(direction='中 ↔ 英', amount='20', unit='小时', quantity=3),
        dict(direction='英 ↔ 日', amount='30', unit='半天', quantity=1, currency='USD'),
    ], has_overtime=True, overtime=dict(amount='50', currency='CNY'),
       adjusted_totals=[dict(amount='280', currency='CNY')])
    assert data.rates[0].hours == Decimal(8)
    assert data.rates[2].hours == Decimal(3)
    result = finance.calculate(data.model_dump(mode='json'))
    assert result['totals'] == {'CNY': '310.25', 'USD': '30.00'}
    assert result['adjusted_totals'] == {'CNY': '280', 'USD': '30.00'}


def test_invalid_prices_and_duplicate_adjustments():
    for changes in [dict(has_overtime=True), dict(rates=[dict(direction=' ',amount=1)]),
                    dict(adjusted_totals=[dict(amount=1),dict(amount=2)]),
                    dict(rates=[dict(direction='英',amount='NaN')])]:
        with pytest.raises(ValidationError):
            finance.FinanceWrite(revision=0, **changes)


def test_adjustment_history_conflict_permissions_and_migration(environment, monkeypatch):
    db, (user, other, _) = environment
    monkeypatch.setattr(finance, 'user_has_permission', lambda db, uid, code: uid == user.id)
    project = InterpretationProject(id=uuid4(), order_no='I-FIN-TEST', project_name='测试口译')
    db.add(project); db.commit()
    first = finance.save(db, user, 'project', project.id, finance.FinanceWrite(revision=0, has_overtime=True, overtime=dict(amount=50)))
    assert first['revision'] == 1 and first['totals'] == {'CNY':'50.00'}
    with pytest.raises(HTTPException) as conflict:
        finance.save(db, user, 'project', project.id, finance.FinanceWrite(revision=0))
    assert conflict.value.status_code == 409
    db.rollback()
    second = finance.save(db, user, 'project', project.id, finance.FinanceWrite(revision=1, adjusted_totals=[dict(amount=0)]))
    assert second['adjusted_totals'] == {'CNY':'0'}
    events = finance.history('project', project.id, page=1, db=db, user=user)
    assert events['total'] == 2
    assert events['items'][0]['before']['overtime']['amount'] == '50'
    assert events['items'][0]['created_at'].endswith('+08:00')
    with pytest.raises(HTTPException) as denied:
        finance.save(db, other, 'project', project.id, finance.FinanceWrite(revision=2))
    assert denied.value.status_code == 403
    from tools.apply_interpretation_customer_finance_migration import apply_migration
    apply_migration(db.connection()); apply_migration(db.connection())
    assert db.query(finance.InterpretationCustomerFinanceHistory).count() == 2


def test_manager_scope_default_self_and_switch(environment, monkeypatch):
    db, (user, other, _) = environment
    monkeypatch.setattr(finance, 'user_has_permission', lambda *_: True)
    from project_client_manager import ProjectClientManagerChange
    for index, manager in enumerate([user, other]):
        project = InterpretationProject(id=uuid4(), order_no=f'I-FIN-{index}', project_name='财务 筛选')
        db.add(project); db.flush()
        db.add(ProjectClientManagerChange(id=uuid4(), project_type='interpretation', project_id=project.id,
            revision=1, new_manager_id=manager.id, new_manager_name=manager.username, reason='测试'))
    db.commit()
    args=dict(db=db,user=user,skip=0,limit=10)
    assert finance.page(only_mine=True,**args)['total']==1
    assert finance.page(only_mine=False,**args)['total']==2
    assert finance.page(only_mine=False,client_manager=other.username,**args)['total']==1
    assert finance.page(only_mine=False,keyword='筛选 财务',**args)['total']==2
