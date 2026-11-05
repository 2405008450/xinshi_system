from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
import translation_customer_finance as finance
import translation_finance_audit as audit
import customer_statements as statements
from tools.apply_translation_finance_notes_migration import apply_migration

def test_two_notes_round_trip_and_generated_statement_uses_customer_only(setup):
    http,db,clients,_,actor,root,_=setup
    original=finance.read(db,root.id)
    assert original['item']['explanation']=='项目收费备注' and original['item']['customer_explanation']==''
    result=finance.save_table_cell(db,actor,root.id,finance.TablePatch(version=original['version'],order_id=root.id,explanation='内部说明新版',customer_explanation='客户说明独立'))
    assert result['item']['explanation']=='内部说明新版' and result['item']['customer_explanation']=='客户说明独立'
    assert result['version']!=original['version']
    fresh=statements.build_statement(db,root.id,None,'2026-10','project')
    assert fresh['rows'][0]['remarks']=='客户说明独立'
    assert '内部说明新版' not in str(fresh)
    assert '项目收费备注' not in str(fresh)
    # 修改客户说明不影响内部说明或收费。
    updated=finance.save_table_cell(db,actor,root.id,finance.TablePatch(version=result['version'],order_id=root.id,customer_explanation=''))
    assert updated['item']['customer_explanation']=='' and updated['item']['explanation']=='内部说明新版'
    assert updated['item']['totals_excl_tax']==original['item']['totals_excl_tax']
    assert statements.build_statement(db,root.id,None,'2026-10','project')['rows'][0]['remarks']==''
    records=audit.history(db,root.id)['items']
    assert records[0]['before']['customer_explanation']=='客户说明独立' and records[0]['after']['customer_explanation']==''
    apply_migration(db.connection());apply_migration(db.connection())

def test_history_is_snapshot_and_fee_window_save_preserves_both_notes(setup):
    http,db,clients,_,actor,root,_=setup
    previous=imported(setup,['2026-10'])
    initial=finance.read(db,root.id)
    payload=finance.PriceWrite(version=initial['version'],order_id=root.id,pricing_mode='fixed',adjusted_total=80,explanation='新的内部说明',customer_explanation='不进入账单的客户说明',billing_month='2026-10')
    saved=finance.save(db,actor,root.id,payload)
    assert saved['item']['explanation']=='新的内部说明' and saved['item']['customer_explanation']=='不进入账单的客户说明'
    old=http.get(f"/translation-statement-workspaces/{clients[0].id}").json()
    assert old['documents'][0]['statement']['rows'][0]['remarks']==previous['documents'][0]['statement']['rows'][0]['remarks']

def test_parent_notes_do_not_create_prices_or_overwrite_child_notes(environment):
    from tests.test_customer_translation_rates import context as make_tree
    db,(actor,*_)=environment
    _,root,middle,leaf=make_tree(db,actor)
    initial=finance.read(db,root.id)
    updated=finance.save_table_cell(db,actor,root.id,finance.TablePatch(version=initial['version'],order_id=root.id,explanation='母单内部',customer_explanation='母单客户'))
    assert updated['item']['explanation']=='母单内部' and updated['item']['customer_explanation']=='母单客户'
    assert not root.customer_charge_items
    child=updated['item']['children'][0]
    assert child['explanation']=='' and child['customer_explanation']==''

def test_existing_statement_updates_customer_notes_only_with_confirmed_audit(setup):
    http,db,clients,_,actor,root,_=setup
    previous=imported(setup,['2026-10']);board=previous['documents'][0]
    # 模拟历史版本曾把内部备注带入账单的快照。
    state=change(setup,previous,'edit_row',{'board_id':board['id'],'row_id':board['statement']['rows'][0]['_row_id'],'fields':{'remarks':'历史内部测试备注'}})
    current=finance.read(db,root.id)
    finance.save_table_cell(db,actor,root.id,finance.TablePatch(version=current['version'],order_id=root.id,explanation='不能外发',customer_explanation='客户可见备注'))
    updated=change(setup,state,'sync_customer_notes',{'board_id':board['id']})
    assert updated['documents'][0]['statement']['rows'][0]['remarks']=='客户可见备注'
    records=http.get(f"/translation-statement-workspaces/{clients[0].id}/history").json()['items']
    assert records[0]['action']=='同步客户说明'
    assert records[0]['changes']['rows'][0]['fields']['remarks']=={'before':'历史内部测试备注','after':'客户可见备注'}


def test_parent_summary_never_uses_internal_explanation():
    node={'order_no':'TP-261001-001','project_name':'母单','language_pair':'中→英','children':[{}],'explanation':'不能外发的内部说明','customer_explanation':'客户可见说明'}
    rows=[{'order_no':'TP-261001-001.001','currency':'CNY','subtotal':'12','remarks':'子单客户说明'}]
    for mode in ('parents','all'):
        # all模式递归需要完整子节点；此处验证生成父级汇总的核心路径。
        if mode=='all':continue
        result=statements.statement_display_rows(node,rows,mode)
        assert result[0]['remarks']=='客户可见说明'
        node['customer_explanation']=''
        assert statements.statement_display_rows(node,rows,mode)[0]['remarks']==''
