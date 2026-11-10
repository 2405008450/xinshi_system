from decimal import Decimal
from sqlalchemy import inspect
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
import translation_customer_finance as finance
import translation_billing_tax_mode as billing
import customer_statements as statements


def test_both_prices_choose_included_and_new_statement_uses_selection(context):
    _,db,clients,_,actor=context
    root=project(db,clients[0])
    original=statements.build_statement(db,root.id,None,'2026-11','project')
    data=finance.read(db,root.id)
    saved=finance.save_table_cell(db,actor,root.id,finance.TablePatch(version=data['version'],order_id=root.id,billing_tax_mode='incl_tax'))
    assert saved['item']['billing_totals']=={'CNY':'130.80'}
    assert saved['item']['totals_excl_tax']=={'CNY':'123.40'}
    result=statements.build_statement(db,root.id,None,'2026-11','project')
    assert result['totals']=={'CNY':'130.80'} and result['rows'][0]['unit_label']=='含税'
    assert original['totals']=={'CNY':'123.40'}
    event=finance.audit.history(db,root.id)['items'][0]
    assert event['after']['billing_tax_mode']=='incl_tax'
    assert event['before']['billing_tax_mode'] is None


def test_single_price_automatically_wins_even_over_previous_selection(context):
    _,db,clients,_,actor=context;root=project(db,clients[0])
    billing.save(db,actor,root,root,'excl_tax')
    root.customer_charge_items[0].unit_price_excl_tax=None
    root.customer_charge_items[0].unit_price=None
    db.commit()
    data=finance.read(db,root.id)['item']
    assert data['effective_billing_tax_mode']=='incl_tax'
    assert data['billing_totals']=={'CNY':'130.80'}
    assert statements.build_statement(db,root.id,None,'2026-11','project')['totals']=={'CNY':'130.80'}


def test_fixed_zero_is_filled_and_migration_only_creates_new_table(context):
    _,db,clients,_,actor=context;root=project(db,clients[0],fixed=True)
    charge=root.customer_charge_items[0];charge.total_excl_tax=None;charge.total_incl_tax=Decimal(0);db.commit()
    data=finance.read(db,root.id)['item']
    assert data['effective_billing_tax_mode']=='incl_tax' and Decimal(data['billing_totals']['CNY'])==0
    from tools.apply_translation_billing_tax_mode_migration import apply_migration
    columns=[row['name'] for row in inspect(db.connection()).get_columns('translation_project')]
    apply_migration(db.connection());apply_migration(db.connection())
    assert columns==[row['name'] for row in inspect(db.connection()).get_columns('translation_project')]
